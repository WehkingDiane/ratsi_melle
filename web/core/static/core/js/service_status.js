(function () {
  const indicator = document.getElementById("job-indicator");
  const text = document.getElementById("job-indicator-text");
  if (!indicator || !text) {
    return;
  }

  async function refreshServiceStatus() {
    try {
      const response = await fetch("/daten/jobs/status/", {
        headers: { "Accept": "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      const active = payload.active || [];
      if (active.length === 0) {
        indicator.hidden = true;
        return;
      }
      const job = active[active.length - 1];
      indicator.hidden = false;
      indicator.href = "/daten/jobs/" + job.job_id + "/";
      text.textContent = active.length === 1
        ? "Service laeuft: " + job.action
        : active.length + " Service-Jobs laufen";
    } catch (_error) {
      return;
    }
  }

  refreshServiceStatus();
  window.setInterval(refreshServiceStatus, 2000);
}());
