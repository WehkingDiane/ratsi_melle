(function () {
  document.querySelectorAll("[data-confirm-delete-token]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      if (!window.confirm("Soll der gespeicherte Token wirklich gelöscht werden?")) {
        event.preventDefault();
      }
    });
  });
}());
