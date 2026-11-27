"""Strict input forms for the fixed RI script actions."""
from django import forms
from django.core.exceptions import ValidationError

from src.config.ri import select_months
from src.config.ri_proton import RiAccessError



class RiActionForm(forms.Form):
    """Reject unexpected or repeated POST parameters."""

    def clean(self):
        cleaned = super().clean()
        allowed = set(self.fields) | {"action", "csrfmiddlewaretoken"}
        if set(self.data) - allowed:
            raise ValidationError("Die Aktion enthält nicht erlaubte Parameter.")
        if hasattr(self.data, "getlist") and any(len(self.data.getlist(key)) != 1 for key in self.data):
            raise ValidationError("Parameter dürfen nur einmal angegeben werden.")
        return cleaned


class RiMonthForm(RiActionForm):
    year = forms.IntegerField(label="Jahr", min_value=2000, max_value=2100)
    months = forms.CharField(label="Monate", required=False, max_length=100,
                            help_text="Zum Beispiel 11 12. Leer bedeutet alle zugänglichen Monate des Jahres.")

    def clean_months(self):
        value = self.cleaned_data["months"].replace(",", " ").strip()
        try:
            months = [int(part) for part in value.split()] if value else list(range(1, 13))
        except ValueError:
            raise ValidationError("Monate müssen Zahlen von 1 bis 12 sein.") from None
        if any(month < 1 or month > 12 for month in months):
            raise ValidationError("Monate müssen zwischen 1 und 12 liegen.")
        return months

    def clean(self):
        cleaned = super().clean()
        if "year" in cleaned and "months" in cleaned:
            try:
                cleaned["months"] = select_months(cleaned["year"], cleaned["months"])
            except RiAccessError as error:
                raise ValidationError(str(error)) from None
        return cleaned


class RiFetchForm(RiMonthForm):
    update_local_index = forms.BooleanField(label="Lokalen Index anschließend aktualisieren", required=False, initial=True)
    force_download = forms.BooleanField(label="Vorhandene Dokumente erneut herunterladen", required=False)


class RiLocalForm(RiActionForm):
    refresh_existing = forms.BooleanField(label="Bestehende Sitzungen aktualisieren", required=False)
    only_refresh = forms.BooleanField(label="Nur bestehende Sitzungen aktualisieren", required=False)


class RiOnlineForm(RiMonthForm):
    refresh_existing = forms.BooleanField(label="Bestehende Sitzungen aktualisieren", required=False)
    only_refresh = forms.BooleanField(label="Nur bestehende Sitzungen aktualisieren", required=False)


ACTIONS = {
    "ri_login": ("Portalzugang prüfen", "scripts/login_ri.py", RiActionForm),
    "ri_fetch": ("Unterlagen herunterladen", "scripts/fetch_ri_sessions.py", RiFetchForm),
    "ri_online": ("Online-Datenbank aktualisieren", "scripts/build_ri_online_index_db.py", RiOnlineForm),
    "ri_local": ("Lokale Datenbank aktualisieren", "scripts/build_ri_local_index.py", RiLocalForm),
}


def build_command(action, data):
    """Construct an RI command from validated form values only."""
    import sys

    if action not in ACTIONS or data.get("action", action) != action:
        raise ValueError("Unbekannte RI-Aktion.")
    form = ACTIONS[action][2](data)
    if not form.is_valid():
        raise ValueError("RI-Formular ist ungültig. Angaben prüfen.")
    values = form.cleaned_data
    command = [sys.executable, ACTIONS[action][1]]
    if action in {"ri_fetch", "ri_online"}:
        command += [str(values["year"]), "--months", *map(str, values["months"])]
    for key in ("force_download", "refresh_existing", "only_refresh"):
        if values.get(key):
            command.append("--" + key.replace("_", "-"))
    return command
