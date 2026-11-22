"""Presentation forms for data jobs; command validation stays in the service layer."""

from django import forms


class MonthForm(forms.Form):
    year = forms.IntegerField(label='Jahr', min_value=2000, max_value=2100, required=False)
    months = forms.CharField(label='Monate', required=False,
                            widget=forms.TextInput(attrs={'placeholder': 'z. B. 1 2 3 oder leer für alle'}))


class SingleSessionForm(forms.Form):
    session_id = forms.CharField(label='Session-ID', required=False,
                                 widget=forms.TextInput(attrs={'placeholder': 'z. B. 7128'}))


class LocalIndexForm(forms.Form):
    refresh_existing = forms.BooleanField(label='Bestehende Sitzungen aktualisieren', required=False,
                                         widget=forms.CheckboxInput(attrs={'value': '1'}))
    only_refresh = forms.BooleanField(label='Nur bestehende Sitzungen aktualisieren', required=False,
                                     widget=forms.CheckboxInput(attrs={'value': '1'}))


class OnlineIndexForm(MonthForm, LocalIndexForm):
    field_order = ['year', 'months', 'refresh_existing', 'only_refresh']


class LandkreisFetchForm(forms.Form):
    source = forms.ChoiceField(label='Quelle', choices=[('all', 'Alle'), ('bekanntmachungen', 'Bekanntmachungen'),
                                                      ('amtsblaetter', 'Amtsblätter')], required=False)
    data_dir = forms.CharField(label='Datenwurzel', required=False,
                              widget=forms.TextInput(attrs={'placeholder': 'Optional, z. B. /mnt/d/landkreis_osnabrueck'}))
    query = forms.CharField(label='Suchbegriff', required=False,
                           widget=forms.TextInput(attrs={'placeholder': 'Optional, z. B. Melle'}))
    from_date = forms.DateField(label='Von', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    to_date = forms.DateField(label='Bis', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    limit = forms.IntegerField(label='Limit', required=False, min_value=1,
                               widget=forms.NumberInput(attrs={'placeholder': 'Optional'}))
    dry_run = forms.BooleanField(label='Nur Treffer prüfen', required=False,
                                 widget=forms.CheckboxInput(attrs={'value': '1'}))
    refresh_existing = forms.BooleanField(label='Bestehende Detailseiten aktualisieren', required=False,
                                         widget=forms.CheckboxInput(attrs={'value': '1'}))


class LandkreisBuildForm(forms.Form):
    data_dir = forms.CharField(label='Datenwurzel', required=False,
                              widget=forms.TextInput(attrs={'placeholder': 'Optional, z. B. /mnt/d/landkreis_osnabrueck'}))
    max_text_chars = forms.IntegerField(label='Maximale Textzeichen', required=False, min_value=1,
                                       widget=forms.NumberInput(attrs={'placeholder': 'Standard: 200000'}))


PAGES = {
    'fetch': [
        ('ratsinfo', 'fetch_sessions', 'Monate laden', 'Sitzungen laden', MonthForm),
        ('ratsinfo', 'fetch_session_from_index', 'Einzelsitzung aus Online-Index laden', 'Einzelsitzung laden', SingleSessionForm),
        ('landkreis', 'fetch_landkreis_publications', 'Landkreis-Veröffentlichungen laden', 'Landkreis laden', LandkreisFetchForm),
    ],
    'build': [
        ('ratsinfo', 'build_local_index', 'Lokalen Index bauen', 'Lokalen Index bauen', LocalIndexForm),
        ('ratsinfo', 'build_online_index', 'Online-Index bauen', 'Online-Index bauen', OnlineIndexForm),
        ('landkreis', 'build_landkreis_publications_db', 'Landkreis-Datenbank bauen', 'Landkreis-Datenbank bauen', LandkreisBuildForm),
    ],
}


def script_forms(page, source, current_year):
    """Provide scoped presentation forms with unique IDs, preserving existing actions."""
    return [{'action': action, 'label': label, 'submit_label': submit,
             'form': form_class(initial={'year': current_year, 'source': 'all'}, auto_id=f'id_{action}_%s')}
            for scope, action, label, submit, form_class in PAGES[page] if not source or source == scope]
