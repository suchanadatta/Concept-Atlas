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
};

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
  $("reader-title").textContent = Reader.bookId;
  $("reader-download-pdf").onclick = () => { location.href = `/book/pdf/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-download-txt").onclick = () => { location.href = `/book/txt/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-download-md").onclick = () => { location.href = `/book/md/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-download-jsonl").onclick = () => { location.href = `/book/jsonl/${encodeURIComponent(Reader.bookId)}`; };
  $("reader-export-json").onclick = () => { location.href = `/book/api/export_annotations?book=${encodeURIComponent(Reader.bookId)}&fmt=json`; };
  $("reader-export-md").onclick = () => { location.href = `/book/api/export_annotations?book=${encodeURIComponent(Reader.bookId)}&fmt=markdown`; };
  $("reader-close").onclick = closeReader;
  $("reader-prev").onclick = () => gotoPage(Reader.pageNum - 1);
  $("reader-next").onclick = () => gotoPage(Reader.pageNum + 1);
  $("reader-jump").onchange = (e) => gotoPage(parseInt(e.target.value, 10) || 1);
  $("reader-zoom-in").onclick = () => { Reader.userZoom = true; Reader.scale = Math.min(4, Reader.scale * 1.2); renderReaderPage(); };
  $("reader-zoom-out").onclick = () => { Reader.userZoom = true; Reader.scale = Math.max(0.25, Reader.scale / 1.2); renderReaderPage(); };
  $("reader-zoom-fit").onclick = () => { Reader.userZoom = false; Reader.scale = 1; renderReaderPage(); };
  $("reader-annot-toggle").onclick = toggleAnnotMode;
  $("reader-search-go").onclick = doBookSearch;
  $("reader-search").onkeydown = (e) => { if (e.key === "Enter") doBookSearch(); };
}
async function openReader(bookId, opts = {}) {
  if (!bookId) return;
  Reader.bookId = bookId;
  Reader.open = true;
  Reader.txtMode = false;
  Reader.pendingHighlight = opts.highlight || null;
  Reader.pageNum = opts.page || 1;
  showReaderShell();
  // loading screen while the PDF streams (large scans take seconds)
  $("reader-body").innerHTML = `
    <div class="pdf-loading-state">
      <div class="searching-spinner"></div>
      <div class="pdf-loading-text">Opening <b>${esc(bookId.slice(0, 48))}</b>…</div>
      <div class="pdf-loading-sub">streaming PDF scan · rendering page ${opts.page || 1}</div>
    </div>`;
  setStatus(`Opening ${bookId}…`);
  try {
    if (!Reader.pdfDoc || Reader._loadedFor !== bookId) {
      const url = `/book/pdf/${encodeURIComponent(bookId)}`;
      const task = pdfjsLib.getDocument({ url, disableAutoFetch: false });
      Reader.pdfDoc = await task.promise;
      Reader._loadedFor = bookId;
    }
    Reader.numPages = Reader.pdfDoc.numPages;
    $("reader-page-total").textContent = Reader.numPages;
    $("reader-jump").max = Reader.numPages;
    // restore the page-wrap markup (loading screen replaced it)
    $("reader-body").innerHTML = `
      <div id="reader-page-wrap">
        <canvas id="reader-canvas"></canvas>
        <div id="reader-overlay"></div>
      </div>`;
    // rewire overlay drag for annotations
    overlayDragHandlers();
    await renderReaderPage();
    await loadAnnotations();
    await loadPageOcr();
    setStatus(`${bookId} — ${Reader.numPages} pages`);
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
  Reader.pageNum = p;
  await renderReaderPage();
  await loadAnnotations();
  await loadPageOcr();
}

/* ————— render one page + overlay ————— */
async function renderReaderPage() {
  const page = await Reader.pdfDoc.getPage(Reader.pageNum);
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
  $("reader-page-cur").textContent = Reader.pageNum;
  $("reader-jump").value = Reader.pageNum;
  $("reader-zoom-label").textContent = Math.round(scale / fitScale * 100) + "%";
  drawOverlay(page, vp);
}

/* map PDF points (bbox_pts) -> canvas px using page viewport in points */
function ptsToCanvas(bbox, vp) {
  const [x0, y0, x1, y1] = bbox;
  const sx = vp.width / vp.viewBox[2], sy = vp.height / vp.viewBox[3];
  return { x: x0 * sx, y: vp.height - y1 * sy, w: (x1 - x0) * sx, h: (y1 - y0) * sy };
}

function drawOverlay(page, vp) {
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
  applyWordHighlights();
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

async function applyWordHighlights() {
  if (!Reader.activeTerms || !Reader.activeTerms.length) return;
  // dedup: clear previous word highlights for this page before re-applying
  document.querySelectorAll(".hl-word").forEach(el => el.remove());
  const wrap = $("reader-overlay");
  // fetch page words
  try {
    const res = await fetch(`/book/api/page_text?book=${encodeURIComponent(Reader.bookId)}&page=${Reader.pageNum}`);
    if (!res.ok) return;
    const d = await res.json();
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
async function loadPageOcr() {
  const el = $("reader-ocr");
  if (!el) return;
  el.textContent = "loading…";
  try {
    const res = await fetch(`/book/api/page_text?book=${encodeURIComponent(Reader.bookId)}&page=${Reader.pageNum}`);
    if (!res.ok) { el.textContent = "(no OCR for this page)"; return; }
    const d = await res.json();
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

async function loadAnnotations() {
  try {
    const res = await fetch(`/book/api/annotations?book=${encodeURIComponent(Reader.bookId)}`);
    const d = await res.json();
    Reader.annotations = d.annotations || {};
  } catch { Reader.annotations = {}; }
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
  try {
    const res = await fetch(`/book/api/txt_paragraphs?book=${encodeURIComponent(bookId)}`);
    if (!res.ok) throw new Error("no txt");
    const d = await res.json();
    Reader.txtParas = d.paragraphs;
    setStatus(`${d.book_id.slice(0, 40)} — ${d.n_paragraphs} paragraphs (text mode)`);
    renderTxtParas(null);
    $("reader-page-cur").textContent = "txt";
    $("reader-page-total").textContent = d.n_paragraphs + " ¶";
    // scroll to evidence passage if we came from a search hit
    if (Reader.pendingHighlight && Reader.pendingHighlight.text) {
      scrollTxtTo(Reader.pendingHighlight.text);
      Reader.pendingHighlight = null;
    }
    await loadTxtAnnotations();
  } catch (e2) {
    setStatus(`No PDF or TXT for ${bookId}`);
    showReaderFallback(bookId);
  }
}

function renderTxtParas(filterFn) {
  const body = $("reader-body");
  const host = document.createElement("div");
  host.id = "reader-txt";
  host.style.cssText = "max-width:760px;margin:0 auto;padding:28px 20px 60px";
  const paras = Reader.txtParas || [];
  let shown = 0;
  paras.forEach((p, i) => {
    if (shown > 600 && !filterFn) return; // initial paint cap; use search for more
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
  body.appendChild(host);
  wireTxtSelection(host);
  renderTxtAnnotationMarks();
}

function scrollTxtTo(text) {
  const needle = (text || "").slice(0, 80).toLowerCase().replace(/\s+/g, " ");
  const host = document.getElementById("reader-txt");
  if (!host) return;
  for (const pel of host.querySelectorAll(".txt-para")) {
    const t = pel.textContent.toLowerCase().replace(/\s+/g, " ");
    if (needle && t.includes(needle.slice(0, 40))) {
      pel.scrollIntoView({ block: "center" });
      pel.classList.add("txt-flash");
      setTimeout(() => pel.classList.remove("txt-flash"), 3000);
      return;
    }
  }
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
