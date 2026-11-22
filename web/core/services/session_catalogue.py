"""Shared filtering and pagination for BI and RI session catalogues."""

import re

from django.core.paginator import Paginator


def committee_key(value):
    """Normalize spelling variants without changing stored source data."""
    return re.sub(r'[\s_\-‐‑‒–—−]+', ' ', value).strip().casefold()


def session_list_context(request, all_sessions, page_size=20):
    """Build the filter choices and current page for a session list."""
    names = sorted({str(item.get('committee') or '').strip() for item in all_sessions} - {''},
                   key=lambda name: (not any(char in name for char in '-‐‑‒–—−'), name.casefold(), name))
    labels = {}
    for name in names:
        labels.setdefault(committee_key(name), name)
    all_sessions = [{**item, 'committee': labels.get(committee_key(str(item.get('committee') or '')), '')}
                    for item in all_sessions]
    query = request.GET.get('q', '').strip()
    committee = request.GET.get('committee', '').strip()
    committee = labels.get(committee_key(committee), committee)
    year = request.GET.get('year', '').strip()
    sessions = [item for item in all_sessions
                if (not query or query.casefold() in ' '.join(str(item.get(key) or '') for key in
                    ('session_id', 'meeting_name', 'committee', 'location')).casefold())
                and (not committee or item.get('committee') == committee)
                and (not year or str(item.get('date') or '')[:4] == year)]
    page = Paginator(sessions, page_size).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return {
        'sessions': list(page.object_list), 'page_obj': page, 'result_count': len(sessions),
        'query': query, 'selected_committee': committee, 'selected_year': year,
        'committees': sorted({item['committee'] for item in all_sessions if item.get('committee')}),
        'years': sorted({str(item.get('date') or '')[:4] for item in all_sessions if item.get('date')}, reverse=True),
        'filter_query': params.urlencode(),
    }
