/* Search-engine interface: landing → results (passages/concepts/graph) */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* Function words never carry retrieval meaning; highlighting them painted
     "and"/"the" yellow in every snippet and buried the real matches. Kept in
     step with LEX_STOP in jasper_search_server_v2.py. */
  const STOP = new Set(("the a an and or but nor for yet so of in on at to from by with about as into over " +
    "after before between under above is are was were be been being am do does did have has had having " +
    "shall should may might must can could that this these those there their it its his her him she he " +
    "they them we you your our not no all any some such which who whom whose what when where why how than " +
    "then thus also more most much many very upon whether if either neither both each other others " +
    "another same own one two say said let make made take taken come came go went thing things way ways").split(" "));

  function init() {
    // published before anything can dispatch atlas:search
    window.__doGlobalSearch = doGlobalSearch;
    // landing state: hide main app chrome until search/graph chosen
    const params = new URLSearchParams(location.search);
    const q = params.get("q");
    const view = params.get("view");
    if (q) {
      doGlobalSearch(q);
    } else if (view === "graph" || view === "queries") {
      hideLanding();
      if (view === "queries") $("tab-queries").click();
    } else {
      showLanding();
    }
    $("landing-go").onclick = () => submitLanding();
    $("landing-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitLanding();
    });
    document.querySelectorAll(".landing-examples .ex").forEach(b => {
      b.onclick = () => { $("landing-input").value = b.dataset.q; submitLanding(); };
    });
    $("landing-graph").onclick = () => { hideLanding(); history.replaceState({}, "", "?view=graph"); };
    $("landing-queries").onclick = () => { hideLanding(); $("tab-queries").click(); history.replaceState({}, "", "?view=queries"); };
    const openAuthors = () => { if (window.Authors) Authors.open(); };
    if ($("landing-authors")) $("landing-authors").onclick = openAuthors;
    if ($("btn-authors")) $("btn-authors").onclick = openAuthors;
    $("gres-back").onclick = () => { $("gres").classList.add("hidden"); showLanding(); history.replaceState({}, "", "/"); };
    const rerunFromBar = () => {
      const q = $("gres-input").value.trim();
      if (q.length >= 2) doGlobalSearch(q);
    };
    $("gres-go").onclick = rerunFromBar;
    $("gres-input").addEventListener("keydown", (e) => { if (e.key === "Enter") rerunFromBar(); });
    window._forceSearchMode = window._forceSearchMode || "auto"; // auto|semantic|bm25|keyword
    const algoSel = $("gres-algo");
    if (algoSel) {
      algoSel.value = window._forceSearchMode === "auto" ? "hybrid" : window._forceSearchMode;
      algoSel.onchange = () => {
        window._forceSearchMode = algoSel.value === "hybrid" ? "auto" : algoSel.value;
        if (window.syncSettings) window.syncSettings({ mode: window._forceSearchMode });
        rerunSearch();
      };
    }
    window.__rerunSearch = rerunSearch;
    function rerunSearch() {
      const u = new URLSearchParams(location.search);
      const q = u.get("q") || (currentResults && currentResults.q);
      if (q) doGlobalSearch(q);
    }
    $("gres-tab-passages").onclick = () => setResTab("passages");
    $("gres-tab-concepts").onclick = () => setResTab("concepts");
    $("gres-tab-graph").onclick = () => {
      // concept+book network for THIS query — built live by the semantic backend
      if (typeof window.openDynGraph === "function" && currentResults) {
        window.openDynGraph(currentResults.q);
      }
    };
    const ctxAll = $("gres-ctx");
    if (ctxAll) ctxAll.onclick = () => {
      if (!currentResults || !window.Chat) return;
      Chat.addContext([{ kind: "search", query: currentResults.q,
                         top_k: Math.min(60, currentResults.passages.length || 20) }]);
    };
    const sortSel = $("gres-sort");
    if (sortSel) sortSel.onchange = () => { sortMode = sortSel.value; renderResults(); };
    const facetToggle = $("gres-facet-toggle");
    if (facetToggle) facetToggle.onclick = () => {
      document.body.classList.toggle("facets-collapsed");
      const on = !document.body.classList.contains("facets-collapsed");
      facetToggle.classList.toggle("active", on);
      if (window.syncSettings) window.syncSettings({ facets: on ? "on" : "off" });
    };
    document.addEventListener("keydown", onResultsKey);
  }

  function showLanding() {
    $("landing").classList.remove("hidden");
    $("landing-input").focus();
  }
  function hideLanding() { $("landing").classList.add("hidden"); }

  function submitLanding() {
    const q = $("landing-input").value.trim();
    if (!q) return;
    doGlobalSearch(q);
  }

  let currentResults = null;
  let currentTab = "passages";
  let sortMode = "relevance";
  let activeFacets = { author: new Set(), writer: new Set(), period: new Set(), source: new Set() };
  let cursor = -1;          // keyboard-selected result index
  let searchSeq = 0;        // guards against out-of-order responses

  /* ------------------------------------------------------------------ search */
  async function doGlobalSearch(q) {
    const seq = ++searchSeq;
    hideLanding();
    $("gres").classList.remove("hidden");
    setTabsEnabled(false); // results not ready yet — prevents empty-graph clicks
    activeFacets = { author: new Set(), writer: new Set(), period: new Set(), source: new Set() };
    cursor = -1;
    $("gres-summary").textContent = `Searching “${q}”…`;
    showSearching(q);
    history.replaceState({}, "", `?q=${encodeURIComponent(q)}`);

    const forceMode = window._forceSearchMode || "auto"; // auto | semantic | bm25 | keyword
    const topK = window._searchTopK || 60;
    const tStart = Date.now();
    // concepts and passages are independent backends — run them together so
    // the concept tab is ready the moment passages land
    const conceptsP = searchConcepts(q, forceMode);
    let passages = [];
    let mode = "lexical";
    let facets = null;
    let serverMs = null;
    if (forceMode === "semantic" || forceMode === "auto") {
      // Jasper semantic search. A cold model load can take several seconds;
      // retry once before falling back to lexical.
      let r = null, lastErr = null;
      for (let attempt = 0; attempt < 2 && !r; attempt++) {
        try {
          // same-origin proxy: works from ANY client machine (direct
          // 127.0.0.1:8790 only resolves on the server host itself)
          r = await fetch("/book/api/semantic_proxy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: q, top_k: topK, mode: forceMode === "semantic" ? "semantic" : "hybrid" }),
            signal: AbortSignal.timeout(60000),
          });
          if (!r.ok) { r = null; }
        } catch (e) { lastErr = e; r = null; }
      }
      if (r) {
        const d = await r.json();
        facets = d.facets || null;
        serverMs = d.took_ms;
        passages = (d.results || []).map(x => ({
          book_id: x.book_id, page: x.page, printed_page_number: x.printed_page,
          count: Math.round(x.score * 100), snippet: x.snippet,
          blocks: x.bbox_pts ? [{ text: x.text, bbox_pts: x.bbox_pts }] : [],
          score: x.score, semantic: x.semantic, lexical: x.lexical,
          source: x.source, author: x.author, year: x.year, title: x.title,
          volume: x.volume, cite: x.cite,
          pure: forceMode === "semantic",
        }));
        mode = "semantic";
      } else if (lastErr) {
        console.warn("semantic search unavailable:", lastErr.message || lastErr);
      }
    }
    if (!passages.length && forceMode === "bm25") {
      try {
        const res = await fetch("/book/api/bm25_proxy", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q, top_k: topK }),
        });
        const d = await res.json();
        facets = d.facets || null;
        serverMs = d.took_ms;
        passages = (d.results || []).map(x => ({
          book_id: x.book_id, page: x.page, printed_page_number: x.printed_page,
          count: Math.round(x.score), snippet: x.snippet,
          blocks: x.bbox_pts ? [{ text: "", bbox_pts: x.bbox_pts }] : [],
          score: x.score, bm25: true,
          source: x.source, author: x.author, year: x.year, title: x.title,
          volume: x.volume, cite: x.cite,
        }));
        mode = "bm25";
      } catch (e) { console.error(e); }
    }
    if (!passages.length) {
      try {
        const res = await fetch(`/book/api/gsearch?q=${encodeURIComponent(q)}&limit=${topK}`);
        const d = await res.json();
        passages = d.results || [];
        mode = "lexical";
      } catch (e) { console.error(e); }
    }
    if (seq !== searchSeq) return;  // a newer search already landed
    const concepts = await conceptsP;
    if (seq !== searchSeq) return;

    window._searchMode = mode;
    window._lastQuery = q;
    if (typeof window.reportSearchTiming === "function") {
      const wall = Date.now() - tStart;
      // a sub-200ms server leg means the query vector came from the cache
      window.reportSearchTiming(serverMs != null && serverMs < 200 ? serverMs : wall,
                                serverMs != null && serverMs < 200);
    }
    setTabsEnabled(true);
    // feed the floating dynamic graph (documents + matched concepts)
    if (typeof window.setDynamicData === "function") {
      window.setDynamicData({
        query: q, mode,
        passages: passages.map(p => ({ book_id: p.book_id, page: p.page, count: p.count, blocks: p.blocks })),
        concepts: concepts.slice(0, 8).map(c => ({ id: c.n.id, label: c.n.label })),
      });
    }
    currentResults = { q, passages, concepts, facets: facets || deriveFacets(passages) };
    const gi = document.getElementById("gres-input");
    if (gi && document.activeElement !== gi) gi.value = q;
    currentTab = "passages"; // reset tab on every new search
    sortMode = "relevance";
    if ($("gres-sort")) $("gres-sort").value = "relevance";
    document.querySelectorAll(".gres-tabs button").forEach(b => b.classList.remove("active"));
    document.getElementById("gres-tab-passages").classList.add("active");
    renderSummary();
    renderResults();
  }

  function showSearching(q) {
    const engine = window._engineInfo || {};
    const slow = engine.device === "cpu";
    $("gres-body").innerHTML = `
      <div class="searching-state">
        <div class="searching-spinner"></div>
        <div class="searching-text">Searching ${(engine.books || 197)} sources<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
        <div class="searching-sub">embedding “${esc(q)}” with Jasper · ranking ${(engine.index || 90975).toLocaleString()} passages${slow ? " · running on CPU, this takes a few seconds" : ""}</div>
        <div class="searching-elapsed" id="searching-elapsed">0.0s</div>
      </div>`;
    const t0 = Date.now();
    const el = $("searching-elapsed");
    clearInterval(window.__searchTimer);
    window.__searchTimer = setInterval(() => {
      if (!document.body.contains(el)) { clearInterval(window.__searchTimer); return; }
      el.textContent = ((Date.now() - t0) / 1000).toFixed(1) + "s";
    }, 100);
  }

  function renderSummary() {
    const { q, passages, concepts } = currentResults;
    const mode = window._searchMode;
    const forceMode = window._forceSearchMode || "auto";
    const shown = visiblePassages().length;
    const modeLabel = mode === "semantic"
      ? (forceMode === "semantic" ? "pure semantic" : "hybrid semantic")
      : mode === "bm25" ? "BM25" : "keyword";
    const filtered = shown !== passages.length ? `${shown} of ${passages.length}` : `${passages.length}`;
    $("gres-summary").innerHTML =
      `<b>${filtered}</b> passage${passages.length === 1 ? "" : "s"} · <span class="gs-mode">${modeLabel}</span> · ${concepts.length} concept${concepts.length === 1 ? "" : "s"}`;
  }

  /* --------------------------------------------------------------- concepts */
  async function searchConcepts(q, forceMode) {
    // Semantic concept search: the 202 concept vectors let a question with no
    // literal overlap ("what makes an action right?") still find Moral
    // Obligation / Moral Fitness. Falls back to local string matching when the
    // engine is down or the user forced a lexical mode.
    if (forceMode !== "bm25" && forceMode !== "keyword") {
      try {
        const r = await fetch("/book/api/concepts_proxy", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q, top_k: 16, mode: forceMode === "semantic" ? "semantic" : "hybrid" }),
          signal: AbortSignal.timeout(60000),
        });
        if (r.ok) {
          const d = await r.json();
          const byId = new Map((typeof S !== "undefined" && S.nodes ? S.nodes : []).map(n => [n.id, n]));
          const out = (d.results || [])
            .filter(c => c.score > 0.18)
            .map(c => {
              const n = byId.get(c.id) || {
                id: c.id, label: c.label, definition: c.definition,
                category: c.category, books: c.books, color: "#8A7B6B",
              };
              return {
                n, score: c.score, semantic: c.semantic, lexical: c.lexical, sem: true,
                relations: c.relations || [], nRelations: c.n_relations || 0,
                aliases: c.aliases || [], books: c.books, bookIds: c.book_ids || [],
                importance: c.importance,
              };
            });
          if (out.length) return out;
        }
      } catch (e) { console.warn("concept search unavailable:", e.message || e); }
    }
    return searchConceptsLocal(q);
  }

  // question words + filler stripped so "What is love?" matches the love concept
  const QSTOP = new Set(["what","is","are","was","were","who","whom","whose","where","when","why","how","does","do","did","can","could","should","would","will","shall","may","might","must","the","a","an","of","in","on","at","to","for","and","or","by","with","about","as","it","its","this","that","these","those","i","you","me","tell","explain","define","describe","meaning","mean","means","s","t","any","some","there","their","ours"]);
  function contentTerms(q) {
    return q.toLowerCase().replace(/[^a-z0-9\s-]/g, " ").split(/[\s\-]+/)
      .filter(t => t.length > 2 && !QSTOP.has(t));
  }

  function searchConceptsLocal(q) {
    if (typeof S === "undefined" || !S.data) return [];
    const qs = q.toLowerCase();
    const terms = qs.split(/\s+/).filter(Boolean);
    const content = contentTerms(q);
    const scored = [];
    for (const n of S.nodes) {
      let score = 0;
      const label = n.label.toLowerCase();
      const id = n.id.toLowerCase();
      const aliases = (n.aliases || []).map(a => a.toLowerCase());
      const hay = label + " " + id.replace(/_/g, " ") + " " + aliases.join(" ");
      if (label === qs || id === qs.replace(/\s+/g, "_")) score += 10;
      if (label.includes(qs)) score += 6;
      if (id.includes(qs.replace(/\s+/g, "_"))) score += 4;
      for (const a of aliases) if (a.includes(qs)) score += 3;
      // content-term matching (natural-language queries: "What is love?" -> love)
      if (content.length) {
        const allIn = content.every(t => hay.includes(t));
        if (allIn) score += 8;
        for (const t of content) {
          if (label === t || id === t) score += 12;         // exact concept hit
          else if (label.includes(t)) score += 3;
          else if (id.includes(t)) score += 2;
          else if (aliases.some(a => a.includes(t))) score += 2;
        }
        // single-term exact concept match dominates (e.g. "love" in "what is love?")
        if (content.length === 1 && (label === content[0] || id === content[0])) score += 10;
      }
      // all raw words present (legacy)
      if (terms.length > 1 && terms.every(t => label.includes(t) || aliases.some(a => a.includes(t)))) score += 4;
      if (score > 0) scored.push({ n, score });
    }
    scored.sort((a, b) => b.score - a.score || b.n.importance - a.n.importance);
    return scored.slice(0, 12);
  }

  function setTabsEnabled(on) {
    ["gres-tab-passages", "gres-tab-concepts", "gres-tab-graph"].forEach(id => {
      const b = document.getElementById(id);
      if (b) { b.disabled = !on; b.style.opacity = on ? 1 : 0.45; }
    });
  }

  function setResTab(tab) {
    if (!currentResults) return;
    currentTab = tab;
    cursor = -1;
    document.querySelectorAll(".gres-tabs button").forEach(b => b.classList.remove("active"));
    $("gres-tab-" + tab).classList.add("active");
    document.body.classList.toggle("tab-concepts", tab === "concepts");
    renderResults();
  }

  /* ----------------------------------------------------------------- facets */
  function deriveFacets(passages) {
    const authors = {}, periods = {}, works = {};
    for (const p of passages) {
      const c = Cite.of(p);
      const a = c.author || "unattributed";
      authors[a] = (authors[a] || 0) + 1;
      const w = c.title || p.book_id;
      works[w] = (works[w] || 0) + 1;
      if (c.year) { const d = `${Math.floor(+c.year / 10) * 10}s`; periods[d] = (periods[d] || 0) + 1; }
    }
    const top = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, n).map(([value, count]) => ({ value, count }));
    return {
      authors: top(authors, 24),
      works: top(works, 24),
      periods: Object.entries(periods).sort().map(([value, count]) => ({ value, count })),
    };
  }

  const WRITER_LABEL = { women: "women", men: "men", joint: "joint", unattributed: "unattributed" };

  function passageFacetKeys(p) {
    const c = Cite.of(p);
    return {
      author: c.author || "unattributed",
      // the author registry carries the sex of each creator, which turns
      // "who wrote this?" into a filter — the reason the registry exists
      writer: window.Authors ? WRITER_LABEL[Authors.sexOf(c.author)] : null,
      period: c.year ? `${Math.floor(+c.year / 10) * 10}s` : null,
      source: p.source === "txt" || p.page == null ? "text edition" : "scanned page",
    };
  }

  function visiblePassages() {
    if (!currentResults) return [];
    let list = currentResults.passages.filter(p => {
      const k = passageFacetKeys(p);
      if (activeFacets.author.size && !activeFacets.author.has(k.author)) return false;
      if (activeFacets.writer.size && !activeFacets.writer.has(k.writer)) return false;
      if (activeFacets.period.size && !activeFacets.period.has(k.period)) return false;
      if (activeFacets.source.size && !activeFacets.source.has(k.source)) return false;
      return true;
    });
    if (sortMode === "year") {
      list = list.slice().sort((a, b) => (+(Cite.of(a).year || 9999)) - (+(Cite.of(b).year || 9999)));
    } else if (sortMode === "author") {
      list = list.slice().sort((a, b) => (Cite.of(a).author || "~").localeCompare(Cite.of(b).author || "~"));
    }
    return list;
  }

  function renderFacets() {
    const host = $("gres-facets");
    if (!host || !currentResults) return;
    if (currentTab !== "passages" || currentResults.passages.length < 4) {
      host.innerHTML = "";
      host.classList.add("empty");
      return;
    }
    host.classList.remove("empty");
    const counts = { author: {}, writer: {}, period: {}, source: {} };
    for (const p of currentResults.passages) {
      const k = passageFacetKeys(p);
      for (const dim of ["author", "writer", "period", "source"]) {
        if (k[dim]) counts[dim][k[dim]] = (counts[dim][k[dim]] || 0) + 1;
      }
    }
    const anyActive = Object.values(activeFacets).some(s => s.size);
    const group = (dim, title, entries) => entries.length < 2 ? "" : `
      <div class="fg">
        <h4>${title}</h4>
        ${entries.map(([value, count]) => `
          <label class="fitem${activeFacets[dim].has(value) ? " on" : ""}" data-dim="${dim}" data-value="${esc(value)}">
            <span class="fname">${esc(value)}</span><span class="fcount">${count}</span>
          </label>`).join("")}
      </div>`;
    const sortEnt = (o) => Object.entries(o).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    host.innerHTML = `
      <div class="facets-head">
        <h3>Refine</h3>
        ${anyActive ? `<button id="facet-clear" class="mini">clear</button>` : ""}
      </div>
      ${group("writer", "Written by", sortEnt(counts.writer))}
      ${group("author", "Author", sortEnt(counts.author).slice(0, 18))}
      ${group("period", "Period", Object.entries(counts.period).sort())}
      ${group("source", "Source", sortEnt(counts.source))}`;
    host.querySelectorAll(".fitem").forEach(el => {
      el.onclick = () => {
        const { dim, value } = el.dataset;
        activeFacets[dim].has(value) ? activeFacets[dim].delete(value) : activeFacets[dim].add(value);
        cursor = -1;
        renderResults();
        renderSummary();
      };
    });
    const clr = $("facet-clear");
    if (clr) clr.onclick = () => {
      activeFacets = { author: new Set(), writer: new Set(), period: new Set(), source: new Set() };
      renderResults(); renderSummary();
    };
  }

  /* ---------------------------------------------------------------- results */
  function renderResults() {
    if (!currentResults) return;
    clearInterval(window.__searchTimer);
    const { q, concepts } = currentResults;
    const body = $("gres-body");
    renderFacets();
    if (currentTab === "passages") {
      const list = visiblePassages();
      setScoreScale(currentResults.passages);  // stable across facet changes
      body.innerHTML = list.length
        ? list.map((p, i) => passageCard(p, i, q)).join("")
        : `<p class="hint empty-note">No passage matches for “${esc(q)}”${
            Object.values(activeFacets).some(s => s.size) ? " with these filters" : ""
          }. Try the Concepts tab, a broader query, or an archaic spelling (e.g. <i>vertue</i>).</p>`;
      body.querySelectorAll(".gr-pass").forEach((el, i) => {
        el.onclick = () => openPassage(list[i], q);
      });
      // a passage, or the whole result set, can be handed to the chat panel
      body.querySelectorAll(".gp-ctx").forEach(b => {
        b.onclick = (e) => {
          e.stopPropagation();
          const p = list[+b.dataset.i];
          if (!p || !window.Chat) return;
          Chat.addContext([{
            kind: "passage", book_id: p.book_id, page: p.page,
            cite: p.cite || p.book_id, label: `${p.cite || p.book_id}${p.page != null ? ` p.${p.page}` : ""}`,
            text: p.blocks?.[0]?.text || p.snippet || "",
          }]);
        };
      });
    } else {
      const cHi = Math.max(0.01, ...concepts.map(c => +c.score || 0));
      body.innerHTML = concepts.length
        ? concepts.map((c, i) => conceptCard(c, i, cHi)).join("")
        : `<p class="hint empty-note">No concept matches for “${esc(q)}”.</p>`;
      const showInMap = (id) => {
        window._lastSearchConcept = id;
        if (typeof window.setGraphFloatMode === "function") window.setGraphFloatMode(false);
        if (typeof openGraphFloat === "function") openGraphFloat(id);
      };
      body.querySelectorAll(".gr-concept").forEach(el => {
        el.onclick = () => showInMap(el.dataset.id);
      });
      // a relation chip navigates to that concept's card instead of opening
      // the map, so following an argument stays inside the result list
      body.querySelectorAll(".gc-rel").forEach(el => {
        el.onclick = (e) => {
          e.stopPropagation();
          const target = el.dataset.goto;
          const card = body.querySelector(`.gr-concept[data-id="${CSS.escape(target)}"]`);
          if (card) {
            card.scrollIntoView({ block: "center", behavior: "smooth" });
            card.classList.add("flash");
            setTimeout(() => card.classList.remove("flash"), 1200);
          } else {
            showInMap(target);
          }
        };
      });
      body.querySelectorAll(".gc-act").forEach(el => {
        el.onclick = (e) => {
          e.stopPropagation();
          if (el.dataset.act === "graph") showInMap(el.dataset.id);
          else if (el.dataset.act === "ctx") {
            if (window.Chat) Chat.addContext([{ kind: "concept", concept_id: el.dataset.id, label: el.dataset.label }]);
          } else doGlobalSearch(el.dataset.label);
        };
      });
    }
  }

  function passageCard(p, i, q) {
    const c = Cite.of(p);
    const isTxt = p.source === "txt" || p.page == null;
    const printed = p.printed_page_number
      ? (typeof p.printed_page_number === "object" ? p.printed_page_number.value : p.printed_page_number)
      : null;
    const loc = isTxt
      ? `<span class="gp-loc gp-loc-txt" title="clean-text edition — no page scan">text edition</span>`
      : `<span class="gp-loc">p. ${p.page}${printed ? ` <span class="gp-printed">(printed ${printed})</span>` : ""}</span>`;
    return `
      <div class="gr-pass" data-i="${i}" tabindex="0">
        <div class="gp-head">
          <span class="gp-cite">
            ${c.author ? `<span class="gp-author">${esc(c.author)}</span>, ` : ""}<span class="gp-title">${esc(c.title)}</span>${c.volume ? `<span class="gp-vol">, ${esc(c.volume)}</span>` : ""}${c.year ? ` <span class="gp-year">${esc(c.year)}</span>` : ""}
          </span>
          <span class="gp-meta">${loc} ${scoreChip(p)}</span>
        </div>
        <div class="gp-snip">${highlightTerms(esc(p.snippet), q)}</div>
        <div class="gp-actions">
          <span class="gp-open">${isTxt ? "read the text" : "open the scan"} →</span>
          <button class="ctx-btn gp-ctx" data-i="${i}" title="Attach this passage to the chat context">+ context</button>
        </div>
      </div>`;
  }

  /* The score is the one thing a reader can't verify by eye, so it gets a bar
     as well as a number. The bar is scaled ACROSS THE RESULT SET, not against
     an absolute 0-1: every cosine in a good result set sits around 0.85, so an
     absolute bar was full for all 60 rows and said nothing. Relative to the
     best hit, the fall-off down the list becomes legible at a glance. */
  let scoreScale = { lo: 0, hi: 1 };
  function setScoreScale(list) {
    const vals = list.map(p => +p.score).filter(v => isFinite(v));
    if (!vals.length) { scoreScale = { lo: 0, hi: 1 }; return; }
    const hi = Math.max(...vals), lo = Math.min(...vals);
    // keep a visible floor so the weakest hit isn't an empty bar
    scoreScale = { lo: lo - (hi - lo) * 0.45 - 1e-6, hi };
  }
  function scoreChip(p) {
    const { lo, hi } = scoreScale;
    const pct = hi > lo ? Math.max(0.06, Math.min(1, (+p.score - lo) / (hi - lo))) : 1;
    let label, tip;
    if (p.pure) {
      label = `cos ${(+p.score).toFixed(3)}`;
      tip = "pure semantic: cosine similarity between the query and passage embeddings (bar is relative to the best hit)";
    } else if (p.semantic != null) {
      label = (+p.score).toFixed(2);
      tip = `hybrid 0.6·semantic + 0.4·lexical — semantic ${(+p.semantic).toFixed(2)}, lexical ${(+p.lexical).toFixed(2)} (bar is relative to the best hit)`;
    } else if (p.bm25) {
      label = `bm25 ${(+p.score).toFixed(1)}`;
      tip = "BM25 relevance (k1=1.5, b=0.75, archaic-spelling expanded)";
    } else {
      label = `×${p.count}`;
      tip = "keyword occurrences on this page";
    }
    const sub = p.semantic != null && !p.pure
      ? `<span class="gp-sub">sem ${(+p.semantic).toFixed(2)} · lex ${(+p.lexical).toFixed(2)}</span>` : "";
    return `<span class="gp-score" title="${esc(tip)}">
        <span class="gp-bar"><i style="width:${(pct * 100).toFixed(0)}%"></i></span>
        <span class="gp-num">${label}</span>${sub}</span>`;
  }

  /* Relation glyphs. A concept card that shows only a definition wastes the
     map: what makes it a map is how the concept sits among the others, so
     each card carries its edges, with the ones that are also hits for this
     query marked — those are the ones that explain the result set. */
  const REL_STYLE = {
    supports: ["→", "#3E6B52"], requires: ["⊢", "#2E7D74"], entails: ["⇒", "#2F5D3A"],
    underlies: ["⊥", "#7A7A3A"], develops_from: ["↤", "#4E6BA7"], influences: ["↝", "#6A9AC7"],
    exemplifies: ["∈", "#9C9484"], subsumes: ["⊃", "#7B68B5"], opposes: ["✕", "#A03A31"],
    contrasts_with: ["↔", "#C0663A"],
  };

  function conceptCard(c, i, hi) {
    const { n, score, semantic, sem, relations = [], nRelations = 0, aliases = [] } = c;
    const cat = (n.category || []).join(" › ");
    const books = c.books != null ? c.books : n.books;
    const chip = sem
      ? `<span class="gp-score" title="semantic match against the concept's embedding${semantic != null ? ` (cosine ${(+semantic).toFixed(2)})` : ""}">
           <span class="gp-bar"><i style="width:${(Math.max(0.06, score / (hi || 1)) * 100).toFixed(0)}%"></i></span>
           <span class="gp-num">${(+score).toFixed(2)}</span></span>`
      : "";
    // One chip per related concept. The map records several relations between
    // the same pair (Self-Love both contrasts_with and opposes Benevolence),
    // which printed "Benevolence" four times in a row; the chip shows the
    // strongest and names them all on hover.
    const byTarget = new Map();
    for (const r of relations) {
      const cur = byTarget.get(r.id);
      if (!cur) byTarget.set(r.id, { ...r, all: [r] });
      else {
        cur.all.push(r);
        if (r.strength > cur.strength) Object.assign(cur, r, { all: cur.all });
      }
    }
    const grouped = [...byTarget.values()];
    const shown = grouped.slice(0, 8);
    const rels = shown.length ? `
      <div class="gc-rels">
        ${shown.map(r => {
          const [glyph, col] = REL_STYLE[r.relation] || ["·", "#8B8375"];
          const kinds = [...new Set(r.all.map(x => x.relation.replace(/_/g, " ")))];
          return `<button class="gc-rel${r.in_results ? " hot" : ""}" data-goto="${esc(r.id)}"
             title="${esc(n.label)} — ${esc(kinds.join(", "))} — ${esc(r.label)} · strength ${r.strength}${r.in_results ? " · also a hit for this query" : ""}">
             <span class="gc-glyph" style="color:${col}">${glyph}</span>${esc(r.label)}${kinds.length > 1 ? `<span class="gc-multi">${kinds.length}</span>` : ""}</button>`;
        }).join("")}
        ${grouped.length > shown.length ? `<span class="gc-more">+${grouped.length - shown.length} more</span>` : ""}
      </div>` : "";
    const alias = aliases.length
      ? `<div class="gc-alias">also: ${aliases.slice(0, 6).map(esc).join(", ")}</div>` : "";
    return `
      <div class="gr-concept" data-id="${esc(n.id)}" data-i="${i}" tabindex="0">
        <span class="gc-dot" style="background:${n.color || "#8A7B6B"}"></span>
        <div class="gc-main">
          <h4>${esc(n.label)}</h4>
          <div class="gc-cat">${esc(cat)}${books ? ` · ${books} book${books === 1 ? "" : "s"}` : ""}${grouped.length ? ` · ${grouped.length} related concept${grouped.length === 1 ? "" : "s"}` : ""}</div>
          <div class="gc-def">${esc((n.definition || "").slice(0, 300))}${(n.definition || "").length > 300 ? "…" : ""}</div>
          ${alias}
          ${rels}
          <div class="gc-actions">
            <button class="gc-act" data-act="graph" data-id="${esc(n.id)}">◎ show in the map</button>
            <button class="gc-act" data-act="passages" data-id="${esc(n.id)}" data-label="${esc(n.label)}">▤ passages for this concept</button>
            <button class="gc-act" data-act="ctx" data-id="${esc(n.id)}" data-label="${esc(n.label)}">💬 add to chat context</button>
          </div>
        </div>
        ${chip}
      </div>`;
  }

  function openPassage(p, q) {
    if (!p || typeof openReader !== "function") return;
    // word-level highlighting: pass the content terms only
    if (typeof Reader !== "undefined") {
      Reader.activeTerms = q.toLowerCase().split(/[\s\-]+/).filter(t => t.length > 2 && !STOP.has(t));
    }
    // TXT-only books (no PDF scan) open directly in text mode.
    // The Jasper index includes txt-source paragraphs whose page is null.
    const txtOnly = p.page == null || p.has_pdf === false || p.source === "txt";
    if (txtOnly) {
      if (typeof Reader !== "undefined") {
        Reader.highlights = [];   // no page geometry in a text edition
        Reader.bookId = p.book_id;
        Reader.open = true;
        Reader.txtMode = false;
        Reader.pendingHighlight = { text: p.snippet || "", page: p.page };
        if (typeof showReaderShell === "function") showReaderShell();
        if (typeof openTxtMode === "function") openTxtMode(p.book_id);
      }
      return;
    }
    // Highlights describe THIS passage. They used to be pushed onto a list
    // that was never cleared, so boxes (and their tooltips) from every
    // previously opened result reappeared on unrelated pages.
    openReader(p.book_id, {
      page: p.page,
      highlight: p.blocks?.[0]?.bbox_pts ? { page: p.page, bbox_pts: p.blocks[0].bbox_pts, concept_id: q } : null,
      highlights: (p.blocks || [])
        .filter(b => b.bbox_pts)
        .map(b => ({ book_id: p.book_id, page: p.page, bbox_pts: b.bbox_pts, concept_id: q, text: b.text })),
    });
  }

  /* -------------------------------------------------------- keyboard nav */
  function onResultsKey(e) {
    if ($("gres").classList.contains("hidden")) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    const cards = [...$("gres-body").querySelectorAll(".gr-pass, .gr-concept")];
    if (!cards.length) return;
    const move = (d) => {
      cursor = Math.max(0, Math.min(cards.length - 1, cursor + d));
      cards.forEach(c => c.classList.remove("cursor"));
      const el = cards[cursor];
      el.classList.add("cursor");
      el.scrollIntoView({ block: "nearest", behavior: "smooth" });
      e.preventDefault();
    };
    if (e.key === "j" || e.key === "ArrowDown") move(cursor < 0 ? 0 : 1);
    else if (e.key === "k" || e.key === "ArrowUp") move(-1);
    else if (e.key === "Enter" && cursor >= 0) { cards[cursor].click(); e.preventDefault(); }
    else if (e.key === "/") { $("gres-input").focus(); $("gres-input").select(); e.preventDefault(); }
    else if (e.key === "Tab" && e.shiftKey === false && e.altKey) {
      setResTab(currentTab === "passages" ? "concepts" : "passages"); e.preventDefault();
    }
  }

  function highlightTerms(text, q) {
    const terms = q.toLowerCase().split(/[\s\-]+/)
      .map(t => t.replace(/[^a-z0-9']/g, ""))
      .filter(t => t.length > 2 && !STOP.has(t));
    if (!terms.length) return text;
    // one pass over an alternation, so overlapping terms can't nest <mark>s
    const re = new RegExp(`(${terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
    return text.replace(re, "<mark>$1</mark>");
  }

  /* engine info drives the "running on CPU, this takes a few seconds" hint */
  fetch("/book/api/engine").then(r => r.json()).then(d => { window._engineInfo = d; }).catch(() => {});

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

/* expose for header input hook */
function doGlobalSearchExternal(q) {
  const evt = new CustomEvent("atlas:search", { detail: q });
  document.dispatchEvent(evt);
}
document.addEventListener("atlas:search", (e) => {
  const input = document.getElementById("landing-input");
  if (input) input.value = e.detail;
  // doGlobalSearch hides the landing page itself; hiding it here first would
  // leave a blank screen if the call never happened
  if (window.__doGlobalSearch) window.__doGlobalSearch(e.detail);
});
