// ===============================
// Tema (dark/light) com animação
// ===============================
(function themeManager() {
  const KEY = "atm:theme";
  const html = document.documentElement;

  function applyTheme(value) {
    // animação suave ao trocar
    document.body.classList.add("theme-switching");
    requestAnimationFrame(() => {
      html.setAttribute("data-theme", value);
      localStorage.setItem(KEY, value);
      // remove classe após alguns ms
      setTimeout(() => document.body.classList.remove("theme-switching"), 260);
    });
  }

  // Carrega salvo ou respeita prefers-color-scheme
  const saved = localStorage.getItem(KEY);
  if (saved === "light" || saved === "dark") {
    html.setAttribute("data-theme", saved);
  } else {
    const prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
    html.setAttribute("data-theme", prefersLight ? "light" : "dark");
  }

  // Botões
  const btnDark = document.getElementById("btnThemeDark");
  const btnLight = document.getElementById("btnThemeLight");
  const btnToggle = document.getElementById("btnThemeToggle");

  btnDark && btnDark.addEventListener("click", () => applyTheme("dark"));
  btnLight && btnLight.addEventListener("click", () => applyTheme("light"));
  btnToggle && btnToggle.addEventListener("click", () => {
    const current = html.getAttribute("data-theme");
    applyTheme(current === "light" ? "dark" : "light");
  });
})();

// ===============================
// Fade-in inicial de páginas
// ===============================
(function pageFadeIn() {
  window.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("in");
    document.querySelectorAll(".fade-in").forEach(el => {
      requestAnimationFrame(() => el.classList.add("in"));
    });
  });
})();

// ===============================
// Ripple em botões
// ===============================
(function rippleButtons() {
  function createRipple(e) {
    const btn = e.currentTarget;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;

    const ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.width = ripple.style.height = size + "px";
    ripple.style.left = x + "px";
    ripple.style.top = y + "px";

    btn.appendChild(ripple);
    ripple.addEventListener("animationend", () => ripple.remove());
  }

  document.addEventListener("click", (e) => {
    const target = e.target.closest(".btn");
    if (target) createRipple(e);
  });
})();

// ===============================
// Labels flutuantes (focus+texto)
// "o que ele é fica escrito nele e quando clica o que é sai dele
//  e se tiver texto ele não volta"
// ===============================
(function floatingLabels() {
  function updateGroup(group) {
    const input = group.querySelector("input, textarea");
    const hasText = input && input.value.trim().length > 0;
    if (document.activeElement === input || hasText) {
      group.classList.add("active");   // label sobe e fica
    } else {
      group.classList.remove("active"); // label volta só se sem texto
    }
  }

  function bind(group) {
    const input = group.querySelector("input, textarea");
    if (!input) return;
    ["focus", "blur", "input", "change"].forEach(evt => {
      input.addEventListener(evt, () => updateGroup(group));
    });
    // estado inicial
    updateGroup(group);
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".floating-group").forEach(bind);
  });
})();

// ===============================
// Util: helper de CSRF + fetch JSON
// ===============================
function getCSRFToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

async function fetchJSON(url, { method = "GET", body = null, headers = {} } = {}) {
  const defaultHeaders = {
    "X-Requested-With": "XMLHttpRequest",
    "X-CSRFToken": getCSRFToken(),
  };
  if (body && !(body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  const res = await fetch(url, { method, headers: { ...defaultHeaders, ...headers }, body });
  const isJSON = res.headers.get("content-type")?.includes("application/json");
  if (!res.ok) {
    const msg = isJSON ? (await res.json()) : await res.text();
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return isJSON ? res.json() : res.text();
}

// ===============================
// Expor utilitários
// ===============================
window.ATM = { fetchJSON };
