(() => {
  const root = document.getElementById('ri-job');
  if (!root) return;
  const status = document.getElementById('ri-job-status');
  const feedback = document.getElementById('ri-job-feedback');
  function showError(message) {
    feedback.textContent = message;
    feedback.hidden = false;
  }
  async function update() {
    try {
      const response = await fetch(root.dataset.statusUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      if (response.redirected || !response.ok) {
        showError('Status nicht verfügbar. Bitte die Seite neu laden.');
        return;
      }
      const {job} = await response.json();
      feedback.hidden = true;
      status.textContent = job.status_label;
      status.className = job.status === 'ok' ? 'status-ok' :
        (job.running || job.status === 'partial' ? 'status-warning' : 'status-error');
      document.getElementById('ri-job-start').textContent = job.started_at || '–';
      document.getElementById('ri-job-end').textContent = job.finished_at || '–';
      document.getElementById('ri-job-running').hidden = !job.running;
      document.getElementById('ri-job-exit').textContent = job.exit_code ?? '–';
      document.getElementById('ri-job-output').textContent = job.output || 'Noch keine Ausgabe.';
      if (job.running) window.setTimeout(update, 2000);
    } catch (_) {
      showError('Status konnte nicht aktualisiert werden. Seite erneut laden.');
    }
  }
  update();
})();
