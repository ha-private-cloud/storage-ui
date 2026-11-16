(function () {
  "use strict";

  var toggle = document.getElementById("profile-menu-toggle");
  var menu = document.getElementById("profile-menu");
  if (!toggle || !menu) return;

  function setOpen(open) {
    menu.classList.toggle("hidden", !open);
    toggle.setAttribute("aria-expanded", String(open));
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    setOpen(menu.classList.contains("hidden"));
  });

  document.addEventListener("click", function (e) {
    if (!menu.contains(e.target) && e.target !== toggle) {
      setOpen(false);
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setOpen(false);
  });
})();
