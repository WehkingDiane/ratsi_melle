(function () {
  const toggle = document.querySelector(".nav-toggle");
  const navigation = document.getElementById("main-navigation");
  if (!toggle || !navigation) {
    return;
  }

  function setOpen(isOpen) {
    navigation.classList.toggle("is-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute("aria-label", isOpen ? "Navigation schließen" : "Navigation öffnen");
  }

  toggle.addEventListener("click", function () {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setOpen(false);
      toggle.focus();
    }
  });

  navigation.addEventListener("click", function (event) {
    if (event.target.closest("a")) {
      setOpen(false);
    }
  });
}());
