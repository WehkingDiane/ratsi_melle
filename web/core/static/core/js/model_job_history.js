(function () {
  const panel = document.getElementById("model-job-history");
  if (!panel) { return; }
  const feedback = panel.querySelector("[data-history-feedback]");
  function paragraph(parent, text) {
    const node = document.createElement("p");
    node.textContent = text;
    parent.appendChild(node);
  }
  function link(parent, jobId, label) {
    const node = document.createElement("a");
    node.href = "/daten/jobs/" + encodeURIComponent(jobId) + "/";
    node.textContent = label;
    parent.appendChild(node);
  }
  async function refresh() {
    try {
      const response = await fetch(panel.getAttribute("data-history-url"), {
        cache: "no-store", headers: { "Accept": "application/json" },
      });
      if (!response.ok) { throw new Error("History unavailable"); }
      const history = (await response.json()).history || {};
      if (!history.available) { throw new Error("History unavailable"); }
      panel.querySelectorAll("[data-history-scope]").forEach(function (card) {
        const entry = (history.entries || []).find(item => item.scope === card.getAttribute("data-history-scope"));
        const last = card.querySelector("[data-history-last]");
        const active = card.querySelector("[data-history-active]");
        last.replaceChildren();
        active.replaceChildren();
        if (!entry || !entry.last_finished) {
          paragraph(last, "Kein gespeichertes Prüfergebnis.");
        } else {
          const job = entry.last_finished;
          paragraph(last, job.status_label + (job.result ? ": " + job.result : "") + " – " + (job.finished_at || "Abschlusszeit unbekannt"));
          paragraph(last, job.association_label);
          paragraph(last, "Modellverzeichnis: " + (job.models_dir || "Nicht nachgewiesen"));
          if (job.manifest_sha256) { paragraph(last, "Manifest: " + job.manifest_sha256); }
          link(last, job.job_id, "Letzten Versuch anzeigen");
        }
        (entry ? entry.active : []).forEach(function (job) {
          paragraph(active, job.status_label + ": " + job.progress.message);
          link(active, job.job_id, "Laufenden Job anzeigen");
        });
      });
      feedback.hidden = true;
    } catch (_error) {
      feedback.textContent = "Prüfhistorie konnte nicht aktualisiert werden; Anzeige kann veraltet sein.";
      feedback.hidden = false;
    }
  }
  window.setInterval(refresh, 3000);
  document.addEventListener("servicejob:finished", refresh);
}());
