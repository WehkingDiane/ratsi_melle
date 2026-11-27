"""Calendar lifecycle metadata shared by BI and RI, independent of document access."""
from datetime import date, datetime, timezone
import re

FIELDS = ('calendar_status', 'calendar_note', 'rescheduled_date', 'replacement_session_id', 'calendar_observed_at')
CHANGED = frozenset({'postponed', 'cancelled', 'unknown'})
LABELS = {'scheduled': 'Geplant', 'postponed': 'Verschoben', 'cancelled': 'Abgesagt', 'unknown': 'Status unklar'}


def parse_calendar_notices(details):
    """Separate lifecycle notices from time/place; never guess a replacement ID."""
    notes = [text for text in details if re.search(
        r'verschob|verlegt|abgesagt|entfällt|faellt aus|fällt aus|findet nicht statt|ausgefallen|status.*unklar', text, re.I)]
    note = ' · '.join(notes) or None
    status = 'scheduled'
    target = None
    if note:
        status = 'postponed' if re.search(r'verschob|verlegt', note, re.I) else (
            'cancelled' if re.search(r'abgesagt|entfällt|faellt aus|fällt aus|findet nicht statt|ausgefallen', note, re.I) else 'unknown')
        if re.search(r'nicht\s+(?:abgesagt|verschoben|verlegt)|(?:öffentlicher|nichtöffentlicher)\s+Teil', note, re.I):
            status = 'unknown'
        match = re.search(r'\b(?:auf|zum)\s+(?:den\s+)?(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)', note, re.I)
        if status == 'postponed' and match:
            try:
                target = date(int(match[3]), int(match[2]), int(match[1]))
            except ValueError:
                pass
    remaining = [text for text in details if text not in notes]
    time = next((text for text in remaining if re.match(r'^\d{1,2}:\d{2}(?:\s*Uhr)?(?:\s|$)', text)), None)
    location = next((text for text in remaining if text != time), None)
    return {'calendar_status': status, 'calendar_note': note, 'rescheduled_date': target,
            'start_time': time, 'location': location}


def calendar_metadata(source):
    """Serialize only known calendar fields, supporting rows from older indices."""
    get = source.get if isinstance(source, dict) else lambda key, default=None: getattr(source, key, default)
    status = get('calendar_status') or 'scheduled'
    note = get('calendar_note')
    target = get('rescheduled_date')
    # Old index versions placed lifecycle notices in the time field.
    legacy = parse_calendar_notices([str(get('start_time') or '')])
    if legacy['calendar_status'] != 'scheduled' and (status == 'scheduled' or not note):
        status, note, target = legacy['calendar_status'], legacy['calendar_note'], legacy['rescheduled_date']
    if status not in LABELS:
        status = 'unknown'
    return {'calendar_status': status, 'calendar_note': note,
            'rescheduled_date': target.isoformat() if isinstance(target, date) else target,
            'replacement_session_id': get('replacement_session_id'), 'calendar_observed_at': get('calendar_observed_at')}


def display_calendar_metadata(row):
    """Enrich a copied row with labels without rewriting the stored original date."""
    result = dict(row)
    result.update(calendar_metadata(row))
    result['calendar_status_label'] = LABELS[result['calendar_status']]
    result['calendar_changed'] = result['calendar_status'] in CHANGED
    if parse_calendar_notices([str(result.get('start_time') or '')])['calendar_status'] != 'scheduled':
        result['start_time'] = None
    target = result.get('rescheduled_date')
    try:
        result['rescheduled_display_date'] = date.fromisoformat(target).strftime('%d.%m.%Y') if target else None
    except (ValueError, TypeError):
        result['rescheduled_display_date'] = None
    return result


def merge_calendar_rows(existing, incoming):
    """Merge row values while keeping lifecycle fields from the freshest observation."""
    result = {**existing, **{k:v for k,v in incoming.items() if v is not None and v != ''}}
    old, new = calendar_metadata(existing), calendar_metadata(incoming)
    def observed(value):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
        except (ValueError, TypeError):
            return None
    old_time, new_time = observed(old.get('calendar_observed_at')), observed(new.get('calendar_observed_at'))
    if new_time is not None or old_time is not None:
        chosen = new if new_time is not None and (old_time is None or new_time >= old_time) else old
    else:
        chosen = new if new['calendar_status'] != 'scheduled' or old['calendar_status'] == 'scheduled' else old
    result.update(chosen)
    return result
