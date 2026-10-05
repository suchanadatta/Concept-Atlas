/* Author registry: roster, corpus composition, and the concept skew.

   Built by tools/build_author_stats.py from data/authors.csv joined to the
   v2 index and the concept map's inverted index. Two jobs here:
     1. lookup(surname) -> the author record, so the search facets can group
        results by who wrote them;
     2. the Authors panel, which is where the registry earns its keep — the
        corpus was deliberately assembled to put women moral philosophers
        beside the canonical men, and that is only visible once you can count
        it. */
"use strict";

const Authors = (function () {
  let data = null;
  let byKey = new Map();
  let bySurname = new Map();
  let byBook = new Map();   // book_id -> group, the exact join
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const GROUP = {
    women: { label: "women", color: "#B45E52" },
    men: { label: "men", color: "#4E79A7" },
    joint: { label: "joint", color: "#7B68B5" },
    unattributed: { label: "unattributed", color: "#948B7B" },
  };

  function groupOf(sex) {
    const s = String(sex || "U").toUpperCase();
    if (s.startsWith("F")) return "women";
    if (s.includes("&")) return "joint";
    if (s.startsWith("M")) return "men";
    return "unattributed";
  }

  async function load() {
    if (data) return data;
    try {
      data = await (await fetch("/book/api/authors")).json();
    } catch { data = { authors: [], groups: [] }; }
    byKey = new Map(data.authors.map(a => [a.key, a]));
    bySurname = new Map();
    byBook = new Map();
    for (const a of data.authors) {
      // The registry lists every book each author wrote, and all 202 book_ids
      // in the corpus are covered, so this is an exact join. The graphs and the
      // search facets key on book_id; recovering the author from a filename is
      // only a fallback now.
      for (const b of a.book_ids || []) byBook.set(b, groupOf(a.sex));
    }
    // Surnames in two passes. A joint record like "astell-and-norris" used to
    // claim the bare surname "astell" and, depending on iteration order, won
    // it from Mary Astell herself — so her books were filed as joint, and
    // Elizabeth Burnet's as Thomas Burnet's. A solo author owns their surname;
    // a joint record only fills a gap.
    const solo = data.authors.filter(a => !a.key.includes("-and-"));
    const joint = data.authors.filter(a => a.key.includes("-and-"));
    for (const a of [...solo, ...joint]) {
      bySurname.set(a.key, a);   // the exact key always resolves to its own record
      const bare = a.key.replace(/-and-.*/, "");
      if (!bySurname.has(bare)) bySurname.set(bare, a);
      const surname = (a.name.split(",")[0] || "").trim().toLowerCase();
      if (surname && !bySurname.has(surname)) bySurname.set(surname, a);
    }
    return data;
  }

  /* Search results carry a display author ("Astell & Norris"); map it back. */
  function lookup(displayAuthor) {
    if (!displayAuthor) return null;
    const k = String(displayAuthor).toLowerCase().replace(/ & /g, "-and-").replace(/\s+/g, "-");
    return bySurname.get(k) || bySurname.get(k.split("-and-")[0]) || null;
  }

  function sexOf(displayAuthor) {
    const a = lookup(displayAuthor);
    return a ? groupOf(a.sex) : "unattributed";
  }

  /* book_id -> "women" | "men" | "joint" | "unattributed". Exact, unlike
     sexOf, which has to recover the author from a display string. */
  function groupOfBook(bookId) {
    if (!bookId) return "unattributed";
    const hit = byBook.get(bookId);
    if (hit) return hit;
    // OCR and text editions of the same work sometimes differ by a suffix
    const base = String(bookId).replace(/__txt$/, "");
    if (byBook.has(base)) return byBook.get(base);
    // fall back to the surname heading the id
    const g = sexOf(String(bookId).split(/[_ ]/)[0]);
    return g || "unattributed";
  }

  /* Which groups are present at all, so a filter never offers an empty box. */
  function groupsPresent() {
    return [...new Set(byBook.values())];
  }

  /* ---------------------------------------------------------------- panel */
  function open() {
    const host = document.getElementById("authors-panel");
    if (!host) return;
    host.classList.remove("hidden");
    document.body.classList.add("authors-open");
    render();
  }
  function close() {
    const host = document.getElementById("authors-panel");
    if (!host) return;
    host.classList.add("hidden");
    document.body.classList.remove("authors-open");
  }

  function bar(groups) {
    const total = groups.reduce((s, g) => s + g.passages, 0) || 1;
    return `<div class="au-bar" role="img" aria-label="share of indexed passages by author group">
      ${groups.map(g => `<span style="width:${(100 * g.passages / total).toFixed(2)}%;background:${GROUP[g.group].color}"
          title="${GROUP[g.group].label}: ${g.authors} authors, ${g.books} books, ${g.passages.toLocaleString()} passages"></span>`).join("")}
    </div>
    <div class="au-key">${groups.map(g => `<span><i style="background:${GROUP[g.group].color}"></i>${GROUP[g.group].label}
      <b>${(100 * g.passages / total).toFixed(0)}%</b> <span class="au-sub">${g.authors} authors · ${g.books} books</span></span>`).join("")}</div>`;
  }

  function personCard(a) {
    const g = groupOf(a.sex);
    const life = a.born ? `${a.born}–${a.died || ""}` : "";
    const active = a.first_year
      ? (a.first_year === a.last_year ? a.first_year : `${a.first_year}–${a.last_year}`)
      : "";
    return `<div class="au-person" data-key="${esc(a.key)}">
      <span class="au-dot" style="background:${GROUP[g].color}" title="${GROUP[g].label}"></span>
      <div class="au-body">
        <h4>${esc(a.name)}${life ? ` <span class="au-life">${esc(life)}</span>` : ""}</h4>
        <div class="au-stats">${a.books} book${a.books === 1 ? "" : "s"} ·
          ${a.passages.toLocaleString()} passages${active ? ` · in the corpus ${esc(active)}` : ""}</div>
        ${a.concepts && a.concepts.length ? `<div class="au-concepts">${a.concepts.slice(0, 6)
            .map(c => `<button class="au-chip" data-q="${esc(c.label)}">${esc(c.label)}</button>`).join("")}</div>` : ""}
        ${a.note ? `<div class="au-note">${esc(a.note)}</div>` : ""}
      </div>
      <button class="au-read" data-q="${esc((a.name.split(",")[0] || a.name).trim())}">search →</button>
    </div>`;
  }

  function skewTable(rows, side) {
    return `<ol class="au-skew">${rows.slice(0, 8).map(r => `
      <li><button class="au-chip" data-q="${esc(r.label)}">${esc(r.label)}</button>
        <span class="au-counts" title="attestations in the concept map's inverted index">${r.n_women} / ${r.n_men}</span></li>`).join("")}</ol>`;
  }

  async function render() {
    const host = document.getElementById("authors-panel");
    await load();
    const groups = (data.groups || []).filter(g => GROUP[g.group]);
    const people = [...(data.authors || [])].sort((a, b) => b.passages - a.passages);
    const em = data.concept_emphasis || { women_lean: [], men_lean: [] };
    const women = groups.find(g => g.group === "women");
    const totalP = groups.reduce((s, g) => s + g.passages, 0) || 1;

    host.innerHTML = `
      <div class="au-bar-top">
        <button id="authors-close" title="Close (Esc)">×</button>
        <span class="reader-title">Authors</span>
        <span class="au-hint">who wrote the corpus, and what they wrote about</span>
      </div>
      <div class="au-body-scroll">
        <section class="au-sec">
          <h3>Composition</h3>
          <p class="au-lede">${(data.authors || []).length} authors across
            ${groups.reduce((s, g) => s + g.books, 0)} indexed sources.
            ${women ? `Women wrote <b>${(100 * women.passages / totalP).toFixed(0)}%</b> of the indexed
            text (${women.authors} authors, ${women.books} sources) — this corpus was assembled to put them
            beside the canonical men rather than in a separate appendix.` : ""}</p>
          ${bar(groups)}
        </section>

        <section class="au-sec">
          <h3>What each group dwells on</h3>
          <p class="au-lede">Share of a group's own concept attestations, so this is not just a restatement
            of who published more. Counts are <i>women / men</i>; the thin ones are suggestive, not conclusive.</p>
          <div class="au-skew-cols">
            <div><h4>Distinctive of the women</h4>${skewTable(em.women_lean, "w")}</div>
            <div><h4>Distinctive of the men</h4>${skewTable(em.men_lean, "m")}</div>
          </div>
        </section>

        <section class="au-sec">
          <h3>The roster</h3>
          <div class="au-filter">
            ${["all", "women", "men", "joint"].map(f =>
              `<button class="au-f${f === "all" ? " active" : ""}" data-f="${f}">${f}</button>`).join("")}
          </div>
          <div class="au-list">${people.map(personCard).join("")}</div>
        </section>
      </div>`;

    host.querySelector("#authors-close").onclick = close;
    host.querySelectorAll(".au-chip, .au-read").forEach(b => {
      b.onclick = () => {
        close();
        document.dispatchEvent(new CustomEvent("atlas:search", { detail: b.dataset.q }));
      };
    });
    host.querySelectorAll(".au-f").forEach(b => {
      b.onclick = () => {
        host.querySelectorAll(".au-f").forEach(x => x.classList.remove("active"));
        b.classList.add("active");
        const f = b.dataset.f;
        host.querySelectorAll(".au-person").forEach(el => {
          const a = byKey.get(el.dataset.key);
          el.style.display = (f === "all" || (a && groupOf(a.sex) === f)) ? "" : "none";
        });
      };
    });
  }

  document.addEventListener("keydown", (e) => {
    const host = document.getElementById("authors-panel");
    if (e.key === "Escape" && host && !host.classList.contains("hidden")) { close(); e.stopPropagation(); }
  }, true);

  load();
  return { load, lookup, sexOf, groupOf, groupOfBook, groupsPresent, open, close, GROUP,
    get data() { return data; } };
})();

window.Authors = Authors;
