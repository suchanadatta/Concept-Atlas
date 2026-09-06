/* Concept Atlas — Book Reader: pdf.js page view + bbox highlight overlay + annotations */
"use strict";

const Reader = {
  open: false,
  bookId: null,
  pdf: null,
  pageNum: 1,
  numPages: 0,
  scale: 1.6,
  highlights: [],       // [{page, bbox_pts, concept_id, text}]
  annotations: {},      // page -> [{id,type,rect,note,ts}]
  pdfDoc: null,
  renderTask: null,
  pendingHighlight: null,  // {page, bbox_pts, concept_id} to flash after render
  _initDone: false,
  /* Every async step below (PDF load, page render, OCR fetch, word-highlight
     fetch, annotation fetch) writes into this one shared object. Clicking a
     second search result before the first finished let a stale response land
     on the new page: the OCR panel showed another page's text and word boxes
     from the previous passage were painted over the current scan. `seq` is
     bumped by every navigation; each continuation captures it and bails if it
     is no longer current. */
  seq: 0,
};
function readerBump() { return ++Reader.seq; }
function readerStale(t) { return t !== Reader.seq; }
window.Reader = Reader;   // exposed for tests and the panel-stacking manager

const READER_CDN = "vendor/pdfjs/";
function setStatus(msg) {
  const el = document.getElementById("status-text");
  if (el) el.textContent = msg;
}

async function readerInit() {
  if (Reader._initDone) return;
  // pdf.js from vendored files (set by worker src below)
  Reader._initDone = true;
}

/* ————— open the reader for a book, optionally jumping to a page+highlight ————— */
function showReaderShell() {
  const el = $("reader");
  el.classList.remove("hidden");
  // split-reading: when results view is open, reader slides in as the right
  // half (results shrink left) instead of covering the whole screen
  const resultsOpen = !$("gres")?.classList.contains("hidden") || !$("landing")?.classList.contains("hidden");
  el.classList.toggle("split", resultsOpen);
  el.classList.remove("docked");
  document.body.classList.toggle("split-reading", resultsOpen);
  positionSplit(resultsOpen);
  // the raw id is a filename ("KING_1731_1732_An-Essay-on-the-Origin-of-Evil_1");
  // show the citation and keep the id on hover for provenance
  const _c = window.Cite ? Cite.parse(Reader.bookId) : null;
  $("reader-title").textContent = _c && _c.cite ? _c.cite : Reader.bookId;
  $("reader-title").title = Reader.bookId;
  $("reader-download-pdf").onclick = () => { location.href = `/book/pdf/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-download-txt").onclick = () => { location.href = `/book/txt/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-download-md").onclick = () => { location.href = `/book/md/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-download-jsonl").onclick = () => { location.href = `/book/jsonl/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-export-json").onclick = () => { location.href = `/book/api/export_annotations?book=${encodeURIComponent(Reader.bookId)}&fmt=json`; };
  $("reader-export-md").onclick = () => { location.href = `/book/api/export_annotations?book=${encodeURIComponent(Reader.bookId)}&fmt=markdown`; };
  $("reader-close").onclick = () => {
    if (window.closeReader) window.closeReader();
    else closeReader();
  };
  $("reader-prev").onclick = () => gotoPage(Reader.pageNum - 1);
  $("reader-next").onclick = () => gotoPage(Reader.pageNum + 1);
  $("reader-jump").onchange = (e) => gotoPage(parseInt(e.target.value, 10) || 1);
  $("reader-zoom-in").onclick = () => { Reader.userZoom = true; Reader.scale = Math.min(4, Reader.scale * 1.2); renderReaderPage(); };
  $("reader-zoom-out").onclick = () => { Reader.userZoom = true; Reader.scale = Math.max(0.25, Reader.scale / 1.2); renderReaderPage(); };
  $("reader-zoom-fit").onclick = () => { Reader.userZoom = false; Reader.scale = 1; renderReaderPage(); };
  $("reader-annot-toggle").onclick = toggleAnnotMode;
  $("reader-search-go").onclick = doBookSearch;
  $("reader-search").onkeydown = (e) => { if (e.key === "Enter") doBookSearch(); };
  wireMoreMenu();
  wireSideToggle();
  wireCtxButton();
}

/* Attaching what you are reading is the commonest way to build context, so it
   is a button in the reader rather than only a row in the picker. */
function wireCtxButton() {
  const btn = $("reader-ctx");
  if (!btn || btn._wired) return;
  btn._wired = true;
  btn.onclick = () => {
    if (!window.Chat) return;
    const c = window.Cite ? Cite.parse(Reader.bookId) : null;
    const label = (c && c.cite) || Reader.bookId;
    const page = Reader.txtMode ? null : Reader.pageNum;
    const choice = page
      ? prompt(
          `Attach to the chat context:\n\n` +
          `  1  this page (${page})\n` +
          `  2  pages ${Math.max(1, page - 5)}–${Math.min(Reader.numPages, page + 5)}\n` +
          `  3  the whole book (${Reader.numPages} pages)\n\n` +
          `Enter 1, 2 or 3 — or a range like 40-60:`, "2")
      : "3";
    if (!choice) return;
    let from = null, to = null;
    const m = String(choice).match(/^\s*(\d+)\s*[-–]\s*(\d+)\s*$/);
    if (m) { from = +m[1]; to = +m[2]; }
    else if (choice.trim() === "1") { from = page; to = page; }
    else if (choice.trim() === "2") { from = Math.max(1, page - 5); to = Math.min(Reader.numPages, page + 5); }
    else if (choice.trim() !== "3") return;
    Chat.addContext([{ kind: "book", book_id: Reader.bookId, label, page_from: from, page_to: to }]);
  };
}

/* The notes/page-text pane is useful when transcribing and in the way when
   reading, so it is a toggle, and the choice is remembered. */
function wireSideToggle() {
  const btn = $("reader-side-toggle");
  if (!btn || btn._wired) return;
  btn._wired = true;
  const paint = () => {
    const off = document.body.classList.contains("reader-side-off");
    btn.classList.toggle("active", !off);
    btn.setAttribute("aria-pressed", String(!off));
  };
  try {
    if (localStorage.getItem("atlas.readerSide") === "off") document.body.classList.add("reader-side-off");
  } catch { /* private mode */ }
  paint();
  btn.onclick = () => {
    const off = document.body.classList.toggle("reader-side-off");
    try { localStorage.setItem("atlas.readerSide", off ? "off" : "on"); } catch { /* ignore */ }
    paint();
    // the pane is a flex sibling: the canvas has to be re-fitted to the new width
    if (!Reader.txtMode) renderReaderPage();
  };
}

/* ————— loading veil —————
   Clicking a second result left the previous book on screen until the new one
   finished streaming, so the reader showed one text while claiming another.
   The veil goes up synchronously on the click and only comes down when the
   new source has actually painted. */
function setReaderPage(n) {
  const el = $("reader-jump");
  if (!el) return;
  el.value = n === "" ? "" : String(n);
  el.dataset.page = String(n);
}

function readerVeil(title, sub) {
  const v = $("reader-veil");
  if (!v) return;
  v.querySelector(".rv-title").textContent = title || "Opening…";
  v.querySelector(".rv-sub").textContent = sub || "";
  v.classList.remove("hidden");
}
function readerVeilDown() {
  const v = $("reader-veil");
  if (v) v.classList.add("hidden");
}
window.readerVeil = readerVeil;

function wireMoreMenu() {
  const btn = $("reader-more"), pop = $("reader-more-menu");
  if (!btn || !pop || btn._wired) return;
  btn._wired = true;
  const close = () => { pop.classList.add("hidden"); btn.setAttribute("aria-expanded", "false"); };
  btn.onclick = (e) => {
    e.stopPropagation();
    const show = pop.classList.contains("hidden");
    pop.classList.toggle("hidden", !show);
    btn.setAttribute("aria-expanded", String(show));
  };
  document.addEventListener("click", (e) => {
    if (!pop.classList.contains("hidden") && !pop.contains(e.target) && e.target !== btn) close();
  });
  pop.querySelectorAll("button").forEach(b => b.addEventListener("click", close));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); }, true);
}
/* The side pane serves a scan (annotations + the page's OCR text) and a text
   edition (annotations only) differently. */
function setSidePanelMode(txt) {
  const annT = $("reader-side-ann-title");
  const ocrT = $("reader-ocr-title");
  const ocr = $("reader-ocr");
  if (annT) annT.textContent = txt ? "Annotations" : "Page annotations";
  if (ocrT) ocrT.hidden = !!txt;
  if (ocr) ocr.hidden = !!txt;
}

async function openReader(bookId, opts = {}) {
  if (!bookId) return;
  setSidePanelMode(false);
  const token = readerBump();
  // Highlights belong to one book+query. They used to accumulate across every
  // passage opened in a session and reappear on unrelated pages, so the caller
  // now hands in the boxes for THIS passage; anything else is dropped.
  if (opts.highlights) Reader.highlights = opts.highlights;
  else if (Reader.bookId !== bookId) Reader.highlights = [];
  Reader.bookId = bookId;
  Reader.open = true;
  Reader.txtMode = false;
  Reader.pendingHighlight = opts.highlight || null;
  Reader.pageNum = opts.page || 1;
  showReaderShell();
  const cite = window.Cite ? Cite.parse(bookId) : null;
  readerVeil(
    (cite && cite.cite) || bookId,
    `streaming the scan · page ${opts.page || 1}`,
  );
  setStatus(`Opening ${(cite && cite.cite) || bookId}…`);
  try {
    if (!Reader.pdfDoc || Reader._loadedFor !== bookId) {
      const url = `/book/pdf/${encodeURIComponent(bookId)}`;
      const task = pdfjsLib.getDocument({ url, disableAutoFetch: false });
      const doc = await task.promise;
      if (readerStale(token)) { try { doc.destroy(); } catch {} return; }   // newer open owns the veil
      Reader.pdfDoc = doc;
      Reader._loadedFor = bookId;
    }
    if (readerStale(token)) return;
    Reader.numPages = Reader.pdfDoc.numPages;
    $("reader-page-total").textContent = Reader.numPages;
    $("reader-jump").max = Reader.numPages;
    $("reader-jump").disabled = false;
    $("reader-jump").placeholder = "";
    // restore the page-wrap markup (loading screen replaced it)
    $("reader-body").innerHTML = `
      <div id="reader-page-wrap">
        <canvas id="reader-canvas"></canvas>
        <div id="reader-overlay"></div>
      </div>`;
    // rewire overlay drag for annotations
    overlayDragHandlers();
    await renderReaderPage(token);
    if (readerStale(token)) return;
    readerVeilDown();          // the new page is on screen; reveal it
    await loadAnnotations(token);
    await loadPageOcr(token);
    if (readerStale(token)) return;
    setStatus(`${(cite && cite.cite) || bookId} — ${Reader.numPages} pages`);
  } catch (e) {
    console.error("reader open failed", e);
    await openTxtMode(bookId);
  }
}

function closeReader() {
  Reader.open = false;
  $("reader").classList.add("hidden");
  document.body.classList.remove("split-reading");
  positionSplit(false);
  clearSplit(); // restore results pane to full width
}

/* ————— draggable divider between results and reader ————— */
function positionSplit(on) {
  const div = document.getElementById("split-divider");
  if (!on) { div.classList.add("hidden"); return; }
  const pct = Reader.splitPct ?? 54; // reader occupies right pct%
  applySplit(pct);
  div.classList.remove("hidden");
  div.style.left = `calc(${100 - pct}% - 5px)`;
}
function applySplit(pct) {
  pct = Math.max(28, Math.min(75, pct));
  Reader.splitPct = pct;
  const mobile = window.matchMedia("(max-width: 820px)").matches;
  const gres = document.getElementById("gres");
  const r = document.getElementById("reader");
  if (mobile) {
    // mobile: reader covers the full screen, results hidden beneath
    gres.style.right = "";
    r.style.left = "0";
    r.style.width = "100%";
    const div = document.getElementById("split-divider");
    if (div) div.style.display = "none";
  } else {
    gres.style.right = pct + "%";
    r.style.left = (100 - pct) + "%";
    r.style.width = pct + "%";
    const div = document.getElementById("split-divider");
    if (div) { div.style.display = ""; div.style.left = `calc(${100 - pct}% - 5px)`; }
  }
}
function clearSplit() {
  // restore results to full width (reader/dyngraph closed)
  document.getElementById("gres").style.right = "";
  const r = document.getElementById("reader");
  r.style.left = "";
  r.style.width = "";
}
(function initDivider() {
  const div = document.getElementById("split-divider");
  if (!div) return;
  let dragging = false;
  div.addEventListener("mousedown", (e) => { dragging = true; div.classList.add("active"); e.preventDefault(); });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const pct = 100 - (e.clientX / window.innerWidth * 100);
    applySplit(pct);
  });
  window.addEventListener("mouseup", () => { dragging = false; div.classList.remove("active"); });
})();

async function gotoPage(p) {
  p = clamp(p, 1, Reader.numPages);
  const token = readerBump();   // invalidates any in-flight load for the old page
  Reader.pageNum = p;
  await renderReaderPage(token);
  if (readerStale(token)) return;
  await loadAnnotations(token);
  await loadPageOcr(token);
}

/* ————— render one page + overlay ————— */
async function renderReaderPage(token) {
  if (token == null) token = Reader.seq;   // zoom/redraw: keep the current generation
  if (!Reader.pdfDoc) return;
  const pageAtStart = Reader.pageNum;
  const page = await Reader.pdfDoc.getPage(pageAtStart);
  if (readerStale(token) || Reader.pageNum !== pageAtStart) return;
  const canvas = $("reader-canvas");
  const ctx2 = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  // auto-fit: scale page to fit the reader pane (unless user zoomed manually)
  const pane = $("reader-body").clientWidth - 48;
  const paneH = $("reader-body").clientHeight - 48;
  const base = page.getViewport({ scale: 1 });
  const fitW = pane / base.width, fitH = paneH / base.height;
  const fitScale = Math.max(0.1, Math.min(fitW, fitH));
  const scale = Reader.userZoom ? Reader.scale * fitScale : fitScale;
  Reader._fitScale = fitScale;
  const vp = page.getViewport({ scale });
  canvas.width = Math.floor(vp.width * dpr);
  canvas.height = Math.floor(vp.height * dpr);
  canvas.style.width = `${vp.width}px`;
  canvas.style.height = `${vp.height}px`;
  if (Reader.renderTask) try { Reader.renderTask.cancel(); } catch {}
  Reader.renderTask = page.render({ canvasContext: ctx2, viewport: page.getViewport({ scale: scale * dpr }) });
  await Reader.renderTask.promise.catch(() => {});
  if (readerStale(token) || Reader.pageNum !== pageAtStart) return;
  // the jump input IS the current-page display now, so there is one number on
  // screen instead of a label and a box that could disagree
  setReaderPage(Reader.pageNum);
  $("reader-zoom-label").textContent = Math.round(scale / fitScale * 100) + "%";
  drawOverlay(page, vp, token);
}

/* map PDF points (bbox_pts) -> canvas px using page viewport in points */
function ptsToCanvas(bbox, vp) {
  const [x0, y0, x1, y1] = bbox;
  const sx = vp.width / vp.viewBox[2], sy = vp.height / vp.viewBox[3];
  return { x: x0 * sx, y: vp.height - y1 * sy, w: (x1 - x0) * sx, h: (y1 - y0) * sy };
}

function drawOverlay(page, vp, token) {
  Reader._lastVp = vp;
  const wrap = $("reader-overlay");
  wrap.innerHTML = "";
  wrap.style.width = `${vp.width}px`;
  wrap.style.height = `${vp.height}px`;
  // concept highlights for this page
  const pageHighlights = Reader.highlights.filter(h => h.page === Reader.pageNum && h.book_id === Reader.bookId);
  for (const h of pageHighlights) {
    if (!h.bbox_pts) continue;
    const r = ptsToCanvas(h.bbox_pts, vp);
    const div = document.createElement("div");
    div.className = "hl-box";
    div.style.left = `${r.x}px`; div.style.top = `${r.y}px`;
    div.style.width = `${r.w}px`; div.style.height = `${r.h}px`;
    div.title = `${h.concept_id} — ${h.text?.slice(0, 80) || ""}`;
    wrap.appendChild(div);
  }
  // flash pending highlight (jumped from concept)
  if (Reader.pendingHighlight && Reader.pendingHighlight.page === Reader.pageNum) {
    const h = Reader.pendingHighlight;
    if (h.bbox_pts) {
      const r = ptsToCanvas(h.bbox_pts, vp);
      const div = document.createElement("div");
      div.className = "hl-flash";
      div.style.left = `${r.x}px`; div.style.top = `${r.y}px`;
      div.style.width = `${r.w}px`; div.style.height = `${r.h}px`;
      wrap.appendChild(div);
      setTimeout(() => div.remove(), 4000);
    }
    Reader.pendingHighlight = null;
  }
  // word-level query highlights (async, appends)
  applyWordHighlights(token != null ? token : Reader.seq);
  // saved annotations
  const anns = Reader.annotations[Reader.pageNum] || [];
  for (const a of anns) {
    const div = document.createElement("div");
    div.className = "ann-box" + (a.type === "note" ? " ann-note" : "");
    div.style.left = `${a.rect.x}px`; div.style.top = `${a.rect.y}px`;
    div.style.width = `${a.rect.w}px`; div.style.height = `${a.rect.h}px`;
    div.title = a.note || "annotation";
    div.dataset.annId = a.id;
    wrap.appendChild(div);
  }
}

/* ————— word-level highlighting for the active query —————
   Reader.activeTerms: string[] — set before opening; every word in the
   page's OCR words[] matching a term gets its own precise box. */
Reader.activeTerms = Reader.activeTerms || null;

async function applyWordHighlights(token) {
  if (!Reader.activeTerms || !Reader.activeTerms.length) return;
  // dedup: clear previous word highlights for this page before re-applying
  document.querySelectorAll(".hl-word").forEach(el => el.remove());
  const wrap = $("reader-overlay");
  const bookAtStart = Reader.bookId, pageAtStart = Reader.pageNum;
  // fetch page words
  try {
    const res = await fetch(`/book/api/page_text?book=${encodeURIComponent(bookAtStart)}&page=${pageAtStart}`);
    if (!res.ok) return;
    const d = await res.json();
    // a newer navigation started while this fetch was in flight
    if (readerStale(token) || Reader.bookId !== bookAtStart || Reader.pageNum !== pageAtStart) return;
    const terms = Reader.activeTerms.map(t => t.toLowerCase());
    const vp = Reader._lastVp;
    if (!vp) return;
    let n = 0;
    for (const b of d.blocks || []) {
      for (const w of b.words || []) {
        const wt = (w.t || "").toLowerCase().replace(/^[^a-z0-9]+|[^a-z0-9]+$/g, "");
        if (!wt || !w.bbox_pts) continue;
        const hit = terms.some(t => wt === t || wt.startsWith(t) || (t.length > 4 && wt.includes(t)));
        if (!hit) continue;
        const r = ptsToCanvas(w.bbox_pts, vp);
        const div = document.createElement("div");
        div.className = "hl-word";
        div.style.left = `${r.x}px`; div.style.top = `${r.y}px`;
        div.style.width = `${r.w}px`; div.style.height = `${r.h}px`;
        div.title = w.t;
        wrap.appendChild(div);
        n++;
      }
    }
    if (n) setStatus(`${n} word highlights on p.${Reader.pageNum}`);
  } catch (e) { /* page without words[] */ }
}

/* fetch OCR blocks for the current page (text + printed page no.) */
async function loadPageOcr(token) {
  const el = $("reader-ocr");
  if (!el) return;
  if (token == null) token = Reader.seq;
  const bookAtStart = Reader.bookId, pageAtStart = Reader.pageNum;
  el.textContent = "loading…";
  try {
    const res = await fetch(`/book/api/page_text?book=${encodeURIComponent(bookAtStart)}&page=${pageAtStart}`);
    if (readerStale(token) || Reader.bookId !== bookAtStart || Reader.pageNum !== pageAtStart) return;
    if (!res.ok) { el.textContent = "(no OCR for this page)"; return; }
    const d = await res.json();
    if (readerStale(token) || Reader.pageNum !== pageAtStart) return;
    const printed = d.printed_page_number ? ` (printed p. ${typeof d.printed_page_number === 'object' ? d.printed_page_number.value : d.printed_page_number})` : "";
    const body = (d.blocks || []).map(b => b.text).join("\n\n");
    el.textContent = `— page ${d.page_number}${printed} —\n\n${body || "(empty page)"}`;
  } catch { el.textContent = "(OCR unavailable)"; }
}

/* ————— annotations ————— */
let annotMode = false;
function toggleAnnotMode() {
  annotMode = !annotMode;
  $("reader-annot-toggle").classList.toggle("active", annotMode);
  $("reader-overlay").classList.toggle("annotating", annotMode);
}

async function loadAnnotations(token) {
  if (token == null) token = Reader.seq;
  const bookAtStart = Reader.bookId;
  try {
    const res = await fetch(`/book/api/annotations?book=${encodeURIComponent(bookAtStart)}`);
    const d = await res.json();
    if (readerStale(token) || Reader.bookId !== bookAtStart) return;
    Reader.annotations = d.annotations || {};
  } catch {
    if (readerStale(token)) return;
    Reader.annotations = {};
  }
  drawAnnotationsList();
}

async function saveAnnotation(rect, note, type = "highlight") {
  const id = `a${Date.now()}`;
  const pageAnns = Reader.annotations[Reader.pageNum] || (Reader.annotations[Reader.pageNum] = []);
  pageAnns.push({ id, type, rect, note, ts: Date.now() });
  await fetch(`/book/api/annotations?book=${encodeURIComponent(Reader.bookId)}&page=${Reader.pageNum}`, {
    method: "POST", body: JSON.stringify(Reader.annotations[Reader.pageNum]),
    headers: { "Content-Type": "application/json" },
  });
  drawAnnotationsList();
}

function drawAnnotationsList() {
  const list = $("reader-ann-list");
  const anns = Reader.annotations[Reader.pageNum] || [];
  list.innerHTML = anns.length
    ? anns.map(a => `<div class="ann-item" data-id="${a.id}"><span class="ann-type">${a.type}</span> ${esc((a.note || "").slice(0, 60)) || "<i>(box)</i>"}</div>`).join("")
    : `<p class="hint">No annotations on this page. Toggle ✎ and drag to add.</p>`;
  list.querySelectorAll(".ann-item").forEach(el => {
    el.onclick = () => {
      const anns = Reader.annotations[Reader.pageNum] || [];
      const a = anns.find(x => x.id === el.dataset.id);
      if (a) { const note = prompt("Edit/delete note (empty=delete):", a.note || ""); if (note === "") { Reader.annotations[Reader.pageNum] = anns.filter(x => x.id !== a.id); saveAnnotationPage(); } else if (note !== null) { a.note = note; saveAnnotationPage(); } }
    };
  });
}

async function saveAnnotationPage() {
  await fetch(`/book/api/annotations?book=${encodeURIComponent(Reader.bookId)}&page=${Reader.pageNum}`, {
    method: "POST", body: JSON.stringify(Reader.annotations[Reader.pageNum]),
    headers: { "Content-Type": "application/json" },
  });
  renderReaderPage();
}

/* full-text search inside the current book */
async function doBookSearch() {
  const q = $("reader-search").value.trim();
  if (!q || !Reader.bookId) return;
  setStatus(`Searching "${q}" in ${Reader.bookId}…`);
  try {
    const res = await fetch(`/book/api/search?book=${encodeURIComponent(Reader.bookId)}&q=${encodeURIComponent(q)}`);
    const d = await res.json();
    const side = $("reader-side");
    const listHtml = d.results?.length
      ? d.results.map(r => `
          <div class="search-hit" data-page="${r.page}" data-para="${r.para_idx ?? ""}">
            <div class="sh-page">${r.page != null ? `p. ${r.page}${r.printed_page_number ? ` (printed ${typeof r.printed_page_number === 'object' ? r.printed_page_number.value : r.printed_page_number})` : ""}` : `¶ ${r.para_idx}`} · ${r.count}×</div>
            <div class="sh-snip">…${esc(r.snippet)}…</div>
          </div>`).join("")
      : `<p class="hint">No matches for "${esc(q)}".</p>`;
    let sec = document.getElementById("reader-search-results");
    if (!sec) {
      sec = document.createElement("div");
      sec.id = "reader-search-results";
      side.prepend(sec);
    }
    sec.innerHTML = `<h4>Search: "${esc(q)}" — ${d.n} ${Reader.txtMode ? "paragraphs" : "pages"} <button class="mini" id="search-close">×</button></h4>${listHtml}`;
    sec.querySelectorAll(".search-hit").forEach(el => {
      el.onclick = () => {
        if (Reader.txtMode || el.dataset.page === "null") {
          // TXT hit: scroll to that paragraph
          const para = el.dataset.para;
          if (para != null) {
            const pel = document.querySelector(`.txt-para[data-para="${para}"]`);
            if (pel) { pel.scrollIntoView({ block: "center" }); pel.classList.add("txt-flash"); setTimeout(() => pel.classList.remove("txt-flash"), 2500); }
          }
        } else {
          gotoPage(parseInt(el.dataset.page, 10));
        }
      };
    });
    document.getElementById("search-close").onclick = () => sec.remove();
    setStatus(`"${q}": ${d.n} pages in ${Reader.bookId}`);
  } catch (e) {
    setStatus("search failed: " + e.message);
  }
}

/* drag-to-annotate on overlay */
function overlayDragHandlers() {
  const wrap = $("reader-overlay");
  let start = null, box = null;
  wrap.addEventListener("mousedown", (e) => {
    if (!annotMode) return;
    const r = wrap.getBoundingClientRect();
    start = { x: e.clientX - r.left, y: e.clientY - r.top };
    box = document.createElement("div");
    box.className = "ann-drawing";
    wrap.appendChild(box);
  });
  window.addEventListener("mousemove", (e) => {
    if (!start) return;
    const r = wrap.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    box.style.left = `${Math.min(start.x, x)}px`; box.style.top = `${Math.min(start.y, y)}px`;
    box.style.width = `${Math.abs(x - start.x)}px`; box.style.height = `${Math.abs(y - start.y)}px`;
  });
  window.addEventListener("mouseup", (e) => {
    if (!start) return;
    const r = wrap.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const rect = { x: Math.min(start.x, x), y: Math.min(start.y, y), w: Math.abs(x - start.x), h: Math.abs(y - start.y) };
    start = null;
    if (rect.w < 8 || rect.h < 8) { box.remove(); return; }
    const note = prompt("Annotation note (optional):", "") || "";
    box.remove();
    saveAnnotation(rect, note, "highlight");
  });
}
document.addEventListener("DOMContentLoaded", overlayDragHandlers);

/* ————— keyboard shortcuts ————— */
document.addEventListener("keydown", (e) => {
  if (!Reader.open) return;
  const tag = document.activeElement?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (e.key === "Escape") { closeReader(); }
  else if (e.key === "ArrowLeft" || e.key === "PageUp") { gotoPage(Reader.pageNum - 1); }
  else if (e.key === "ArrowRight" || e.key === "PageDown") { gotoPage(Reader.pageNum + 1); }
  else if (e.key === "+" || e.key === "=") { Reader.userZoom = true; Reader.scale = Math.min(4, Reader.scale * 1.2); renderReaderPage(); }
  else if (e.key === "-") { Reader.userZoom = true; Reader.scale = Math.max(0.25, Reader.scale / 1.2); renderReaderPage(); }
});

/* TXT reading mode: paragraph-structured with word-level spans for annotation.
   TXT books have no PDF pages: paragraphs come from /book/api/txt_paragraphs,
   each word is a clickable/draggable span; annotations anchor to (para_idx, w0, w1). */
Reader.txtParas = null;

async function openTxtMode(bookId) {
  Reader.txtMode = true;
  Reader.txtParas = null;
  const _c = window.Cite ? Cite.parse(bookId) : null;
  readerVeil((_c && _c.cite) || bookId, "loading the text edition…");
  try {
    const res = await fetch(`/book/api/txt_paragraphs?book=${encodeURIComponent(bookId)}`);
    if (!res.ok) throw new Error("no txt");
    const d = await res.json();
    Reader.txtParas = d.paragraphs;
    setStatus(`${d.book_id.slice(0, 40)} — ${d.n_paragraphs} paragraphs (text mode)`);
    // The initial paint caps at 600 paragraphs for speed, but 9 of the 68
    // text editions have passages past ¶600 (Butler's Analogy runs to 2546),
    // and those silently opened at the top of the book with nothing found.
    // Locate the target first and render the window containing it.
    const target = Reader.pendingHighlight && Reader.pendingHighlight.text
      ? findTxtParaIndex(Reader.pendingHighlight.text) : -1;
    renderTxtParas(null, target);
    // a text edition has no scanned page, so the OCR pane has nothing to show;
    // leaving the empty "Page text (OCR)" heading there just looked broken
    setSidePanelMode(true);
    setReaderPage("");
    $("reader-jump").disabled = true;         // a text edition has no pages
    $("reader-jump").placeholder = "txt";
    $("reader-page-total").textContent = d.n_paragraphs + " ¶";
    // scroll to evidence passage if we came from a search hit
    if (Reader.pendingHighlight && Reader.pendingHighlight.text) {
      scrollTxtTo(Reader.pendingHighlight.text);
      Reader.pendingHighlight = null;
    }
    applyTxtTermHighlights();
    readerVeilDown();
    await loadTxtAnnotations();
  } catch (e2) {
    readerVeilDown();
    setStatus(`No PDF or TXT for ${bookId}`);
    showReaderFallback(bookId);
  }
}

/* Index of the paragraph whose text contains the passage, over the full
   data — not over what happens to be painted. */
function findTxtParaIndex(text) {
  const needle = (text || "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim().slice(0, 44);
  if (!needle) return -1;
  const paras = Reader.txtParas || [];
  for (let i = 0; i < paras.length; i++) {
    const t = (paras[i].words || []).map(w => w.w).join(" ")
      .toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ");
    if (t.includes(needle)) return i;
  }
  return -1;
}

function renderTxtParas(filterFn, centreOn = -1) {
  const body = $("reader-body");
  const host = document.createElement("div");
  host.id = "reader-txt";
  host.style.cssText = "max-width:760px;margin:0 auto;padding:28px 20px 60px";
  const paras = Reader.txtParas || [];
  const CAP = 600;
  // window the paint around the passage we were asked to show
  let lo = 0, hi = CAP;
  if (!filterFn && centreOn >= 0 && paras.length > CAP) {
    lo = Math.max(0, centreOn - Math.floor(CAP / 2));
    hi = Math.min(paras.length, lo + CAP);
    lo = Math.max(0, hi - CAP);
  }
  Reader.txtWindow = { lo, hi, total: paras.length };
  let shown = 0;
  paras.forEach((p, i) => {
    if (!filterFn && (i < lo || i >= hi)) return;
    if (shown > CAP && !filterFn) return; // paint cap; use search for more
    const div = document.createElement("div");
    div.className = "txt-para";
    div.dataset.para = p.para_idx;
    div.innerHTML = `<div class="txt-para-no">¶${p.para_idx}</div>` +
      p.words.map((w, wi) =>
        `<span class="txt-w" data-para="${p.para_idx}" data-wi="${wi}">${esc(w.w)}</span>`
      ).join(" ");
    host.appendChild(div);
    shown++;
  });
  body.innerHTML = "";
  const win = Reader.txtWindow;
  if (win && !filterFn && (win.lo > 0 || win.hi < win.total)) {
    const note = document.createElement("div");
    note.className = "txt-window-note";
    note.textContent = `showing ¶${win.lo}–¶${win.hi - 1} of ${win.total} — use the in-book search for the rest`;
    body.appendChild(note);
  }
  body.appendChild(host);
  wireTxtSelection(host);
  renderTxtAnnotationMarks();
}

/* Word-level query highlighting for text editions.
   PDF pages box every matching word; text editions showed nothing, so the
   reader dropped you into a wall of prose with no marker at all. */
function applyTxtTermHighlights() {
  const terms = (Reader.activeTerms || []).map(t => t.toLowerCase()).filter(t => t.length > 2);
  if (!terms.length) return;
  const host = document.getElementById("reader-txt");
  if (!host) return;
  let n = 0;
  for (const el of host.querySelectorAll(".txt-w")) {
    const w = el.textContent.toLowerCase().replace(/^[^a-z0-9]+|[^a-z0-9]+$/g, "");
    if (!w) continue;
    if (terms.some(t => w === t || w.startsWith(t) || (t.length > 4 && w.includes(t)))) {
      el.classList.add("txt-hit");
      n++;
    }
  }
  if (n) setStatus(`${n} matching words in this text`);
}

function scrollTxtTo(text) {
  const norm = (t) => (t || "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
  const needle = norm(text).slice(0, 44);
  const host = document.getElementById("reader-txt");
  if (!host || !needle) return false;
  host.querySelectorAll(".txt-target").forEach(e => e.classList.remove("txt-target"));
  for (const pel of host.querySelectorAll(".txt-para")) {
    if (norm(pel.textContent).includes(needle)) {
      pel.scrollIntoView({ block: "center" });
      // a 3s flash was the only marker, so anyone who looked away lost the
      // passage in a wall of prose; the marker now stays until you open
      // another one, the way a PDF highlight box does
      pel.classList.add("txt-target");
      return true;
    }
  }
  return false;
}

/* word-range selection → annotation */
function handleTxtSelection() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.anchorNode) return;
    const range = sel.getRangeAt(0);
    const startEl = sel.anchorNode.parentElement?.closest?.(".txt-w");
    const endEl = sel.focusNode.parentElement?.closest?.(".txt-w");
    if (!startEl || !endEl || startEl.dataset.para !== endEl.dataset.para) {
      sel.removeAllRanges();
      return;
    }
    const para = parseInt(startEl.dataset.para, 10);
    const w0 = Math.min(+startEl.dataset.wi, +endEl.dataset.wi);
    const w1 = Math.max(+startEl.dataset.wi, +endEl.dataset.wi);
    const note = prompt(`Annotate ¶${para} words ${w0}-${w1} (note, empty=cancel):`, "");
    sel.removeAllRanges();
    if (note === null || note === "") return;
    saveTxtAnnotation({ para_idx: para, w0, w1, note, ts: Date.now(),
                        quote: selectedQuote(para, w0, w1) });
}

function wireTxtSelection(host) {
  host.onmouseup = handleTxtSelection;
  // document-level fallback: selection may release outside the host element
  document.onmouseup = (e) => {
    if (!Reader.txtMode || !Reader.open) return;
    if (!document.getElementById("reader-txt")) return;
    const inTxt = e.target?.closest?.("#reader-txt");
    if (inTxt) handleTxtSelection();
  };
}

function selectedQuote(para, w0, w1) {
  const host = document.getElementById("reader-txt");
  const pel = host?.querySelector(`.txt-para[data-para="${para}"]`);
  if (!pel) return "";
  const spans = [...pel.querySelectorAll(".txt-w")].slice(w0, w1 + 1);
  return spans.map(s => s.textContent).join(" ").slice(0, 300);
}

async function loadTxtAnnotations() {
  try {
    const res = await fetch(`/book/api/annotations?book=${encodeURIComponent(Reader.bookId + "__txt")}`);
    const d = await res.json();
    Reader.annotations = {};
    for (const [k, v] of Object.entries(d.annotations || {})) {
      Reader.annotations[k] = v;
    }
  } catch { Reader.annotations = {}; }
  renderTxtAnnotationMarks();
  drawAnnotationsListTxt();
}

function renderTxtAnnotationMarks() {
  const host = document.getElementById("reader-txt");
  if (!host) return;
  host.querySelectorAll(".txt-w.ann").forEach(s => s.classList.remove("ann"));
  const flat = Object.values(Reader.annotations || {}).flat();
  const byPara = {};
  flat.forEach(a => { (byPara[a.para_idx] = byPara[a.para_idx] || []).push(a); });
  for (const [para, anns] of Object.entries(byPara)) {
    const pel = host.querySelector(`.txt-para[data-para="${para}"]`);
    if (!pel) continue;
    const spans = pel.querySelectorAll(".txt-w");
    anns.forEach(a => {
      for (let i = a.w0; i <= Math.min(a.w1, spans.length - 1); i++) {
        spans[i].classList.add("ann");
        spans[i].title = a.note || "";
      }
    });
  }
}

async function saveTxtAnnotation(a) {
  const key = String(a.para_idx);
  const cur = Reader.annotations[key] || (Reader.annotations[key] = []);
  cur.push(a);
  await fetch(`/book/api/annotations?book=${encodeURIComponent(Reader.bookId + "__txt")}&page=${key}`, {
    method: "POST", body: JSON.stringify(cur),
    headers: { "Content-Type": "application/json" },
  });
  renderTxtAnnotationMarks();
  drawAnnotationsListTxt();
}

function drawAnnotationsListTxt() {
  const list = $("reader-ann-list");
  const flat = Object.values(Reader.annotations || {}).flat();
  list.innerHTML = flat.length
    ? flat.map(a => `<div class="ann-item" data-p="${a.para_idx}"><span class="ann-type">¶${a.para_idx} w${a.w0}-${a.w1}</span> ${esc((a.note || "").slice(0, 70)) || "<i>(mark)</i>"}<br><span style="opacity:.6">${esc((a.quote || "").slice(0, 90))}</span></div>`).join("")
    : `<p class="hint">Select words in any paragraph to annotate.</p>`;
  list.querySelectorAll(".ann-item").forEach(el => {
    el.onclick = () => {
      const pel = document.querySelector(`.txt-para[data-para="${el.dataset.p}"]`);
      if (pel) { pel.scrollIntoView({ block: "center" }); pel.classList.add("txt-flash"); setTimeout(() => pel.classList.remove("txt-flash"), 2500); }
    };
  });
}

/* ————— helpers used by app.js ————— */
function setReaderHighlights(conceptId) {
  const evList = (S.data.evidence[conceptId] || []);
  Reader.highlights = evList
    .filter(e => e.book_id && e.page)
    .map(e => ({ book_id: e.book_id, page: e.page, bbox_pts: e.bbox_pts, concept_id: conceptId, text: e.text }));
  // also set word-highlight terms from the concept's label/aliases so opening
  // evidence from the detail panel highlights the concept's words on the page
  const n = (typeof S !== "undefined" && S.byId?.get(conceptId)) || null;
  if (n) {
    const terms = new Set();
    n.label?.toLowerCase().split(/[\s\-]+/).forEach(t => { if (t.length > 2) terms.add(t); });
    (n.aliases || []).forEach(a => a.toLowerCase().split(/[\s\-]+/).forEach(t => { if (t.length > 2) terms.add(t); }));
    Reader.activeTerms = terms.size ? [...terms].slice(0, 6) : null;
  }
}

/* open reader at a specific evidence entry */
function openEvidenceInReader(evidence) {
  if (!evidence.book_id) return;
  if (!evidence.has_pdf) {
    // TXT mode: no PDF scan; load text and scroll to the passage
    Reader.bookId = evidence.book_id;
    Reader.open = true;
    Reader.txtMode = false;
    Reader.pendingHighlight = { text: evidence.text || "", page: evidence.page };
    showReaderShell();
    openTxtMode(evidence.book_id);
    return;
  }
  openReader(evidence.book_id, {
    page: evidence.page || 1,
    highlight: evidence.bbox_pts ? { page: evidence.page, bbox_pts: evidence.bbox_pts, concept_id: evidence.concept_id } : null,
  });
}

/* ————— keyboard shortcuts ————— */
document.addEventListener("keydown", (e) => {
  if (!Reader.open) return;
  // don't hijack typing in inputs
  const tag = document.activeElement?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (e.key === "Escape") { closeReader(); }
  else if (e.key === "ArrowLeft" || e.key === "PageUp") { gotoPage(Reader.pageNum - 1); }
  else if (e.key === "ArrowRight" || e.key === "PageDown") { gotoPage(Reader.pageNum + 1); }
  else if (e.key === "+" || e.key === "=") { Reader.userZoom = true; Reader.scale = Math.min(4, Reader.scale * 1.2); renderReaderPage(); }
  else if (e.key === "-") { Reader.userZoom = true; Reader.scale = Math.max(0.25, Reader.scale / 1.2); renderReaderPage(); }
});
