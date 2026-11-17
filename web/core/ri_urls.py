"""Routes for protected RI script controls and the local web login."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import ri_views
from .ri_forms import RiAuthenticationForm

app_name = 'ri'
urlpatterns = [
    path('', ri_views.status, name='index'),
    path('anmelden/', auth_views.LoginView.as_view(template_name='core/ri/login.html',
         authentication_form=RiAuthenticationForm, extra_context={'active_nav': 'ri'}), name='login'),
    path('abmelden/', auth_views.LogoutView.as_view(next_page='ri:login'), name='logout'),
    path('zugang/', ri_views.script_page, {'page': 'zugang'}, name='access'),
    path('daten/', ri_views.status, name='status'),
    path('daten/fetch/', ri_views.script_page, {'page': 'fetch'}, name='fetch'),
    path('daten/build/', ri_views.script_page, {'page': 'build'}, name='build'),
    path('daten/jobs/<str:job_id>/', ri_views.job_detail, name='job'),
    path('daten/jobs/<str:job_id>/status/', ri_views.job_status, name='job_status'),
    path('sitzungen/', ri_views.placeholder, {'page': 'sitzungen'}),
    path('suche/', ri_views.placeholder, {'page': 'suche'}),
    path('daten/vektor/', ri_views.placeholder, {'page': 'vektor'}),
    path('sitzungen/<str:session_id>/', ri_views.session_detail),
]
