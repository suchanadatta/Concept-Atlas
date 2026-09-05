/* Settings: engine device switch, search preferences, live index status,
   and the panel stacking manager. */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const LS = "atlas.settings";

  const defaults = { topk: 60, mode: "auto", facets: "on", theme: "light" };
  let prefs = { ...defaults };

  function load() {
    try { prefs = { ...defaults, ...JSON.parse(localStorage.getItem(LS) || "{}") }; }
    catch { prefs = { ...defaults }; }
  }
  function save() {
    try { localStorage.setItem(LS, JSON.stringify(prefs)); } catch { /* private mode */ }
  }

  /* ---------- device switcher ---------- */
  async function api(body) {
    const r = await fetch("/book/api/device_proxy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  }

  function paintDevice(cur, cudaOk) {
    $("device-cpu").classList.toggle("active", cur === "cpu");
    $("device-cuda").classList.toggle("active", cur === "cuda");
    if (cudaOk != null) $("device-cuda").disabled = !cudaOk;
    const label = cur === "cuda" ? "GPU" : "CPU";
    $("device-status").textContent = cur ? `running on ${label}` : "offline";
    $("engine-chip-text").textContent = cur ? `Jasper on ${label}` : "engine offline";
    const dot = $("engine-dot");
    dot.className = "chip-dot" + (!cur ? " off" : cur === "cpu" ? " warn" : "");
    dot.title = cur === "cpu" ? "on CPU — searches take a few seconds" : "";
  }

  async function refreshDevice() {
    try {
      const d = await api({ action: "get" });
      const cur = d.device || "cpu";
      paintDevice(cur, !!(d.available && d.available.cuda));
      return cur;
    } catch {
      paintDevice(null, null);
      return null;
    }
  }

  async function switchDevice(target) {
    $("device-status").textContent = `switching to ${target.toUpperCase()}…`;
    $("engine-chip-text").textContent = "switching…";
    try {
      const d = await api({ action: "switch", device: target });
      if (d.error) { $("device-status").textContent = `error: ${d.error}`; return; }
      paintDevice(d.device, null);
      refreshStatus();
    } catch {
      $("device-status").textContent = "switch failed";
    }
  }

  /* ---------- live index status ---------- */
  async function refreshStatus() {
    let d = null;
    try { d = await (await fetch("/book/api/engine")).json(); } catch { /* offline */ }
    window._engineInfo = d || {};
    const chip = $("chip-index");
    if (!d || d.status !== "ok") {
      chip.innerHTML = `<b>index</b> unavailable`;
      $("sp-stats").innerHTML = `<span>engine</span><b>offline</b>`;
      return;
    }
    chip.innerHTML = `<b>${(d.index || 0).toLocaleString()}</b> passages · <b>${d.books || 0}</b> books`;
    const c = d.cache || {};
    const total = (c.hits || 0) + (c.misses || 0);
    $("sp-stats").innerHTML = [
      ["passages", (d.index || 0).toLocaleString()],
      ["books", d.books || 0],
      ["concepts", d.concepts || 0],
      ["embedding dim", d.dim || 0],
      ["device", (d.device || "?").toUpperCase()],
      ["query cache", `${c.size || 0} vectors · ${total ? Math.round(100 * (c.hits || 0) / total) : 0}% hit`],
    ].map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join("");
  }

  /* Search timing is reported back by search.js — it is the number that tells
     a user whether the engine is warm, which the device label alone can't. */
  window.reportSearchTiming = function (ms, cached) {
    const chip = $("chip-timing");
    if (!chip) return;
    chip.style.display = "";
    chip.innerHTML = cached
      ? `<b>${ms} ms</b> · cached`
      : `<b>${(ms / 1000).toFixed(1)} s</b>`;
    chip.title = cached
      ? "the query vector was already cached — no re-embedding"
      : "time to embed the query and rank the index";
  };

  /* ---------- preferences ---------- */
  function applyPrefs() {
    window._searchTopK = prefs.topk;
    if (prefs.facets === "off") document.body.classList.add("facets-collapsed");
    else document.body.classList.remove("facets-collapsed");
    const ft = $("gres-facet-toggle");
    if (ft) ft.classList.toggle("active", prefs.facets === "on");
    if (prefs.theme === "dark") document.body.classList.add("dark");
    else document.body.classList.remove("dark");
    // the ranking select is the same control the results bar exposes
    if (!window._forceSearchMode || window._forceSearchMode === "auto") {
      window._forceSearchMode = prefs.mode;
    }
    const algo = $("gres-algo");
    if (algo) algo.value = prefs.mode === "auto" ? "hybrid" : prefs.mode;
  }

  function wirePrefs() {
    $("set-topk").value = String(prefs.topk);
    $("set-mode").value = prefs.mode;
    $("set-facets").value = prefs.facets;
    $("set-theme").value = prefs.theme;
    $("set-topk").onchange = (e) => { prefs.topk = +e.target.value; save(); applyPrefs(); };
    $("set-mode").onchange = (e) => {
      prefs.mode = e.target.value; save();
      window._forceSearchMode = prefs.mode;
      applyPrefs();
      if (window.__rerunSearch) window.__rerunSearch();
    };
    $("set-facets").onchange = (e) => { prefs.facets = e.target.value; save(); applyPrefs(); };
    $("set-theme").onchange = (e) => { prefs.theme = e.target.value; save(); applyPrefs(); };
    $("sp-refresh").onclick = () => { refreshDevice(); refreshStatus(); };
  }

  /* keep the panel in step when the same settings are changed from the
     results bar or the header theme button */
  window.syncSettings = function (patch) {
    Object.assign(prefs, patch);
    save();
    if ($("set-mode")) {
      $("set-mode").value = prefs.mode;
      $("set-facets").value = prefs.facets;
      $("set-theme").value = prefs.theme;
    }
  };

  /* ---------- popover ---------- */
  function togglePanel(force) {
    const panel = $("settings-panel");
    const show = force != null ? force : panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !show);
    $("settings-open").classList.toggle("on", show);
    if (show) { refreshDevice(); refreshStatus(); }
  }

  /* ---------- panel stacking manager ----------
     Only ONE side panel (reader | dyngraph) is visible at a time; closing
     the top panel reveals the one beneath it instead of leaving a gap. */
  const stack = []; // e.g. ["dyngraph", "reader"] — last = top

  function drop(name) {
    const i = stack.lastIndexOf(name);
    if (i >= 0) stack.splice(i, 1);
  }

  const origCloseReader = window.closeReader;
  window.closeReader = function () {
    const wasTop = stack[stack.length - 1] === "reader";
    drop("reader");
    if (origCloseReader) origCloseReader();
    if (wasTop && stack.length) revealTop();
    else if (!stack.length) document.body.classList.remove("split-reading", "split-graph");
  };

  const origCloseDyn = window.closeDynGraph;
  window.closeDynGraph = function () {
    const wasTop = stack[stack.length - 1] === "dyngraph";
    drop("dyngraph");
    if (origCloseDyn) origCloseDyn();
    if (wasTop && stack.length) revealTop();
    else if (!stack.length) {
      document.body.classList.remove("split-graph", "split-reading");
      $("gres").style.right = "";
    }
  };

  function revealTop() {
    const top = stack[stack.length - 1];
    if (top === "reader") {
      $("reader").classList.remove("hidden");
      document.body.classList.add("split-reading");
      document.body.classList.remove("split-graph");
      $("gres").style.right = "";
      positionSplit(true);
    } else if (top === "dyngraph") {
      $("dyngraph").classList.remove("hidden");
      document.body.classList.add("split-graph");
      document.body.classList.remove("split-reading");
      $("gres").style.right = "54%";
    }
  }

  /* hook opens: patch showReaderShell + openDynGraph to push onto the stack
     and hide the panel beneath */
  const origShowShell = window.showReaderShell;
  window.showReaderShell = function () {
    if (origShowShell) origShowShell();
    if (stack[stack.length - 1] === "reader") return;
    if (stack[stack.length - 1] === "dyngraph") {
      $("dyngraph").classList.add("hidden"); // hide beneath, keep state
      document.body.classList.remove("split-graph");
      $("gres").style.right = "";
    }
    drop("reader");
    stack.push("reader");
  };

  const origOpenDyn = window.openDynGraph;
  window.openDynGraph = async function (q) {
    // hide reader beneath, keep its state for reveal-on-close
    if (stack[stack.length - 1] === "reader") {
      $("reader").classList.add("hidden");
      document.body.classList.remove("split-reading");
      positionSplit(false);
    }
    if (stack[stack.length - 1] !== "dyngraph") { drop("dyngraph"); stack.push("dyngraph"); }
    return origOpenDyn(q);
  };

  window.panelStack = () => stack.slice();

  /* ---------- init ---------- */
  function init() {
    load();
    // the header theme button and this panel edit the same preference
    if (document.body.classList.contains("dark")) prefs.theme = "dark";
    applyPrefs();
    wirePrefs();
    $("device-cpu").onclick = () => switchDevice("cpu");
    $("device-cuda").onclick = () => switchDevice("cuda");
    $("settings-open").onclick = (e) => { e.stopPropagation(); togglePanel(); };
    document.addEventListener("click", (e) => {
      const panel = $("settings-panel");
      if (panel.classList.contains("hidden")) return;
      if (!panel.contains(e.target) && e.target !== $("settings-open")) togglePanel(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("settings-panel").classList.contains("hidden")) {
        togglePanel(false);
        e.stopPropagation();
      }
    }, true);
    const themeBtn = $("btn-theme");
    if (themeBtn) {
      const orig = themeBtn.onclick;
      themeBtn.onclick = (e) => {
        if (orig) orig.call(themeBtn, e);
        window.syncSettings({ theme: document.body.classList.contains("dark") ? "dark" : "light" });
      };
    }
    refreshDevice();
    refreshStatus();
    setInterval(() => { refreshDevice(); refreshStatus(); }, 30000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
