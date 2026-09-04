/* Settings bar: CPU/GPU switcher for the semantic engine + panel stacking manager. */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);

  /* ---------- device switcher ---------- */
  async function api(body) {
    const r = await fetch("/book/api/device_proxy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  }

  async function refreshDevice() {
    try {
      const d = await api({ action: "get" });
      const cur = d.device || "cpu";
      $("device-cpu").classList.toggle("active", cur === "cpu");
      $("device-cuda").classList.toggle("active", cur === "cuda");
      $("device-cuda").disabled = !(d.available && d.available.cuda);
      $("device-status").textContent =
        cur === "cuda" ? "running on GPU" : "running on CPU";
      return cur;
    } catch (e) {
      $("device-status").textContent = "engine offline";
      return null;
    }
  }

  async function switchDevice(target) {
    $("device-status").textContent = `switching to ${target.toUpperCase()}…`;
    try {
      const d = await api({ action: "switch", device: target });
      if (d.error) {
        $("device-status").textContent = `error: ${d.error}`;
        return;
      }
      $("device-status").textContent =
        d.device === "cuda" ? "running on GPU" : "running on CPU";
      $("device-cpu").classList.toggle("active", d.device === "cpu");
      $("device-cuda").classList.toggle("active", d.device === "cuda");
    } catch (e) {
      $("device-status").textContent = "switch failed";
    }
  }

  /* ---------- panel stacking manager ----------
     Only ONE side panel (reader | dyngraph) is visible at a time; closing
     the top panel reveals the one beneath it instead of leaving a gap. */
  const stack = []; // e.g. ["dyngraph", "reader"] — last = top

  function panelId(el) { return el && el.id; }

  const origCloseReader = window.closeReader;
  window.closeReader = function () {
    const wasTop = stack[stack.length - 1] === "reader";
    if (wasTop) stack.pop();
    if (origCloseReader) origCloseReader();
    if (wasTop && stack.length) revealTop();
    else if (!stack.length) document.body.classList.remove("split-reading", "split-graph");
  };

  const origCloseDyn = window.closeDynGraph;
  window.closeDynGraph = function () {
    const wasTop = stack[stack.length - 1] === "dyngraph";
    if (wasTop) stack.pop();
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
      const r = $("reader");
      r.classList.remove("hidden");
      document.body.classList.add("split-reading");
      positionSplit(true);
    } else if (top === "dyngraph") {
      $("dyngraph").classList.remove("hidden");
      document.body.classList.add("split-graph");
      $("gres").style.right = "54%";
    }
  }

  /* hook opens: patch showReaderShell + dyngraph.open to push onto the stack
     and hide the panel beneath */
  const origShowShell = window.showReaderShell;
  window.showReaderShell = function () {
    if (origShowShell) origShowShell();
    if (stack[stack.length - 1] !== "reader") {
      if (stack.length && stack[stack.length - 1] === "dyngraph") {
        $("dyngraph").classList.add("hidden"); // hide beneath, keep state
      }
      stack.push("reader");
    }
  };

  const origOpenDyn = window.openDynGraph;
  window.openDynGraph = async function (q) {
    // hide reader beneath, keep its state for reveal-on-close
    if (stack.length && stack[stack.length - 1] === "reader") {
      $("reader").classList.add("hidden");
      document.body.classList.remove("split-reading");
      positionSplit(false);
    }
    if (stack[stack.length - 1] !== "dyngraph") stack.push("dyngraph");
    return origOpenDyn(q);
  };

  /* ---------- init ---------- */
  function init() {
    $("device-cpu").onclick = () => switchDevice("cpu");
    $("device-cuda").onclick = () => switchDevice("cuda");
    refreshDevice();
    setInterval(refreshDevice, 30000); // auto-detect server restarts/device changes
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
