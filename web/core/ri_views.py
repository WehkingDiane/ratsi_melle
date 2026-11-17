"""Protected UI controls for the RI command-line workflow."""
from functools import wraps
from pathlib import Path
import sqlite3

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from src.paths import RI_LOCAL_INDEX_DB, RI_ONLINE_INDEX_DB
from . import ri_jobs
from .ri_forms import ACTIONS

PAGES = {
    "sitzungen": ("Sitzungen", "Die Anzeige der lokalen Ratssitzungen wird noch umgesetzt."),
    "suche": ("Interne Dokumentensuche", "Eine RI-Volltext- oder Vektorsuche ist derzeit nicht vorgesehen."),
    "vektor": ("Suchindex", "Für den Ratsbereich wird derzeit kein Suchindex aufgebaut."),
}
PAGE_ACTIONS = {'zugang': ('ri_login',), 'fetch': ('ri_fetch',), 'build': ('ri_online', 'ri_local')}
TITLES = {'zugang': 'Zugang', 'fetch': 'Unterlagen herunterladen', 'build': 'Datenbank aktualisieren'}


def ri_required(view):
    """Require a local active staff account for every RI data response."""
    @wraps(view)
    @login_required(login_url='ri:login')
    def protected(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied('Kein Zugang zum Ratsbereich.')
        return view(request, *args, **kwargs)
    return never_cache(protected)


@ri_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def script_page(request, page):
    actions = PAGE_ACTIONS[page]
    action = request.POST.get('action') if request.method == 'POST' else None
    if request.method == 'POST' and action not in actions:
        return HttpResponseBadRequest('Diese Aktion gehört nicht zur gewählten RI-Seite.')
    forms = []
    errors = []
    for key in actions:
        label, _, form_class = ACTIONS[key]
        form = form_class(request.POST if action == key else None, initial={'year': timezone.localdate().year},
                          auto_id=f'id_{key}_%s')
        if action == key and form.is_valid():
            try:
                job_id = ri_jobs.start_job(key, request.POST)
            except (ri_jobs.RiJobError, ValueError) as error:
                errors.append(str(error))
            else:
                return redirect('ri:job', job_id=job_id)
        forms.append({'action': key, 'label': label, 'form': form})
    return render(request, 'core/ri/scripts.html', {
        'active_nav': 'ri', 'title': TITLES[page], 'forms': forms, 'errors': errors,
        'access_page': page == 'zugang',
    })


def _database_status(path):
    if not Path(path).is_file():
        return {'state': 'noch nicht aufgebaut', 'sessions': None, 'agenda_items': None, 'documents': None}
    try:
        with sqlite3.connect(f'{Path(path).resolve().as_uri()}?mode=ro', uri=True) as connection:
            values = {table: connection.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                      for table in ('sessions', 'agenda_items', 'documents')}
        return {'state': 'vorhanden', **values}
    except sqlite3.Error:
        return {'state': 'nicht lesbar; Datenbank prüfen', 'sessions': None, 'agenda_items': None, 'documents': None}


@ri_required
@require_safe
def status(request):
    errors = []
    try:
        jobs = ri_jobs.list_jobs()
    except (OSError, sqlite3.Error):
        jobs = []
        errors.append('RI-Jobablage ist nicht lesbar.')
    return render(request, 'core/ri/status.html', {
        'active_nav': 'ri', 'title': 'Datenstatus und Jobs', 'jobs': jobs, 'errors': errors,
        'online': _database_status(RI_ONLINE_INDEX_DB), 'local': _database_status(RI_LOCAL_INDEX_DB),
    })


@ri_required
@require_safe
def job_detail(request, job_id):
    job = ri_jobs.get_job(job_id)
    if job is None:
        raise Http404
    return render(request, 'core/ri/job.html', {'active_nav': 'ri', 'title': job['label'], 'job': job})


@ri_required
@require_safe
def job_status(request, job_id):
    job = ri_jobs.get_job(job_id)
    if job is None:
        raise Http404
    return JsonResponse({'job': job})


@require_safe
def placeholder(request, page):
    """Keep unimplemented catalogue/search pages free of RI data."""
    title, description = PAGES[page]
    return render(request, 'core/ri_placeholder.html', {'active_nav': 'ri', 'title': title, 'description': description})


@require_safe
def session_detail(request, session_id):
    raise Http404('Noch keine Sitzungsansicht verfügbar.')
