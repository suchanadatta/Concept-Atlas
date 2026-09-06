/* Compare view + help — wired to app.js state.

   This used to auto-pick two or three concepts by importance, print their
   definitions, and stop; the header told you to ctrl-click nodes but nothing
   listened. It now lets you assemble the comparison yourself and answers it
   from the corpus rather than only from the map:

     * the curated map — definition, category, aliases, each concept's own
       relations, and the relations the map records BETWEEN the picked ones;
     * the embedding space — a pairwise similarity matrix, which is the
       corpus's own answer rather than an editor's;
     * the passages each idea owns, and the shared ground where both are
       argued together.

   Items are concepts OR free text, so ideas the map never recorded can be
   compared too. */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let picks = [];          // [{id, label, kind}]
  let data = null;
  let busy = false;

  function init() {
    $("btn-compare").onclick = openCompare;
    $("compare-close").onclick = closeCompare;
    $("btn-help").onclick = () => $("help").classList.remove("hidden");
    $("help-close").onclick = () => $("help").classList.add("hidden");
    // theme lives in theme.js — one store, applied before first paint
    $("btn-theme").onclick = () => Theme.toggle();
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("compare").classList.contains("hidden")) { closeCompare(); e.stopPropagation(); }
    }, true);
  }

  /* ---------------------------------------------------------------- picking */
  function seed() {
    // a sensible starting pair so the view is never empty on first open
    if (picks.length) return;
    const out = [];
    if (typeof S !== "undefined" && S.selected) out.push(S.selected);
    if (typeof S !== "undefined" && S.query) {
      for (const q of S.query.top.slice(0, 2)) if (!out.includes(q.node)) out.push(q.node);
    }
    if (out.length < 2 && typeof S !== "undefined" && S.nodes) {
      for (const n of [...S.nodes].sort((a, b) => (b.degree || 0) - (a.degree || 0))) {
        if (out.length >= 2) break;
        if (!out.includes(n)) out.push(n);
      }
    }
    picks = out.slice(0, 2).map(n => ({ id: n.id, label: n.label, kind: "concept" }));
  }

  window.compareAdd = function (idOrText, label) {
    const id = String(idOrText || "").trim();
    if (!id || picks.length >= 4 || picks.some(p => p.id === id)) return false;
    const node = (typeof S !== "undefined" && S.byId) ? S.byId.get(id) : null;
    picks.push({ id, label: label || (node ? node.label : id), kind: node ? "concept" : "text" });
    if (!$("compare").classList.contains("hidden")) run();
    return true;
  };

  function removePick(id) {
    picks = picks.filter(p => p.id !== id);
    run();
  }

  /* --------------------------------------------------------------- rendering */
  function chips() {
    return `
      <div class="cmp-picks">
        ${picks.map(p => `
          <span class="cmp-chip${p.kind === "text" ? " cmp-chip-text" : ""}" title="${p.kind === "concept" ? "from the concept map" : "free text — compared by embedding only"}">
            ${esc(p.label)}<button class="cmp-x" data-rm="${esc(p.id)}" aria-label="Remove">×</button>
          </span>`).join("")}
        ${picks.length < 4 ? `
          <span class="cmp-add">
            <input id="cmp-input" placeholder="add a concept or any idea…" autocomplete="off" aria-label="Add to the comparison">
            <div id="cmp-sugg" class="cmp-sugg hidden"></div>
          </span>` : `<span class="cmp-full">four is the maximum</span>`}
      </div>`;
  }

  function matrix() {
    if (!data || !data.similarity || picks.length < 2) return "";
    const n = data.items.length;
    const cell = (v) => {
      const t = Math.max(0, Math.min(1, (v - 0.25) / 0.7));
      return `background:rgba(138,59,50,${(0.08 + t * 0.62).toFixed(3)});color:${t > 0.55 ? "#F6F1E5" : "inherit"}`;
    };
    return `
      <section class="cmp-sec">
        <h3>How close are they?</h3>
        <p class="cmp-lede">Cosine similarity between the embeddings — the corpus's own answer, independent of
          what the concept map records. 1.00 is identical; below about 0.45 the two are barely talking
          about the same thing.</p>
        <table class="cmp-matrix">
          <tr><th></th>${data.items.map(i => `<th>${esc(i.label)}</th>`).join("")}</tr>
          ${data.items.map((ri, a) => `<tr><th>${esc(ri.label)}</th>${
            data.items.map((_, b) => `<td style="${cell(data.similarity[a][b])}">${data.similarity[a][b].toFixed(2)}</td>`).join("")
          }</tr>`).join("")}
        </table>
      </section>`;
  }

  const REL_GLYPH = {
    supports: "→", requires: "⊢", entails: "⇒", underlies: "⊥", develops_from: "↤",
    influences: "↝", exemplifies: "∈", subsumes: "⊃", opposes: "✕", contrasts_with: "↔",
  };

  function between() {
    if (!data || !data.between || !data.between.length) return "";
    const lbl = (id) => (data.items.find(i => i.id === id) || {}).label || id;
    return `
      <section class="cmp-sec">
        <h3>What the map says about the pair</h3>
        <ul class="cmp-between">
          ${data.between.map(r => `<li>
            <b>${esc(lbl(r.s))}</b>
            <span class="cmp-rel">${REL_GLYPH[r.relation] || "·"} ${esc(r.relation.replace(/_/g, " "))}</span>
            <b>${esc(lbl(r.t))}</b>
            <span class="cmp-w">${r.strength}</span></li>`).join("")}
        </ul>
      </section>`;
  }

  function passageRow(p, extra = "") {
    const isTxt = p.page == null || p.source === "txt";
    return `<div class="cmp-p" data-book="${esc(p.book_id)}" data-page="${p.page == null ? "" : p.page}"
        data-bbox='${JSON.stringify(p.bbox_pts || null)}' data-snip="${esc((p.snippet || "").slice(0, 200))}">
      <div class="cmp-p-head">
        <span class="cmp-p-cite">${esc(p.cite)}</span>
        <span class="cmp-p-meta">${isTxt ? "text edition" : `p. ${p.page}`} ${extra ||
          `<span class="cmp-p-score">${(p.score ?? 0).toFixed(2)}</span>`}</span>
      </div>
      <div class="cmp-p-snip">${esc(p.snippet || "")}</div>
    </div>`;
  }

  function columns() {
    if (!data) return "";
    return `
      <section class="cmp-sec">
        <h3>Each on its own</h3>
        <div class="cmp-grid" style="grid-template-columns:repeat(${data.items.length},minmax(0,1fr))">
          ${data.items.map(it => `
            <div class="cmp-col">
              <h4>${esc(it.label)}${it.kind === "text" ? ' <span class="cmp-kind">free text</span>' : ""}</h4>
              <div class="cmp-cat">${esc((it.category || []).join(" › "))}${
                it.books ? ` · ${it.books} book${it.books === 1 ? "" : "s"}` : ""}</div>
              ${it.definition ? `<div class="cmp-def">${esc(it.definition)}</div>`
                : `<div class="cmp-def cmp-none">Not in the concept map — compared by embedding alone.</div>`}
              ${it.aliases && it.aliases.length ? `<div class="cmp-alias">also: ${it.aliases.slice(0, 5).map(esc).join(", ")}</div>` : ""}
              ${it.relations && it.relations.length ? `
                <div class="cmp-rels">${it.relations.slice(0, 6).map(r =>
                  `<span class="cmp-relchip" title="${esc(it.label)} ${esc(r.relation.replace(/_/g, " "))} ${esc(r.label)} (${r.strength})">
                    <i>${REL_GLYPH[r.relation] || "·"}</i>${esc(r.label)}</span>`).join("")}</div>` : ""}
              <div class="cmp-ph">Strongest passages</div>
              ${(it.passages || []).map(p => passageRow(p)).join("") || `<p class="cmp-none">none</p>`}
            </div>`).join("")}
        </div>
      </section>`;
  }

  function shared() {
    if (!data || !data.shared || !data.shared.length) return "";
    return `
      <section class="cmp-sec">
        <h3>Shared ground</h3>
        <p class="cmp-lede">Passages that score well for <i>every</i> item — ranked by the weakest of the
          scores, not the average, so a passage that is excellent for one and irrelevant to another
          cannot get in. This is where the ideas are argued together.</p>
        ${data.shared.map(p => passageRow(p,
          `<span class="cmp-p-score" title="${data.items.map((it, k) => `${it.label} ${p.scores[k]}`).join(" · ")}">min ${p.min_score.toFixed(2)}</span>`
        )).join("")}
      </section>`;
  }

  async function run() {
    const grid = $("compare-grid");
    if (picks.length < 2) {
      grid.innerHTML = chips() + `<p class="cmp-none cmp-empty">Add at least two things to compare.</p>`;
      wire();
      return;
    }
    busy = true;
    grid.innerHTML = chips() + `
      <div class="searching-state"><div class="searching-spinner"></div>
        <div class="searching-text">Comparing across 90,975 passages…</div></div>`;
    wire();
    try {
      const r = await fetch("/book/api/compare_proxy", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: picks.map(p => p.id), top_k: 5, n_shared: 5 }),
        signal: AbortSignal.timeout(120000),
      });
      data = await r.json();
    } catch (e) {
      grid.innerHTML = chips() + `<p class="cmp-none cmp-empty">Comparison backend unavailable.</p>`;
      wire(); busy = false; return;
    }
    busy = false;
    if (data.error) {
      grid.innerHTML = chips() + `<p class="cmp-none cmp-empty">${esc(data.error)}</p>`;
      wire(); return;
    }
    grid.innerHTML = chips() + matrix() + between() + shared() + columns();
    wire();
  }

  function wire() {
    const grid = $("compare-grid");
    grid.querySelectorAll(".cmp-x").forEach(b => { b.onclick = () => removePick(b.dataset.rm); });
    grid.querySelectorAll(".cmp-p").forEach(el => {
      el.onclick = () => {
        const page = el.dataset.page === "" ? null : parseInt(el.dataset.page, 10);
        let bbox = null;
        try { bbox = JSON.parse(el.dataset.bbox); } catch { /* no geometry */ }
        closeCompare();
        openPassageFromCompare(el.dataset.book, page, bbox, el.dataset.snip);
      };
    });
    const inp = $("cmp-input");
    if (inp) {
      inp.oninput = () => suggest(inp.value);
      inp.onkeydown = (e) => {
        if (e.key === "Enter") {
          const first = grid.querySelector(".cmp-sugg .cmp-s");
          if (first) first.click();
          else if (inp.value.trim().length > 2) { window.compareAdd(inp.value.trim()); }
        } else if (e.key === "Escape") { $("cmp-sugg").classList.add("hidden"); }
      };
      inp.focus();
    }
  }

  function suggest(q) {
    const box = $("cmp-sugg");
    if (!box) return;
    q = q.trim().toLowerCase();
    if (!q) { box.classList.add("hidden"); return; }
    const nodes = (typeof S !== "undefined" && S.nodes) ? S.nodes : [];
    const hits = nodes.filter(n =>
      n.label.toLowerCase().includes(q) || (n.aliases || []).some(a => a.toLowerCase().includes(q)))
      .slice(0, 6);
    box.innerHTML = hits.map(n =>
      `<div class="cmp-s" data-id="${esc(n.id)}" data-label="${esc(n.label)}">
        <span class="dot" style="background:${n.color}"></span>${esc(n.label)}</div>`).join("")
      + `<div class="cmp-s cmp-s-free" data-id="${esc(q)}" data-label="${esc(q)}">
          use “${esc(q)}” as free text</div>`;
    box.classList.remove("hidden");
    box.querySelectorAll(".cmp-s").forEach(el => {
      el.onclick = () => { window.compareAdd(el.dataset.id, el.dataset.label); box.classList.add("hidden"); };
    });
  }

  /* a compared passage opens in the reader, same jump a search result makes */
  function openPassageFromCompare(book, page, bbox, snippet) {
    if (typeof Reader === "undefined") return;
    Reader.activeTerms = picks.map(p => p.label.toLowerCase()).join(" ")
      .split(/[\s\-]+/).filter(t => t.length > 3);
    if (page == null) {
      Reader.highlights = [];
      Reader.bookId = book; Reader.open = true; Reader.txtMode = false;
      Reader.pendingHighlight = { text: snippet || "", page: null };
      if (typeof showReaderShell === "function") showReaderShell();
      if (typeof openTxtMode === "function") openTxtMode(book);
      return;
    }
    if (typeof openReader !== "function") return;
    openReader(book, {
      page,
      highlight: bbox ? { page, bbox_pts: bbox, concept_id: picks.map(p => p.label).join(" / ") } : null,
      highlights: bbox ? [{ book_id: book, page, bbox_pts: bbox, concept_id: picks.map(p => p.label).join(" / "), text: snippet }] : [],
    });
  }

  function openCompare() {
    $("compare").classList.remove("hidden");
    seed();
    run();
  }
  function closeCompare() { $("compare").classList.add("hidden"); }
  window.openCompare = openCompare;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
