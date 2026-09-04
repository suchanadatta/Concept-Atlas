/* Search-engine interface: landing → results (passages/concepts/graph) */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);

  function init() {
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
    $("gres-back").onclick = () => { $("gres").classList.add("hidden"); showLanding(); history.replaceState({}, "", "/"); };
    const rerunFromBar = () => {
      const q = $("gres-input").value.trim();
      if (q.length >= 2) doGlobalSearch(q);
    };
    $("gres-go").onclick = rerunFromBar;
    $("gres-input").addEventListener("keydown", (e) => { if (e.key === "Enter") rerunFromBar(); });
    window._forceSearchMode = window._forceSearchMode || "auto"; // auto|keyword|bm25
    const algoSel = $("gres-algo");
    if (algoSel) {
      algoSel.value = window._forceSearchMode === "auto" ? "hybrid" : window._forceSearchMode;
      algoSel.onchange = () => {
        window._forceSearchMode = algoSel.value === "hybrid" ? "auto" : algoSel.value;
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

  async function doGlobalSearch(q) {
    window.__doGlobalSearch = doGlobalSearch;
    hideLanding();
    $("gres").classList.remove("hidden");
    setTabsEnabled(false); // results not ready yet — prevents empty-graph clicks
    $("gres-summary").textContent = `Searching “${q}”…`;
    $("gres-body").innerHTML = `
      <div class="searching-state">
        <div class="searching-spinner"></div>
        <div class="searching-text">Searching 129 books<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
        <div class="searching-sub">embedding your query with Jasper · ranking 132,444 passages</div>
      </div>`;
    history.replaceState({}, "", `?q=${encodeURIComponent(q)}`);

    // fire both: passage search (mode-gated) + concepts
    const concepts = searchConceptsLocal(q);
    let passages = [];
    const forceMode = window._forceSearchMode || "auto"; // auto | semantic | keyword
    let mode = "lexical";
    if (forceMode === "semantic" || forceMode === "auto") {
      // 1) Jasper semantic search (if the embedding server is up).
      //    Cold start can take ~4s; retry once before falling back to lexical.
      let r = null, lastErr = null;
      for (let attempt = 0; attempt < 2 && !r; attempt++) {
        try {
          // same-origin proxy: works from ANY client machine (direct
          // 127.0.0.1:8790 only resolves on the server host itself)
          r = await fetch("/book/api/semantic_proxy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: q, top_k: 40, mode: forceMode === "semantic" ? "semantic" : "hybrid" }),
            signal: AbortSignal.timeout(14000),
          });
          if (!r.ok) { r = null; }
        } catch (e) { lastErr = e; r = null; }
      }
      if (r) {
        const d = await r.json();
        passages = (d.results || []).map(x => ({
          book_id: x.book_id, page: x.page, printed_page_number: x.printed_page,
          count: Math.round(x.score * 100), snippet: x.snippet,
          blocks: x.bbox_pts ? [{ text: x.text, bbox_pts: x.bbox_pts }] : [],
          score: x.score, semantic: x.semantic, lexical: x.lexical,
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
          body: JSON.stringify({ query: q, top_k: 40 }),
        });
        const d = await res.json();
        passages = (d.results || []).map(x => ({
          book_id: x.book_id, page: x.page, printed_page_number: x.printed_page,
          count: Math.round(x.score), snippet: x.snippet,
          blocks: x.bbox_pts ? [{ text: "", bbox_pts: x.bbox_pts }] : [],
          score: x.score, bm25: true,
        }));
        mode = "bm25";
      } catch (e) { console.error(e); }
    }
    if (!passages.length) {
      try {
        const res = await fetch(`/book/api/gsearch?q=${encodeURIComponent(q)}&limit=40`);
        const d = await res.json();
        passages = d.results || [];
        mode = "lexical";
      } catch (e) { console.error(e); }
    }
    window._searchMode = mode;
    window._lastQuery = q;
    setTabsEnabled(true);
    // feed the floating dynamic graph (documents + matched concepts)
    if (typeof window.setDynamicData === "function") {
      window.setDynamicData({
        query: q, mode,
        passages: passages.map(p => ({ book_id: p.book_id, page: p.page, count: p.count, blocks: p.blocks })),
        concepts: concepts.slice(0, 8).map(c => ({ id: c.n.id, label: c.n.label })),
      });
    }
    currentResults = { q, passages, concepts };
    const gi = document.getElementById("gres-input");
    if (gi && document.activeElement !== gi) gi.value = q;
    currentTab = "passages"; // reset tab on every new search
    document.querySelectorAll(".gres-tabs button").forEach(b => b.classList.remove("active"));
    document.getElementById("gres-tab-passages").classList.add("active");
    $("gres-summary").textContent =
      `${passages.length} passage${passages.length === 1 ? "" : "s"}${mode === "semantic" ? (forceMode === "semantic" ? " · pure semantic" : " · semantic") : mode === "bm25" ? " · BM25" : ""} · ${concepts.length} concept${concepts.length === 1 ? "" : "s"} — “${q}”`;
    renderResults();
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
    document.querySelectorAll(".gres-tabs button").forEach(b => b.classList.remove("active"));
    $("gres-tab-" + (tab === "passages" ? "passages" : "concepts")).classList.add("active");
    renderResults();
  }

  function renderResults() {
    if (!currentResults) return;
    const { q, passages, concepts } = currentResults;
    const body = $("gres-body");
    const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    if (currentTab === "passages") {
      body.innerHTML = passages.length
        ? passages.map(p => `
          <div class="gr-pass" data-book="${esc(p.book_id)}" data-page="${p.page}">
            <div class="gp-head">
              <span class="gp-book">${esc(p.book_id.replace(/_/g, " "))}</span>
              <span>page ${p.page}${p.printed_page_number ? ` (printed ${typeof p.printed_page_number === "object" ? p.printed_page_number.value : p.printed_page_number})` : ""} · ${p.pure
                ? `<span class="gp-score" title="pure semantic: cosine similarity to the query embedding">cos ${(+p.score).toFixed(3)}</span>`
                : p.semantic != null
                ? `<span class="gp-score" title="hybrid: 0.6·semantic + 0.4·lexical">score ${(+p.score).toFixed(2)} <span class="gp-sub">(sem ${(+p.semantic).toFixed(2)} · lex ${(+p.lexical).toFixed(2)})</span></span>`
                : p.bm25
                ? `<span class="gp-score" title="BM25 relevance (k1=1.5, b=0.75, archaic-expanded)">bm25 ${(+p.score).toFixed(1)}</span>`
                : `<span class="gp-count">keyword ×${p.count}</span>`}</span>
            </div>
            <div class="gp-snip">${highlightTerms(esc(p.snippet), q)}</div>
          </div>`).join("")
        : `<p class="hint" style="padding:40px;text-align:center">No passage matches for “${esc(q)}”. Try the Concepts tab, or an archaic spelling (e.g. <i>vertue</i>).</p>`;
      body.querySelectorAll(".gr-pass").forEach(el => {
        el.onclick = () => {
          // open reader at this page, highlighting matching blocks
          const p = passages.find(x => x.book_id === el.dataset.book && String(x.page) === el.dataset.page);
          if (p && typeof openReader === "function") {
            // word-level highlighting: pass the query terms
            if (typeof Reader !== "undefined") {
              // split on whitespace AND hyphens so "self-love" highlights self + love words
              Reader.activeTerms = q.toLowerCase().split(/[\s\-]+/).filter(t => t.length > 2);
            }
            // TXT-only books (no PDF scan) open directly in text mode.
            // The Jasper index includes txt-source paragraphs whose page is null.
            const txtOnly = p.page == null || p.has_pdf === false;
            if (txtOnly) {
              if (typeof Reader !== "undefined") {
                Reader.bookId = p.book_id;
                Reader.open = true;
                Reader.txtMode = false;
                Reader.pendingHighlight = { text: p.snippet || "", page: p.page };
                if (typeof showReaderShell === "function") showReaderShell();
                if (typeof openTxtMode === "function") openTxtMode(p.book_id);
              }
            } else {
              openReader(p.book_id, {
                page: p.page,
                highlight: p.blocks?.[0]?.bbox_pts ? { page: p.page, bbox_pts: p.blocks[0].bbox_pts, concept_id: q } : null,
              });
              // add ALL matching blocks as persistent highlights
              if (p.blocks) {
                for (const b of p.blocks) {
                  if (b.bbox_pts) Reader.highlights.push({ book_id: p.book_id, page: p.page, bbox_pts: b.bbox_pts, concept_id: q, text: b.text });
                }
              }
            }
          }
        };
      });
    } else {
      body.innerHTML = concepts.length
        ? concepts.map(({ n, score }) => `
          <div class="gr-concept" data-id="${esc(n.id)}">
            <span class="gc-dot" style="background:${n.color}"></span>
            <div>
              <h4>${esc(n.label)} <span class="gc-cat">· ${(n.category || []).join(" › ")} · ${n.books} books</span></h4>
              <div class="gc-def">${esc((n.definition || "").slice(0, 220))}…</div>
            </div>
          </div>`).join("")
        : `<p class="hint" style="padding:40px;text-align:center">No concept matches for “${esc(q)}”.</p>`;
      body.querySelectorAll(".gr-concept").forEach(el => {
        el.onclick = () => {
          window._lastSearchConcept = el.dataset.id;
          // stay on results; open the floating graph focused on this concept (static map)
          if (typeof window.setGraphFloatMode === "function") window.setGraphFloatMode(false);
          if (typeof openGraphFloat === "function") openGraphFloat(el.dataset.id);
        };
      });
    }
  }

  function highlightTerms(text, q) {
    const terms = q.toLowerCase().split(/\s+/).filter(t => t.length > 2);
    let out = text;
    for (const t of terms) {
      const re = new RegExp(`(${t.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&")})`, "gi");
      out = out.replace(re, "<mark>$1</mark>");
    }
    return out;
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

/* expose for header input hook */
function doGlobalSearchExternal(q) {
  const evt = new CustomEvent("atlas:search", { detail: q });
  document.dispatchEvent(evt);
}
document.addEventListener("atlas:search", (e) => {
  document.getElementById("landing").classList.add("hidden");
  // reuse internal via programmatic call
  const input = document.getElementById("landing-input");
  input.value = e.detail;
  // call the IIFE-internal fn via a re-bound reference
  window.__doGlobalSearch ? window.__doGlobalSearch(e.detail) : null;
});
