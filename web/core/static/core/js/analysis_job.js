(function () {
  const form = document.getElementById("analysis-job-run-form");
  const submitButton = document.getElementById("analysis-job-run-submit");
  const runStatus = document.getElementById("analysis-job-run-status");
  let submitting = false;

  if (!form || !submitButton || !runStatus) {
    return;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    submitting = true;
    form.setAttribute("aria-busy", "true");
    submitButton.disabled = true;
    submitButton.textContent = "Analyse läuft …";
    runStatus.hidden = false;

    window.setTimeout(function () {
      form.submit();
    }, 50);
  });
}());
