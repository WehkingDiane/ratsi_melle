(function () {
  const container = document.querySelector("[data-service-job-id]");
  if (!container) {
    return;
  }

  const jobId = container.getAttribute("data-service-job-id");
  const statusNode = document.getElementById("job-status");
  const exitCodeNode = document.getElementById("job-exit-code");
  const startedAtNode = document.getElementById("job-started-at");
  const finishedAtNode = document.getElementById("job-finished-at");
  const outputNode = document.getElementById("job-output");
  const runningBanner = document.getElementById("job-running-banner");
  const completionMessage = document.getElementById("job-completion-message");
  let wasRunning = container.getAttribute("data-service-job-running") === "true";

  function setStatusClass(status) {
    if (!statusNode) {
      return;
    }
    statusNode.classList.remove("status-ok", "status-warning", "status-error");
    if (status === "ok") {
      statusNode.classList.add("status-ok");
    } else if (status === "running" || status === "queued") {
      statusNode.classList.add("status-warning");
    } else {
      statusNode.classList.add("status-error");
    }
  }

  async function refreshJob() {
    try {
      const response = await fetch("/daten/jobs/" + jobId + "/status/", {
        headers: { "Accept": "application/json" },
      });
      if (!response.ok) {
        return false;
      }
      const payload = await response.json();
      const job = payload.job || {};
      const status = job.status || "";
      const statusLabel = job.status_label || status;

      if (statusNode) {
        statusNode.textContent = statusLabel || "-";
        setStatusClass(status);
      }
      if (exitCodeNode) {
        exitCodeNode.textContent = job.exit_code === null || job.exit_code === undefined ? "-" : job.exit_code;
      }
      if (startedAtNode) {
        startedAtNode.textContent = job.started_at || "-";
      }
      if (finishedAtNode) {
        finishedAtNode.textContent = job.finished_at || "-";
      }
      if (outputNode) {
        outputNode.textContent = job.output || "Noch keine Ausgabe.";
      }
      if (runningBanner && status !== "queued" && status !== "running") {
        runningBanner.hidden = true;
      }
      if (completionMessage && status !== "queued" && status !== "running") {
        completionMessage.textContent = status === "ok"
          ? "Datenjob wurde erfolgreich abgeschlossen."
          : "Datenjob ist fehlgeschlagen.";
        completionMessage.classList.toggle("status-ok", status === "ok");
        completionMessage.classList.toggle("status-error", status !== "ok");
        completionMessage.hidden = false;
      }
      if (wasRunning && status !== "queued" && status !== "running") {
        wasRunning = false;
        document.dispatchEvent(new CustomEvent("servicejob:finished", {
          detail: { jobId: jobId, status: status },
        }));
      }
      return status === "queued" || status === "running";
    } catch (_error) {
      return true;
    }
  }

  const intervalId = window.setInterval(async function () {
    const keepPolling = await refreshJob();
    if (!keepPolling) {
      window.clearInterval(intervalId);
    }
  }, 1500);
}());
