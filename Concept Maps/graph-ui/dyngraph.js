/* Query graph side panel v2: concept+book network built from the live
   /query_graph endpoint — direct concept matches, bridge concepts, documents,
   and all their interconnections. Full 2D (pan/zoom/hover/drag) + 3D. */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  let nodes = [], links = [];
  let ctx, canvas, W = 0, H = 0, dpr = 1;
  let sim = null, running = false;
  let hovered = null, nodeDrag = null;
  let view = "2d";
  let g3d = null;
  let data = null;

  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const shortBook = (b) => (b || "").replace(/_/g, " ").split(" ").slice(0, 3).join(" ").slice(0, 26);

  // relation colors (mirrors the main graph's REL_STYLE)
  const RSTYLE = {
    supports: "#3E6B52", requires: "#2E7D74", entails: "#2F5D3A", underlies: "#7A7A3A",
    develops_from: "#4E6BA7", influences: "#6A9AC7", exemplifies: "#9C9484",
    subsumes: "#7B68B5", opposes: "#A03A31", contrasts_with: "#C0663A",
    to_query: "#8A3B32", to_doc: "#4E79A7", same_book: "#B0A890",
  };
  const rcol = (r) => RSTYLE[r] || "#8B8375";

  function init() {
    $("dyngraph-close").onclick = () => {
      if (window.closeDynGraph) window.closeDynGraph();
      else close();
    };
    $("dyngraph-2d").onclick = () => setView("2d");
    $("dyngraph-3d").onclick = () => setView("3d");
    new ResizeObserver(() => { sizeCanvas(); if (running && view === "2d") draw(); }).observe($("dyngraph-stage"));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("dyngraph").classList.contains("hidden")) close();
    });
  }

  async function open(query) {
    $("dyngraph").classList.remove("hidden");
    document.body.classList.add("split-graph");
    $("gres").style.right = "54%";
    $("dyngraph-title").textContent = `“${query.slice(0, 40)}”`;
    $("dyngraph-stage").innerHTML = `<div class="pdf-loading-state"><div class="searching-spinner"></div>
      <div class="pdf-loading-text">Building concept–book graph…</div></div>`;
    // fetch the graph from the semantic backend (via same-origin proxy)
    try {
      const r = await fetch("/book/api/query_graph_proxy", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, n_concepts: 10, n_docs: 18 }),
      });
      data = await r.json();
    } catch (e) {
      $("dyngraph-stage").innerHTML = `<p class="hint" style="padding:40px;text-align:center">Graph backend unavailable.</p>`;
      return;
    }
    // clear the loading screen BEFORE creating the canvas
    $("dyngraph-stage").innerHTML = "";
    canvas = null; ctx = null;
    build();
    sizeCanvas();
    if (view === "3d") init3D();
    else { if (!running) { running = true; requestAnimationFrame(tick); } }
  }

  function close() {
    running = false;
    $("dyngraph").classList.add("hidden");
    document.body.classList.remove("split-graph");
    $("gres").style.right = "";
    if (g3d) { try { g3d.pauseAnimation(); } catch {} }
  }
  window.closeDynGraph = close;

  function setView(v) {
    view = v;
    $("dyngraph-2d").classList.toggle("active", v === "2d");
    $("dyngraph-3d").classList.toggle("active", v === "3d");
    if (v === "3d") { running = false; init3D(); }
    else {
      if (g3d) { try { g3d.pauseAnimation(); } catch {} }
      $("dyngraph-stage").innerHTML = "";
      canvas = null; ctx = null;
      sizeCanvas(); build();
      if (!running) { running = true; requestAnimationFrame(tick); }
    }
  }

  function sizeCanvas() {
    const stage = $("dyngraph-stage");
    dpr = window.devicePixelRatio || 1;
    W = stage.clientWidth; H = stage.clientHeight;
    if (view !== "2d") return;
    if (!canvas) { canvas = document.createElement("canvas"); stage.appendChild(canvas); wireCanvas(); }
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + "px"; canvas.style.height = H + "px";
    ctx = canvas.getContext("2d");
  }

  function build() {
    if (!data) return;
    nodes = []; links = [];
    const cx = W / 2, cy = H / 2 - 14;
    const minR = Math.min(W, H);
    const rQuery = 16;
    const rConcept = minR * 0.30;   // inner ring
    const rBridge = minR * 0.44;    // bridge concepts between rings
    const rDoc = minR * 0.46;      // outer ring
    // query node
    nodes.push({ id: "__q", label: "“" + (data.query.length > 30 ? data.query.slice(0, 30) + "…" : data.query) + "”",
                 color: "#8A3B32", r: rQuery, x: cx, y: cy, hx: cx, hy: cy, vx: 0, vy: 0, kind: "query" });
    // concept nodes: direct matches on the inner ring, bridges just outside
    const cById = {};
    const directs = (data.concepts || []).filter(c => c.match !== "bridge");
    const bridges = (data.concepts || []).filter(c => c.match === "bridge");
    const placeRing = (arr, radius, offset, byIdMap) => {
      arr.forEach((c, i) => {
        const ang = (i / Math.max(1, arr.length)) * 6.2832 + offset;
        const hx = cx + Math.cos(ang) * radius, hy = cy + Math.sin(ang) * radius;
        const n = { id: "c:" + c.id, cid: c.id, label: c.label, color: "#C15B5B",
                   r: 7 + 7 * Math.min(1, c.score), x: hx, y: hy, hx, hy,
                   vx: 0, vy: 0, kind: "concept", def: c.definition, match: c.match || "direct", score: c.score };
        byIdMap[c.id] = n; nodes.push(n);
        links.push({ s: "__q", t: n.id, r: "to_query", w: 0.3 + 0.4 * Math.min(1, c.score) });
      });
    };
    placeRing(directs, rConcept, -Math.PI / 2, cById);
    placeRing(bridges, rBridge, -Math.PI / 2 + 0.35, cById);
    // concept↔concept edges (map relations)
    (data.c2c || []).forEach(e => {
      const s = cById[e.s], t = cById[e.t];
      if (s && t) links.push({ s: s.id, t: t.id, r: e.r, w: e.w });
    });
    // doc nodes on the outer ring
    (data.docs || []).forEach((d, i) => {
      const ang = (i / Math.max(1, data.docs.length)) * 6.2832 + 0.12;
      const hx = cx + Math.cos(ang) * rDoc, hy = cy + Math.sin(ang) * rDoc;
      const n = { id: "d" + i, label: shortBook(d.book_id) + " ·" + (d.page != null ? "p" + d.page : "¶"),
                 color: "#4E79A7", r: 5 + 5 * Math.min(1, d.score * 1.2),
                 x: hx, y: hy, hx, hy, vx: 0, vy: 0,
                 kind: "doc", book: d.book_id, page: d.page, snippet: d.snippet, score: d.score };
      nodes.push(n);
      links.push({ s: "__q", t: n.id, r: "to_doc", w: 0.2 + 0.4 * d.score });
    });
    // concept→doc edges
    (data.c2d || []).forEach(e => {
      const c = cById[e.concept];
      const d = nodes.find(n => n.kind === "doc" && n.book === e.book);
      if (c && d) links.push({ s: c.id, t: d.id, r: "to_doc", w: e.w * 0.7 });
    });
    // doc↔doc same-book edges
    (data.d2d || []).forEach(e => {
      const a = nodes.find(n => n.id === "d" + e.a), b = nodes.find(n => n.id === "d" + e.b);
      if (a && b) links.push({ s: a.id, t: b.id, r: "same_book", w: e.w });
    });
    sim = { alpha: 1 };
  }

  const byId = () => { const m = new Map(); nodes.forEach(n => m.set(n.id, n)); return m; };

  function tick() {
    if (!running || view !== "2d") return;
    const alpha = sim ? Math.max(sim.alpha -= 0.0012, 0.012) : 0.012;
    const m = byId();
    // gentle relaxation only — the radial layout does the real work
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d2 = dx * dx + dy * dy; if (d2 < 1) d2 = 1;
        const d = Math.sqrt(d2);
        const minSep = (a.r + b.r + 6);
        if (d < minSep) { // only push apart overlapping nodes
          const f = (minSep - d) * 0.25 * alpha;
          dx /= d; dy /= d;
          a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f;
        }
      }
    }
    for (const l of links) {
      const a = m.get(l.s), b = m.get(l.t);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = (d - 58) * 0.008 * alpha * (0.5 + l.w);
      a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f;
    }
    for (const n of nodes) {
      // ring retention: each node relaxes toward its assigned layout spot
      // (radial positions from build()), not toward the center — this keeps
      // the query/concepts/docs rings from collapsing into a blob
      if (n.hx != null && n !== nodeDrag) {
        n.vx += (n.hx - n.x) * 0.06 * alpha;
        n.vy += (n.hy - n.y) * 0.06 * alpha;
      }
      if (n !== nodeDrag) { n.vx *= 0.82; n.vy *= 0.82; n.x += n.vx; n.y += n.vy; }
    }
    draw();
    requestAnimationFrame(tick);
  }

  const view_t = { k: 1, x: 0, y: 0 };
  let panning = false, panStart = null;

  function draw() {
    if (!ctx) return;
    const dark = document.body.classList.contains("dark");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = dark ? "#1E1C18" : "#F6F1E5";
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.translate(view_t.x, view_t.y); ctx.scale(view_t.k, view_t.k);
    const m = byId();
    const hov = hovered;
    const isNb = (n) => !hov || n === hov || linked(hov, n);
    // EDGES FIRST — always colored by relation so connections read clearly
    for (const l of links) {
      const a = m.get(l.s), b = m.get(l.t);
      if (!a || !b) continue;
      const hot = hov && ((l.s === hov.id) || (l.t === hov.id));
      const base = rcol(l.r);
      ctx.strokeStyle = hot ? base : (dark ? "rgba(150,142,124,.30)" : "rgba(120,105,80,.26)");
      ctx.globalAlpha = hov && !hot ? 0.10 : (hot ? 0.95 : 1);
      ctx.lineWidth = (hot ? 2.6 : 1.5 + (l.w || 0.4)) / view_t.k;
      // dashed for same-book links (weaker semantic)
      if (l.r === "same_book") ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.globalAlpha = 1;
    const labelAlpha = Math.min(1, Math.max(0.15, (view_t.k - 0.45) * 1.7));
    for (const n of nodes) {
      ctx.globalAlpha = isNb(n) ? 1 : 0.22;
      if (n === hov) {
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 4, 0, 6.2832);
        ctx.strokeStyle = dark ? "#C15B5B" : "#8A3B32"; ctx.lineWidth = 2.2 / view_t.k; ctx.stroke();
      }
      // bridge concepts: dashed ring
      if (n.match === "bridge") {
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 2.5, 0, 6.2832);
        ctx.setLineDash([3, 3]); ctx.strokeStyle = "rgba(123,104,181,.7)"; ctx.lineWidth = 1.2 / view_t.k;
        ctx.stroke(); ctx.setLineDash([]);
      }
      ctx.fillStyle = n.color;
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 6.2832); ctx.fill();
      // white rim so nodes pop against edges
      ctx.lineWidth = 1.5 / view_t.k;
      ctx.strokeStyle = dark ? "rgba(30,28,24,.8)" : "rgba(251,248,240,.9)";
      ctx.stroke();
      // score badge on direct concept matches
      if (n.kind === "concept" && n.match === "direct" && n.score > 0) {
        ctx.beginPath(); ctx.arc(n.x + n.r * 0.72, n.y - n.r * 0.72, 6.5, 0, 6.2832);
        ctx.fillStyle = "#8A3B32"; ctx.fill();
        ctx.fillStyle = "#F6F1E5"; ctx.font = "700 8px Inter, sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(Math.round(n.score * 100), n.x + n.r * 0.72, n.y - n.r * 0.72 + 0.5);
        ctx.textBaseline = "alphabetic";
      }
      // labels: query + concepts always; docs on hover/zoom
      if (n.kind !== "doc" || n === hov || view_t.k > 1.4) {
        ctx.globalAlpha = isNb(n) ? labelAlpha : 0.1;
        ctx.fillStyle = dark ? "#E8E2D5" : "#2E2A24";
        ctx.font = (n.kind === "query" ? "600 13px" : "500 10.5px") + " Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(n.label, n.x, n.y + n.r + 13);
      }
    }
    ctx.globalAlpha = 1;
    ctx.restore();
    drawLegend();
  }

  function linked(a, b) { return links.some(l => (l.s === a.id && l.t === b.id) || (l.t === a.id && l.s === b.id)); }

  /* bottom legend: node kinds + edge relations present in this graph */
  function drawLegend() {
    if (!ctx) return;
    const dark = document.body.classList.contains("dark");
    const rels = [...new Set(links.map(l => l.r))].filter(r => r !== "to_query");
    const items = [
      { color: "#8A3B32", label: "query" },
      { color: "#C15B5B", label: "concept" },
      { color: "#4E79A7", label: "document" },
      ...rels.map(r => ({ color: rcol(r), label: r.replace(/_/g, " "), edge: true })),
    ];
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = "500 10px Inter, sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    let x = 12;
    const y = H - 14;
    for (const it of items) {
      if (it.edge) {
        ctx.strokeStyle = it.color; ctx.lineWidth = 2;
        ctx.setLineDash(it.label === "same book" ? [4, 4] : []);
        ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x + 16, y - 4); ctx.stroke();
        ctx.setLineDash([]);
      } else {
        ctx.fillStyle = it.color;
        ctx.beginPath(); ctx.arc(x + 8, y - 4, 5, 0, 6.2832); ctx.fill();
      }
      ctx.fillStyle = dark ? "#B8B2A4" : "#6B6353";
      ctx.fillText(it.label, x + (it.edge ? 20 : 16), y - 4);
      x += (it.edge ? 20 : 16) + ctx.measureText(it.label).width + 14;
      if (x > W - 90) break; // wrap guard
    }
    ctx.textBaseline = "alphabetic";
  }

  function pick(gx, gy) {
    let best = null, bestD = 1e9;
    for (const n of nodes) {
      const d = (n.x - gx) ** 2 + (n.y - gy) ** 2;
      if (d < (n.r + 7) ** 2 && d < bestD) { bestD = d; best = n; }
    }
    return best;
  }

  function wireCanvas() {
    if (!canvas) return;
    canvas.onmousemove = (e) => {
      const r = canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      if (nodeDrag) { nodeDrag.x = (mx - view_t.x) / view_t.k; nodeDrag.y = (my - view_t.y) / view_t.k; nodeDrag.vx = 0; nodeDrag.vy = 0; return; }
      if (panning) { view_t.x += mx - panStart.x; view_t.y += my - panStart.y; panStart = { x: mx, y: my }; return; }
      hovered = pick((mx - view_t.x) / view_t.k, (my - view_t.y) / view_t.k);
      canvas.style.cursor = hovered ? "pointer" : "grab";
    };
    canvas.onmousedown = (e) => {
      const r = canvas.getBoundingClientRect();
      const gx = (e.clientX - r.left - view_t.x) / view_t.k, gy = (e.clientY - r.top - view_t.y) / view_t.k;
      const n = pick(gx, gy);
      if (n) nodeDrag = n;
      else { panning = true; panStart = { x: e.clientX - r.left, y: e.clientY - r.top }; canvas.style.cursor = "grabbing"; }
    };
    canvas.onmouseup = (e) => {
      if (nodeDrag) {
        const r = canvas.getBoundingClientRect();
        const gx = (e.clientX - r.left - view_t.x) / view_t.k, gy = (e.clientY - r.top - view_t.y) / view_t.k;
        const wasDrag = Math.hypot(nodeDrag.x - gx, nodeDrag.y - gy) > 4;
        const clicked = nodeDrag; nodeDrag = null;
        if (clicked && !wasDrag) {
          if (clicked.kind === "doc" && typeof openReader === "function") {
            if (clicked.page == null && typeof openTxtMode === "function") {
              Reader.bookId = clicked.book; Reader.open = true; Reader.txtMode = false;
              if (typeof showReaderShell === "function") showReaderShell();
              openTxtMode(clicked.book);
            } else openReader(clicked.book, { page: clicked.page });
          } else if (clicked.kind === "concept" && typeof selectById === "function") {
            selectById(clicked.cid, false);
          }
        }
      }
      panning = false; panStart = null;
      canvas.style.cursor = hovered ? "pointer" : "grab";
    };
    canvas.onwheel = (e) => {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const nk = Math.max(0.15, Math.min(6, view_t.k * f));
      view_t.x = mx - (mx - view_t.x) * (nk / view_t.k);
      view_t.y = my - (my - view_t.y) * (nk / view_t.k);
      view_t.k = nk;
    };
  }

  /* 3D */
  function init3D() {
    const stage = $("dyngraph-stage");
    if (typeof ForceGraph3D === "undefined") { setView("2d"); return; }
    stage.innerHTML = ""; canvas = null; ctx = null;
    if (g3d) { try { g3d._destructor?.(); } catch {} g3d = null; }
    build();
    g3d = new ForceGraph3D(stage, { controlType: "orbit" })
      .width(stage.clientWidth).height(stage.clientHeight)
      .backgroundColor(document.body.classList.contains("dark") ? "#1E1C18" : "#F6F1E5")
      .nodeRelSize(4.5).nodeResolution(22).linkResolution(3)
      .nodeLabel(n => `<div style="font:600 12.5px Inter,sans-serif;color:#F6F1E5;background:#2E2A24;padding:5px 9px;border-radius:6px;max-width:240px">${esc(n.label)}${n.def ? `<div style="font:italic 11px Georgia;color:#CFC7B4;margin-top:3px">${esc(n.def.slice(0, 110))}…</div>` : ""}${n.snippet ? `<div style="font:italic 11px Georgia;color:#CFC7B4;margin-top:3px">${esc(n.snippet.slice(0, 110))}…</div>` : ""}</div>`)
      .linkColor(l => rcol(l.r))
      .linkWidth(l => 0.4 + (l.w || 0.4) * 1.6)
      .linkOpacity(0.45)
      .onNodeHover((n) => { stage.style.cursor = n ? "pointer" : "default"; })
      .onNodeClick((n) => {
        if (n.kind === "doc" && typeof openReader === "function") openReader(n.book, { page: n.page });
        else if (n.kind === "concept" && typeof selectById === "function") selectById(n.cid, false);
      });
    // persistent label sprites (same mechanism as the main concept graph)
    if (window.Atlas3D && window.Atlas3D.makeLabel) {
      const { makeLabel } = window.Atlas3D;
      g3d.nodeThreeObjectExtend(true)
        .nodeThreeObject((n) => {
          // query + concepts always labeled; docs labeled when important
          if (n.kind === "doc" && (n.r || 0) < 6) return null;
          const dark = document.body.classList.contains("dark");
          const spr = makeLabel(n.label, dark ? "#E8E2D5" : "#3A352C", 13);
          spr.position.set(0, (n.r || 5) + 7, 0);
          return spr;
        });
    }
    g3d.graphData({ nodes: nodes.map(n => ({ ...n })), links: links.map(l => ({ source: l.s, target: l.t, r: l.r, w: l.w })) });
    window.__dynG3D = g3d; // for live theme switching
    setTimeout(() => { try { g3d.zoomToFit(600, 40); } catch {} }, 1500);
  }

  window.openDynGraph = open;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
