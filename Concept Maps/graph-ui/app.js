/* Concept Atlas — force-directed concept graph (canvas + d3-force) */
"use strict";

/* ————————— state ————————— */
const S = {
  data: null,
  byId: new Map(),
  nodes: [],            // master node objects (sim mutates x/y)
  edges: [],            // {s,t,r,w} id refs
  adj: new Map(),       // id -> Map(id -> edge)
  // filters
  catsOn: new Set(),
  writersOn: new Set(),   // empty = every group; else "women"|"men"|"joint"|"unattributed"
  conceptWriters: new Map(),  // concept id -> Set of groups that wrote its evidence
  minImp: 0,
  minStr: 0,
  cluster: true,
  labels: "standard",
  // view
  t: { k: 1, x: 0, y: 0 },
  // interaction
  hovered: null,
  selected: null,
  dragging: null,
  panning: false,
  query: null,          // {id,text,top:[{node,rel,rank}]}
  egoDepth: 0,          // 0 = full graph, 1/2 = isolate 1-/2-hop neighborhood of selection
  // sim
  sim: null,
  simNodes: [],
  simEdges: [],
  quad: null,
  // render
  dirty: true,
  fitted: false,
  w: 0, h: 0, dpr: 1,
  baseLabelCount: 30,
  // view mode
  mode: "2d",
  g3d: null,          // ForceGraph3D instance
  g3dNodes: [],
  g3dLinks: [],
};

const POS_REL = new Set(["supports","requires","entails","underlies","develops_from","exemplifies","subsumes","influences"]);
const NEG_REL = new Set(["opposes","contrasts_with"]);
const REL_ORDER = ["supports","requires","opposes","contrasts_with","underlies","entails","exemplifies","subsumes","develops_from","influences"];
const REL_COLOR = { pos: "#3E6B52", neg: "#A03A31", neu: "#6B6353" };
// per-relation visual language: color + dash + width multiplier (user asked: differentiable everywhere)
const REL_STYLE = {
  supports:       { color: "#3E6B52", dash: [],        wmul: 1.25, desc: "supports" },
  requires:       { color: "#2E7D74", dash: [],        wmul: 1.15, desc: "requires" },
  entails:        { color: "#2F5D3A", dash: [],        wmul: 1.20, desc: "entails" },
  underlies:      { color: "#7A7A3A", dash: [7,4],     wmul: 1.0,  desc: "underlies" },
  develops_from:  { color: "#4E6BA7", dash: [10,4],    wmul: 1.0,  desc: "develops from" },
  influences:     { color: "#6A9AC7", dash: [2,4],     wmul: 0.9,  desc: "influences" },
  exemplifies:    { color: "#9C9484", dash: [3,4],     wmul: 0.85, desc: "exemplifies" },
  subsumes:       { color: "#7B68B5", dash: [12,4,2,4],wmul: 1.0,  desc: "subsumes" },
  opposes:        { color: "#A03A31", dash: [],        wmul: 1.5,  desc: "opposes" },
  contrasts_with: { color: "#C0663A", dash: [6,3],     wmul: 1.1,  desc: "contrasts with" },
};
function relStyle(rel) { return REL_STYLE[rel] || { color: "#8B8375", dash: [], wmul: 1.0, desc: rel || "related" }; }

const canvas = document.getElementById("graph");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("tooltip");
const detail = document.getElementById("detail");

/* ————————— helpers ————————— */
const $ = (id) => document.getElementById(id);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function nodeRadius(n) {
  return 4 + n.importance * 9 + Math.min(n.degree, 25) * 0.22;
}
function polarity(rel) { return POS_REL.has(rel) ? "pos" : NEG_REL.has(rel) ? "neg" : "neu"; }

function isVisible(n) {
  if (!S.catsOn.has(n.top) || n.importance < S.minImp) return false;
  if (S.writersOn.size) {
    const g = S.conceptWriters.get(n.id);
    if (!g) return false;                     // no evidence, so no author
    let any = false;
    for (const w of S.writersOn) if (g.has(w)) { any = true; break; }
    if (!any) return false;
  }
  return true;
}

/* Which groups of writers each concept's evidence comes from.

   The concept map records the book behind every piece of evidence, and the
   author registry says who wrote each book, so the join says which parts of
   the map each group actually reaches — 99 of 202 concepts for the women in
   this corpus, 13 of which no male-authored book here touches. Computed once,
   after the registry has loaded. */
async function buildConceptWriters() {
  if (!window.Authors) return;
  await Authors.load();
  const ev = (S.data && S.data.evidence) || {};
  S.conceptWriters = new Map();
  for (const [cid, rows] of Object.entries(ev)) {
    const set = new Set();
    for (const r of rows || []) {
      if (r.book_id) set.add(Authors.groupOfBook(r.book_id));
    }
    if (set.size) S.conceptWriters.set(cid, set);
  }
  renderWriterFilter();
}

const WRITER_ORDER = ["women", "men", "joint", "unattributed"];

function renderWriterFilter() {
  const host = document.getElementById("writer-list");
  if (!host) return;
  const counts = new Map();
  for (const g of S.conceptWriters.values()) {
    for (const w of g) counts.set(w, (counts.get(w) || 0) + 1);
  }
  const groups = WRITER_ORDER.filter(w => counts.has(w));
  if (!groups.length) { host.innerHTML = '<p class="hint">registry unavailable</p>'; return; }
  const label = (w) => (window.Authors && Authors.GROUP[w] ? Authors.GROUP[w].label : w);
  const colour = (w) => (window.Authors && Authors.GROUP[w] ? Authors.GROUP[w].color : "#948B7B");
  host.innerHTML = groups.map(w => `
    <label class="witem${S.writersOn.has(w) ? " on" : ""}" data-w="${w}">
      <span class="wdot" style="background:${colour(w)}"></span>
      <span class="wname">${label(w)}</span>
      <span class="wcount">${counts.get(w)}</span>
    </label>`).join("") +
    `<div class="row-mini"><button id="writers-all" class="mini">all</button></div>`;
  host.querySelectorAll(".witem").forEach(el => {
    el.onclick = () => {
      const w = el.dataset.w;
      S.writersOn.has(w) ? S.writersOn.delete(w) : S.writersOn.add(w);
      renderWriterFilter();
      applyFilters(0.35);
    };
  });
  const all = document.getElementById("writers-all");
  if (all) all.onclick = () => { S.writersOn.clear(); renderWriterFilter(); applyFilters(0.35); };

  const val = document.getElementById("writer-val");
  if (val) val.textContent = S.writersOn.size
    ? [...WRITER_ORDER].filter(w => S.writersOn.has(w)).map(label).join(" + ")
    : "all";

  // when exactly one group is chosen, say what is unique to it
  const note = document.getElementById("writer-note");
  if (note) {
    if (S.writersOn.size !== 1) { note.textContent = ""; note.classList.add("hidden"); }
    else {
      const only = [...S.writersOn][0];
      let unique = 0;
      for (const g of S.conceptWriters.values()) {
        if (g.has(only) && g.size === 1) unique++;
      }
      note.textContent = `${counts.get(only)} concepts, ${unique} reached by no other group.`;
      note.classList.remove("hidden");
    }
  }
}
function edgeVisible(e) {
  const a = S.byId.get(e.s), b = S.byId.get(e.t);
  return a && b && isVisible(a) && isVisible(b) && e.w >= S.minStr;
}
function neighborsOf(n) {
  const out = new Set();
  const m = S.adj.get(n.id);
  if (m) for (const id of m.keys()) out.add(id);
  return out;
}

/* ————————— data load ————————— */
async function init() {
  try {
    const res = await fetch("data/graph-data.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    S.data = await res.json();
  } catch (err) {
    $("status-text").textContent = "Failed to load data: " + err.message;
    return;
  }
  const d = S.data;
  // counts come from the data so the chrome cannot drift out of step with it
  // (the queries badge said 43 for a 42-query set)
  $("stat-nodes").textContent = d.meta.nodes;
  $("stat-edges").textContent = d.meta.edges;
  const nq = (d.queries || []).length;
  for (const id of ["stat-queries", "stat-queries-2"]) {
    const el = $(id);
    if (el) el.textContent = nq;
  }
  for (const n of d.nodes) { S.byId.set(n.id, n); n.color = d.colors[n.top] || "#79706E"; }
  S.nodes = d.nodes;
  S.edges = d.edges;
  // adjacency
  for (const n of d.nodes) S.adj.set(n.id, new Map());
  for (const e of d.edges) {
    S.adj.get(e.s)?.set(e.t, e);
    S.adj.get(e.t)?.set(e.s, e);
  }
  // base label ranking: importance + degree
  const maxDeg = Math.max(1, ...d.nodes.map(n => n.degree));
  for (const n of d.nodes) n._score = n.importance * 0.65 + (n.degree / maxDeg) * 0.35;
  const ranked = [...d.nodes].sort((a, b) => b._score - a._score);
  ranked.forEach((n, i) => n._labelRank = i);

  for (const c of d.categories) S.catsOn.add(c.name);

  // slider ranges follow the observed data ranges (importance 0.73–0.96, strength 0.55–0.97)
  S.impMin = Math.min(...d.nodes.map(n => n.importance));
  S.impMax = Math.max(...d.nodes.map(n => n.importance));
  S.strMin = Math.min(...d.edges.map(e => e.w));
  S.strMax = Math.max(...d.edges.map(e => e.w));

  buildSidebar();
  buildQueries();
  // needs the author registry, so it paints itself when that resolves rather
  // than holding up the first frame of the graph
  buildConceptWriters();
  $("imp-val").textContent = "≥ " + (S.impMin - 0.001).toFixed(2);
  $("str-val").textContent = "≥ " + (S.strMin - 0.001).toFixed(2);
  resize();
  rebuildSim(1.0);
  bindEvents();
  requestAnimationFrame(tick);
  $("status-text").textContent = "laying out graph…";
}

/* ————————— simulation ————————— */
function rebuildSim(alpha) {
  const vis = S.nodes.filter(isVisible);
  const idset = new Set(vis.map(n => n.id));
  const evis = S.edges.filter(e => e.w >= S.minStr && idset.has(e.s) && idset.has(e.t));

  S.simNodes = vis;
  S.simEdges = evis.map(e => ({ source: S.byId.get(e.s), target: S.byId.get(e.t), r: e.r, w: e.w }));

  if (S.sim) S.sim.stop();
  // spread factor: user-controlled extra spacing (⤢ spread button)
  const spread = S.spread || 1;
  const sim = d3.forceSimulation(S.simNodes)
    .force("link", d3.forceLink(S.simEdges).id(n => n.id)
      .distance(l => (68 + (1 - l.w) * 68) * spread)
      .strength(l => clamp(0.2 + l.w * 0.55, 0, 0.85)))
    .force("charge", d3.forceManyBody().strength(n => (-150 - n.importance * 220) * spread))
    .force("collide", d3.forceCollide().radius(n => nodeRadius(n) + 9 * spread).iterations(2))
    .velocityDecay(0.4)
    .alpha(alpha)
    .on("tick", () => { S.dirty = true; });

  applyClusterForces(sim);
  S.sim = sim;
  S.quad = null; // (kept for compat; hitQuad rebuilds fresh each call)
  updateStatus();
}

function applyClusterForces(sim) {
  // remove old x/y forces
  sim.force("cx", null);
  if (S.cluster) {
    const cats = S.data.categories.filter(c => S.catsOn.has(c.name));
    const R = 430 * (S.spread || 1);
    const pos = new Map();
    cats.forEach((c, i) => {
      const a = (i / Math.max(cats.length, 1)) * Math.PI * 2 - Math.PI / 2;
      pos.set(c.name, [Math.cos(a) * R, Math.sin(a) * R * 0.82]);
    });
    sim.force("cx", d3.forceX(n => (pos.get(n.top) || [0, 0])[0]).strength(0.045));
    sim.force("cy", d3.forceY(n => (pos.get(n.top) || [0, 0])[1]).strength(0.045));
    sim.force("x", null); sim.force("y", null);
  } else {
    sim.force("x", d3.forceX(0).strength(0.02));
    sim.force("y", d3.forceY(0).strength(0.02));
    sim.force("cx", null); sim.force("cy", null);
  }
}

function hitQuad() {
  // rebuild fresh: node positions change while the simulation runs
  return d3.quadtree(S.simNodes, n => n.x, n => n.y);
}

/* ————————— canvas ————————— */
function resize() {
  const stage = $("stage");
  S.w = stage.clientWidth; S.h = stage.clientHeight;
  S.dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(S.w * S.dpr);
  canvas.height = Math.round(S.h * S.dpr);
  S.dirty = true;
}

function tick() {
  if (S.mode === "3d") { requestAnimationFrame(tick); return; }
  if (S.dirty) { draw(); S.dirty = false; }
  requestAnimationFrame(tick);
}

/* ————————— filter dispatch (2D sim vs 3D graph) ————————— */
function applyFilters(alpha = 0.35) {
  if (S.mode === "3d") rebuild3DData();
  else rebuildSim(alpha);
}

function currentLabelSet() {
  const vis = S.simNodes;
  const k = S.t.k;
  const zoomBoost = clamp(k, 1, 2.6);
  const base = { few: 14, standard: 30, all: 90 }[S.labels] ?? 30;
  const count = Math.min(vis.length, Math.round(base * zoomBoost));
  const set = new Set();
  const ranked = vis.slice().sort((a, b) => a._labelRank - b._labelRank);
  for (let i = 0; i < count; i++) set.add(ranked[i].id);
  // always label focus nodes
  if (S.hovered) { set.add(S.hovered.id); for (const id of neighborsOf(S.hovered)) set.add(id); }
  if (S.selected) { set.add(S.selected.id); for (const id of neighborsOf(S.selected)) set.add(id); }
  if (S.query) for (const q of S.query.top) set.add(q.node.id);
  return set;
}

function draw() {
  const { w, h, dpr, t } = S;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // parchment (light) / slate (dark) field with soft vignette
  const dark = document.body.classList.contains("dark");
  ctx.fillStyle = dark ? "#1E1C18" : "#F6F1E5";
  ctx.fillRect(0, 0, w, h);
  const g = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.35, w / 2, h / 2, Math.max(w, h) * 0.75);
  if (dark) {
    g.addColorStop(0, "rgba(255,255,255,0.03)");
    g.addColorStop(1, "rgba(0,0,0,0.25)");
  } else {
    g.addColorStop(0, "rgba(255,255,255,0.20)");
    g.addColorStop(1, "rgba(120,105,80,0.10)");
  }
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  ctx.translate(t.x, t.y);
  ctx.scale(t.k, t.k);

  const nodes = S.simNodes;
  const edges = S.simEdges;
  const focus = S.selected || S.hovered;
  const focusNb = focus ? neighborsOf(focus) : null;
  const qTop = S.query ? new Set(S.query.top.map(q => q.node.id)) : null;
  const labels = currentLabelSet();
  const ego = egoSet();

  /* edges */
  for (const e of edges) {
    const a = e.source, b = e.target;
    if (a.x == null || b.x == null) continue;
    if (ego && (!ego.has(a.id) || !ego.has(b.id))) continue;
    const rs = relStyle(e.r);
    let alpha = 0.34, width = (0.5 + e.w * 1.2) * rs.wmul, color = rs.color;
    // zoom-adaptive edge fading: zoomed in (k>1.4) → edges fade so nodes read;
    // zoomed out (k<0.7) → edges fade too (too dense at distance); sweet spot ~1
    const kf = S.t.k;
    if (kf > 1.4) alpha *= Math.max(0.12, 1 - (kf - 1.4) * 0.55);   // deep zoom: strong fade
    else if (kf < 0.7) alpha *= Math.max(0.15, 0.4 + kf * 0.6);      // far out: thin the mesh
    if (S.query) {
      const inQ = qTop.has(a.id) && qTop.has(b.id);
      alpha = inQ ? 0.75 : 0.04;
      if (inQ) { color = "#7A6A50"; width *= 1.4; }
    } else if (focus) {
      const inc = (a.id === focus.id || b.id === focus.id);
      if (inc) {
        const foc = S.adj.get(focus.id)?.get(a.id === focus.id ? b.id : a.id);
        const r2 = relStyle(foc?.r || e.r);
        alpha = 0.9; width = (1.1 + e.w * 1.8) * r2.wmul;
        color = r2.color;
      } else if (focusNb && (focusNb.has(a.id) && focusNb.has(b.id))) {
        alpha = 0.22;
      } else {
        alpha = 0.03;
      }
    }
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.setLineDash(relStyle(e.r).dash);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    ctx.setLineDash([]);
    // store screen-space segment for edge click hit-testing
    // (matches draw(): translate(t.x,t.y) then scale(k))
    e._sx1 = a.x * t.k + t.x; e._sy1 = a.y * t.k + t.y;
    e._sx2 = b.x * t.k + t.x; e._sy2 = b.y * t.k + t.y;
  }
  ctx.globalAlpha = 1;

  /* nodes */
  for (const n of nodes) {
    if (n.x == null) continue;
    if (ego && !ego.has(n.id)) continue;
    const r = nodeRadius(n);
    let alpha = 1;
    if (S.query) {
      alpha = qTop.has(n.id) ? 1 : 0.13;
    } else if (focus) {
      alpha = (n === focus || focusNb.has(n.id)) ? 1 : 0.15;
    }
    ctx.globalAlpha = alpha;
    // halo (theme-aware: parchment in light, dark card in dark mode)
    ctx.beginPath();
    ctx.arc(n.x, n.y, r + 1.6, 0, Math.PI * 2);
    ctx.fillStyle = document.body.classList.contains("dark")
      ? "rgba(38,35,30,0.95)" : "rgba(251,248,240,0.9)";
    ctx.fill();
    // body
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = n.color;
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = document.body.classList.contains("dark")
      ? "rgba(232,226,213,0.25)" : "rgba(46,42,36,0.35)";
    ctx.stroke();

    if (n === S.selected || n === S.hovered) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 4.5, 0, Math.PI * 2);
      ctx.strokeStyle = n === S.selected ? "#2E2A24" : "rgba(46,42,36,0.5)";
      ctx.lineWidth = n === S.selected ? 1.8 : 1.3;
      ctx.stroke();
    }
    if (S.query && qTop.has(n.id)) {
      const q = S.query.top.find(q => q.node === n);
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2);
      ctx.strokeStyle = "#8A3B32";
      ctx.lineWidth = 1.6;
      ctx.stroke();
      if (q && q.rank <= 10) {
        ctx.beginPath();
        ctx.arc(n.x + r * 0.75, n.y - r * 0.75, 7.5, 0, Math.PI * 2);
        ctx.fillStyle = "#8A3B32";
        ctx.fill();
        ctx.fillStyle = document.body.classList.contains("dark") ? "#1E1C18" : "#F6F1E5";
        ctx.font = "600 9.5px Inter, sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(String(q.rank), n.x + r * 0.75, n.y - r * 0.75 + 0.5);
      }
    }
  }
  ctx.globalAlpha = 1;

  /* labels — collision-culled.
     202 concepts in one cluster produced overprinted text ("Moral
     Obligat|Reward and Punishment"). Labels are laid out in importance order
     and any that would overlap an already-placed label, or a node circle,
     is dropped rather than drawn on top of it. Focused/selected/query nodes
     are placed first so they always survive the cull. */
  ctx.font = "500 11px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const darkMode = document.body.classList.contains("dark");
  const boxes = [];
  for (const n of nodes) {
    if (n.x == null) continue;
    const r = nodeRadius(n);
    boxes.push({ x: n.x - r, y: n.y - r, w: r * 2, h: r * 2 });
  }
  const overlaps = (b) => boxes.some(o =>
    b.x < o.x + o.w && b.x + b.w > o.x && b.y < o.y + o.h && b.y + b.h > o.y);
  const pri = (n) => (n === focus ? 4 : qTop?.has(n.id) ? 3 : focusNb?.has(n.id) ? 2 : 0);
  const cands = nodes
    .filter(n => labels.has(n.id) && n.x != null && !(ego && !ego.has(n.id)))
    .sort((a, b) => pri(b) - pri(a) || a._labelRank - b._labelRank);
  for (const n of cands) {
    const r = nodeRadius(n);
    const w = ctx.measureText(n.label).width, y = n.y + r + 3;
    const box = { x: n.x - w / 2 - 2, y: y - 1, w: w + 4, h: 13 };
    const must = pri(n) >= 3;
    if (!must && overlaps(box)) continue;
    boxes.push(box);
    let alpha = 0.92;
    if (S.query && !qTop.has(n.id)) alpha = 0.25;
    else if (focus && n !== focus && !focusNb.has(n.id)) alpha = 0.22;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = 3;
    ctx.strokeStyle = darkMode ? "rgba(30,28,24,0.9)" : "rgba(246,241,229,0.85)";
    ctx.strokeText(n.label, n.x, y);
    ctx.fillStyle = darkMode ? "#E8E2D5" : "#3A352C";
    ctx.fillText(n.label, n.x, y);
  }
  ctx.globalAlpha = 1;
}

/* ————————— view transforms ————————— */
function toGraph(px, py) {
  return { x: (px - S.t.x) / S.t.k, y: (py - S.t.y) / S.t.k };
}
function fitView(nodes = S.simNodes, animate = true) {
  if (!nodes.length) return;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const n of nodes) {
    if (n.x == null) continue;
    x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y);
    x1 = Math.max(x1, n.x); y1 = Math.max(y1, n.y);
  }
  if (x0 === Infinity) return;
  const pad = 70;
  const bw = (x1 - x0) + pad * 2, bh = (y1 - y0) + pad * 2;
  const k = clamp(Math.min(S.w / bw, S.h / bh), 0.15, 1.7);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const target = { k, x: S.w / 2 - cx * k, y: S.h / 2 - cy * k };
  if (animate) animateTo(target); else { S.t = target; S.dirty = true; }
}
function animateTo(target, ms = 420) {
  const from = { ...S.t };
  const t0 = performance.now();
  function step(now) {
    const p = clamp((now - t0) / ms, 0, 1);
    const e = 1 - Math.pow(1 - p, 3);
    S.t = {
      k: from.k + (target.k - from.k) * e,
      x: from.x + (target.x - from.x) * e,
      y: from.y + (target.y - from.y) * e,
    };
    S.dirty = true;
    updateStatus();
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
function zoomBy(factor) {
  const k2 = clamp(S.t.k * factor, 0.12, 6);
  const cx = S.w / 2, cy = S.h / 2;
  const ratio = k2 / S.t.k;
  animateTo({ k: k2, x: cx - (cx - S.t.x) * ratio, y: cy - (cy - S.t.y) * ratio }, 180);
}

/* ————————— 3D view (ForceGraph3D) ————————— */
function ensure3DLibs() {
  // labels3d.mjs (ES module) may still be loading; wait up to 4s
  return new Promise((resolve) => {
    if (window.Atlas3D) return resolve(true);
    const t0 = Date.now();
    const iv = setInterval(() => {
      if (window.Atlas3D) { clearInterval(iv); resolve(true); }
      else if (Date.now() - t0 > 4000) { clearInterval(iv); resolve(false); }
    }, 100);
  });
}

function nodeColor3D(n) {
  if (S.query) {
    return S.query.topIds.has(n.id) ? "#8A3B32" : "rgba(186,178,160,0.30)";
  }
  if (S.selected) {
    if (n.id === S.selected.id) return "#2E2A24";
    if (S.adj.get(S.selected.id)?.has(n.id)) return n.color;
    return "rgba(186,178,160,0.22)";
  }
  return n.color;
}
function linkColor3D(l) {
  const r = l.r || l.rel;
  if (S.query) return (S.query.topIds.has(l.source.id || l.source) && S.query.topIds.has(l.target.id || l.target)) ? "#8A3B32" : "rgba(150,142,124,0.14)";
  if (S.selected) {
    const sid = S.selected.id;
    const s = l.source.id || l.source, t = l.target.id || l.target;
    if (s === sid || t === sid) return relStyle(r).color;
    return "rgba(150,142,124,0.10)";
  }
  return relStyle(r).color;
}

function labelSet3D() {
  const set = new Set();
  // 36 labels in a 202-node cloud overlapped into an unreadable slab; the
  // hover card carries the detail, so the sprites only need to orient you
  for (const n of S.g3dNodes) if (n._labelRank < 18) set.add(n.id);
  if (S.query) for (const q of S.query.top) set.add(q.node.id);
  if (S.selected) { set.add(S.selected.id); for (const id of neighborsOf(S.selected)) set.add(id); }
  return set;
}

/* ego-neighborhood of the selection up to S.egoDepth hops; null when off */
function egoSet() {
  if (!S.egoDepth || !S.selected) return null;
  const seen = new Set([S.selected.id]);
  let frontier = [S.selected.id];
  for (let d = 0; d < S.egoDepth && frontier.length; d++) {
    const next = [];
    for (const id of frontier) {
      const n = S.byId.get(id);
      if (!n) continue;
      for (const nid of neighborsOf(n)) {
        if (!seen.has(nid)) { seen.add(nid); next.push(nid); }
      }
    }
    frontier = next;
  }
  return seen;
}

function rebuild3DData() {
  if (!S.g3d) return;
  const eg = egoSet();
  const vis = S.nodes.filter(n => isVisible(n) && (!eg || eg.has(n.id)));
  const idset = new Set(vis.map(n => n.id));
  const links = S.edges
    .filter(e => e.w >= S.minStr && idset.has(e.s) && idset.has(e.t))
    .map(e => ({ source: e.s, target: e.t, r: e.r, w: e.w }));
  // carry positions across rebuilds; give new nodes a random z
  const prev = new Map(S.g3dNodes.map(n => [n.id, n]));
  for (const n of vis) {
    if (n.z == null || !prev.has(n.id)) {
      if (n.x == null) { n.x = (Math.random() - 0.5) * 300; n.y = (Math.random() - 0.5) * 300; }
      n.z = (Math.random() - 0.5) * 200;
    }
  }
  S.g3dNodes = vis;
  S.g3dLinks = links;
  S.g3d.graphData({ nodes: vis, links });
  apply3DCluster();
  updateStatus();
}

function apply3DCluster() {
  const G = S.g3d;
  if (!G) return;
  // The internal d3 simulation only exists after the engine digests graphData.
  // Configuring forces synchronously right after graphData() breaks the
  // animation cycle (verified: deferred config works). Defer until first tick.
  let done = false;
  const configure = () => {
    if (done || !S.g3d) return;
    done = true;
    try {
      G.d3Force("charge").strength(-230 * (S.spread || 1));
      G.d3Force("link").distance(l => (74 + (1 - l.w) * 76) * (S.spread || 1)).strength(l => clamp(0.15 + l.w * 0.5, 0, 0.8));
      if (S.cluster) {
        const cats = S.data.categories.filter(c => S.catsOn.has(c.name));
        // fibonacci sphere placement of category centroids
        const pos = new Map();
        const N = Math.max(cats.length, 1);
        const R = 300;
        const ga = Math.PI * (3 - Math.sqrt(5));
        cats.forEach((c, i) => {
          const y = 1 - (i + 0.5) / N;
          const r = Math.sqrt(1 - y * y);
          const th = ga * i;
          pos.set(c.name, { x: Math.cos(th) * r * R, y: y * R * 0.8, z: Math.sin(th) * r * R });
        });
        G.d3Force("cluster", (alpha) => {
          for (const n of S.g3dNodes) {
            const p = pos.get(n.top);
            if (!p) continue;
            n.vx += (p.x - n.x) * 0.05 * alpha;
            n.vy += (p.y - n.y) * 0.05 * alpha;
            n.vz += (p.z - n.z) * 0.05 * alpha;
          }
        });
      } else {
        G.d3Force("cluster", null);
      }
      G.d3ReheatSimulation();
    } catch (err) {
      console.error("3D force config failed:", err);
    }
  };
  G.onEngineTick(configure);
  setTimeout(configure, 900); // fallback if no tick fires
}

function update3DColors() {
  if (!S.g3d || S.mode !== "3d") return;
  // defer: recreating Three objects inside a pointer-event handler can race
  // the controls' own listeners (observed one-off .x TypeError)
  setTimeout(() => {
    if (!S.g3d || S.mode !== "3d") return;
    try {
      S.g3d.nodeColor(S.g3d.__colorFn).linkColor(S.g3d.__linkFn).refresh();
    } catch (err) { console.warn("3D refresh failed:", err); }
  }, 0);
}

function focus3D(n) {
  if (!S.g3d || n.x == null) return;
  const d = 200;
  S.g3d.cameraPosition(
    { x: n.x + d * 0.55, y: n.y + d * 0.35, z: n.z + d },
    { x: n.x, y: n.y, z: n.z },
    700
  );
}

function zoom3D(factor) {
  if (!S.g3d) return;
  const c = S.g3d.cameraPosition();
  const f = factor;
  S.g3d.cameraPosition({ x: c.x * f, y: c.y * f, z: c.z * f }, { x: 0, y: 0, z: 0 }, 220);
}

async function initGraph3D() {
  if (S.g3d) return true;
  const hasLibs = await ensure3DLibs();
  try {
    const G = new ForceGraph3D($("graph3d"), { controlType: "orbit" })
      .width($("stage").clientWidth)
      .height($("stage").clientHeight)
      .backgroundColor(document.body.classList.contains("dark") ? "#141310" : "#F6F1E5")
      .showNavInfo(false)
      .nodeRelSize(3.6)
      .nodeVal(n => 1.5 + n.importance * 9)
      .nodeOpacity(0.95)
      .nodeResolution(28)   // smooth spheres, not faceted polyhedra
      .linkResolution(6)    // smooth link cylinders
      // fog gives the cloud depth: near concepts read as near
      .linkCurvature(l => (l.r === "opposes" || l.r === "contrasts_with") ? 0.12 : 0)
      .nodeLabel(n => `<div style="font:600 13px Inter,sans-serif;color:#F6F1E5">${esc(n.label)}</div>
        <div style="font:11px Inter,sans-serif;color:#CFC7B4">${esc(n.top)}${n.sub ? " › " + esc(n.sub) : ""} · importance ${n.importance.toFixed(2)}</div>
        ${n.definition ? `<div style="font:italic 12px 'EB Garamond',serif;color:#E4DCC8;max-width:260px;margin-top:4px">${esc(n.definition.slice(0, 180))}…</div>` : ""}`)
      .linkWidth(l => (0.4 + (l.w || 0.5) * 2.0) * relStyle(l.r).wmul)
      .linkOpacity(document.body.classList.contains("dark") ? 0.5 : 0.36)
      .linkDirectionalParticles(l => (l.r === "opposes" || l.r === "contrasts_with") ? 1 : 0)
      .linkDirectionalParticleWidth(1.6)
      .cooldownTicks(360)
      .onNodeClick((n) => { selectNode(n); })
      .onLinkClick((l) => {
        try {
          selectEdge({ s: l.source.id || l.source, t: l.target.id || l.target, r: l.r, w: l.w });
        } catch (err) { console.warn("3D edge select failed:", err); }
      })
      .onNodeHover((n) => { $("graph3d").style.cursor = n ? "pointer" : "default"; });
    G.__colorFn = nodeColor3D;
    G.__linkFn = linkColor3D;
    G.nodeColor(nodeColor3D).linkColor(linkColor3D);
    // labels via vendored three (optional — degrades gracefully)
    if (hasLibs) {
      const { makeLabel } = window.Atlas3D;
      G.nodeThreeObjectExtend(true)
        .nodeThreeObject((n) => {
          if (!labelSet3D().has(n.id)) return null;
          const dimmed =
            (S.query && !S.query.topIds.has(n.id)) ||
            (S.selected && n.id !== S.selected.id && !S.adj.get(S.selected.id)?.has(n.id));
          const r = 3.6 * Math.cbrt(1.5 + n.importance * 9);
          const dark = document.body.classList.contains("dark");
          const spr = makeLabel(
            n.label,
            dimmed ? (dark ? "#7E776A" : "#B7AF9C") : (dark ? "#EFE9DC" : "#2E2A24"),
            11,
            dark ? "rgba(20,19,16,0.88)" : "rgba(246,241,229,0.92)",
          );
          spr.position.set(0, r + 6, 0);
          return spr;
        });
    }
    S.g3d = G;
    return true;
  } catch (err) {
    console.error("3D init failed:", err);
    $("status-text").textContent = "3D unavailable (WebGL?): " + err.message;
    return false;
  }
}

async function setMode(mode) {
  if (mode === S.mode) return;
  if (mode === "3d") {
    const ok = await initGraph3D();
    if (!ok) return;
    S.mode = "3d";
    if (S.sim) { S.sim.stop(); S.sim.alpha(0); }
    $("btn-3d").classList.add("active");
    $("btn-2d").classList.remove("active");
    canvas.classList.add("hidden");
    tooltip.classList.add("hidden");
    $("graph3d").classList.remove("hidden");
    rebuild3DData();
    updateStatus();
    // the force layout is still spreading at 3s, so a single fit leaves the
    // cloud small in the middle of an empty stage
    setTimeout(() => { if (S.g3d && S.mode === "3d") S.g3d.zoomToFit(700, 50); }, 3200);
    setTimeout(() => { if (S.g3d && S.mode === "3d") S.g3d.zoomToFit(900, 50); }, 7000);
  } else {
    S.mode = "2d";
    $("btn-2d").classList.add("active");
    $("btn-3d").classList.remove("active");
    $("graph3d").classList.add("hidden");
    canvas.classList.remove("hidden");
    if (S.g3d) S.g3d.pauseAnimation();
    rebuildSim(0.4);
    S.fitted = true; // don't auto-fit again
    updateStatus();
  }
}

/* ————————— hit testing ————————— */
function pickNode(px, py) {
  const p = toGraph(px, py);
  const quad = hitQuad();
  let best = null, bestD = Infinity;
  quad.visit((node, x0, y0, x1, y1) => {
    if (!node.length) {
      // leaf: linked list of wrapped data nodes
      let leaf = node;
      do {
        const n = leaf.data;
        if (n && n.x != null) {
          const d = Math.hypot(n.x - p.x, n.y - p.y);
          if (d < nodeRadius(n) + 4 && d < bestD) { bestD = d; best = n; }
        }
        leaf = leaf.next;
      } while (leaf);
    }
    return x0 > p.x + 60 || x1 < p.x - 60 || y0 > p.y + 60 || y1 < p.y - 60;
  });
  return best;
}

/* ————————— events ————————— */
function bindEvents() {
  /* The stage resizes without the window doing so: opening the detail panel,
     the compare overlay, or a split view all narrow it. Watching only
     window.resize left the canvas backing store at its old width while the
     CSS width shrank, so the bitmap was stretched non-uniformly and every
     node circle rendered as an oval. A ResizeObserver catches all of it. */
  const onStageResize = () => {
    resize();
    if (S.g3d) S.g3d.width($("stage").clientWidth).height($("stage").clientHeight);
  };
  window.addEventListener("resize", onStageResize);
  if (window.ResizeObserver) {
    let raf = 0;
    new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(onStageResize);   // coalesce transition frames
    }).observe($("stage"));
  }

  /* canvas pointer */
  let downPos = null, moved = false;
  canvas.addEventListener("pointerdown", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const px = ev.clientX - rect.left, py = ev.clientY - rect.top;
    const n = pickNode(px, py);
    downPos = { px, py }; moved = false;
    if (n) {
      S.dragging = n;
      n.fx = n.x; n.fy = n.y;
      S.sim.alphaTarget(0.25).restart();
      canvas.classList.add("grabbing");
    } else {
      S.panning = true;
      canvas.classList.add("grabbing");
    }
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener("pointermove", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const px = ev.clientX - rect.left, py = ev.clientY - rect.top;
    if (S.dragging) {
      const p = toGraph(px, py);
      S.dragging.fx = p.x; S.dragging.fy = p.y;
      moved = true;
      S.dirty = true;
      return;
    }
    if (S.panning && downPos) {
      S.t.x += px - downPos.px;
      S.t.y += py - downPos.py;
      downPos = { px, py };
      moved = true;
      S.dirty = true;
      updateStatus();
      return;
    }
    // hover
    const n = pickNode(px, py);
    if (n !== S.hovered) {
      S.hovered = n;
      S.dirty = true;
      canvas.classList.toggle("pointing", !!n);
      if (n) {
        tooltip.classList.remove("hidden");
        tooltip.innerHTML = `<b>${esc(n.label)}</b><div class="t-cat">${esc(n.top)}${n.sub ? " › " + esc(n.sub) : ""} · importance ${n.importance.toFixed(2)}</div>${n.definition ? `<div class="t-def">${esc(n.definition)}</div>` : ""}`;
      } else {
        tooltip.classList.add("hidden");
      }
    }
    if (n) {
      tooltip.style.left = clamp(px + 14, 8, S.w - 270) + "px";
      tooltip.style.top = clamp(py + 14, 8, S.h - 110) + "px";
    }
  });
  canvas.addEventListener("pointerup", (ev) => {
    if (S.dragging) {
      const n = S.dragging;
      n.fx = null; n.fy = null;
      S.sim.alphaTarget(0);
      if (!moved) selectNode(n);
      S.dragging = null;
    } else if (S.panning && !moved && downPos) {
      // click on background: try edge hit-test before clearing
      const rect = canvas.getBoundingClientRect();
      const hit = pickEdge(ev.clientX - rect.left, ev.clientY - rect.top);
      if (hit) selectEdge(hit);
      else clearSelection();
    }
    S.panning = false;
    downPos = null;
    canvas.classList.remove("grabbing");
  });
  canvas.addEventListener("pointerleave", () => {
    S.hovered = null;
    tooltip.classList.add("hidden");
    canvas.classList.remove("pointing");
    S.dirty = true;
  });
  canvas.addEventListener("dblclick", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const n = pickNode(ev.clientX - rect.left, ev.clientY - rect.top);
    if (n) focusNode(n);
  });
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const px = ev.clientX - rect.left, py = ev.clientY - rect.top;
    const factor = Math.pow(1.0016, -ev.deltaY);
    const k2 = clamp(S.t.k * factor, 0.12, 6);
    const ratio = k2 / S.t.k;
    S.t = { k: k2, x: px - (px - S.t.x) * ratio, y: py - (py - S.t.y) * ratio };
    S.dirty = true;
    updateStatus();
  }, { passive: false });

  /* zoom buttons */
  $("zoom-in").onclick = () => S.mode === "3d" ? zoom3D(0.78) : zoomBy(1.35);
  $("zoom-out").onclick = () => S.mode === "3d" ? zoom3D(1.28) : zoomBy(1 / 1.35);

  /* search */
  const search = $("search");
  search.addEventListener("input", () => renderSuggestions(search.value));
  search.addEventListener("keydown", (ev) => {
    const box = $("suggestions");
    const items = [...box.querySelectorAll(".sg")];
    const cur = box.querySelector(".sg.active");
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      if (!items.length) return;
      const idx = cur ? items.indexOf(cur) : -1;
      const next = ev.key === "ArrowDown" ? (idx + 1) % items.length : (idx - 1 + items.length) % items.length;
      items.forEach(i => i.classList.remove("active"));
      items[next].classList.add("active");
    } else if (ev.key === "Enter") {
      const target = cur || items[0];
      if (target && target.dataset.id) {
        selectById(target.dataset.id, true);
        box.classList.add("hidden");
      }
    } else if (ev.key === "Escape") {
      box.classList.add("hidden");
      search.blur();
    }
  });
  document.addEventListener("pointerdown", (ev) => {
    if (!$("searchbox").contains(ev.target)) $("suggestions").classList.add("hidden");
  });

  /* keyboard */
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "/" && document.activeElement !== search && document.activeElement !== $("query-filter")) {
      ev.preventDefault(); search.focus(); search.select();
    } else if (ev.key === "Escape") {
      if (!$("suggestions").classList.contains("hidden")) $("suggestions").classList.add("hidden");
      else if (S.selected) clearSelection();
      else if (S.query) clearQuery();
    }
  });

  /* sidebar tabs */
  $("tab-filters").onclick = () => switchTab("filters");
  $("tab-queries").onclick = () => switchTab("queries");

  /* view mode */
  $("btn-2d").onclick = () => setMode("2d");
  $("btn-3d").onclick = () => setMode("3d");

  /* filters */
  $("cats-all").onclick = () => setAllCats(true);
  $("cats-none").onclick = () => setAllCats(false);
  $("imp-slider").oninput = (ev) => {
    const f = ev.target.value / 100;
    S.minImp = S.impMin + f * (S.impMax - S.impMin) - 0.001;
    $("imp-val").textContent = "≥ " + S.minImp.toFixed(2);
    applyFilters(0.35);
  };
  $("str-slider").oninput = (ev) => {
    const f = ev.target.value / 100;
    S.minStr = S.strMin + f * (S.strMax - S.strMin) - 0.001;
    $("str-val").textContent = "≥ " + S.minStr.toFixed(2);
    applyFilters(0.25);
  };
  $("chk-cluster").onchange = (ev) => {
    S.cluster = ev.target.checked;
    if (S.mode === "3d") apply3DCluster();
    else { applyClusterForces(S.sim); S.sim.alpha(0.5).restart(); }
  };
  $("sel-labels").onchange = (ev) => { S.labels = ev.target.value; S.dirty = true; };
  $("sel-ego").onchange = (ev) => {
    S.egoDepth = parseInt(ev.target.value, 10) || 0;
    if (S.mode === "3d") rebuild3DData();
    else if (S.selected && S.egoDepth) {
      const eg = egoSet();
      if (eg) fitViewCapped(S.simNodes.filter(x => eg.has(x.id)), true, 1.15);
    } else if (S.mode === "2d") fitView();
    S.dirty = true;
    updateStatus();
  };
  $("btn-fit").onclick = () => S.mode === "3d" ? (S.g3d && S.g3d.zoomToFit(700, 50)) : fitView();
  $("btn-spread").onclick = () => {
    S.spread = Math.min(2.5, (S.spread || 1) + 0.4); // each click spreads 40% more
    if (S.mode === "3d") {
      apply3DCluster();
      if (S.g3d) {
        const G = S.g3d;
        G.d3Force("charge").strength(-230 * S.spread);
        G.d3Force("link").distance(l => (74 + (1 - l.w) * 76) * S.spread);
        G.d3ReheatSimulation();
      }
    } else {
      rebuildSim(0.8);
    }
    $("btn-spread").textContent = `⤢ ${(S.spread).toFixed(1)}×`;
  };
  $("btn-reheat").onclick = () => {
    if (S.mode === "3d") apply3DCluster();
    else { S.fitted = false; rebuildSim(1.0); }
  };

  /* queries */
  $("query-filter").oninput = renderQueryList;
  $("btn-clear-query").onclick = clearQuery;
  $("query-banner").onclick = clearQuery;

  /* fit once layout settles */
  const fitWatch = setInterval(() => {
    if (S.sim && S.sim.alpha() < 0.35 && !S.fitted && S.simNodes.length) {
      S.fitted = true;
      fitView();
      clearInterval(fitWatch);
      $("status-text").textContent = "";
      updateStatus();
    }
  }, 200);

  document.fonts?.ready.then(() => { S.dirty = true; });
}

function switchTab(tab) {
  const f = tab === "filters";
  $("tab-filters").classList.toggle("active", f);
  $("tab-queries").classList.toggle("active", !f);
  $("panel-filters").classList.toggle("hidden", !f);
  $("panel-queries").classList.toggle("hidden", f);
}

function setAllCats(on) {
  for (const c of S.data.categories) {
    if (on) S.catsOn.add(c.name); else S.catsOn.delete(c.name);
  }
  syncCatList();
  applyFilters(0.4);
  if (S.selected && !isVisible(S.selected)) clearSelection();
}

/* ————————— sidebar build ————————— */
function buildSidebar() {
  const list = $("cat-list");
  list.innerHTML = "";
  for (const c of S.data.categories) {
    const el = document.createElement("div");
    el.className = "cat-item";
    el.dataset.cat = c.name;
    el.innerHTML = `<span class="swatch" style="background:${c.color}"></span>
      <span class="name">${esc(c.name)}</span><span class="n">${c.count}</span>`;
    el.onclick = () => {
      if (S.catsOn.has(c.name)) S.catsOn.delete(c.name); else S.catsOn.add(c.name);
      syncCatList();
      applyFilters(0.4);
      if (S.selected && !isVisible(S.selected)) clearSelection();
    };
    list.appendChild(el);
  }
  // relation legend
  const counts = {};
  for (const e of S.edges) counts[e.r] = (counts[e.r] || 0) + 1;
  const legend = $("rel-legend");
  legend.innerHTML = "";
  const shown = REL_ORDER.filter(r => counts[r]);
  for (const r of shown) {
    const rs = relStyle(r);
    const row = document.createElement("div");
    row.className = "rel-row";
    const dash = rs.dash.length ? `stroke-dasharray="${rs.dash.join(" ")}"` : "";
    const sw = (0.8 + rs.wmul * 1.2).toFixed(1);
    row.title = `${r.replace(/_/g, " ")} — edges are this color${rs.dash.length ? " and this dash pattern" : ""} in 2D and 3D`;
    row.innerHTML = `<svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="${rs.color}" stroke-width="${sw}" ${dash}/></svg>
      <span>${esc(r.replace(/_/g, " "))}</span><span class="n">${counts[r]}</span>`;
    legend.appendChild(row);
  }
}
function syncCatList() {
  document.querySelectorAll(".cat-item").forEach(el => {
    el.classList.toggle("off", !S.catsOn.has(el.dataset.cat));
  });
}

/* ————————— search —————————
   Two-stage: instant literal matching on labels/aliases, then a semantic
   pass over the 202 concept embeddings. A phrase like "what makes an action
   right" shares no substring with any concept label, so the literal pass
   alone returned "No concepts match" for exactly the questions this atlas
   exists to answer. */
let _sugSeq = 0, _sugTimer = null;

function literalMatches(q) {
  const scored = [];
  for (const n of S.nodes) {
    let s = -1;
    const lbl = n.label.toLowerCase();
    if (lbl === q) s = 100;
    else if (lbl.startsWith(q)) s = 80 - lbl.length * 0.1;
    else if (lbl.includes(q)) s = 60;
    else if (n.aliases?.some(a => a.toLowerCase().startsWith(q))) s = 50;
    else if (n.aliases?.some(a => a.toLowerCase().includes(q))) s = 40;
    else if (n.id.includes(q.replace(/\s+/g, "_"))) s = 30;
    if (s > 0) scored.push([s, n]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  return scored.map(([, n]) => n);
}

function paintSuggestions(list, q, { pending = false, semantic = false } = {}) {
  const box = $("suggestions");
  const rows = list.slice(0, 8).map(n => `
    <div class="sg${n._sem ? " sg-sem" : ""}" data-id="${esc(n.id)}">
      <span class="dot" style="background:${n.color}"></span>
      <span class="lbl">${esc(n.label)}</span>
      <span class="cat">${esc(n.top || (n.category || [])[0] || "")}</span>
    </div>`).join("");
  const foot = pending
    ? `<div class="sg-foot">searching the concept map…</div>`
    : semantic
    ? `<div class="sg-foot">◆ = related in meaning, not spelling</div>`
    : "";
  box.innerHTML = rows
    ? rows + foot
    : pending
    ? `<div class="sg-foot">searching the concept map…</div>`
    : `<div class="none">No concepts match “${esc(q)}”</div>`;
  box.classList.remove("hidden");
  box.querySelectorAll(".sg").forEach(el => {
    el.onclick = () => { selectById(el.dataset.id, true); box.classList.add("hidden"); };
  });
}

function renderSuggestions(raw) {
  const box = $("suggestions");
  const q = raw.trim().toLowerCase();
  clearTimeout(_sugTimer);
  const seq = ++_sugSeq;
  if (!q) { box.classList.add("hidden"); return; }
  const lit = literalMatches(q);
  paintSuggestions(lit, q, { pending: lit.length < 8 });
  if (lit.length >= 8 || q.length < 3) return;
  // only reach for the engine once typing settles
  _sugTimer = setTimeout(async () => {
    let sem = [];
    try {
      const r = await fetch("/book/api/concepts_proxy", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: raw.trim(), top_k: 10, mode: "hybrid" }),
        signal: AbortSignal.timeout(30000),
      });
      if (r.ok) sem = (await r.json()).results || [];
    } catch { /* engine down — literal results stand */ }
    if (seq !== _sugSeq) return;
    const byId = new Map(S.nodes.map(n => [n.id, n]));
    const have = new Set(lit.map(n => n.id));
    const extra = sem
      .filter(c => c.score > 0.25 && !have.has(c.id))
      .map(c => { const n = byId.get(c.id); return n ? { ...n, _sem: true } : null; })
      .filter(Boolean);
    paintSuggestions([...lit, ...extra], q, { semantic: extra.length > 0 });
  }, 260);
}

function ensureVisible(n) {
  let changed = false;
  if (!S.catsOn.has(n.top)) { S.catsOn.add(n.top); changed = true; }
  if (n.importance < S.minImp) {
    S.minImp = 0; $("imp-slider").value = 0;
    $("imp-val").textContent = "≥ " + (S.impMin - 0.001).toFixed(2);
    changed = true;
  }
  if (changed) { syncCatList(); applyFilters(0.35); }
}

/* ————————— edge selection ————————— */
function pickEdge(mx, my) {
  // point-to-segment distance over currently rendered edges
  let best = null, bestD = 7; // px tolerance
  for (const e of S.simEdges || []) {
    if (e._sx1 == null) continue;
    if (!isVisible(e.source) || !isVisible(e.target)) continue;
    const x1 = e._sx1, y1 = e._sy1, x2 = e._sx2, y2 = e._sy2;
    const dx = x2 - x1, dy = y2 - y1;
    const L2 = dx * dx + dy * dy;
    if (L2 < 1) continue;
    let t = ((mx - x1) * dx + (my - y1) * dy) / L2;
    t = Math.max(0, Math.min(1, t));
    const d = Math.hypot(mx - (x1 + t * dx), my - (y1 + t * dy));
    if (d < bestD) { bestD = d; best = e; }
  }
  return best;
}

function selectEdge(e) {
  S.selected = null;
  S.selectedEdge = e;
  S.dirty = true;
  // sim edges carry .source/.target (node objects); raw/filtered edges carry .s/.t (ids)
  const sid = e.source?.id ?? e.s?.id ?? e.source ?? e.s;
  const tid = e.target?.id ?? e.t?.id ?? e.target ?? e.t;
  const a = S.byId.get(sid), b = S.byId.get(tid);
  const rs = relStyle(e.r);
  detail.innerHTML = `
    <button class="close" title="Close (Esc)">×</button>
    <div class="crumb">relation</div>
    <h2 style="font-size:20px">${a ? esc(a.label) : esc(sid)} <span style="color:${rs.color}">—[${esc(rs.desc)}]→</span> ${b ? esc(b.label) : esc(tid)}</h2>
    <div class="stat-chips">
      <div class="chip"><div class="k">Relation</div><div class="v">${esc((e.r || "").replace(/_/g, " "))}</div></div>
      <div class="chip"><div class="k">Strength</div><div class="v">${(+e.w).toFixed(2)}</div></div>
    </div>
    <div class="d-sec">
      <h4>Endpoints</h4>
      <div class="rel-target" data-id="${esc(a?.id || sid)}"><span class="dot" style="background:${a?.color || "#999"}"></span><span>${esc(a?.label || sid)}</span></div>
      <div class="rel-target" data-id="${esc(b?.id || tid)}"><span class="dot" style="background:${b?.color || "#999"}"></span><span>${esc(b?.label || tid)}</span></div>
    </div>
    <div class="d-sec">
      <h4>Same-relation links</h4>
      ${sameRelationLinks(e.r).slice(0, 8).map(x => `
        <div class="rel-target" data-id="${esc(x.id)}"><span class="dot" style="background:${rs.color}"></span><span>${esc(x.label)}</span></div>`).join("") || `<p class="hint">none other</p>`}
    </div>`;
  detail.classList.remove("hidden");
  detail.querySelector(".close").onclick = clearSelection;
  detail.querySelectorAll(".rel-target").forEach(el => {
    el.onclick = () => selectById(el.dataset.id, false);
  });
}

function sameRelationLinks(rel) {
  const out = [];
  for (const n of S.nodes) {
    const m = S.adj.get(n.id);
    if (!m) continue;
    for (const [tid, e] of m) {
      if ((e.r || e.rel) === rel && out.length < 40) {
        const t = S.byId.get(tid);
        if (t) out.push(t);
      }
    }
  }
  return out;
}

function selectById(id, zoom = false) {
  const n = S.byId.get(id);
  if (!n) return;
  ensureVisible(n);
  // node may not be in simNodes yet if just unhidden — wait a beat
  const trySelect = (attempt = 0) => {
    const simNode = S.simNodes.find(m => m.id === id) || n;
    selectNode(simNode);
    if (zoom) focusNode(simNode);
  };
  if (S.simNodes.includes(n)) trySelect();
  else { setTimeout(() => trySelect(), 60); }
}

function selectNode(n) {
  S.selected = n;
  S.dirty = true;
  renderNodeDetail(n);
  update3DColors();
  if (S.egoDepth && S.mode === "2d") {
    const eg = egoSet();
    if (eg) {
      // fit to the neighborhood but never zoom IN aggressively — keep at
      // most a gentle 1.15x so the view doesn't "shrink/flash" on click
      const sub = S.simNodes.filter(x => eg.has(x.id));
      fitViewCapped(sub, true, 1.15);
    }
  }
  if (S.egoDepth && S.mode === "3d") rebuild3DData();
}

/* fitView but with a max zoom-IN cap so clicking a node never snaps the
   camera into the node's face (the reported "shrink/scaling glitch") */
function fitViewCapped(nodes, animate = true, maxK = 1.15) {
  if (!nodes || !nodes.length) return;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const n of nodes) {
    if (n.x == null) continue;
    x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y);
    x1 = Math.max(x1, n.x); y1 = Math.max(y1, n.y);
  }
  if (x0 === Infinity) return;
  const pad = 90;
  const bw = (x1 - x0) + pad * 2, bh = (y1 - y0) + pad * 2;
  // never zoom in past maxK; if the neighborhood is small, stay wide enough
  const k = clamp(Math.min(S.w / bw, S.h / bh), 0.15, maxK);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const target = { k, x: S.w / 2 - cx * k, y: S.h / 2 - cy * k };
  if (animate) animateTo(target, 600); else { S.t = target; S.dirty = true; }
}

function clearSelection() {
  S.selected = null;
  S.selectedEdge = null;
  detail.classList.add("hidden");
  detail.innerHTML = "";
  S.dirty = true;
  update3DColors();
  if (S.egoDepth) {
    if (S.mode === "3d") rebuild3DData();
    else { fitView(); S.dirty = true; }
  }
}

function focusNode(n) {
  if (S.mode === "3d") { focus3D(n); return; }
  if (n.x == null) return;
  const k = clamp(Math.max(S.t.k, 1.5), 0.12, 6);
  animateTo({ k, x: S.w / 2 - n.x * k, y: S.h / 2 - n.y * k });
}

/* ————————— global search hook on header input ————————— */
(function () {
  const inp = document.getElementById("search");
  inp.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    // if a suggestion is active, app.js handles it; check for .sg.active
    if (document.querySelector(".suggestions .sg.active")) return;
    const sug = document.getElementById("suggestions");
    const hasVisible = sug && !sug.classList.contains("hidden") && sug.querySelector(".sg");
    if (hasVisible) return; // let the suggestion list handle Enter
    const q = inp.value.trim();
    if (q.length >= 2 && typeof doGlobalSearchExternal === "function") {
      doGlobalSearchExternal(q);
    }
  });
  // Getting back to search is the app bar's Search button now (Nav.go), which
  // is present on every view. The old #btn-home here was hidden by an inline
  // style and its sync function was never called, so the concept map had no
  // way back at all.
})();

/* ————————— detail panel ————————— */
function renderNodeDetail(n) {
  const evList = (S.data.evidence[n.id] || []);
  if (typeof setReaderHighlights === "function") setReaderHighlights(n.id);
  const relMap = new Map(); // relation -> [{target, w}]
  const adjm = S.adj.get(n.id) || new Map();
  for (const [tid, e] of adjm) {
    const rel = e.s === n.id ? e.r : (S.edges.find(x => x.s === tid && x.t === n.id)?.r) || e.r;
    if (!relMap.has(rel)) relMap.set(rel, []);
    relMap.get(rel).push({ target: S.byId.get(tid), w: e.w, rel });
  }
  const rels = [...relMap.entries()].sort((a, b) =>
    (b[1].reduce((s, x) => s + x.w, 0)) - (a[1].reduce((s, x) => s + x.w, 0)));

  const impPct = Math.round(n.importance * 100);
  detail.innerHTML = `
    <button class="close" title="Close (Esc)">×</button>
    <div class="crumb">${n.category.map((c, i) => i === n.category.length - 1 ? `<b>${esc(c)}</b>` : esc(c)).join(" › ")}</div>
    <h2>${esc(n.label)}</h2>
    ${n.aliases?.length ? `<div class="aliases">${n.aliases.slice(0, 8).map(a => `<span class="alias">${esc(a)}</span>`).join("")}</div>` : ""}
    <p class="definition">${esc(n.definition)}</p>
    <div class="stat-chips">
      <div class="chip"><div class="k">Importance</div><div class="v">${n.importance.toFixed(2)}</div>
        <div class="impbar"><i style="width:${impPct}%;background:${n.color}"></i></div></div>
      <div class="chip"><div class="k">Books</div><div class="v">${n.books}</div></div>
      <div class="chip"><div class="k">Evidence</div><div class="v">${n.evidence}</div></div>
      <div class="chip"><div class="k">Links</div><div class="v">${adjm.size}</div></div>
    </div>
    <div class="d-sec">
      <h4>Related concepts</h4>
      ${rels.length ? rels.map(([rel, items]) => {
        const pol = polarity(rel);
        return `<div class="rel-group">
          <div class="rel-head"><span class="rel-badge ${pol}">${esc(rel.replace(/_/g, " "))}</span></div>
          ${items.sort((a, b) => b.w - a.w).map(it => `
            <div class="rel-target" data-id="${esc(it.target.id)}">
              <span class="dot" style="background:${it.target.color}"></span>
              <span>${esc(it.target.label)}</span>
              <span class="w"><span class="wbar"><i style="width:${Math.round(it.w * 100)}%"></i></span>${it.w.toFixed(2)}</span>
            </div>`).join("")}
        </div>`;
      }).join("") : `<p class="hint">No explicit relations indexed.</p>`}
    </div>
    <div class="d-sec">
      <h4>Evidence — ${evList.length ? `${evList.length} passage${evList.length > 1 ? "s" : ""}` : "none indexed"}
        ${evList.length > 5 ? `<button class="mini" id="ev-expand" style="margin-left:8px">${"show all " + evList.length}</button>` : ""}</h4>
      <div id="ev-list-wrap">
      ${evList.slice(0, 5).map((e, i) => `
        <div class="evidence-item ev-click" data-ev="${i}">
          <div class="q">“${esc(e.text)}”</div>
          <div class="cite"><b>${esc(e.author)}</b>${e.year ? " · " + esc(e.year) : ""}${e.page ? " · p. " + esc(e.page) : ""}${e.title ? `<br>${esc(e.title)}` : ""}</div>
          <div class="ev-actions">
            ${e.has_pdf ? `<button class="ev-open" data-ev="${i}" title="Open PDF at this passage">📖 Open in PDF</button>` : `<button class="ev-open ev-txt" data-ev="${i}" title="Open text version">📄 Open text</button>`}
            ${e.has_pdf ? `<button class="ev-dl" data-ev="${i}" title="Download this book's PDF">⬇</button>` : ""}
          </div>
        </div>`).join("")}
      </div>
    </div>`;
  detail.querySelectorAll(".ev-click").forEach(el => {
    const ev = evList[parseInt(el.dataset.ev, 10)];
    if (!ev) return;
    el.querySelectorAll(".ev-open").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        if (typeof openEvidenceInReader === "function") {
          openEvidenceInReader({ ...ev, concept_id: n.id });
        }
      };
    });
    el.querySelectorAll(".ev-dl").forEach(btn => {
      btn.onclick = (e) => { e.stopPropagation(); location.href = `/book/pdf/${encodeURIComponent(ev.book_id)}`; };
    });
  });
  // evidence expander: show all passages beyond the first 5
  const expandBtn = detail.querySelector("#ev-expand");
  if (expandBtn) {
    expandBtn.onclick = () => {
      const wrap = detail.querySelector("#ev-list-wrap");
      const evHtml = (e, i) => `
        <div class="evidence-item ev-click" data-ev="${i}">
          <div class="q">“${esc(e.text)}”</div>
          <div class="cite"><b>${esc(e.author)}</b>${e.year ? " · " + esc(e.year) : ""}${e.page ? " · p. " + esc(e.page) : ""}${e.title ? `<br>${esc(e.title)}` : ""}</div>
          <div class="ev-actions">
            ${e.has_pdf ? `<button class="ev-open" data-ev="${i}" title="Open PDF at this passage">📖 Open in PDF</button>` : `<button class="ev-open ev-txt" data-ev="${i}" title="Open text version">📄 Open text</button>`}
            ${e.has_pdf ? `<button class="ev-dl" data-ev="${i}" title="Download this book's PDF">⬇</button>` : ""}
          </div>
        </div>`;
      wrap.innerHTML = evList.map(evHtml).join("");
      expandBtn.remove();
      // rewire the new cards
      wrap.querySelectorAll(".ev-click").forEach(el => {
        const ev = evList[parseInt(el.dataset.ev, 10)];
        if (!ev) return;
        el.querySelectorAll(".ev-open").forEach(btn => {
          btn.onclick = (e) => {
            e.stopPropagation();
            if (typeof openEvidenceInReader === "function") {
              openEvidenceInReader({ ...ev, concept_id: n.id });
            }
          };
        });
        el.querySelectorAll(".ev-dl").forEach(btn => {
          btn.onclick = (e) => { e.stopPropagation(); location.href = `/book/pdf/${encodeURIComponent(ev.book_id)}`; };
        });
      });
    };
  }
  detail.classList.remove("hidden");
  detail.querySelector(".close").onclick = clearSelection;
  detail.querySelectorAll(".rel-target").forEach(el => {
    el.onclick = () => selectById(el.dataset.id, false);
  });
  detail.scrollTop = 0;
}

/* ————————— queries ————————— */
function buildQueries() {
  renderQueryList();
}
function renderQueryList() {
  const qf = ($("query-filter").value || "").trim().toLowerCase();
  const list = $("query-list");
  const qs = S.data.queries.filter(q =>
    !qf || q.id.toLowerCase().includes(qf) || q.text.toLowerCase().includes(qf));
  list.innerHTML = qs.map(q => `
    <div class="query-item ${S.query?.id === q.id ? "active" : ""}" data-qid="${esc(q.id)}">
      <div class="qid">${esc(q.id)}</div>
      <div class="qtext">${esc(q.text)}</div>
      <button class="q-run" data-run="${esc(q.text)}"
        title="Run this as a corpus search">search the corpus &rarr;</button>
    </div>`).join("") || `<p class="hint">No queries match.</p>`;
  list.querySelectorAll(".query-item").forEach(el => {
    el.onclick = () => activateQuery(el.dataset.qid);
  });
  // highlighting the concepts is only half of what a researcher wants from a
  // curated query; the other half is the passages behind them
  list.querySelectorAll(".q-run").forEach(el => {
    el.onclick = (e) => {
      e.stopPropagation();
      document.dispatchEvent(new CustomEvent("atlas:search", { detail: el.dataset.run }));
    };
  });
}
function activateQuery(qid) {
  const q = S.data.queries.find(x => x.id === qid);
  if (!q) return;
  const top = q.concepts.slice(0, 10)
    .map((c, i) => ({ node: S.byId.get(c.id), rel: c.rel, rank: i + 1 }))
    .filter(x => x.node);
  S.query = { id: q.id, text: q.text, top, topIds: new Set(top.map(x => x.node.id)) };
  S.selected = null;
  detail.classList.add("hidden");
  $("btn-clear-query").classList.remove("hidden");
  const banner = $("query-banner");
  banner.textContent = `query: ${q.id} — top ${top.length} highlighted · click to clear`;
  banner.classList.remove("hidden");
  renderQueryList();
  renderQueryDetail();
  S.dirty = true;
  update3DColors();
  // focus on highlighted set
  if (S.mode === "3d") {
    setTimeout(() => S.g3d && S.g3d.zoomToFit(700, 60, n => S.query.topIds.has(n.id)), 60);
  } else {
    setTimeout(() => fitView(top.map(x => x.node)), 50);
  }
}
function clearQuery() {
  S.query = null;
  $("btn-clear-query").classList.add("hidden");
  $("query-banner").classList.add("hidden");
  renderQueryList();
  detail.classList.add("hidden");
  S.dirty = true;
  update3DColors();
  if (S.mode === "3d") { S.g3d && S.g3d.zoomToFit(700, 50); } else { fitView(); }
}
function renderQueryDetail() {
  const q = S.query;
  detail.innerHTML = `
    <button class="close" title="Close (Esc)">×</button>
    <div class="crumb"><b>query</b> · ${esc(q.id)}</div>
    <h2 style="font-size:20px">${esc(q.id.replace(/-/g, " "))}</h2>
    <p class="qtext-full">“${esc(q.text)}”</p>
    <div class="d-sec">
      <h4>Top-ranked concepts</h4>
      ${q.top.map(x => `
        <div class="qrank" data-id="${esc(x.node.id)}">
          <span class="rank">${x.rank}</span>
          <span class="rl">${esc(x.node.label)}</span>
          <span class="rr">rel ${x.rel.toFixed(2)}</span>
        </div>`).join("")}
    </div>`;
  detail.classList.remove("hidden");
  detail.querySelector(".close").onclick = clearQuery;
  detail.querySelectorAll(".qrank").forEach(el => {
    el.onclick = () => {
      detail.querySelectorAll(".qrank").forEach(e => e.classList.remove("sel"));
      el.classList.add("sel");
      selectById(el.dataset.id, true);
    };
  });
  detail.scrollTop = 0;
}

/* ————————— status ————————— */
function updateStatus() {
  if (S.mode === "3d") {
    $("status-text").textContent = `${S.g3dNodes.length} concepts · ${S.g3dLinks.length} relations · 3D`;
    return;
  }
  const n = S.simNodes.length;
  const e = S.simEdges.length;
  const eg = egoSet();
  const egotxt = eg ? ` · neighborhood ${eg.size}` : "";
  // "157%" beside two counts read like a coverage figure; it is the zoom
  $("status-text").textContent = `${n} concepts · ${e} relations · zoom ${Math.round(S.t.k * 100)}%${egotxt}`;
}

init();

/* debug/testing handle (read-only usage) */
window.__atlas = { S, selectById, fitView, pickAt: (px, py) => pickNode(px, py) };
