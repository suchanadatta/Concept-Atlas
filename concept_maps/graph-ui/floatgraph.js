/* Floating graph window: movable/resizable mini concept graph that renders the
   same 2D data in its own canvas — open from search results without leaving the page. */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  let sim = null, nodes = [], links = [], positions = null, running = false;
  let ctx, canvas, W = 0, H = 0, dpr = 1;
  let hovered = null, transform = { k: 1, x: 0, y: 0 };

  function init() {
    $("gf-bar").addEventListener("mousedown", startDrag);
    $("gf-close").onclick = close;
    const modeBtn = $("gf-mode");
    if (modeBtn) modeBtn.onclick = () => setMode(!dynMode);
    wireNodeClick();
    $("gf-expand").onclick = () => {
      // expand = open the main graph view
      close();
      document.getElementById("landing").classList.add("hidden");
      document.getElementById("gres").classList.add("hidden");
    };
    // resize observer keeps canvas crisp
    new ResizeObserver(() => { sizeCanvas(); if (running) draw(); }).observe($("gf-body"));
  }

  function open(focusId) {
    const el = $("graph-float");
    el.classList.remove("hidden");
    sizeCanvas();
    if (!sim) build(focusId);
    else if (focusId) highlightFocus(focusId);
    if (!running) { running = true; requestAnimationFrame(tick); }
  }
  function close() { running = false; $("graph-float").classList.add("hidden"); }

  function sizeCanvas() {
    canvas = $("gf-canvas");
    const body = $("gf-body");
    dpr = window.devicePixelRatio || 1;
    W = body.clientWidth; H = body.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + "px"; canvas.style.height = H + "px";
    ctx = canvas.getContext("2d");
  }

  function build(focusId) {
    if (typeof S === "undefined" || !S.data) return;
    nodes = S.nodes.map(n => ({ id: n.id, label: n.label, color: n.color, importance: n.importance, x: W/2 + (Math.random()-0.5)*100, y: H/2 + (Math.random()-0.5)*100, vx: 0, vy: 0 }));
    const idset = new Set(nodes.map(n => n.id));
    links = S.edges.filter(e => idset.has(e.s) && idset.has(e.t)).map(e => ({ s: e.s, t: e.t, w: e.w }));
    // lightweight force sim
    sim = { alpha: 1 };
    if (focusId) highlightFocus(focusId);
  }

  /* ————— dynamic mode: graph built live from search results —————
     Nodes: query (center) + document hits (books) + matched concepts.
     Edges: doc→query (relevance), doc↔doc (same book). */
  let dynMode = false;   // false = static concept map, true = dynamic query graph
  let dynData = null;    // {query, passages:[{book_id,page,count,blocks}], concepts:[{id}]}

  function setMode(dyn) {
    dynMode = dyn;
    document.getElementById("gf-mode").textContent = dyn ? "⇄ dynamic" : "⇄ static";
    document.querySelector("#graph-float .gf-title").textContent =
      dyn ? "Dynamic query graph" : "Concept graph";
    if (dyn) buildDynamic();
    else { if (typeof S !== "undefined") { nodes = []; links = []; sim = null; build(window._lastSearchConcept); } }
  }

  function setDynamicData(data) { dynData = data; if (dynMode) buildDynamic(); }

  function buildDynamic() {
    if (!dynData || !dynData.passages.length) {
      nodes = [{ id: "__q", label: "“" + ((dynData && dynData.query) || "query") + "”", color: "#8A3B32", importance: 1, x: W/2, y: H/2, vx: 0, vy: 0, focus: true }];
      links = [];
      sim = { alpha: 1 };
      return;
    }
    nodes = [{ id: "__q", label: "“" + (dynData.query.length > 40 ? dynData.query.slice(0, 40) + "…" : dynData.query) + "”",
               color: "#8A3B32", importance: 1, x: W/2, y: H/2, vx: 0, vy: 0, focus: true, query: true }];
    links = [];
    const maxC = Math.max(1, ...dynData.passages.map(p => p.count || 1));
    const docNodes = dynData.passages.slice(0, 24).map((p, i) => {
      const id = "doc:" + p.book_id + "#" + p.page;
      const ang = (i / Math.min(24, dynData.passages.length)) * 6.2832;
      return { id, label: shortBook(p.book_id) + " p." + p.page, color: "#4E79A7",
               importance: 0.3 + 0.6 * (p.count / maxC), book: p.book_id, page: p.page,
               x: W/2 + Math.cos(ang) * 120, y: H/2 + Math.sin(ang) * 120, vx: 0, vy: 0 };
    });
    nodes.push(...docNodes);
    docNodes.forEach(n => links.push({ s: "__q", t: n.id, w: 0.5 + n.importance * 0.5 }));
    (dynData.concepts || []).slice(0, 8).forEach((c, i) => {
      const id = "c:" + (c.id || c.n?.id || c);
      const ang = (i / 8) * 6.2832 + 0.4;
      nodes.push({ id, label: c.label || (c.n && c.n.label) || c.id || id, color: "#C15B5B", importance: 0.7,
                   x: W/2 + Math.cos(ang) * 190, y: H/2 + Math.sin(ang) * 190, vx: 0, vy: 0 });
      links.push({ s: "__q", t: id, w: 0.35 });
    });
    const byBook = {};
    docNodes.forEach(n => { (byBook[n.book] = byBook[n.book] || []).push(n); });
    Object.values(byBook).forEach(group => {
      for (let i = 0; i < group.length; i++) for (let j = i + 1; j < group.length; j++) {
        links.push({ s: group[i].id, t: group[j].id, w: 0.25 });
      }
    });
    sim = { alpha: 1 };
  }

  function shortBook(bid) {
    return (bid || "").split("_").slice(0, 2).join(" ").slice(0, 22);
  }

  function wireNodeClick() {
    const cv = $("gf-canvas");
    cv.onclick = (e) => {
      const rect = cv.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      let best = null, bestD = 1e9;
      for (const n of nodes) {
        if (n.id === "__q") continue;
        const d = (n.x - mx) ** 2 + (n.y - my) ** 2;
        if (d < bestD) { bestD = d; best = n; }
      }
      const r = best ? 2.5 + best.importance * 5 + 8 : 0;
      if (best && bestD < r * r && best.book && typeof openReader === "function") {
        openReader(best.book, { page: best.page });
      } else if (best && best.id.startsWith("c:") && typeof selectById === "function") {
        selectById(best.id.slice(2), false);
      }
    };
  }

  function highlightFocus(id) {
    nodes.forEach(n => n.focus = n.id === id || links.some(l => (l.s === id && l.t === n.id) || (l.t === id && l.s === n.id)));
  }

  const byId = () => { const m = new Map(); nodes.forEach(n => m.set(n.id, n)); return m; };

  function tick() {
    if (!running) return;
    // forces: repulsion + link spring + centering
    const alpha = sim ? Math.max(sim.alpha -= 0.0015, 0.02) : 0.02;
    const m = byId();
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d2 = dx*dx + dy*dy; if (d2 < 1) d2 = 1;
        const f = 900 / d2 * alpha;
        const d = Math.sqrt(d2);
        dx /= d; dy /= d;
        a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f;
      }
    }
    for (const l of links) {
      const a = m.get(l.s), b = m.get(l.t);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx*dx + dy*dy) || 1;
      const f = (d - 46) * 0.02 * alpha * (0.5 + l.w);
      a.vx += dx / d * f; a.vy += dy / d * f;
      b.vx -= dx / d * f; b.vy -= dy / d * f;
    }
    for (const n of nodes) {
      n.vx += (W/2 - n.x) * 0.004 * alpha;
      n.vy += (H/2 - n.y) * 0.004 * alpha;
      n.vx *= 0.86; n.vy *= 0.86;
      n.x += n.vx; n.y += n.vy;
    }
    draw();
    requestAnimationFrame(tick);
  }

  function draw() {
    if (!ctx) return;
    const dark = document.body.classList.contains("dark");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = dark ? "#1E1C18" : "#F6F1E5";
    ctx.fillRect(0, 0, W, H);
    const m = byId();
    // edges
    ctx.lineWidth = 0.6;
    for (const l of links) {
      const a = m.get(l.s), b = m.get(l.t);
      if (!a || !b) continue;
      const hot = (a.focus || b.focus);
      ctx.strokeStyle = hot ? "rgba(138,59,50,.55)" : (dark ? "rgba(150,142,124,.18)" : "rgba(120,105,80,.14)");
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    // nodes
    for (const n of nodes) {
      const r = 2.5 + n.importance * 5;
      ctx.globalAlpha = n.focus === undefined || n.focus ? 1 : 0.25;
      ctx.fillStyle = n.color;
      ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 6.2832); ctx.fill();
      if (n.focus) {
        ctx.strokeStyle = "#8A3B32"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(n.x, n.y, r + 2.5, 0, 6.2832); ctx.stroke();
      }
      if (n.focus || n.importance > 0.9) {
        ctx.fillStyle = dark ? "#E8E2D5" : "#2E2A24";
        ctx.font = "10px Inter, sans-serif";
        ctx.fillText(n.label, n.x + r + 2, n.y + 3);
      }
    }
    ctx.globalAlpha = 1;
  }

  /* drag window */
  function startDrag(e) {
    if (e.target.tagName === "BUTTON") return;
    const el = $("graph-float");
    const sx = e.clientX - el.offsetLeft, sy = e.clientY - el.offsetTop;
    const move = (ev) => {
      el.style.left = Math.max(0, ev.clientX - sx) + "px";
      el.style.top = Math.max(0, ev.clientY - sy) + "px";
      el.style.right = "auto";
    };
    const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  }

  /* click node in float -> select in main app */
  canvas?.addEventListener?.("click", () => {});

  window.openGraphFloat = open;
  window.closeGraphFloat = close;
  window.setDynamicData = setDynamicData;
  window.setGraphFloatMode = setMode;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
