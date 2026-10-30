"""Shared navigation for public areas and the future council area."""
from django import template
from django.urls import reverse

register = template.Library()

@register.inclusion_tag("core/partials/navigation.html", takes_context=True)
def main_navigation(context):
    """Build navigation and retain the source on shared public pages."""
    request = context["request"]
    active = context.get("active_nav", "")
    section = context.get("scoped_source")
    if request.path.startswith("/ratsbereich/"):
        active = "ri"
    elif section or active == "search":
        active = section or context.get("selected_source", "ratsinfo")
    elif request.path.startswith("/analyse/sitzungen/") or active == "data":
        job = context.get("job")
        active = "landkreis" if job and "landkreis" in job.action else "ratsinfo"
    elif active == "publishing":
        active = "analysis"
    groups = []
    def add(key, label, links):
        groups.append({"label": label, "active": active == key, "links": links})
    add("dashboard", "Übersicht", [(reverse("dashboard"), "Übersicht öffnen")])
    for source, label, prefix in [("ratsinfo", "Bürgerinformation", "/buergerinformation/"), ("ri", "Ratsbereich", "/ratsbereich/"), ("landkreis", "Landkreis", "/landkreis/")]:
        links = []
        if source == "ri":
            links.append((prefix + "zugang/", "Zugang"))
        if source != "landkreis":
            links.append((reverse("analysis:session_list") if source == "ratsinfo" else prefix + "sitzungen/", "Sitzungen"))
        links += [(prefix + "suche/", "Dokumentensuche"), (prefix + "daten/fetch/", "Unterlagen herunterladen"), (prefix + "daten/build/", "Datenbank aktualisieren"), (prefix + "daten/vektor/", "Suchindex aktualisieren"), (prefix + "daten/", "Datenstatus und Jobs")]
        if source == "ratsinfo":
            links.append((reverse("data_tools:service_status_detail"), "Datenstatus nach Jahr"))
        add(source, label, links)
    add("analysis", "Erweiterungen", [(reverse("analysis:" + route), title) for route, title in [("index", "Analyse-Übersicht"), ("analysis_start", "KI-Analyse starten"), ("answer_reader", "Antworten lesen"), ("prompt_template_list", "Prompt-Vorlagen"), ("job_list", "Analysejobs")]])
    add("service", "Einstellungen", [(reverse("settings_ui:index"), "Allgemeine Einstellungen und Zugänge"), (reverse("service:maintenance"), "Wartung und Suchmodelle"), (reverse("service:index"), "Wartungsjobs")])
    return {"groups": groups}
