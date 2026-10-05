/* Landing boards: central concepts, curated research questions, corpus facts.

   The landing page was a title and a search box on an empty field — nothing
   told a first-time visitor what is in the corpus or what a good question
   looks like. These three boards are entry points: every item runs a real
   search or opens the graph. */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function run(q) {
    const input = $("landing-input");
    if (input) input.value = q;
    document.dispatchEvent(new CustomEvent("atlas:search", { detail: q }));
  }

  /* ---- central concepts: highest degree, then importance ---- */
  function fillConcepts() {
    if (typeof S === "undefined" || !S.nodes || !S.nodes.length) return false;
    const top = S.nodes.slice()
      .sort((a, b) => (b.degree || 0) - (a.degree || 0) || (b.importance || 0) - (a.importance || 0))
      .slice(0, 14);
    $("lb-concepts").innerHTML = top.map(n => `
      <button class="lb-chip" data-q="${esc(n.label)}" title="${esc((n.definition || "").slice(0, 160))}">
        <span class="lb-dot" style="background:${n.color}"></span>${esc(n.label)}
        <span class="lb-n">${n.books || 0}</span>
      </button>`).join("");
    $("lb-concepts").querySelectorAll(".lb-chip").forEach(b => { b.onclick = () => run(b.dataset.q); });
    return true;
  }

  /* ---- curated research questions ---- */
  function fillQueries() {
    if (typeof S === "undefined" || !S.data || !S.data.queries) return false;
    // the longest ones read as real research questions rather than name lookups
    const qs = S.data.queries.slice()
      .filter(q => (q.text || "").split(/\s+/).length >= 4)
      .sort((a, b) => (b.concepts?.length || 0) - (a.concepts?.length || 0))
      .slice(0, 6);
    $("lb-queries").innerHTML = qs.map(q => `
      <button class="lb-row" data-q="${esc(q.text)}">${esc(q.text)}</button>`).join("");
    $("lb-queries").querySelectorAll(".lb-row").forEach(b => { b.onclick = () => run(b.dataset.q); });
    return true;
  }

  /* ---- corpus facts + most-represented authors ---- */
  async function fillCorpus() {
    let eng = window._engineInfo;
    if (!eng || eng.status !== "ok") {
      try { eng = await (await fetch("/book/api/engine")).json(); } catch { eng = null; }
    }
    const stats = eng && eng.status === "ok"
      // the index holds 129 scanned volumes plus 68 clean-text editions, so
      // "books" here means sources, not the 129 in the PDF library
      ? [["sources indexed", eng.books], ["passages", (eng.index || 0).toLocaleString()],
         ["concepts", eng.concepts], ["relations", (typeof S !== "undefined" && S.edges ? S.edges.length : "—")]]
      : [["sources indexed", 197], ["concepts", 202]];
    $("lb-stats").innerHTML = stats
      .map(([k, v]) => `<span class="lb-stat"><b>${v}</b>${esc(k)}</span>`).join("");

    try {
      const lib = await (await fetch("/book/api/library")).json();
      const byAuthor = {};
      for (const b of lib.books || []) {
        const a = Cite.parse(b.book_id).author || b.author || "";
        if (a && a !== "Anonymous") byAuthor[a] = (byAuthor[a] || 0) + 1;
      }
      const top = Object.entries(byAuthor).sort((a, b) => b[1] - a[1]).slice(0, 12);
      $("lb-authors").innerHTML = top.map(([a, n]) => `
        <button class="lb-chip lb-chip-plain" data-q="${esc(a)}">${esc(a)}<span class="lb-n">${n}</span></button>`).join("");
      $("lb-authors").querySelectorAll(".lb-chip").forEach(b => { b.onclick = () => run(b.dataset.q); });
    } catch { /* library unavailable — the stats row still stands */ }
  }

  /* the header tagline counts sources, which only the engine knows */
  async function fillHeaderStats() {
    let eng = window._engineInfo;
    if (!eng || eng.status !== "ok") {
      try { eng = await (await fetch("/book/api/engine")).json(); } catch { return; }
    }
    const el = document.getElementById("stat-books");
    if (el && eng.books) el.textContent = eng.books;
  }

  function init() {
    fillHeaderStats();
    fillCorpus();
    // the graph data loads asynchronously; poll briefly rather than reaching
    // into app.js's load sequence
    let tries = 0;
    const t = setInterval(() => {
      const done = fillConcepts() && fillQueries();
      if (done || ++tries > 60) clearInterval(t);
    }, 250);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
