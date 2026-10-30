"""Informational council-area pages; no RI connection is configured yet."""
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_safe

PAGES = {
    "zugang": ("Zugang", "Hier wird später der Zugang zum Ratsbereich eingerichtet."),
    "sitzungen": ("Sitzungen", "Hier werden später die verfügbaren Ratssitzungen angezeigt."),
    "suche": ("Interne Dokumentensuche", "Hier werden später berechtigte Ratsunterlagen durchsucht."),
    "daten": ("Datenstatus und Jobs", "Hier wird später der Stand der internen Datenpflege angezeigt."),
    "fetch": ("Unterlagen herunterladen", "Hier werden später Ratsunterlagen abgerufen."),
    "build": ("Datenbank aktualisieren", "Hier wird später der interne Dokumentbestand aufbereitet."),
    "vektor": ("Suchindex aktualisieren", "Hier wird später die interne Suche vorbereitet."),
}

@require_safe
def placeholder(request, page="zugang"):
    """Show a purpose-specific placeholder without reading RI data."""
    title, description = PAGES[page]
    return render(request, "core/ri_placeholder.html", {
        "active_nav": "ri", "title": title, "description": description,
    })

@require_safe
def session_detail(request, session_id):
    """Do not invent details for sessions that have not been imported."""
    raise Http404("Ratsbereich noch nicht eingerichtet; keine Sitzung verfügbar.")
