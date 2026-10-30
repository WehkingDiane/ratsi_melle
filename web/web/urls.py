"""Top-level routes for the standalone web UI."""

from __future__ import annotations

from django.urls import include, path
from settings_ui import views as settings_views


urlpatterns = [
    path("", include("core.urls")),
    path("analyse/", include("analysis.urls")),
    path("daten/", include("data_tools.urls")),
    path("veroeffentlichung/", include("publishing.urls")),
    path("suche/", include("search.urls")),
    path("service/", include("data_tools.service_urls")),
    path("service/einstellungen/", include("settings_ui.urls")),
    path("einstellungen/", settings_views.index),
]

from data_tools import views as data_views
from search import views as search_views

for prefix, source in (("buergerinformation", "ratsinfo"), ("landkreis", "landkreis")):
    for suffix, view in (("daten/", data_views.service_home), ("daten/fetch/", data_views.service_fetch), ("daten/build/", data_views.service_build), ("daten/vektor/", data_views.service_vector), ("suche/", search_views.index)):
        urlpatterns.append(path(prefix + "/" + suffix, view, {"source": source}))

from core import ri_views

urlpatterns += [path("ratsbereich/", ri_views.placeholder)]
for suffix, page in (("zugang/", "zugang"), ("sitzungen/", "sitzungen"), ("suche/", "suche"), ("daten/", "daten"), ("daten/fetch/", "fetch"), ("daten/build/", "build"), ("daten/vektor/", "vektor")):
    urlpatterns.append(path("ratsbereich/" + suffix, ri_views.placeholder, {"page": page}))
urlpatterns.append(path("ratsbereich/sitzungen/<str:session_id>/", ri_views.session_detail))
