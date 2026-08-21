(function () {
  const analysisForm = document.getElementById("analysis-start-form");
  const submitButton = document.getElementById("analysis-start-submit");
  const startStatus = document.getElementById("analysis-start-status");

  if (analysisForm && submitButton && startStatus) {
    analysisForm.addEventListener("submit", function () {
      startStatus.hidden = false;
      submitButton.disabled = true;
      submitButton.textContent = "Analyse läuft …";
    });
  }

  document.querySelectorAll('input[name="scope"]').forEach(function (input) {
    input.addEventListener("change", function () {
      if (!input.checked) {
        return;
      }

      const url = new URL(window.location.pathname, window.location.origin);
      const sessionInput = document.querySelector('input[name="session_id"]');
      const sessionId = sessionInput ? sessionInput.value : "";
      if (sessionId) {
        url.searchParams.set("session_id", sessionId);
      }
      url.searchParams.set("scope", input.value);
      url.searchParams.delete("template_id");
      window.location.href = url.toString();
    });
  });
}());
