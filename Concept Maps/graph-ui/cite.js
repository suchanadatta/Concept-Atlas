/* Human-readable citations for raw corpus book ids.

   The index carries ids in two shapes:
     OCR  "CLARKE_1706_1708_A-Discourse-concerning-the-unchangeable-Obligations"
     TXT  "Turnbull The Principles of Moral and Christian Philosophy vol. 1"

   Showing those verbatim ("BUTLER 1726 1887 Human-Nature-and-other-Sermons 0")
   made every result read like a filename. The semantic/BM25 backends now
   return parsed author/title/year fields; this is the mirror for the client
   paths that don't (keyword fallback, the concept graph, the reader title),
   and it must stay in step with parse_book_id() in jasper_search_server_v2.py. */
"use strict";

const Cite = (function () {
  const ROMAN = /^[ivxlcdm]+$/i;
  const STOPCAP = new Set(["and", "of", "the", "or", "on", "in", "to", "a", "an", "with", "de"]);

  function titlecase(s) {
    return String(s || "")
      .split(/\s+/)
      .map((w, i) => {
        if (!w) return w;
        const lw = w.toLowerCase();
        if (w.length > 1 && w === w.toUpperCase() && ROMAN.test(w)) return w.toUpperCase();
        if (i && STOPCAP.has(lw)) return lw;
        if (w === w.toUpperCase()) return lw[0].toUpperCase() + lw.slice(1);
        return w[0].toUpperCase() + w.slice(1);
      })
      .join(" ");
  }

  const cache = new Map();

  function parse(bookId) {
    const raw = String(bookId || "").trim();
    if (!raw) return { author: "", year: null, title: "", volume: "", cite: "", short: "" };
    if (cache.has(raw)) return cache.get(raw);

    let author = "", year = null, volume = "", title = "";
    const parts = raw.split("_");
    const AUTHOR_SEG = /^[A-Z][A-Za-z-]*(-and-[A-Z][A-Za-z-]*)?$/;
    if (parts.length >= 2 && AUTHOR_SEG.test(parts[0]) &&
        (parts[0] === parts[0].toUpperCase() || /^\d{4}(-\d{4})?$/.test(parts[1]))) {
      author = parts[0].replace(/-and-/g, " & ").replace(/-/g, " ")
        .split(" & ").map(titlecase).join(" & ");
      if (author.toLowerCase() === "anon") author = "Anonymous";
      const rest = parts.slice(1);
      if (/^\d{4}(-\d{4})?$/.test(rest[0])) year = rest.shift().split("-")[0];
      if (rest.length && /^\d{1,4}$/.test(rest[0])) rest.shift();   // reprint year
      while (rest.length && /^\d{1,2}$/.test(rest[rest.length - 1])) {
        const v = rest.pop();
        if (v !== "0") volume = `vol. ${v}`;
      }
      title = titlecase(rest.join(" ").replace(/[-_]/g, " "));
    } else {
      const m = raw.match(/^([A-Z][a-zA-Z'-]+)\s+(.*)$/);
      if (m) { author = m[1]; title = m[2]; } else { title = raw; }
      title = title.replace(/_/g, " ");
      const ym = title.match(/\b(1[4-9]\d\d|20\d\d)\b/);
      if (ym) year = ym[1];
      const vm = title.match(/\b(vol\.?\s*\d+|part\s*\d+)\b/i);
      if (vm) { volume = vm[1]; title = (title.slice(0, vm.index) + title.slice(vm.index + vm[0].length)).trim().replace(/[\s,]+$/, ""); }
      if (year) title = title.split(year).join(" ");
    }
    title = title.replace(/\(\s*\)|\[\s*\]/g, " ").replace(/\s+/g, " ").replace(/^[\s,.-]+|[\s,.-]+$/g, "");
    if (!title && author) { title = author; author = ""; }

    let cite = title;
    if (author) cite = title ? `${author}, ${title}` : author;
    if (volume) cite += `, ${volume}`;
    if (year) cite += ` (${year})`;

    const out = { author, year, title, volume, cite, short: shortOf(author, title, year) };
    cache.set(raw, out);
    return out;
  }

  function shortOf(author, title, year) {
    const t = title.length > 46 ? title.slice(0, 44).replace(/\s+\S*$/, "") + "…" : title;
    return [author, t].filter(Boolean).join(", ") + (year ? ` (${year})` : "");
  }

  /* Prefer the fields the backend already parsed; fall back to parsing here. */
  function of(result) {
    if (result && result.cite) {
      return {
        author: result.author || "", year: result.year || null,
        title: result.title || "", volume: result.volume || "",
        cite: result.cite, short: shortOf(result.author || "", result.title || "", result.year),
      };
    }
    return parse(result && result.book_id ? result.book_id : result);
  }

  return { parse, of, titlecase };
})();

window.Cite = Cite;
