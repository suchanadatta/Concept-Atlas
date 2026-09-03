/* Compare view + theme toggle + help — wired to app.js state */
"use strict";

(function () {
  const picked = [];

  function init() {
    document.getElementById("btn-compare").onclick = openCompare;
    document.getElementById("compare-close").onclick = closeCompare;
    document.getElementById("btn-help").onclick = () => document.getElementById("help").classList.remove("hidden");
    document.getElementById("help-close").onclick = () => document.getElementById("help").classList.add("hidden");
    document.getElementById("btn-theme").onclick = toggleTheme;
    // theme persistence
    if (localStorage.getItem("atlas-theme") === "dark") {
      document.body.classList.add("dark");
      document.getElementById("btn-theme").textContent = "☀️";
    }
    // hook node clicks for compare picking (ctrl/meta-click)
    document.addEventListener("click", (e) => {
      // only when compare overlay is open
      if (document.getElementById("compare").classList.contains("hidden")) return;
    }, true);
  }

  function toggleTheme() {
    const dark = document.body.classList.toggle("dark");
    localStorage.setItem("atlas-theme", dark ? "dark" : "light");
    document.getElementById("btn-theme").textContent = dark ? "☀️" : "🌙";
    if (typeof S !== "undefined") S.dirty = true; // redraw 2D
  }

  function openCompare() {
    document.getElementById("compare").classList.remove("hidden");
    renderCompare();
  }
  function closeCompare() {
    document.getElementById("compare").classList.add("hidden");
  }

  /* default pick: selected + top importance nodes */
  function autoPick() {
    const list = [];
    if (typeof S !== "undefined" && S.selected) list.push(S.selected);
    if (typeof S !== "undefined" && S.query) {
      for (const q of S.query.top.slice(0, 3)) {
        if (!list.includes(q.node)) list.push(q.node);
      }
    }
    if (list.length < 2 && typeof S !== "undefined") {
      const byImp = [...S.nodes].sort((a, b) => b.importance - a.importance);
      for (const n of byImp) {
        if (list.length >= 3) break;
        if (!list.includes(n)) list.push(n);
      }
    }
    return list.slice(0, 4);
  }

  function renderCompare() {
    const grid = document.getElementById("compare-grid");
    let nodes = autoPick();
    // allow ?ids= override
    const params = new URLSearchParams(location.search);
    const ids = params.get("compare");
    if (ids) {
      nodes = ids.split(",").map(id => (typeof S !== "undefined" ? S.byId.get(id) : null)).filter(Boolean);
    }
    grid.innerHTML = nodes.map(n => {
      const evList = (typeof S !== "undefined" ? S.data.evidence[n.id] : []) || [];
      return `<div class="cmp-col" data-id="${n.id}">
        <h3>${esc(n.label)}</h3>
        <div class="cmp-cat">${esc((n.category || []).join(" › "))} · imp ${n.importance.toFixed(2)} · ${n.books} books</div>
        <div class="cmp-def">${esc(n.definition)}</div>
        <div class="cmp-ev">
          ${evList.slice(0, 4).map(e => `
            <div class="cmp-ev-item">
              <div class="q">“${esc(e.text)}”</div>
              <div class="cite"><b>${esc(e.author)}</b>${e.year ? " · " + esc(e.year) : ""}${e.page ? " · p. " + esc(e.page) : ""}</div>
              ${e.has_pdf ? `<button class="ev-open" data-book="${esc(e.book_id)}" data-page="${e.page}" data-bbox='${JSON.stringify(e.bbox_pts || null)}' data-text="${esc(e.text.slice(0, 100))}">📖 open</button>` : ""}
            </div>`).join("")}
        </div>
      </div>`;
    }).join("");
    grid.querySelectorAll(".ev-open").forEach(btn => {
      btn.onclick = () => {
        let bbox = null;
        try { bbox = JSON.parse(btn.dataset.bbox); } catch {}
        if (typeof openEvidenceInReader === "function") {
          openEvidenceInReader({ book_id: btn.dataset.book, page: parseInt(btn.dataset.page, 10), bbox_pts: bbox, text: btn.dataset.text, has_pdf: true });
        }
      };
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
