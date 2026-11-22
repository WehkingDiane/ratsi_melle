"""Routes for the local RI script controls without web authentication."""
from django.urls import path

from . import ri_views

app_name = 'ri'
urlpatterns = [
    path('', ri_views.status, name='index'),
    path('anmelden/', ri_views.access_redirect),
    path('abmelden/', ri_views.access_redirect),
    path('zugang/', ri_views.script_page, {'page': 'zugang'}, name='access'),
    path('daten/', ri_views.status, name='status'),
    path('daten/fetch/', ri_views.script_page, {'page': 'fetch'}, name='fetch'),
    path('daten/build/', ri_views.script_page, {'page': 'build'}, name='build'),
    path('daten/jobs/status/', ri_views.jobs_status, name='jobs_status'),
    path('daten/jobs/<str:job_id>/', ri_views.job_detail, name='job'),
    path('daten/jobs/<str:job_id>/status/', ri_views.job_status, name='job_status'),
    path('sitzungen/', ri_views.session_list, name='session_list'),
    path('suche/', ri_views.placeholder, {'page': 'suche'}),
    path('daten/vektor/', ri_views.placeholder, {'page': 'vektor'}),
    path('sitzungen/<str:session_id>/', ri_views.session_detail, name='session_detail'),
    path('sitzungen/<str:session_id>/dokumente/<int:document_id>/pdf/', ri_views.document_pdf, name='document_pdf'),
]
