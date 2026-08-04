/* Skillik — UI helpers */

(function () {
  const root = document.documentElement;

  function systemPrefersDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function applyTheme(pref) {
    let theme = pref;
    if (pref === "system" || !pref) {
      theme = systemPrefersDark() ? "dark" : "light";
    }
    root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("skillik-theme", pref || "system");
    } catch (e) {}
  }

  // Init theme (body may force preference from profile)
  let stored = "system";
  try {
    const bodyPref = document.body && document.body.dataset.themePref;
    stored = localStorage.getItem("skillik-theme") || bodyPref || "system";
    // Профиль student: light/dark/system имеет приоритет, если задан явно
    if (bodyPref && bodyPref !== "system") {
      stored = bodyPref;
    }
  } catch (e) {}
  applyTheme(stored);

  // Theme toggle
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const current = root.getAttribute("data-theme");
      applyTheme(current === "dark" ? "light" : "dark");
    });
  });

  // Follow system when preference is system
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      let pref = "system";
      try {
        pref = localStorage.getItem("skillik-theme") || "system";
      } catch (e) {}
      if (pref === "system") applyTheme("system");
    });
  }

  // Mobile menu
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  function closeMenu() {
    if (sidebar) sidebar.classList.remove("open");
    if (overlay) overlay.classList.remove("show");
    document.body.style.overflow = "";
  }

  function openMenu() {
    if (sidebar) sidebar.classList.add("open");
    if (overlay) overlay.classList.add("show");
    document.body.style.overflow = "hidden";
  }

  document.querySelectorAll("[data-menu-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!sidebar) return;
      if (sidebar.classList.contains("open")) closeMenu();
      else openMenu();
    });
  });
  if (overlay) overlay.addEventListener("click", closeMenu);

  // Close menu on nav click (mobile)
  if (sidebar) {
    sidebar.querySelectorAll("nav a").forEach(function (a) {
      a.addEventListener("click", function () {
        if (window.innerWidth <= 900) closeMenu();
      });
    });
  }

  // Escape closes menu
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeMenu();
  });

  // Countdown to lesson
  document.querySelectorAll("[data-countdown]").forEach(function (el) {
    const raw = el.getAttribute("data-countdown");
    const target = new Date(raw).getTime();
    if (isNaN(target)) {
      el.textContent = "—";
      return;
    }
    function tick() {
      const now = Date.now();
      let diff = Math.max(0, target - now);
      if (diff === 0) {
        el.textContent = "Сейчас";
        return;
      }
      const d = Math.floor(diff / 86400000);
      diff %= 86400000;
      const h = Math.floor(diff / 3600000);
      diff %= 3600000;
      const m = Math.floor(diff / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      let text = "";
      if (d > 0) text += d + "д ";
      text +=
        String(h).padStart(2, "0") +
        ":" +
        String(m).padStart(2, "0") +
        ":" +
        String(s).padStart(2, "0");
      el.textContent = text;
    }
    tick();
    setInterval(tick, 1000);
  });

  // User accent color
  const accent = document.body && document.body.dataset.accent;
  if (accent) {
    root.style.setProperty("--user-accent", accent);
  }

  // Dismissible / auto-hide alerts
  document.querySelectorAll("[data-dismiss-alert]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const alert = btn.closest(".alert");
      if (alert) alert.remove();
    });
  });
  document.querySelectorAll("[data-auto-dismiss]").forEach(function (el) {
    const ms = parseInt(el.getAttribute("data-auto-dismiss"), 10) || 5000;
    setTimeout(function () {
      el.style.transition = "opacity 0.35s";
      el.style.opacity = "0";
      setTimeout(function () {
        el.remove();
      }, 400);
    }, ms);
  });

  // Clean flash query params from URL (keep history clean)
  try {
    const u = new URL(window.location.href);
    if (u.searchParams.has("ok") || u.searchParams.has("error") || u.searchParams.has("msg")) {
      ["ok", "error", "msg"].forEach(function (k) {
        u.searchParams.delete(k);
      });
      window.history.replaceState({}, "", u.pathname + (u.search ? u.search : "") + u.hash);
    }
  } catch (e) {}
})();
