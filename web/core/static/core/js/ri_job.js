(() => {
  const root = document.getElementById('ri-job');
  if (!root) return;
  const status = document.getElementById('ri-job-status');
  async function update() {
    try {
      const response = await fetch(root.dataset.statusUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      if (response.redirected || !response.ok) {
        status.textContent = 'Status nicht verfügbar. Bitte erneut anmelden oder die Seite neu laden.';
        return;
      }
      const {job} = await response.json();
      status.textContent = job.status_label;
      document.getElementById('ri-job-exit').textContent = job.exit_code ?? '–';
      document.getElementById('ri-job-output').textContent = job.output;
      if (job.running) window.setTimeout(update, 2000);
    } catch (_) {
      status.textContent = 'Status konnte nicht aktualisiert werden. Seite erneut laden.';
    }
  }
  update();
})();
