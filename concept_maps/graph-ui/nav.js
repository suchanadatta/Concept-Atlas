/* One router for the whole app.

   There used to be three disjoint navigation surfaces — the landing page, the
   results view and the concept-map header — each with its own buttons and no
   shared identity. Worse, the graph view's "← Search" button was wired but
   its sync function was never called, so once you opened the map there was no
   way back to search at all.

   Everything now goes through Nav.go(view), which owns what is visible, which
   nav button is lit, and the URL. The panels (reader, chat, compare, authors)
   are overlays on top of a view, not views themselves. */
"use strict";

const Nav = (function () {
  const $ = (id) => document.getElementById(id);
  let current = null;

  const el = {
    landing: () => $("landing"),
    gres: () => $("gres"),
  };

  function hide(node) { if (node) node.classList.add("hidden"); }
  function show(node) { if (node) node.classList.remove("hidden"); }

  /* The map is `main` + `#topbar`, which are always in the document; they are
     revealed by hiding whatever full-screen panel covers them. */
  function paintNav(view) {
    document.querySelectorAll("#app-nav button").forEach(b => {
      b.classList.toggle("active", b.dataset.view === view);
    });
    document.body.classList.toggle("view-map", view === "map" || view === "queries");
    document.body.classList.toggle("view-search", view === "search" || view === "results");
  }

  /* The reader, the chat, Compare and the Authors registry are overlays on top
     of a view. The app bar sits above them, so its buttons were clickable —
     but going to a view left the overlay covering it, and Search and Concept
     map looked broken because the chat was still on screen over the result. */
  function dismissOverlays() {
    if (window.Chat && typeof Chat.close === "function") Chat.close();
    if (typeof window.closeReader === "function") window.closeReader();
    if (window.Authors && typeof Authors.close === "function") Authors.close();
    if (window.DocsPanel && typeof DocsPanel.close === "function") DocsPanel.close();
    // Compare's closer is private to its module; hiding the panel is the same thing
    const cmp = $("compare");
    if (cmp) cmp.classList.add("hidden");
    const pick = $("chat-picker");
    if (pick) pick.classList.add("hidden");
  }

  function go(view, opts = {}) {
    if (view !== "ask") dismissOverlays();
    switch (view) {
      case "search": {
        // Restore a live search rather than throwing it away. Checking only
        // whether #gres was *visible* failed the moment you went to the map,
        // which hides it — coming back landed you on the empty landing page
        // with the results still sitting in the DOM behind it.
        const hasResults = !!window._lastQuery
          && el.gres() && el.gres().querySelector(".gr-pass, .gr-concept");
        if (hasResults && !opts.force) {
          hide(el.landing());
          show(el.gres());
          if (window._lastQuery) history.replaceState({}, "", `?q=${encodeURIComponent(window._lastQuery)}`);
          current = "results";
          paintNav("search");
          return;
        }
        hide(el.gres());
        show(el.landing());
        const inp = $("landing-input");
        if (inp) inp.focus();
        history.replaceState({}, "", "/");
        current = "search";
        paintNav("search");
        break;
      }
      case "results":
        hide(el.landing());
        show(el.gres());
        current = "results";
        paintNav("search");
        break;
      case "map":
      case "queries":
        // the query graph is a split of the results view; it would otherwise
        // stay open on top of the concept map it has nothing to do with
        if (typeof window.closeDynGraph === "function") window.closeDynGraph();
        hide(el.landing());
        hide(el.gres());
        if (view === "queries") { const t = $("tab-queries"); if (t) t.click(); }
        else { const t = $("tab-filters"); if (t) t.click(); }
        history.replaceState({}, "", view === "queries" ? "?view=queries" : "?view=graph");
        current = view;
        paintNav("map");
        // the stage was display:none-adjacent while covered; re-fit it
        window.dispatchEvent(new Event("resize"));
        break;
      case "ask":
        if (window.Chat) Chat.open();
        paintNav("ask");
        break;
      default:
        break;
    }
  }

  /* Which view is on screen, ignoring overlays. */
  function currentView() { return current; }

  function init() {
    document.querySelectorAll("#app-nav button").forEach(b => {
      b.onclick = () => go(b.dataset.view);
    });
    const brand = $("app-brand");
    if (brand) brand.onclick = () => go("search", { force: true });

    // search.js owns the landing/results transition; keep the nav in step
    document.addEventListener("atlas:view", (e) => paintNav(e.detail));

    // reflect the entry URL
    const p = new URLSearchParams(location.search);
    if (p.get("q")) paintNav("search");
    else if (p.get("view")) paintNav("map");
    else paintNav("search");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  return { go, currentView, paintNav };
})();

window.Nav = Nav;
