(function () {
  const indicator = document.getElementById("job-indicator");
  const text = document.getElementById("job-indicator-text");

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
        ? "Datenjob läuft: " + job.action
        : active.length + " Datenjobs laufen";
    } catch (_error) {
      return;
    }
  }

  async function refreshOverallStatus(container) {
    const button = container.querySelector("[data-service-status-refresh]");
    const feedback = container.querySelector("[data-service-status-feedback]");
    const statusUrl = container.getAttribute("data-status-url");
    if (!button || !statusUrl) {
      return;
    }

    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Wird aktualisiert…";
    if (feedback) {
      feedback.hidden = true;
    }

    try {
      const response = await fetch(statusUrl, {
        cache: "no-store",
        headers: { "Accept": "application/json" },
      });
      if (!response.ok) {
        throw new Error("Status request failed");
      }
      const payload = await response.json();
      const status = payload.status || {};
      container.querySelectorAll("[data-status-field]").forEach(function (node) {
        const valueField = node.getAttribute("data-status-field");
        const existsField = node.getAttribute("data-status-exists-field");
        node.textContent = status[valueField] === undefined ? "-" : status[valueField];
        node.classList.toggle("status-ok", Boolean(status[existsField]));
        node.classList.toggle("status-muted", !status[existsField]);
      });
      container.querySelectorAll("[data-model-field]").forEach(function (node) {
        const value = node.getAttribute("data-model-field").split(".").reduce(function (current, key) {
          return current && Object.prototype.hasOwnProperty.call(current, key) ? current[key] : undefined;
        }, status.embedding_models);
        const format = node.getAttribute("data-model-format");
        let display = value;
        if (value === undefined || value === null) {
          display = node.getAttribute("data-model-empty") || "Nicht verfügbar";
        } else if (format === "bytes") {
          const units = ["Bytes", "KB", "MB", "GB", "TB", "PB"];
          const unit = value > 0 ? Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1) : 0;
          display = (value / Math.pow(1024, unit)).toLocaleString("de-DE", { maximumFractionDigits: 1 }) + " " + units[unit];
        } else if (format === "status" && value === "unvollstaendig") {
          display = "unvollständig";
        }
        node.textContent = display;
        if (format === "status") {
          node.classList.toggle("status-ok", value === "bereit");
          node.classList.toggle("status-warning", Boolean(value) && value !== "bereit");
          node.classList.toggle("status-muted", !value);
        }
      });
      if (feedback) {
        feedback.textContent = "Status wurde aktualisiert.";
        feedback.hidden = false;
      }
    } catch (_error) {
      if (feedback) {
        feedback.textContent = "Status konnte nicht aktualisiert werden.";
        feedback.hidden = false;
      }
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  document.querySelectorAll("[data-service-status]").forEach(function (container) {
    const button = container.querySelector("[data-service-status-refresh]");
    if (button) {
      button.addEventListener("click", function () {
        refreshOverallStatus(container);
      });
    }
  });

  document.addEventListener("servicejob:finished", function () {
    document.querySelectorAll("[data-service-status]").forEach(function (container) {
      refreshOverallStatus(container);
    });
  });

  if (indicator && text) {
    refreshServiceStatus();
    window.setInterval(refreshServiceStatus, 2000);
  }
}());
