(() => {
  const forms = [...document.querySelectorAll('[data-ri-script-form]')];
  if (!forms.length) return;
  const banner = document.querySelector('[data-ri-active-job]');
  const link = document.querySelector('[data-ri-active-job-link]');
  let submitting = false;
  let running = banner && !banner.hidden;
  function updateButtons() {
    forms.forEach(form => form.querySelectorAll('button[type=submit]').forEach(button => {
      button.disabled = submitting || running;
      if (!button.dataset.originalLabel) button.dataset.originalLabel = button.textContent;
      button.textContent = submitting ? 'Auftrag wird gestartet…' : button.dataset.originalLabel;
    }));
  }
  forms.forEach(form => form.addEventListener('submit', event => {
    if (submitting || running) {
      event.preventDefault();
      return;
    }
    submitting = true;
    form.setAttribute('aria-busy', 'true');
    updateButtons();
  }));
  document.addEventListener('servicejobs:status', event => {
    const job = event.detail.active.find(item => item.area === 'ri');
    running = Boolean(job);
    if (banner) banner.hidden = !running;
    if (job && link) link.href = job.detail_url;
    updateButtons();
  });
  window.addEventListener('pageshow', () => {
    submitting = false;
    forms.forEach(form => form.removeAttribute('aria-busy'));
    updateButtons();
  });
  updateButtons();
})();
