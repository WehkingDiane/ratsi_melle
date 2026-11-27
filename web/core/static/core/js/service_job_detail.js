(function () {
  const container = document.querySelector('[data-job-detail]');
  if (!container) return;
  const node = id => document.getElementById(id);
  const jobId = container.getAttribute('data-service-job-id');
  const jobLabel = container.getAttribute('data-job-label') || 'Auftrag';
  const jobArea = container.getAttribute('data-job-area');
  const statusUrl = container.getAttribute('data-status-url');
  const evidencePanel = node('model-job-evidence');
  const feedback = node('job-feedback');
  let wasRunning = container.getAttribute('data-service-job-running') === 'true';
  function statusClass(status) {
    return status === 'ok' ? 'status-ok' :
      (['queued', 'running', 'partial'].includes(status) ? 'status-warning' : 'status-error');
  }
  function setText(id, value) {
    const target = node(id);
    if (target) target.textContent = value;
  }
  async function refreshJob() {
    try {
      const response = await fetch(statusUrl, {cache: 'no-store', headers: {'Accept': 'application/json'}});
      if (response.redirected || !response.ok) throw new Error('Status request failed');
      const payload = await response.json();
      const job = payload.job;
      if (!job || !job.status) throw new Error('Missing job');
      const running = job.status === 'queued' || job.status === 'running';
      if (feedback) feedback.hidden = true;
      setText('job-status', job.status_label || job.status);
      if (node('job-status')) node('job-status').className = statusClass(job.status);
      setText('job-exit-code', job.exit_code ?? '–');
      setText('job-started-at', job.started_at || '–');
      setText('job-finished-at', job.finished_at || '–');
      setText('job-output', job.output || 'Noch keine Ausgabe.');
      if (node('job-running-banner')) node('job-running-banner').hidden = !running;
      const completion = node('job-completion-message');
      if (completion) {
        completion.hidden = running;
        completion.className = statusClass(job.status);
        completion.textContent = running ? '' : jobLabel + (job.status === 'ok'
          ? ' wurde erfolgreich abgeschlossen.' : job.status === 'partial'
            ? ' wurde mit Hinweisen abgeschlossen.' : ' ist fehlgeschlagen.');
      }
      setText('job-progress-text', (job.progress || {}).message || 'Fortschritt nicht verfügbar.');
      if (node('job-progress')) node('job-progress').hidden = job.status !== 'running';
      if (evidencePanel) {
        const evidence = payload.model_job_evidence || {};
        evidencePanel.querySelectorAll('[data-job-evidence]').forEach(target => {
          target.textContent = evidence[target.getAttribute('data-job-evidence')] || 'Nicht nachgewiesen';
        });
      }
      if (wasRunning && !running) {
        wasRunning = false;
        document.dispatchEvent(new CustomEvent('servicejob:finished', {
          detail: {jobId: jobId || job.job_id, status: job.status, area: jobArea},
        }));
        if (container.getAttribute('data-legacy-job') === 'true') window.location.reload();
      }
      return running;
    } catch (_) {
      if (feedback) {
        feedback.textContent = 'Status konnte nicht aktualisiert werden. Erneuter Versuch folgt.';
        feedback.hidden = false;
      }
      return true;
    }
  }
  async function poll() {
    if (await refreshJob()) window.setTimeout(poll, 1500);
  }
  poll();
}());
