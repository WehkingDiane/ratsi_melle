"""Local UI controls for the RI command-line workflow."""
from pathlib import Path
import sqlite3

from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
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


@never_cache
@require_safe
def access_redirect(request):
    """Keep old login bookmarks usable without displaying an authentication page."""
    return redirect('ri:status')


@never_cache
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
            except ri_jobs.RiJobBusyError as error:
                return redirect(reverse('ri:job', kwargs={'job_id': error.job_id}) + '?already_running=1')
            except (ri_jobs.RiJobError, ValueError) as error:
                errors.append(str(error))
            else:
                return redirect('ri:job', job_id=job_id)
        forms.append({'action': key, 'label': label, 'form': form})
    return render(request, 'core/ri/scripts.html', {
        'active_nav': 'ri', 'title': TITLES[page], 'forms': forms, 'errors': errors,
        'access_page': page == 'zugang', 'active_job': _active_job(),
        'online': _database_status(RI_ONLINE_INDEX_DB), 'local': _database_status(RI_LOCAL_INDEX_DB),
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


@never_cache
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


@never_cache
@require_safe
def job_detail(request, job_id):
    job = ri_jobs.get_job(job_id)
    if job is None:
        raise Http404
    return render(request, 'core/ri/job.html', {'active_nav': 'ri', 'title': job['label'], 'job': job,
                                                           'already_running': request.GET.get('already_running') == '1'})


@never_cache
@require_safe
def job_status(request, job_id):
    job = ri_jobs.get_job(job_id)
    if job is None:
        raise Http404
    return JsonResponse({'job': job})


def _active_job():
    try:
        return next((job for job in ri_jobs.list_jobs() if job['running']), None)
    except (OSError, sqlite3.Error):
        return None


@never_cache
@require_safe
def jobs_status(request):
    """Expose RI lifecycle metadata to the RI area's shared job indicator."""
    try:
        jobs = ri_jobs.list_jobs()
    except (OSError, sqlite3.Error):
        return JsonResponse({'error': 'RI-Status nicht verfügbar.'}, status=503)
    active = []
    for job in jobs:
        if job['running']:
            active.append({key: job[key] for key in ('job_id', 'action', 'label', 'status', 'status_label')})
            active[-1].update(area='ri', detail_url=reverse('ri:job', kwargs={'job_id': job['job_id']}))
    return JsonResponse({'active': active})


@require_safe
def placeholder(request, page):
    """Keep unimplemented catalogue/search pages free of RI data."""
    title, description = PAGES[page]
    return render(request, 'core/ri_placeholder.html', {'active_nav': 'ri', 'title': title, 'description': description})


@require_safe
def session_detail(request, session_id):
    raise Http404('Noch keine Sitzungsansicht verfügbar.')
