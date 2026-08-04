/* Skillik — минимальный JS */

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

  // Инициализация темы
  let stored = "system";
  try {
    stored = localStorage.getItem("skillik-theme") || document.body.dataset.themePref || "system";
  } catch (e) {}
  applyTheme(stored);

  // Кнопка переключения
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const current = root.getAttribute("data-theme");
      applyTheme(current === "dark" ? "light" : "dark");
    });
  });

  // Мобильное меню
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  document.querySelectorAll("[data-menu-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!sidebar) return;
      sidebar.classList.toggle("open");
      if (overlay) overlay.classList.toggle("show");
    });
  });
  if (overlay) {
    overlay.addEventListener("click", function () {
      sidebar && sidebar.classList.remove("open");
      overlay.classList.remove("show");
    });
  }

  // Таймер до урока
  document.querySelectorAll("[data-countdown]").forEach(function (el) {
    const target = new Date(el.getAttribute("data-countdown")).getTime();
    function tick() {
      const now = Date.now();
      let diff = Math.max(0, target - now);
      const d = Math.floor(diff / 86400000);
      diff %= 86400000;
      const h = Math.floor(diff / 3600000);
      diff %= 3600000;
      const m = Math.floor(diff / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      let text = "";
      if (d > 0) text += d + "д ";
      text += String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
      el.textContent = diff === 0 && d === 0 && target <= now ? "Сейчас" : text;
    }
    tick();
    setInterval(tick, 1000);
  });

  // Пользовательский акцент
  const accent = document.body.dataset.accent;
  if (accent) {
    root.style.setProperty("--user-accent", accent);
  }
})();
