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
  let data = null;        // /query_graph response  (concept-driven)
  let semData = null;     // /semantic_graph response (embedding-driven)
  let graphMode = "concept";   // concept | semantic | overlay
  let writersOn = new Set();   // empty = every group
  let lastQuery = "";

  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  /* Document nodes used to be labelled with a chopped raw id
     ("BUTLER 1726 1887 ·p106"); the parsed citation is both shorter and
     actually identifies the work. */
  function shortBook(b) {
    const c = (window.Cite ? Cite.parse(b) : null);
    if (!c || !c.title) return (b || "").replace(/_/g, " ").slice(0, 26);
    const t = c.title.length > 22 ? c.title.slice(0, 21).replace(/\s+\S*$/, "") + "…" : c.title;
    return [c.author, t].filter(Boolean).join(" · ") + (c.year ? ` ${c.year}` : "");
  }

  // relation colors (mirrors the main graph's REL_STYLE)
  const RSTYLE = {
    supports: "#3E6B52", requires: "#2E7D74", entails: "#2F5D3A", underlies: "#7A7A3A",
    develops_from: "#4E6BA7", influences: "#6A9AC7", exemplifies: "#9C9484",
    subsumes: "#7B68B5", opposes: "#A03A31", contrasts_with: "#C0663A",
    to_query: "#8A3B32", to_doc: "#4E79A7", same_book: "#B0A890",
    // semantic bands: these are not editorial relations, only how close two
    // passages sit in the embedding space, so they get their own ramp
    near_identical: "#8A3B32", closely_allied: "#B45E52",
    related: "#7F94A8", loosely_related: "#B0A890",
    to_concept: "#7B68B5",
  };
  const SEM_REL_LABEL = {
    near_identical: "near-identical wording",
    closely_allied: "closely allied",
    related: "related",
    loosely_related: "loosely related",
    to_concept: "nearest concept",
  };
  const rcol = (r) => RSTYLE[r] || "#8B8375";

  function init() {
    $("dyngraph-close").onclick = () => {
      if (window.closeDynGraph) window.closeDynGraph();
      else close();
    };
    $("dyngraph-2d").onclick = () => setView("2d");
    $("dyngraph-3d").onclick = () => setView("3d");
    ["concept", "semantic", "overlay"].forEach(m => {
      const b = $("dyngraph-mode-" + m);
      if (b) b.onclick = () => setGraphMode(m);
    });
    new ResizeObserver(() => { sizeCanvas(); if (running && view === "2d") draw(); }).observe($("dyngraph-stage"));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("dyngraph").classList.contains("hidden")) close();
    });
  }

  const needsConcept = () => graphMode === "concept" || graphMode === "overlay";
  const needsSemantic = () => graphMode === "semantic" || graphMode === "overlay";

  async function fetchConcept(query) {
    const r = await fetch("/book/api/query_graph_proxy", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, n_concepts: 10, n_docs: 18 }),
      signal: AbortSignal.timeout(120000),
    });
    return r.json();
  }
  async function fetchSemantic(query) {
    const r = await fetch("/book/api/semantic_graph_proxy", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, n_docs: 44, min_sim: 0.72, max_deg: 5, n_concepts: 10 }),
      signal: AbortSignal.timeout(120000),
    });
    return r.json();
  }

  function loadingScreen(msg) {
    $("dyngraph-stage").innerHTML = `<div class="pdf-loading-state"><div class="searching-spinner"></div>
      <div class="pdf-loading-text">${esc(msg)}</div></div>`;
  }

  let openSeq = 0;
  async function open(query) {
    const seq = ++openSeq;
    $("dyngraph").classList.remove("hidden");
    document.body.classList.add("split-graph");
    $("gres").style.right = "54%";
    $("dyngraph-title").textContent = `“${query.slice(0, 40)}”`;
    if (query !== lastQuery) { data = null; semData = null; lastQuery = query; }
    loadingScreen(graphMode === "semantic"
      ? "Building the passage network from the embeddings…"
      : graphMode === "overlay"
      ? "Building both graphs…"
      : "Building concept–book graph…");
    try {
      const jobs = [];
      if (needsConcept() && !data) jobs.push(fetchConcept(query).then(d => { data = d; }));
      if (needsSemantic() && !semData) jobs.push(fetchSemantic(query).then(d => { semData = d; }));
      await Promise.all(jobs);
    } catch (e) {
      if (seq !== openSeq) return;
      $("dyngraph-stage").innerHTML = `<p class="hint" style="padding:40px;text-align:center">
        The graph needs the search engine, which is not answering.<br>
        <span style="font-size:12px">${esc(e.message || e)}</span><br>
        <span style="font-size:12px">Passages and the concept map still work.</span></p>`;
      return;
    }
    if (seq !== openSeq) return;   // a newer open superseded this one
    paintModeButtons();
    // clear the loading screen BEFORE creating the canvas
    $("dyngraph-stage").innerHTML = "";
    canvas = null; ctx = null;
    build();
    paintHint();
    sizeCanvas();
    if (view === "3d") init3D();
    else { if (!running) { running = true; requestAnimationFrame(tick); } }
  }

  function paintModeButtons() {
    ["concept", "semantic", "overlay"].forEach(m => {
      const b = $("dyngraph-mode-" + m);
      if (b) b.classList.toggle("active", graphMode === m);
    });
    paintWriterChips();
    paintHint();
  }

  /* What the graph describes, and how much of it is on screen. The size
     matters once the writer filter can remove nodes: without it a filter that
     hides two thirds of the network looks the same as one that hides nothing. */
  function paintHint() {
    const hint = $("dyngraph-hint");
    if (!hint) return;
    const what = graphMode === "concept"
      ? "curated concepts & the documents that attest them"
      : graphMode === "semantic"
      ? "passages linked by embedding similarity — no concept map involved"
      : "curated concepts over the passage network";
    const n = nodes.length, e = links.length;
    hint.textContent = n
      ? `${what} — ${n} nodes, ${e} links${writersOn.size ? " (filtered)" : ""}`
      : what;
    hint.dataset.nodes = String(n);
    hint.dataset.links = String(e);
    hint.dataset.filtered = writersOn.size ? [...writersOn].sort().join(",") : "";
  }

  async function setGraphMode(m) {
    if (m === graphMode) return;
    graphMode = m;
    paintModeButtons();
    if (lastQuery) await open(lastQuery);
  }
  window.setDynGraphMode = setGraphMode;

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

  /* Author sex, the same filter the full concept map carries.

     A passage or document node names its book, so the registry answers it
     directly. A concept node has no single book — it is attested by evidence
     drawn from several — so it survives if any of its evidence was written by
     a selected group, which is what the map's own filter does. The query node
     is not a source and is always kept. */
  function nodeGroups(n) {
    if (n.kind === "query") return null;                  // never filtered
    if (n.book) return [window.Authors ? Authors.groupOfBook(n.book) : "unattributed"];
    if (n.kind === "concept" && n.cid) {
      const g = window.S && S.conceptWriters && S.conceptWriters.get(n.cid);
      return g ? [...g] : null;    // map not loaded: do not hide it on a guess
    }
    return null;
  }

  function keepNode(n) {
    if (!writersOn.size) return true;
    const gs = nodeGroups(n);
    if (!gs) return true;
    return gs.some(g => writersOn.has(g));
  }

  function applyWriterFilter() {
    if (!writersOn.size) return;
    nodes = nodes.filter(keepNode);
    const live = new Set(nodes.map(n => n.id));
    links = links.filter(l => live.has(l.s) && live.has(l.t));
  }

  function build() {
    nodes = []; links = [];
    if (needsSemantic() && semData && semData.nodes) buildSemantic();
    if (needsConcept() && data) buildConcept();
    if (graphMode === "overlay") linkOverlay();
    applyWriterFilter();
    sim = { alpha: 1 };
  }

  const DG_WRITER_ORDER = ["women", "men", "joint", "unattributed"];

  function paintWriterChips() {
    const host = $("dyngraph-writers");
    if (!host) return;
    // count over the unfiltered graph, so the numbers do not shift as you pick
    const all = [];
    const keep = writersOn; writersOn = new Set();
    const savedN = nodes, savedL = links;
    nodes = []; links = [];
    if (needsSemantic() && semData && semData.nodes) buildSemantic();
    if (needsConcept() && data) buildConcept();
    for (const n of nodes) {
      const gs = nodeGroups(n);
      if (gs) all.push(gs);
    }
    nodes = savedN; links = savedL; writersOn = keep;

    const counts = new Map();
    for (const gs of all) for (const g of new Set(gs)) counts.set(g, (counts.get(g) || 0) + 1);
    const groups = DG_WRITER_ORDER.filter(g => counts.has(g));
    if (!groups.length) { host.innerHTML = ""; return; }
    const label = (g) => (window.Authors && Authors.GROUP[g] ? Authors.GROUP[g].label : g);
    const colour = (g) => (window.Authors && Authors.GROUP[g] ? Authors.GROUP[g].color : "#948B7B");
    host.innerHTML =
      `<span class="dg-wlab">by</span>` +
      groups.map(g => `<button class="dg-wchip${writersOn.has(g) ? " active" : ""}" data-w="${g}"
         title="only nodes written by ${label(g)} (${counts.get(g)} here)">
         <span class="wdot" style="background:${colour(g)}"></span>${label(g)}</button>`).join("") +
      (writersOn.size ? `<button class="dg-wchip dg-wclear" data-w="">all</button>` : "");
    host.querySelectorAll(".dg-wchip").forEach(b => {
      b.onclick = () => {
        const g = b.dataset.w;
        if (!g) writersOn.clear();
        else writersOn.has(g) ? writersOn.delete(g) : writersOn.add(g);
        rebuildKeepingView();
      };
    });
  }

  /* Re-derive the graph from data already fetched, keeping whichever view is
     up. No refetch: the filter is a view over the same retrieval. */
  function rebuildKeepingView() {
    if (view === "3d") { init3D(); paintWriterChips(); paintHint(); return; }  // init3D builds
    build();
    paintWriterChips();
    paintHint();
    if (!running) { running = true; requestAnimationFrame(tick); }
  }

  /* ————— semantic graph: passages linked by embedding similarity —————
     Nodes are the retrieved passages themselves, so a query about something
     nobody curated into the concept map ("hypochondriack distemper") still
     produces a real network. Clusters come from the backend's label
     propagation; each gets a colour and a distinctive-terms name. */
  function buildSemantic() {
    const cx = W / 2, cy = H / 2 - 14;
    const R = Math.min(W, H) * (graphMode === "overlay" ? 0.44 : 0.40);
    const clusters = semData.clusters || [];
    const byCluster = {};
    (semData.nodes || []).forEach(n => (byCluster[n.cluster] = byCluster[n.cluster] || []).push(n));
    // clusters get their own arc of the ring, so a community reads as a lobe
    const total = (semData.nodes || []).length || 1;
    let angle = -Math.PI / 2;
    for (const cl of clusters) {
      const members = byCluster[cl.id] || [];
      const span = (members.length / total) * 6.2832;
      const spread = Math.max(span, 0.35);
      members.forEach((d, i) => {
        const a = angle + (members.length > 1 ? (i / (members.length - 1) - 0.5) * spread * 0.92 : 0);
        // rings within a lobe keep dense clusters from stacking on one arc
        const rr = R * (0.72 + 0.28 * ((i % 3) / 2));
        const hx = cx + Math.cos(a) * rr, hy = cy + Math.sin(a) * rr;
        nodes.push({
          id: "p" + d.i, kind: "passage", label: passageLabel(d), color: cl.color,
          r: 5 + 7 * Math.min(1, (d.semantic || 0.5)), x: hx, y: hy, hx, hy, vx: 0, vy: 0,
          book: d.book_id, page: d.page, snippet: d.snippet, bbox_pts: d.bbox_pts,
          source: d.source, cite: d.cite, score: d.score, cluster: cl.id,
          clusterLabel: cl.label, concepts: d.concepts || [],
        });
      });
      angle += span;
    }
    for (const e of semData.edges || []) {
      links.push({ s: "p" + e.s, t: "p" + e.t, r: e.rel, w: e.w });
    }
  }

  function passageLabel(d) {
    const who = d.author || (window.Cite ? Cite.parse(d.book_id).author : "") || "";
    const t = (d.title || "").length > 18 ? d.title.slice(0, 17).replace(/\s+\S*$/, "") + "…" : (d.title || "");
    const loc = d.page != null ? ` p.${d.page}` : "";
    return [who, t].filter(Boolean).join(" · ") + loc;
  }

  /* ————— concept graph (curated map) ————— */
  function buildConcept() {
    const cx = W / 2, cy = H / 2 - 14;
    const minR = Math.min(W, H);
    const overlay = graphMode === "overlay";
    const rQuery = 16;
    // in overlay the passage network already owns the outer ring, so the
    // concepts sit inside it rather than competing for the same radius
    const rConcept = minR * (overlay ? 0.16 : 0.30);
    const rBridge = minR * (overlay ? 0.25 : 0.44);
    const rDoc = minR * 0.46;
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
        // in overlay the cluster palette already uses the warm reds, so a
        // red concept node was indistinguishable from a passage
        const n = { id: "c:" + c.id, cid: c.id, label: c.label,
                   color: overlay ? "#7B68B5" : "#C15B5B",
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
    // doc nodes on the outer ring — omitted in overlay, where the semantic
    // layer already shows every passage and these would duplicate them
    (overlay ? [] : data.docs || []).forEach((d, i) => {
      const ang = (i / Math.max(1, data.docs.length)) * 6.2832 + 0.12;
      const hx = cx + Math.cos(ang) * rDoc, hy = cy + Math.sin(ang) * rDoc;
      const n = { id: "d" + i, label: shortBook(d.book_id) + (d.page != null ? ` p.${d.page}` : ""),
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
  }

  /* ————— overlay: tie each passage to the concepts nearest it —————
     This is the join that makes the two graphs one picture: the curated map
     supplies the vocabulary, the embeddings supply the passages, and these
     edges say which passage the map's words actually land on. */
  function linkOverlay() {
    if (!semData || !data) return;
    const conceptIds = new Set(nodes.filter(n => n.kind === "concept").map(n => n.cid));
    for (const e of semData.c2p || []) {
      if (!conceptIds.has(e.concept)) continue;
      const c = nodes.find(n => n.kind === "concept" && n.cid === e.concept);
      const pn = nodes.find(n => n.id === "p" + e.passage);
      if (c && pn) links.push({ s: c.id, t: pn.id, r: "to_concept", w: e.w * 0.6 });
    }
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
    const labelQueue = [];
    const rank = (n) => n.kind === "query" ? 100 : n.kind === "cluster" ? 50
      : n.kind === "concept" ? 10 + (n.score || 0) : (n.score || 0);
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
      labelQueue.push(n);
    }
    // labels drawn last, after every node, so a circle can never cover text.
    // A coarse occupancy grid drops labels that would overprint an earlier
    // one — the old pass let concept names pile on top of each other.
    // Seed the occupancy map with every node circle: a label that lands on
    // another node reads as part of it ("(*)Happiness"), which the earlier
    // label-vs-label-only check let through.
    const taken = nodes.map(n => ({ x: n.x - n.r, y: n.y - n.r, w: n.r * 2, h: n.r * 2 }));
    const fits = (x0, y0, w, h) => {
      for (const b of taken) {
        if (x0 < b.x + b.w && x0 + w > b.x && y0 < b.y + b.h && y0 + h > b.y) return false;
      }
      taken.push({ x: x0, y: y0, w, h });
      return true;
    };
    // cluster names first: they are the reading of the picture, and without
    // them the colours only mean something in the legend
    if (semData && needsSemantic()) {
      const byCl = {};
      for (const n of nodes) {
        if (n.kind !== "passage") continue;
        (byCl[n.cluster] = byCl[n.cluster] || []).push(n);
      }
      for (const cl of semData.clusters || []) {
        const ms = byCl[cl.id];
        if (!ms || ms.length < 2) continue;
        const mx = ms.reduce((a, n) => a + n.x, 0) / ms.length;
        const my = ms.reduce((a, n) => a + n.y, 0) / ms.length;
        labelQueue.push({
          x: mx, y: my, r: 0, kind: "cluster", label: cl.label,
          color: cl.color, score: 9,
        });
      }
    }
    labelQueue.sort((a, b) => rank(b) - rank(a));   // important labels claim space first
    for (const n of labelQueue) {
      const always = n.kind === "query" || n.kind === "cluster" || n === hov;
      if (!always && (n.kind === "doc" || n.kind === "passage") && view_t.k < 0.75) continue;
      ctx.font = (n.kind === "query" ? "600 13px"
        : n.kind === "cluster" ? "700 11.5px"
        : n.kind === "concept" ? "600 10.5px" : "500 9.5px") + " Inter, sans-serif";
      const w = ctx.measureText(n.label).width, h = 12;
      const x0 = n.x - w / 2, y0 = n.y + n.r + 4;   // below the node, clear of its own circle
      if (!always && !fits(x0 - 2, y0 - 2, w + 4, h + 4)) continue;
      if (always) taken.push({ x: x0 - 2, y: y0 - 2, w: w + 4, h: h + 4 });
      ctx.globalAlpha = isNb(n) ? (n.kind === "doc" ? labelAlpha * 0.85 : labelAlpha) : 0.1;
      // halo keeps text legible where it crosses an edge
      ctx.lineWidth = 3; ctx.lineJoin = "round";
      ctx.strokeStyle = dark ? "rgba(30,28,24,.85)" : "rgba(246,241,229,.85)";
      ctx.textAlign = "center";
      ctx.strokeText(n.label, n.x, n.y + n.r + 13);
      ctx.fillStyle = n.kind === "cluster" ? n.color
        : n.kind === "doc" ? (dark ? "#9FB6CE" : "#3E6187")
        : (dark ? "#E8E2D5" : "#2E2A24");
      ctx.fillText(n.label, n.x, n.y + n.r + 13);
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
    const hasBridge = nodes.some(n => n.match === "bridge");
    const has = (k) => nodes.some(n => n.kind === k);
    const items = [];
    if (has("query")) items.push({ color: "#8A3B32", label: "your query" });
    if (has("concept")) {
      const cc = graphMode === "overlay" ? "#7B68B5" : "#C15B5B";
      items.push({ color: cc, label: "concept · badge = match %" });
      if (hasBridge) items.push({ color: "#C15B5B", label: "bridge concept", ring: true });
    }
    if (has("doc")) items.push({ color: "#4E79A7", label: "passage" });
    // in semantic/overlay mode node colour means cluster, so name the clusters
    if (has("passage") && semData) {
      for (const cl of (semData.clusters || []).slice(0, 4)) {
        items.push({ color: cl.color, label: `${cl.label} (${cl.n})` });
      }
    }
    for (const r of rels) {
      items.push({ color: rcol(r), label: SEM_REL_LABEL[r] || r.replace(/_/g, " "), edge: true });
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = dark ? "rgba(30,28,24,.92)" : "rgba(246,241,229,.92)";
    ctx.fillRect(0, H - 28, W, 28);
    ctx.strokeStyle = dark ? "#3A362E" : "#DDD3BE";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, H - 28.5); ctx.lineTo(W, H - 28.5); ctx.stroke();
    ctx.font = "500 10px Inter, sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    let x = 12;
    const y = H - 10;
    for (const it of items) {
      if (it.edge) {
        ctx.strokeStyle = it.color; ctx.lineWidth = 2;
        ctx.setLineDash(it.label === "same book" ? [4, 4] : []);
        ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x + 16, y - 4); ctx.stroke();
        ctx.setLineDash([]);
      } else {
        ctx.fillStyle = it.color;
        ctx.beginPath(); ctx.arc(x + 8, y - 4, 5, 0, 6.2832); ctx.fill();
        if (it.ring) {
          ctx.beginPath(); ctx.arc(x + 8, y - 4, 7.5, 0, 6.2832);
          ctx.setLineDash([3, 3]); ctx.strokeStyle = "rgba(123,104,181,.85)";
          ctx.lineWidth = 1.2; ctx.stroke(); ctx.setLineDash([]);
        }
      }
      ctx.fillStyle = dark ? "#B8B2A4" : "#6B6353";
      ctx.fillText(it.label, x + (it.edge ? 20 : 16), y - 4);
      x += (it.edge ? 20 : 16) + ctx.measureText(it.label).width + 14;
      if (x > W - 90) break; // wrap guard
    }
    ctx.textBaseline = "alphabetic";
  }

  /* A node is only useful if it takes you to the text. Passage nodes carry
     their own bbox, so opening one lands on the exact scanned block the
     embedding matched — the same jump a search result makes. */
  function openNode(n) {
    if (!n) return;
    if (n.kind === "concept") {
      if (typeof selectById === "function") selectById(n.cid, false);
      return;
    }
    if (n.kind !== "doc" && n.kind !== "passage") return;
    const isTxt = n.page == null || n.source === "txt";
    if (typeof Reader !== "undefined") {
      Reader.activeTerms = (lastQuery || "").toLowerCase().split(/[\s\-]+/).filter(t => t.length > 3);
    }
    if (isTxt) {
      if (typeof openTxtMode !== "function" || typeof Reader === "undefined") return;
      Reader.highlights = [];
      Reader.bookId = n.book; Reader.open = true; Reader.txtMode = false;
      Reader.pendingHighlight = { text: n.snippet || "", page: n.page };
      if (typeof showReaderShell === "function") showReaderShell();
      openTxtMode(n.book);
      return;
    }
    if (typeof openReader !== "function") return;
    const boxes = n.bbox_pts
      ? [{ book_id: n.book, page: n.page, bbox_pts: n.bbox_pts, concept_id: lastQuery, text: n.snippet }]
      : [];
    openReader(n.book, {
      page: n.page,
      highlight: n.bbox_pts ? { page: n.page, bbox_pts: n.bbox_pts, concept_id: lastQuery } : null,
      highlights: boxes,
    });
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
        if (clicked && !wasDrag) openNode(clicked);
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

  /* Shared hover card for 2D tooltips and 3D labels. */
  function tipHTML(n) {
    const head = n.kind === "passage" ? (n.cite || n.label) : n.label;
    const sub = n.kind === "passage"
      ? `${n.page != null ? `page ${n.page}` : "text edition"}${n.clusterLabel ? ` · ${esc(n.clusterLabel)}` : ""}`
      : n.kind === "concept" ? (n.def || "") : (n.snippet || "");
    const cons = (n.concepts || []).length
      ? `<div style="margin-top:4px;font:11px Inter,sans-serif;color:#B9A9C9">${n.concepts.map(c => esc(c.label)).join(" · ")}</div>` : "";
    return `<div style="font:600 12.5px Inter,sans-serif;color:#F6F1E5;background:#2E2A24;padding:6px 10px;border-radius:7px;max-width:280px;box-shadow:0 6px 20px rgba(0,0,0,.4)">
      ${esc(head)}
      ${sub ? `<div style="font:italic 11.5px Georgia;color:#CFC7B4;margin-top:3px">${esc(String(sub).slice(0, 150))}</div>` : ""}
      ${n.snippet && n.kind === "passage" ? `<div style="font:italic 11px Georgia;color:#B8B2A4;margin-top:4px">${esc(n.snippet.slice(0, 130))}…</div>` : ""}
      ${cons}
      <div style="margin-top:5px;font:10.5px Inter,sans-serif;color:#8B8375">click to open the source</div>
    </div>`;
  }

  /* 3D */
  function init3D() {
    const stage = $("dyngraph-stage");
    if (typeof ForceGraph3D === "undefined") { setView("2d"); return; }
    stage.innerHTML = ""; canvas = null; ctx = null;
    if (g3d) { try { g3d._destructor?.(); } catch {} g3d = null; }
    build();
    const dark3 = document.body.classList.contains("dark");
    g3d = new ForceGraph3D(stage, { controlType: "orbit" })
      .width(stage.clientWidth).height(stage.clientHeight)
      .backgroundColor(dark3 ? "#141310" : "#F6F1E5")
      .showNavInfo(false)
      .nodeRelSize(5).nodeResolution(26).linkResolution(6)
      .nodeOpacity(0.94)
      .nodeVal(n => Math.max(1, (n.r || 5) * (n.r || 5) * 0.05))
      .nodeColor(n => n.color)
      // strong links are drawn as moving particles, so the eye can follow
      // where the argument actually flows instead of reading a static hairball
      .linkDirectionalParticles(l => (l.w > 0.85 ? 2 : 0))
      .linkDirectionalParticleWidth(1.4)
      .linkDirectionalParticleSpeed(0.006)
      .nodeLabel(n => tipHTML(n))
      .linkColor(l => rcol(l.r))
      .linkWidth(l => 0.3 + (l.w || 0.4) * 2.2)
      .linkOpacity(dark3 ? 0.5 : 0.38)
      .onNodeHover((n) => { stage.style.cursor = n ? "pointer" : "default"; })
      .onNodeClick((n) => openNode(n));
    /* Label sprites. Labelling every node produced a wall of overlapping
       text that hid the graph it was describing, so only the nodes that
       carry the reading get one: the query, the concepts, and the strongest
       passage in each cluster plus the overall top few. */
    if (window.Atlas3D && window.Atlas3D.makeLabel) {
      const { makeLabel } = window.Atlas3D;
      const labelled = new Set();
      const passages = nodes.filter(n => n.kind === "passage" || n.kind === "doc");
      const bestPerCluster = new Map();
      for (const n of passages) {
        const k = n.cluster ?? "_";
        const cur = bestPerCluster.get(k);
        if (!cur || (n.score || 0) > (cur.score || 0)) bestPerCluster.set(k, n);
      }
      for (const n of bestPerCluster.values()) labelled.add(n.id);
      passages.slice().sort((a, b) => (b.score || 0) - (a.score || 0))
        .slice(0, 6).forEach(n => labelled.add(n.id));
      for (const n of nodes) if (n.kind === "query" || n.kind === "concept") labelled.add(n.id);
      g3d.nodeThreeObjectExtend(true)
        .nodeThreeObject((n) => {
          if (!labelled.has(n.id)) return null;
          const dark = document.body.classList.contains("dark");
          const spr = makeLabel(
            n.label.length > 34 ? n.label.slice(0, 33) + "…" : n.label,
            dark ? "#EFE9DC" : "#2E2A24",
            n.kind === "query" ? 9 : 7,
            dark ? "rgba(20,19,16,0.88)" : "rgba(246,241,229,0.92)",
          );
          spr.position.set(0, (n.r || 5) + 6, 0);
          return spr;
        });
    }
    g3d.graphData({ nodes: nodes.map(n => ({ ...n })), links: links.map(l => ({ source: l.s, target: l.t, r: l.r, w: l.w })) });
    window.__dynG3D = g3d; // for live theme switching
    // fit twice: once when the force layout has roughly settled, again once
    // it has actually stopped, or the graph ends up half off-screen
    setTimeout(() => { try { g3d.zoomToFit(600, 60); } catch { /* not ready */ } }, 1600);
    setTimeout(() => { try { g3d.zoomToFit(800, 60); } catch { /* not ready */ } }, 4200);
  }

  // theme.js calls this so a live 2D graph repaints on a theme flip
  window.redrawDynGraph = () => { if (running && view === "2d" && ctx) draw(); };
  window.openDynGraph = open;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
