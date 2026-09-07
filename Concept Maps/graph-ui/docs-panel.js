/* The documentation as an in-app panel.

   Docs was an <a href="docs.html">: it works, but it navigates away and you
   lose your search, your reader position and your chat. Everything else in
   this app — Authors, Compare, the reader — is an overlay you can dismiss and
   come back from, and the docs should behave the same way.

   The page itself is unchanged and still served, so the link keeps working for
   a new tab, a bookmark or a browser with JavaScript off. */
"use strict";

const DocsPanel = (function () {
  const $ = (id) => document.getElementById(id);
  let html = null;          // fetched once
  let loading = null;

  async function fetchDocs() {
    if (html !== null) return html;
    if (loading) return loading;
    loading = fetch("docs.html")
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.text(); })
      .then(text => {
        // take the article, not the page: its own header bar and theme button
        // would duplicate the app bar's
        const doc = new DOMParser().parseFromString(text, "text/html");
        const art = doc.querySelector(".docs");
        if (!art) throw new Error("the documentation page had no content");
        const bar = art.querySelector(".docs-bar");
        if (bar) bar.remove();
        html = art.innerHTML;
        return html;
      })
      .finally(() => { loading = null; });
    return loading;
  }

  async function open() {
    const host = $("docs-panel");
    if (!host) return;
    host.classList.remove("hidden");
    document.body.classList.add("docs-open");
    host.innerHTML = `<div class="docs-head">
        <span class="docs-title">Documentation</span>
        <a href="docs.html" class="mini" target="_blank" rel="noopener">open in a tab</a>
        <button id="docs-close" title="Close (Esc)">&#215;</button>
      </div>
      <div class="docs-body"><p class="hint">loading&#8230;</p></div>`;
    $("docs-close").onclick = close;
    try {
      const body = await fetchDocs();
      host.querySelector(".docs-body").innerHTML = body;
    } catch (e) {
      host.querySelector(".docs-body").innerHTML =
        `<p class="hint">The documentation could not be loaded (${e.message}).
         <a href="docs.html">Open it as a page instead.</a></p>`;
    }
  }

  function close() {
    const host = $("docs-panel");
    if (!host) return;
    host.classList.add("hidden");
    document.body.classList.remove("docs-open");
  }

  function isOpen() {
    const host = $("docs-panel");
    return !!host && !host.classList.contains("hidden");
  }

  function init() {
    const a = $("btn-docs");
    if (a) a.onclick = (e) => {
      // a middle click, ctrl-click or cmd-click should still open a real tab
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      open();
    };
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isOpen()) { e.stopPropagation(); close(); }
    }, true);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  return { open, close, isOpen };
})();

window.DocsPanel = DocsPanel;
