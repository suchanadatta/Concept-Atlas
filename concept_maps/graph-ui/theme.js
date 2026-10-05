/* One source of truth for the theme.

   There were two: compare.js stored "atlas-theme" and settings.js stored
   theme inside "atlas.settings". Toggling from the header wrote one key and
   the settings panel wrote the other, so the two controls disagreed and the
   preference did not survive a reload made from the other one. Every page
   now reads and writes through here, and applies the class before first
   paint so there is no flash of the wrong theme.

   Loaded as a plain script at the top of <body> on every page. */
"use strict";

window.Theme = (function () {
  const KEY = "atlas.settings";
  const LEGACY = "atlas-theme";

  function read() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
      if (raw && (raw.theme === "dark" || raw.theme === "light")) return raw.theme;
    } catch { /* unparseable — fall through to the legacy key */ }
    try {
      const old = localStorage.getItem(LEGACY);
      if (old === "dark" || old === "light") {
        write(old);          // migrate once, then the legacy key is ignored
        return old;
      }
    } catch { /* storage blocked */ }
    // no stored choice: follow the OS
    try {
      if (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
    } catch { /* no matchMedia */ }
    return "light";
  }

  function write(theme) {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
      raw.theme = theme;
      localStorage.setItem(KEY, JSON.stringify(raw));
      localStorage.setItem(LEGACY, theme);   // kept in step for older tabs
    } catch { /* private mode: the class still applies for this session */ }
  }

  function paint(theme) {
    const dark = theme === "dark";
    // documentElement is available before <body> is parsed, so painting both
    // means the page never renders in the wrong theme first
    document.documentElement.classList.toggle("dark", dark);
    if (document.body) document.body.classList.toggle("dark", dark);
    const btn = document.getElementById("btn-theme");
    if (btn) {
      btn.textContent = dark ? "☀️" : "🌙";
      btn.title = dark ? "Switch to light" : "Switch to dark";
    }
    const sel = document.getElementById("set-theme");
    if (sel && sel.value !== theme) sel.value = theme;
    return dark;
  }

  let current = read();
  paint(current);
  if (!document.body) {
    document.addEventListener("DOMContentLoaded", () => paint(current), { once: true });
  }

  /* Anything that draws to a canvas has to be told; CSS cannot reach it. */
  function repaintCanvases(dark) {
    if (typeof S !== "undefined") {
      S.dirty = true;
      if (S.g3d && S.mode === "3d") {
        try { S.g3d.backgroundColor(dark ? "#141310" : "#F6F1E5"); } catch { /* not ready */ }
      }
    }
    if (window.__dynG3D) {
      try { window.__dynG3D.backgroundColor(dark ? "#141310" : "#F6F1E5"); } catch { /* not ready */ }
    }
    // sprite halos are baked into a canvas texture, so a theme flip has to
    // rebuild them rather than just recolour
    if (typeof S !== "undefined" && S.g3d && S.mode === "3d") {
      try { S.g3d.refresh(); } catch { /* not ready */ }
    }
    if (window.__dynG3D) { try { window.__dynG3D.refresh(); } catch { /* not ready */ } }
    if (typeof window.redrawDynGraph === "function") window.redrawDynGraph();
    if (typeof window.redrawGraphFloat === "function") window.redrawGraphFloat();
  }

  return {
    get: () => current,
    set(theme) {
      current = theme === "dark" ? "dark" : "light";
      write(current);
      const dark = paint(current);
      repaintCanvases(dark);
      document.dispatchEvent(new CustomEvent("atlas:theme", { detail: current }));
      return current;
    },
    toggle() { return this.set(current === "dark" ? "light" : "dark"); },
    isDark: () => current === "dark",
  };
})();
