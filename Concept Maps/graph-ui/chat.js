/* Ask the corpus — chat with explicitly attached context.

   The point of this panel is that nothing is retrieved behind your back: you
   choose what the model may read (a book, a page range, a concept with its
   relations, a passage, a saved search), you can see exactly how much of the
   window it fills, and the answer is grounded in that and cited from it. The
   model's reasoning arrives on its own event stream and is shown apart from
   the answer rather than mixed into it.

   Everything is scoped to a signed-in account; sessions are exportable as
   JSONL and importable by anyone else. */
"use strict";

const Chat = (function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const TOKEN_KEY = "atlas.chatToken";

  let user = null;
  let sessions = [];
  let cur = null;            // {session, messages, context}
  let streaming = false;
  let pickerTab = "books";
  let library = null;
  let webOn = (() => { try { return localStorage.getItem("atlas.chatWeb") === "on"; } catch { return false; } })();
  // the self-check costs a second pass, so it is a choice — but it defaults on,
  // because an unchecked quotation is the failure this whole panel exists to avoid
  let verifyOn = (() => { try { return localStorage.getItem("atlas.chatVerify") !== "off"; } catch { return true; } })();

  const tok = () => { try { return localStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; } };
  const setTok = (t) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ } };

  async function api(path, body, method) {
    const r = await fetch("/book/api/chat" + path, {
      method: method || (body !== undefined ? "POST" : "GET"),
      headers: { "Content-Type": "application/json", "X-Atlas-Token": tok() },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(d.error || `HTTP ${r.status}`), { status: r.status });
    return d;
  }

  /* ------------------------------------------------------------ open/close */
  async function open() {
    $("chat-panel").classList.remove("hidden");
    document.body.classList.add("chat-open");
    // A debate in flight is streaming into the body that is already there.
    // Re-rendering would replace it with the ordinary thread view and the rest
    // of the debate would arrive in a detached node nobody can see — so when
    // one is running, just show what is already on screen.
    if (debating) { scrollDown(); return; }
    if (!user) {
      // distinguish "not signed in" from "the service is not answering" —
      // showing a sign-in form for a dead backend just wastes the reader's
      // time typing a password that cannot be checked
      try {
        user = (await api("/auth/me")).user;
      } catch (e) {
        user = null;
        if (e.status === undefined || e.status >= 500) return renderOffline(e.message);
      }
    }
    if (!user) return renderAuth();
    await loadSessions();
    render();
  }

  function renderOffline(msg) {
    $("chat-side").innerHTML = "";
    $("chat-ctx").innerHTML = "";
    $("chat-body").innerHTML = `
      <div class="ch-auth">
        <h2>The chat service is not answering</h2>
        <p class="ch-auth-sub">Search, the concept map and the reader all still work — only Ask needs
          this service.</p>
        <div class="ch-msg err">${esc(msg || "no response")}</div>
        <p class="ch-auth-sub">Start it on the server with
          <code>log/start_chat.sh</code>, then retry.</p>
        <button class="ch-primary" id="ch-retry">Retry</button>
      </div>`;
    $("ch-retry").onclick = () => { user = null; open(); };
  }
  /* Closing only hides the panel — the DOM stays, so a debate in flight keeps
     streaming into it and is there when you come back. It must NOT be aborted
     here: openSource() calls close() to show the reader, so a reader clicking
     a citation mid-debate would have killed the debate they were reading. */
  function close() {
    $("chat-panel").classList.add("hidden");
    document.body.classList.remove("chat-open");
  }

  /* ------------------------------------------------------------------ auth */
  let authMode = "login";      // login | register | forgot | reset
  let resetCode = "";

  function renderAuth(msg, isErr) {
    const F = {
      login: { title: "Sign in", cta: "Sign in" },
      register: { title: "Create an account", cta: "Create account" },
      forgot: { title: "Reset your password", cta: "Get a reset code" },
      reset: { title: "Set a new password", cta: "Set password" },
    }[authMode];
    $("chat-body").innerHTML = `
      <div class="ch-auth">
        <h2>${F.title}</h2>
        <p class="ch-auth-sub">Conversations, their attached context and their history are tied to your
          account, so they survive a reload and can be exported.</p>
        ${msg ? `<div class="ch-msg ${isErr ? "err" : "ok"}">${esc(msg)}</div>` : ""}
        <form id="ch-auth-form" autocomplete="on">
          ${authMode === "register" ? `
            <label>Username<input name="username" required minlength="3" maxlength="32"
              pattern="[A-Za-z0-9._-]{3,32}" autocomplete="username"></label>
            <label>Email<input name="email" type="email" required autocomplete="email"></label>
            <label>Display name <span class="opt">optional</span><input name="display_name" autocomplete="name"></label>
            <label>Password <span class="opt">at least 8 characters</span>
              <input name="password" type="password" required minlength="8" autocomplete="new-password"></label>
          ` : authMode === "login" ? `
            <label>Username or email<input name="username_or_email" required autocomplete="username"></label>
            <label>Password<input name="password" type="password" required autocomplete="current-password"></label>
          ` : authMode === "forgot" ? `
            <label>Email<input name="email" type="email" required autocomplete="email"></label>
          ` : `
            <label>Reset code<input name="reset_token" required value="${esc(resetCode)}"></label>
            <label>New password<input name="password" type="password" required minlength="8"
              autocomplete="new-password"></label>
          `}
          <button type="submit" class="ch-primary">${F.cta}</button>
        </form>
        <div class="ch-auth-alt">
          ${authMode === "login" ? `
            <button data-mode="register">Create an account</button>
            <button data-mode="forgot">Forgotten your password?</button>` : ""}
          ${authMode === "register" ? `<button data-mode="login">I already have an account</button>` : ""}
          ${authMode === "forgot" ? `<button data-mode="login">Back to sign in</button>
            <button data-mode="reset">I already have a code</button>` : ""}
          ${authMode === "reset" ? `<button data-mode="login">Back to sign in</button>` : ""}
        </div>
      </div>`;
    $("chat-side").innerHTML = "";
    $("chat-ctx").innerHTML = "";
    paintAccount();
    $("ch-auth-form").onsubmit = onAuthSubmit;
    $("chat-body").querySelectorAll(".ch-auth-alt button").forEach(b => {
      b.onclick = () => { authMode = b.dataset.mode; renderAuth(); };
    });
  }

  async function onAuthSubmit(e) {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target).entries());
    try {
      if (authMode === "login" || authMode === "register") {
        const d = await api(authMode === "login" ? "/auth/login" : "/auth/register", fd);
        setTok(d.token); user = d.user;
        await loadSessions(); render();
      } else if (authMode === "forgot") {
        const d = await api("/auth/forgot", fd);
        resetCode = d.reset_token || "";
        authMode = "reset";
        renderAuth(d.reset_token
          ? "No mail server is configured on this host, so here is your code — it expires in an hour."
          : (d.note || "If that address is registered, a code has been issued."));
      } else {
        const d = await api("/auth/reset", fd);
        setTok(d.token); user = d.user;
        await loadSessions(); render();
      }
    } catch (err) {
      renderAuth(err.message, true);
    }
  }

  async function signOut() {
    try { await api("/auth/logout", {}); } catch { /* token already gone */ }
    setTok(""); user = null; sessions = []; cur = null;
    authMode = "login";
    renderAuth("Signed out.");
    paintAccount();
  }

  /* -------------------------------------------------------------- sessions */
  async function loadSessions() {
    try { sessions = (await api("/sessions")).sessions || []; } catch { sessions = []; }
    if (!cur && sessions.length) await loadSession(sessions[0].id);
    if (!sessions.length) await newSession();
  }
  async function newSession() {
    const d = await api("/sessions", { title: "New conversation" });
    // refetch rather than unshifting, so a session created elsewhere (an
    // import, another tab) shows up without a reload
    try { sessions = (await api("/sessions")).sessions || []; } catch { sessions.unshift(d.session); }
    await loadSession(d.session.id);
  }
  async function loadSession(id) {
    // a debate belongs to the session that is on screen
    if (cur && cur.session && cur.session.id !== id) stopDebate("moved to another session");
    // ...and while one is running, do not repaint over its live view
    if (debating && cur && cur.session && cur.session.id === id) return;
    cur = await api("/sessions/" + id);
    render();
  }

  /* The account chip lives in the global app bar so it is reachable from every
     view; before, signing in meant opening the chat panel first. */
  function paintAccount() {
    const host = $("app-account");
    if (!host) return;
    if (!user) {
      host.innerHTML = `<button class="app-btn acct-in" id="acct-signin">Sign in</button>`;
      $("acct-signin").onclick = () => { authMode = "login"; open(); };
      return;
    }
    const name = user.display_name || user.username;
    host.innerHTML = `
      <button class="acct-chip" id="acct-chip" aria-haspopup="true" aria-expanded="false">
        <span class="acct-av">${esc(name.slice(0, 1).toUpperCase())}</span>
        <span class="acct-name">${esc(name)}</span>
      </button>
      <div class="acct-menu hidden" id="acct-menu" role="menu">
        <div class="acct-who"><b>${esc(name)}</b><span>${esc(user.email)}</span></div>
        <button id="acct-sessions" role="menuitem">Your conversations</button>
        <button id="acct-settings" role="menuitem">Account settings</button>
        <button id="acct-out" role="menuitem">Sign out</button>
      </div>`;
    const chip = $("acct-chip"), menu = $("acct-menu");
    const closeMenu = () => { menu.classList.add("hidden"); chip.setAttribute("aria-expanded", "false"); };
    chip.onclick = (e) => {
      e.stopPropagation();
      const showIt = menu.classList.contains("hidden");
      menu.classList.toggle("hidden", !showIt);
      chip.setAttribute("aria-expanded", String(showIt));
    };
    document.addEventListener("click", (e) => {
      if (!menu.classList.contains("hidden") && !menu.contains(e.target) && e.target !== chip) closeMenu();
    });
    $("acct-sessions").onclick = () => { closeMenu(); open(); };
    $("acct-settings").onclick = async () => {
      closeMenu();
      await open();
      renderAccount();
    };
    $("acct-out").onclick = () => { closeMenu(); signOut(); };
  }
  function paintHeader() { paintAccount(); }

  /* ---------------------------------------------------------------- render */
  function render() {
    paintHeader();
    renderSessions();
    renderContext();
    renderThread();
  }

  function renderSessions() {
    $("chat-side").innerHTML = `
      <div class="ch-side-head">
        <button id="ch-new" class="ch-primary sm">+ New</button>
        <button id="ch-import" class="ch-ghost sm" title="Import a session someone exported">Import</button>
        <input id="ch-import-file" type="file" accept=".jsonl,.ndjson,application/x-ndjson" hidden>
      </div>
      <div class="ch-sessions">
        ${sessions.map(s => `
          <div class="ch-sess${cur && cur.session.id === s.id ? " active" : ""}" data-id="${esc(s.id)}">
            <div class="ch-sess-t">${esc(s.title)}</div>
            <div class="ch-sess-m">${s.n_messages} message${s.n_messages === 1 ? "" : "s"} ·
              ${new Date(s.updated_at * 1000).toLocaleDateString()}</div>
            <div class="ch-sess-a">
              <button data-act="rename" data-id="${esc(s.id)}" title="Rename">✎</button>
              <button data-act="export" data-id="${esc(s.id)}" title="Export as JSONL">⬇</button>
              <button data-act="delete" data-id="${esc(s.id)}" title="Delete">🗑</button>
            </div>
          </div>`).join("")}
      </div>`;
    $("ch-new").onclick = () => newSession().catch(e => alert(e.message));
    $("ch-import").onclick = () => $("ch-import-file").click();
    $("ch-import-file").onchange = async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        const d = await api("/sessions/import", { jsonl: await f.text() });
        await loadSessions(); await loadSession(d.session.id);
      } catch (err) { alert("Import failed: " + err.message); }
      e.target.value = "";
    };
    $("chat-side").querySelectorAll(".ch-sess").forEach(el => {
      el.onclick = (e) => { if (!e.target.closest(".ch-sess-a")) loadSession(el.dataset.id); };
    });
    $("chat-side").querySelectorAll(".ch-sess-a button").forEach(b => {
      b.onclick = async (e) => {
        e.stopPropagation();
        const id = b.dataset.id;
        if (b.dataset.act === "export") {
          // the token is a header, so fetch then hand the blob to the browser
          const r = await fetch(`/book/api/chat/sessions/${id}/export`, { headers: { "X-Atlas-Token": tok() } });
          const blob = await r.blob();
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = `atlas-session-${id}.jsonl`;
          a.click();
          setTimeout(() => URL.revokeObjectURL(a.href), 4000);
        } else if (b.dataset.act === "rename") {
          const t = prompt("Rename this conversation:", (sessions.find(s => s.id === id) || {}).title || "");
          if (t) { await api(`/sessions/${id}/rename`, { title: t }); await loadSessions(); if (cur && cur.session.id === id) await loadSession(id); else render(); }
        } else if (b.dataset.act === "delete") {
          if (!confirm("Delete this conversation and its attached context?")) return;
          await api(`/sessions/${id}/delete`, {});
          if (cur && cur.session.id === id) cur = null;
          await loadSessions(); render();
        }
      };
    });
  }

  const KIND_ICON = { book: "📕", concept: "◈", passage: "❝", search: "🔍", note: "✎" };

  function renderContext() {
    const host = $("chat-ctx");
    if (!cur) { host.innerHTML = ""; return; }
    const items = cur.context || [];
    const chars = items.reduce((a, i) => a + (i.n_chars || 0), 0);
    // the model's window in characters, at the same ratio the server budgets by
    const cap = 550000 * 3.6 * 0.55;
    const pct = Math.min(100, (chars / cap) * 100);
    host.innerHTML = `
      <div class="ch-ctx-head">
        <h4>Context</h4>
        <button id="ch-add-ctx" class="ch-primary sm">+ Add to context</button>
      </div>
      <div class="ch-ctx-meter" title="${chars.toLocaleString()} characters ≈ ${Math.round(chars / 3.6).toLocaleString()} tokens of a 550k window">
        <i style="width:${pct.toFixed(1)}%"></i>
      </div>
      <div class="ch-ctx-sub">${items.length} item${items.length === 1 ? "" : "s"} ·
        ≈${Math.round(chars / 3.6).toLocaleString()} tokens of 550k</div>
      <div class="ch-ctx-list">
        ${items.length ? items.map(i => `
          <div class="ch-ctx-item">
            <span class="ch-ctx-k">${KIND_ICON[i.kind] || "•"}</span>
            <span class="ch-ctx-l" title="${esc(i.ref || "")}">${esc(i.label)}</span>
            <span class="ch-ctx-n">${Math.round((i.n_chars || 0) / 3.6).toLocaleString()}t</span>
            <button class="ch-ctx-x" data-rm="${esc(i.id)}" title="Remove">×</button>
          </div>`).join("")
        : `<p class="ch-none">Nothing attached yet. The model can only read what you add here.</p>`}
      </div>`;
    $("ch-add-ctx").onclick = openPicker;
    host.querySelectorAll(".ch-ctx-x").forEach(b => {
      b.onclick = async () => {
        await api(`/sessions/${cur.session.id}/context/remove`, { ids: [b.dataset.rm] });
        await loadSession(cur.session.id);
      };
    });
  }

  const TOOL_LABEL = {
    search_corpus: "searched the corpus", read_source: "read the source",
    find_concept: "looked up concepts", concept_detail: "walked the concept map",
    concept_passages: "pulled attesting quotes", query_network: "built the query network",
    list_authors: "checked the authors", list_books: "listed the books",
    compare_ideas: "compared the ideas", verify_quote: "checked a quotation",
    web_search: "searched the web", web_fetch: "fetched a page",
  };

  function traceHTML(m) {
    // check-phase calls are listed in the check panel instead
    const t = (m.tools || []).filter(c => c.phase !== "verify");
    if (!t.length) return "";
    const live = m._live;
    return `
      <details class="ch-trace" ${live ? "open" : ""}>
        <summary>${live ? "Working" : "What it looked at"}
          <span class="ch-rlen">${t.length} call${t.length === 1 ? "" : "s"}</span></summary>
        <ol class="ch-trace-list">
          ${t.map(c => `<li>
            <span class="ch-tname">${esc(TOOL_LABEL[c.name] || c.name)}</span>
            ${c.args && Object.keys(c.args).length
              ? `<code>${esc(Object.entries(c.args).map(([k, v]) => `${k}=${v}`).join(" · ").slice(0, 120))}</code>` : ""}
            ${c.summary ? `<span class="ch-tsum">${esc(c.summary)}</span>`
              : `<span class="ch-tsum ch-trun">running…</span>`}
          </li>`).join("")}
        </ol>
      </details>`;
  }

  /* Sources are the point of the whole thing: a marker in the answer resolves
     to a book and a page, and clicking it opens the reader there. */
  function sourcesHTML(m) {
    const src = m.sources || [];
    if (!src.length) return "";
    return `
      <details class="ch-srcs">
        <summary>Sources <span class="ch-rlen">${src.length}</span></summary>
        <ol class="ch-src-list">
          ${src.map(sv => `<li>
            <button class="ch-src" data-sid="${esc(sv.id)}">[${esc(sv.id)}]</button>
            ${sv.kind === "web"
              ? `<a href="${esc(sv.url || "#")}" target="_blank" rel="noopener">${esc(sv.cite)}</a>`
              : `<span class="ch-src-cite">${esc(sv.cite)}</span>
                 <span class="ch-src-loc">${sv.page == null || sv.source === "txt" ? "text edition" : "p. " + sv.page}</span>`}
            ${sv.snippet ? `<div class="ch-src-snip">${esc(sv.snippet.slice(0, 180))}</div>` : ""}
          </li>`).join("")}
        </ol>
      </details>`;
  }

  /* [S3] in the prose becomes a chip that opens the passage. Only markers the
     turn actually produced are linked — a hallucinated one stays plain text so
     it cannot pretend to be evidence. */
  /* Turn [S3] into a button — but only where [S3] is text the reader sees.

     This ran over the whole HTML string, so a marker inside an attribute was
     rewritten too: an adjudicator citing [S85] on a mermaid edge had a
     <button> spliced into the diagram's data-src, and the diagram stopped
     parsing. Markers inside a code block are left literal for the same reason:
     the author wrote them as text, not as a citation. */
  function linkMarkers(htmlText, sources) {
    const known = new Set((sources || []).map(s => s.id));
    const link = (t) => t.replace(/\[(S\d+)\]/g, (whole, id) =>
      known.has(id)
        ? `<button class="ch-cite" data-sid="${id}" title="open the source">${id}</button>`
        : whole);
    let inPre = 0;
    // split into tags and the text between them; only the text is rewritten
    return String(htmlText).split(/(<[^>]*>)/).map(part => {
      if (part.startsWith("<")) {
        if (/^<pre\b/i.test(part)) inPre++;
        else if (/^<\/pre>/i.test(part)) inPre = Math.max(0, inPre - 1);
        return part;
      }
      return inPre ? part : link(part);
    }).join("");
  }

  /* What the self-check did. Its prose is only "VERDICT: ..." followed by the
     corrected answer, which is already shown below, so the panel lists the
     checks themselves — for verify_quote the summary is the verdict on that
     quotation, which is the part worth reading. */
  function checkHTML(m, checked) {
    const checks = (m.tools || []).filter(t => t.phase === "verify");
    const quotes = checks.filter(t => t.name === "verify_quote");
    const bad = quotes.filter(t => /NOT FOUND/i.test(t.summary || "")).length;
    const head = checked === "revised"
      ? "Checked &#8212; corrected before you saw it"
      : "Checked &#8212; the answer stood";
    const count = quotes.length
      ? `<span class="ch-rlen">${quotes.length} quotation${quotes.length === 1 ? "" : "s"} verified${
          bad ? `, ${bad} rejected` : ""}</span>`
      : (checks.length ? `<span class="ch-rlen">${checks.length} checks</span>` : "");
    if (!checks.length) {
      return `<div class="ch-check ${checked === "revised" ? "revised" : "stands"} flat">
        <span class="ch-check-head">${head}</span></div>`;
    }
    return `<details class="ch-check ${checked === "revised" ? "revised" : "stands"}">
      <summary>${head} ${count}</summary>
      <ol class="ch-check-list">
        ${checks.map(t => `<li class="${/NOT FOUND/i.test(t.summary || "") ? "bad" : ""}">
          <span class="ch-tname">${esc(TOOL_LABEL[t.name] || t.name)}</span>
          ${t.args && t.args.quote ? `<q>${esc(String(t.args.quote).slice(0, 120))}</q>` : ""}
          <span class="ch-tsum">${esc(t.summary || "")}</span>
        </li>`).join("")}
      </ol>
    </details>`;
  }

  function messageHTML(m, i) {
    if (m.kind === "debate") return debateHTML(m);
    if (m.role === "user") {
      return `<div class="ch-m ch-user"><div class="ch-bubble">${esc(m.content)}</div></div>`;
    }
    const hasR = (m.reasoning || "").trim().length > 0;
    const hasC = (m.check || "").trim().length > 0;
    // The self-check pass is the model re-reading its own draft with the tools
    // still in hand. Its outcome belongs next to the answer — "revised" means
    // what you are reading is the second version.
    const checked = m._checked || (hasC ? (/VERDICT:\s*revised/i.test(m.check) ? "revised" : "stands") : null);
    return `<div class="ch-m ch-asst">
      ${traceHTML(m)}
      ${hasR ? `
        <details class="ch-reason" ${m._openR ? "open" : ""}>
          <summary>Reasoning <span class="ch-rlen">${m.reasoning.length.toLocaleString()} chars</span></summary>
          <div class="ch-reason-body">${esc(m.reasoning)}</div>
        </details>` : ""}
      ${m._phase === "verify" && m._live ? `<div class="ch-checking">checking its own answer&#8230;</div>` : ""}
      ${checked ? checkHTML(m, checked) : ""}
      <div class="ch-answer">${linkMarkers(mdish(m.content || ""), m.sources)}</div>
      ${sourcesHTML(m)}
      ${(m.context_items || []).length ? `<div class="ch-used">also given: ${
        m.context_items.map(c => esc(c.label)).join(" · ")}</div>` : ""}
    </div>`;
  }

  /* A citation opens the reader at that page with the passage highlighted —
     the same jump a search result makes. */
  function openSource(sv) {
    if (!sv) return;
    if (sv.kind === "web") { if (sv.url) window.open(sv.url, "_blank", "noopener"); return; }
    if (typeof Reader === "undefined") return;
    close();
    // A page-range citation's snippet starts with the reader's own "[page 33]"
    // marker and generic prose, which produced highlight terms like "[page"
    // and "things". Strip the furniture and the commonest words so what gets
    // marked on the page is at least worth marking.
    const STOP = new Set(("page the and that with which this from they their there here what when " +
      "shall would could their them those been have hath unto upon into whom whose").split(" "));
    Reader.activeTerms = [...new Set(
      (sv.snippet || "").toLowerCase()
        .replace(/\[[^\]]*\]/g, " ")
        .split(/[^a-z']+/)
        .filter(t => t.length > 5 && !STOP.has(t))
    )].slice(0, 6);
    if (sv.page == null || sv.source === "txt") {
      Reader.highlights = [];
      Reader.bookId = sv.book_id; Reader.open = true; Reader.txtMode = false;
      Reader.pendingHighlight = { text: sv.snippet || "", page: null };
      if (typeof showReaderShell === "function") showReaderShell();
      if (typeof openTxtMode === "function") openTxtMode(sv.book_id);
      return;
    }
    if (typeof openReader !== "function") return;
    const box = sv.bbox_pts
      ? [{ book_id: sv.book_id, page: sv.page, bbox_pts: sv.bbox_pts, concept_id: sv.id, text: sv.snippet }]
      : [];
    openReader(sv.book_id, {
      page: sv.page,
      highlight: sv.bbox_pts ? { page: sv.page, bbox_pts: sv.bbox_pts, concept_id: sv.id } : null,
      highlights: box,
    });
  }

  function wireCites(root) {
    root.querySelectorAll(".ch-cite, .ch-src").forEach(b => {
      b.onclick = (e) => {
        e.preventDefault();
        const id = b.dataset.sid;
        // A debate in progress has no stored message yet, so its table is
        // checked first; otherwise clicking a marker mid-debate does nothing.
        const liveHit = liveSources.find(x => x.id === id);
        if (liveHit) return openSource(liveHit);
        for (const m of (cur && cur.messages) || []) {
          const hit = (m.sources || []).find(x => x.id === id);
          if (hit) return openSource(hit);
        }
      };
    });
  }

  /* Just enough markdown for what the model actually emits: paragraphs,
     bullets, bold/italic and inline code. A full parser would be a dependency
     for no gain here. */
  /* ------------------------------------------------------------- markdown

     The old renderer handled paragraphs, bullets, bold and inline code, which
     was enough while the model wrote prose. Now it is asked for adjudications
     with headings, tables of who-claimed-what, and mermaid diagrams of an
     argument, so this is a real (small) markdown parser: fenced code with a
     language, tables, ordered and nested lists, headings, blockquotes, rules,
     links, and ```mermaid blocks handed to mermaid.js.

     It parses a block at a time rather than running regexes over the whole
     string, because the failure mode of the latter is a table swallowing the
     paragraph after it. */

  function mdInline(x) {
    // escape first: everything below emits its own tags
    let s = esc(x);
    // code spans are literal, so pull them out before anything else runs
    const code = [];
    s = s.replace(/`([^`]+)`/g, (m, c) => "%%CODE" + (code.push(c) - 1) + "%%");
    // Links are finished HTML, so they get parked too. Emitting them before the
    // emphasis pass let the italic rule pair the underscores in two anchors'
    // target="_blank" and turn one into target="<i>blank".
    const links = [];
    const park = (html) => "%%LINK" + (links.push(html) - 1) + "%%";
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      (m, t, u) => park(`<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`));
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<>"')]+)/g,
      (m, pre, u) => pre + park(`<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`));
    s = s.replace(/\*\*\*([^*]+)\*\*\*/g, "<b><i>$1</i></b>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    s = s.replace(/(^|[^*\w])\*([^*\n]+)\*/g, "$1<i>$2</i>");
    s = s.replace(/(^|[^_\w])_([^_\n]+)_/g, "$1<i>$2</i>");
    s = s.replace(/~~([^~]+)~~/g, "<s>$1</s>");
    s = s.replace(/%%LINK(\d+)%%/g, (m, i) => links[+i]);
    s = s.replace(/%%CODE(\d+)%%/g, (m, i) => `<code>${code[+i]}</code>`);
    return s;
  }

  let mermaidSeq = 0;

  /* One list level. Returns [html, indexAfter]. */
  function mdList(lines, i, indent) {
    const bullet = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
    const first = bullet.exec(lines[i]);
    const ordered = /\d/.test(first[2]);
    let out = ordered ? "<ol>" : "<ul>";
    while (i < lines.length) {
      const m = bullet.exec(lines[i]);
      if (!m) break;
      const ind = m[1].replace(/\t/g, "    ").length;
      if (ind < indent) break;
      if (ind > indent) {                      // a nested list belongs to the open <li>
        const [html, next] = mdList(lines, i, ind);
        out = out.replace(/<\/li>$/, html + "</li>");
        i = next;
        continue;
      }
      let item = m[3];
      i++;
      // lazy continuation: an unindented line right after an item is part of it
      while (i < lines.length && lines[i].trim() && !bullet.test(lines[i])
             && !/^\s*(#{1,6}\s|>|```|\||---)/.test(lines[i])) {
        item += " " + lines[i].trim();
        i++;
      }
      out += `<li>${mdInline(item)}</li>`;
    }
    return [out + (ordered ? "</ol>" : "</ul>"), i];
  }

  function mdTable(lines, i) {
    const row = (ln) => ln.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
    const head = row(lines[i]);
    const cells = (r, tag) => r.map(c => `<${tag}>${mdInline(c)}</${tag}>`).join("");
    let out = `<table class="ch-table"><thead><tr>${cells(head, "th")}</tr></thead><tbody>`;
    i += 2;                                     // skip the ---|--- separator
    while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
      out += `<tr>${cells(row(lines[i]), "td")}</tr>`;
      i++;
    }
    return [out + "</tbody></table>", i];
  }

  function mdish(t) {
    const lines = String(t ?? "").replace(/\r/g, "").split("\n");
    let out = "";
    let i = 0;
    while (i < lines.length) {
      const ln = lines[i];

      // fenced block
      const fence = /^\s*```\s*([\w-]*)\s*$/.exec(ln);
      if (fence) {
        const lang = (fence[1] || "").toLowerCase();
        const buf = [];
        i++;
        while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) { buf.push(lines[i]); i++; }
        const closed = i < lines.length;        // an unclosed fence is still streaming
        i++;
        const body = buf.join("\n");
        if (lang === "mermaid") {
          // only hand a finished diagram to mermaid; a half-streamed one throws
          out += closed
            ? `<div class="ch-mermaid" data-src="${esc(body)}" id="mmd${++mermaidSeq}"><div class="ch-mermaid-wait">drawing diagram&#8230;</div></div>`
            : `<pre class="ch-code"><code>${esc(body)}</code></pre>`;
        } else {
          out += `<pre class="ch-code"${lang ? ` data-lang="${esc(lang)}"` : ""}><code>${esc(body)}</code></pre>`;
        }
        continue;
      }

      if (!ln.trim()) { i++; continue; }

      const h = /^\s*(#{1,6})\s+(.*)$/.exec(ln);
      if (h) {
        const lvl = Math.min(6, h[1].length + 2);   // a heading inside a message is not a page title
        out += `<h${lvl} class="ch-h">${mdInline(h[2])}</h${lvl}>`;
        i++;
        continue;
      }

      if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(ln)) { out += "<hr>"; i++; continue; }

      // table: a pipe row followed by a --- separator row
      if (ln.includes("|") && i + 1 < lines.length && /^[\s|:\-]+$/.test(lines[i + 1])
          && lines[i + 1].includes("-")) {
        const [html, next] = mdTable(lines, i);
        out += html; i = next; continue;
      }

      if (/^\s*([-*+]|\d+[.)])\s+/.test(ln)) {
        const ind = (/^(\s*)/.exec(ln)[1] || "").replace(/\t/g, "    ").length;
        const [html, next] = mdList(lines, i, ind);
        out += html; i = next; continue;
      }

      if (/^\s*>\s?/.test(ln)) {
        const buf = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
          buf.push(lines[i].replace(/^\s*>\s?/, "")); i++;
        }
        out += `<blockquote>${mdish(buf.join("\n"))}</blockquote>`;
        continue;
      }

      // paragraph: runs on until a blank line or the start of another block
      const buf = [ln];
      i++;
      while (i < lines.length && lines[i].trim()
             && !/^\s*(#{1,6}\s|>|```|([-*+]|\d+[.)])\s|([-*_])\s*\3\s*\3)/.test(lines[i])
             && !(lines[i].includes("|") && i + 1 < lines.length && /^[\s|:\-]+$/.test(lines[i + 1]))) {
        buf.push(lines[i]); i++;
      }
      out += `<p>${mdInline(buf.join(" "))}</p>`;
    }
    return out;
  }

  /* Mermaid is 3MB, so it loads the first time a diagram appears rather than
     on every page view. A diagram that fails to parse shows its source: the
     model wrote it, and hiding a broken one would hide the reason. */
  let mermaidReady = null;
  function loadMermaid() {
    if (mermaidReady) return mermaidReady;
    mermaidReady = new Promise((resolve, reject) => {
      if (window.mermaid) return resolve(window.mermaid);
      const s = document.createElement("script");
      s.src = "vendor/mermaid.min.js";
      s.onload = () => resolve(window.mermaid);
      s.onerror = () => reject(new Error("mermaid failed to load"));
      document.head.appendChild(s);
    }).then((m) => {
      m.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: document.body.classList.contains("dark") ? "dark" : "neutral",
        fontFamily: "inherit",
      });
      return m;
    });
    return mermaidReady;
  }

  function zoomDiagram(host) {
    const src = host.querySelector("svg");
    if (!src) return;
    let z = document.getElementById("mmd-zoom");
    if (!z) {
      z = document.createElement("div");
      z.id = "mmd-zoom";
      z.className = "hidden";
      z.innerHTML = `<button class="mz-close" aria-label="Close">&#215;</button><div class="mz-inner"></div>`;
      document.body.appendChild(z);
      const hide = () => z.classList.add("hidden");
      z.onclick = (e) => { if (e.target === z || e.target.classList.contains("mz-close")) hide(); };
      // On window, not document: the chat panel's own Escape handler is also a
      // capture listener on document and was registered first, so it would
      // close the whole panel out from under the diagram. Capture runs
      // window -> document, so this one gets there first.
      window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !z.classList.contains("hidden")) {
          e.stopPropagation();
          e.preventDefault();
          hide();
        }
      }, true);
    }
    // A bare clone falls back to the SVG default of 300px. Drop the fixed
    // dimensions and let the viewBox scale it to the space available.
    const clone = src.cloneNode(true);
    clone.removeAttribute("width");
    clone.removeAttribute("height");
    clone.style.width = "min(1500px, 92vw)";
    clone.style.height = "auto";
    clone.style.maxWidth = "none";
    const inner = z.querySelector(".mz-inner");
    inner.innerHTML = "";
    inner.appendChild(clone);
    z.classList.remove("hidden");
  }

  /* Mermaid bakes the palette into the SVG at render time, so a diagram drawn
     in the light theme keeps light nodes on a dark page. Re-initialise and
     redraw everything when the theme changes. */
  document.addEventListener("atlas:theme", () => {
    if (!mermaidReady) return;                 // nothing has been drawn yet
    mermaidReady = mermaidReady.then((m) => {
      m.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: document.body.classList.contains("dark") ? "dark" : "neutral",
        fontFamily: "inherit",
      });
      return m;
    });
    document.querySelectorAll(".ch-mermaid[data-done]").forEach(h => {
      h.removeAttribute("data-done");
      h.classList.remove("ok", "wide");
      h.innerHTML = `<div class="ch-mermaid-wait">redrawing&#8230;</div>`;
    });
    drawMermaid(document);
  });

  async function drawMermaid(root) {
    const hosts = [...(root || document).querySelectorAll(".ch-mermaid:not([data-done])")];
    if (!hosts.length) return;
    let m;
    try {
      m = await loadMermaid();
    } catch (e) {
      hosts.forEach(h => {
        h.dataset.done = "1";
        h.innerHTML = `<pre class="ch-code"><code>${esc(h.dataset.src || "")}</code></pre>`;
      });
      return;
    }
    for (const h of hosts) {
      h.dataset.done = "1";
      const src = h.dataset.src || "";
      try {
        const { svg } = await m.render(h.id + "svg", src);
        h.innerHTML = svg;
        h.classList.add("ok");
        // a graph with one node per claim runs wider than the panel; say so,
        // and let a click open it at full size rather than squinting
        if (h.scrollWidth > h.clientWidth + 4) h.classList.add("wide");
        h.onclick = () => zoomDiagram(h);
      } catch (e) {
        h.innerHTML = `<div class="ch-mermaid-err">the diagram did not parse</div><pre class="ch-code"><code>${esc(src)}</code></pre>`;
      }
    }
  }

  /* ---------------------------------------------------------------- debate

     Two agents argue a motion out of the corpus and a third adjudicates. Each
     speaker has the full toolset and they all share one citation table, so a
     marker means the same passage in the opening, the rebuttal and the verdict
     — and stays clickable throughout.

     A debate is stored as one message in the session, so it exports and
     imports with everything else. */

  const DEBATE_EXAMPLES = [
    "Benevolence in these authors is finally reducible to self-love.",
    "Conscience, not reason, is the seat of moral authority.",
    "The moral sense is a faculty of perception, not of feeling.",
    "Marriage as these writers describe it is a form of servitude.",
  ];

  let debating = false;
  let debateAbort = null; // lets the reader stop a debate that is running
  let liveSources = [];   // the citation table of a turn still streaming

  /* A debate is bound to the connection streaming it: there is no way to
     detach and reattach. Closing the panel or changing session therefore
     stops it — and the server keeps the turns already spoken, so a stopped
     debate is still in the transcript. */
  function stopDebate(why) {
    if (!debateAbort) return false;
    try { debateAbort.abort(why || "stopped"); } catch (e) { /* already gone */ }
    debateAbort = null;
    return true;
  }

  function debateSetupHTML() {
    return `
      <div class="ch-debate-setup">
        <h2>&#9878; Debate the corpus</h2>
        <p class="ch-dsub">Two agents argue a motion, each searching the corpus and citing what
          they find. A third checks their quotations and adjudicates on the evidence.</p>
        <form id="dbt-form">
          <label class="dbt-l">Motion
            <textarea id="dbt-motion" rows="2" placeholder="A claim that can be argued both ways&#8230;"></textarea>
          </label>
          <div class="dbt-eg">${DEBATE_EXAMPLES.map(e =>
            `<button type="button" class="dbt-egb" data-m="${esc(e)}">${esc(e)}</button>`).join("")}</div>
          <div class="dbt-sides">
            <div class="dbt-side">
              <h4>For the motion</h4>
              <label class="dbt-l">Name<input id="dbt-n1" value="Proposition"></label>
              <label class="dbt-l">Voice <span class="opt">optional</span>
                <input id="dbt-p1" placeholder="e.g. a reader of Mandeville and Hobbes"></label>
            </div>
            <div class="dbt-side">
              <h4>Against the motion</h4>
              <label class="dbt-l">Name<input id="dbt-n2" value="Opposition"></label>
              <label class="dbt-l">Voice <span class="opt">optional</span>
                <input id="dbt-p2" placeholder="e.g. a reader of Hutcheson and Butler"></label>
            </div>
          </div>
          <div class="dbt-opts">
            <label class="dbt-l dbt-inline">Rounds
              <select id="dbt-rounds">
                <option value="1">1 &#8212; openings only</option>
                <option value="2" selected>2 &#8212; opening, then closing</option>
                <option value="3">3 &#8212; opening, rebuttal, closing</option>
                <option value="4">4 &#8212; opening, two rebuttals, closing</option>
              </select>
            </label>
            <label class="ch-toggle"><input type="checkbox" id="dbt-judge" checked>
              <span>adjudicate at the end</span></label>
            <label class="ch-toggle" title="Let both sides search the open web as well as the corpus.">
              <input type="checkbox" id="dbt-web" ${webOn ? "checked" : ""}>
              <span>&#127760; web search</span></label>
          </div>
          <div class="dbt-actions">
            <button type="button" id="dbt-cancel" class="mini">back to the conversation</button>
            <button type="submit" id="dbt-go" class="ch-primary">Hold the debate</button>
          </div>
          <p class="hint dbt-warn">A full debate is several agent turns with tool calls in each;
            expect it to take a few minutes.</p>
        </form>
      </div>`;
  }

  function openDebate() {
    if (!user) { open(); return; }
    const body = $("chat-body");
    body.innerHTML = debateSetupHTML();
    body.querySelectorAll(".dbt-egb").forEach(b => {
      b.onclick = () => { $("dbt-motion").value = b.dataset.m; $("dbt-motion").focus(); };
    });
    $("dbt-cancel").onclick = () => renderThread();
    $("dbt-form").onsubmit = (e) => {
      e.preventDefault();
      const motion = $("dbt-motion").value.trim();
      if (!motion) { $("dbt-motion").focus(); return; }
      runDebate({
        motion,
        rounds: +$("dbt-rounds").value,
        judge: $("dbt-judge").checked,
        allow_web: $("dbt-web").checked,
        sides: [
          { name: $("dbt-n1").value.trim() || "Proposition", stance: "for the motion",
            persona: $("dbt-p1").value.trim() },
          { name: $("dbt-n2").value.trim() || "Opposition", stance: "against the motion",
            persona: $("dbt-p2").value.trim() },
        ],
      });
    };
    $("dbt-motion").focus();
  }

  const PHASE_LABEL = { opening: "opening", rebuttal: "rebuttal", closing: "closing",
                        verdict: "adjudication" };

  function turnHTML(t, sources, live) {
    const judge = t.side === "Adjudicator";
    return `<div class="dbt-turn ${judge ? "judge" : (t.seat === 0 ? "side-a" : "side-b")}${live ? " live" : ""}">
      <div class="dbt-head">
        <span class="dbt-who">${esc(t.side)}</span>
        <span class="dbt-phase">${PHASE_LABEL[t.phase] || esc(t.phase)}</span>
        ${judge ? "" : `<span class="dbt-round">round ${t.round}</span>`}
      </div>
      ${traceHTML({ tools: t.tools || [] })}
      ${(t.reasoning || "").trim() ? `
        <details class="ch-reason">
          <summary>Reasoning <span class="ch-rlen">${t.reasoning.length.toLocaleString()} chars</span></summary>
          <div class="ch-reason-body">${esc(t.reasoning)}</div>
        </details>` : ""}
      <div class="ch-answer">${linkMarkers(mdish(t.text || ""), sources)}
        ${live && !(t.text || "").trim() ? '<span class="dbt-think">searching the corpus&#8230;</span>' : ""}</div>
    </div>`;
  }

  /* A stored debate, rendered from the session transcript. */
  function debateHTML(m) {
    const seats = {};
    (m.sides || []).forEach((s, i) => { seats[s.name] = i; });
    return `<div class="ch-m ch-asst dbt-wrap">
      <div class="dbt-motion"><span class="dbt-tag">motion</span>${esc(m.motion || "")}</div>
      ${m.interrupted ? `<div class="dbt-cut">This debate was stopped before it finished.
        What was said is below.</div>` : ""}
      ${(m.turns || []).map(t => turnHTML({ ...t, seat: seats[t.side] }, m.sources, false)).join("")}
      ${sourcesHTML(m)}
    </div>`;
  }

  async function runDebate(opts) {
    if (debating) { flash("A debate is already running in this session"); return; }
    if (!cur) await loadSessions();
    // loadSessions can leave cur null if the backend is down; without this the
    // next line reads cur.session.id and throws into nothing
    if (!cur || !cur.session) {
      flash("Could not open a session for the debate — is the chat service running?");
      return;
    }
    debating = true;
    const body = $("chat-body");
    const sources = [];
    const seats = {};
    opts.sides.forEach((s, i) => { seats[s.name] = i; });
    const turns = [];
    let curTurn = null;
    let stopped = false, failed = null;

    body.innerHTML = `
      <div class="ch-thread dbt-live" id="ch-thread">
        <div class="dbt-motion"><span class="dbt-tag">motion</span>${esc(opts.motion)}</div>
        <div id="dbt-turns"></div>
        <div class="dbt-foot">
          <span id="dbt-status" class="dbt-status">opening the debate&#8230;</span>
          <button id="dbt-stop" class="mini">stop</button>
        </div>
      </div>`;
    const host = $("dbt-turns");
    const status = $("dbt-status");
    debateAbort = new AbortController();
    const stopBtn = $("dbt-stop");
    if (stopBtn) stopBtn.onclick = () => {
      stopBtn.disabled = true;
      status.textContent = "stopping after this turn\u2026";
      stopDebate("reader stopped it");
    };

    const paint = () => {
      host.innerHTML = turns.map(t => turnHTML(t, sources, t === curTurn)).join("");
      wireCites(host);
      drawMermaid(host);
      const th = $("ch-thread");
      if (th) th.scrollTop = th.scrollHeight;
    };

    try {
      const r = await fetch("/book/api/chat/debate", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Atlas-Token": tok() },
        body: JSON.stringify({ session_id: cur.session.id, ...opts, max_steps: 5 }),
        signal: debateAbort.signal,
      });
      if (!r.ok || !r.body) {
        throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
      }
      const rd = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await rd.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const p of parts) {
          const line = p.trim();
          if (!line.startsWith("data:")) continue;
          let d;
          try { d = JSON.parse(line.slice(5)); } catch { continue; }
          if (d.type === "turn_start") {
            curTurn = { side: d.side, phase: d.phase, round: d.round, seat: seats[d.side],
                        text: "", reasoning: "", tools: [] };
            turns.push(curTurn);
            status.textContent = `${d.side} — ${PHASE_LABEL[d.phase] || d.phase}`;
          } else if (d.type === "turn_end") {
            curTurn = null;
          } else if (curTurn && d.type === "content") {
            curTurn.text += d.text;
          } else if (curTurn && d.type === "reasoning") {
            curTurn.reasoning += d.text;
          } else if (curTurn && d.type === "tool_call") {
            curTurn.tools.push({ name: d.name, args: d.args });
          } else if (curTurn && d.type === "tool_result") {
            const pend = [...curTurn.tools].reverse().find(t => t.name === d.name && !t.summary);
            if (pend) { pend.summary = d.summary; pend.took_ms = d.took_ms; }
            else curTurn.tools.push({ name: d.name, summary: d.summary });
          } else if (d.type === "sources") {
            sources.length = 0;
            sources.push(...d.sources);
            liveSources = sources;
          } else if (d.type === "note" && curTurn) {
            curTurn.text += `\n\n_(${d.text})_`;
          } else if (d.type === "error") {
            status.textContent = "the debate stopped: " + d.error;
          } else if (d.type === "done") {
            status.textContent = `${d.turns} turns, ${d.sources} sources cited`;
          }
          paint();
        }
      }
    } catch (err) {
      stopped = err.name === "AbortError";
      status.textContent = stopped
        ? `stopped after ${turns.length} turn${turns.length === 1 ? "" : "s"}`
        : "the debate could not run: " + err.message;
      if (!stopped) failed = err.message;
    }
    debating = false;
    debateAbort = null;
    liveSources = [];
    if (stopBtn) stopBtn.disabled = true;
    // reload so the stored debate renders from the transcript from now on
    const sid = cur && cur.session && cur.session.id;
    await loadSessions();
    if (sid) await loadSession(sid);
    // the re-render wipes the live status, so say what happened somewhere
    // that survives it: the stored debate carries an "interrupted" notice,
    // but a debate stopped before anyone finished has nothing to carry it
    if (failed) flash("The debate could not run: " + failed);
    else if (stopped && !document.querySelector(".dbt-wrap")) {
      flash("Stopped before either side finished — nothing was recorded");
    } else if (stopped) {
      flash("Debate stopped; what was said is kept");
    }
  }

  function renderThread() {
    const body = $("chat-body");
    if (!cur) { body.innerHTML = ""; return; }
    const msgs = cur.messages || [];
    body.innerHTML = `
      <div class="ch-thread" id="ch-thread">
        ${msgs.length ? msgs.map(messageHTML).join("") : `
          <div class="ch-empty">
            <h3>${esc(cur.session.title)}</h3>
            <p>Attach what the model should read — a book, a range of pages, a concept with its
              relations, a passage, or a whole search — then ask. Answers are grounded in what you
              attached and cited from it.</p>
          </div>`}
      </div>
      <div class="ch-opts">
        <label class="ch-toggle" title="Let the agent search the open web when the corpus cannot answer. Off by default: answers stay inside the 197 sources.">
          <input type="checkbox" id="ch-web" ${webOn ? "checked" : ""}>
          <span>&#127760; web search</span>
        </label>
        <label class="ch-toggle" title="After drafting, the model re-reads its own answer with the tools still in hand: it checks every quotation with verify_quote, checks each citation really supports its claim, and either stands by the answer or replaces it.">
          <input type="checkbox" id="ch-verify" ${verifyOn ? "checked" : ""}>
          <span>&#10003; check its own answer</span>
        </label>
        <span class="ch-opts-note">${webOn
          ? "the agent may look outside the corpus, and will say when it does"
          : "answers stay inside the corpus"}${verifyOn ? "" : " \u00b7 answers are not re-checked"}</span>
      </div>
      <form id="ch-form" class="ch-compose">
        <textarea id="ch-input" rows="1" placeholder="${
          window.matchMedia("(max-width: 820px)").matches
            ? "Ask about the attached sources…"
            : "Ask about the attached sources…  (Enter to send, Shift+Enter for a new line)"
        }"></textarea>
        <button type="submit" id="ch-send" class="ch-primary">Send</button>
      </form>`;
    const ta = $("ch-input");
    ta.oninput = () => { ta.style.height = "auto"; ta.style.height = Math.min(200, ta.scrollHeight) + "px"; };
    ta.onkeydown = (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("ch-form").requestSubmit(); }
    };
    $("ch-form").onsubmit = onSend;
    const wt = $("ch-web");
    if (wt) wt.onchange = () => {
      webOn = wt.checked;
      try { localStorage.setItem("atlas.chatWeb", webOn ? "on" : "off"); } catch { /* ignore */ }
      renderThread();
    };
    const vt = $("ch-verify");
    if (vt) vt.onchange = () => {
      verifyOn = vt.checked;
      try { localStorage.setItem("atlas.chatVerify", verifyOn ? "on" : "off"); } catch { /* ignore */ }
      renderThread();
    };
    body.querySelectorAll(".ch-reason").forEach(d => {
      d.addEventListener("toggle", () => { /* stays open across a re-render via _openR */ });
    });
    wireCites(body);
    drawMermaid(body);
    scrollDown();
    ta.focus();
  }

  function scrollDown() {
    const t = $("ch-thread");
    if (t) t.scrollTop = t.scrollHeight;
  }

  /* ------------------------------------------------------------------ send */
  async function onSend(e) {
    e.preventDefault();
    if (streaming) return;
    const ta = $("ch-input");
    const text = ta.value.trim();
    if (!text || !cur) return;
    ta.value = ""; ta.style.height = "auto";
    streaming = true;
    $("ch-send").disabled = true;
    $("ch-send").textContent = "…";

    cur.messages.push({ role: "user", content: text });
    const live = { role: "assistant", content: "", reasoning: "", check: "", tools: [],
                   sources: [], _openR: true, _live: true };
    cur.messages.push(live);
    renderThread();
    const thread = $("ch-thread");
    const node = thread.lastElementChild;

    const paint = () => {
      node.innerHTML = messageHTML(live).replace(/^<div class="ch-m ch-asst">|<\/div>$/g, "");
      wireCites(node);
      drawMermaid(node);
      scrollDown();
    };

    try {
      const r = await fetch("/book/api/chat/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Atlas-Token": tok() },
        body: JSON.stringify({ session_id: cur.session.id, message: text,
                               max_tokens: 4096, allow_web: webOn, verify: verifyOn }),
      });
      if (!r.ok || !r.body) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
      const rd = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await rd.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const p of parts) {
          const line = p.trim();
          if (!line.startsWith("data:")) continue;
          let d;
          try { d = JSON.parse(line.slice(5)); } catch { continue; }
          if (d.type === "reasoning") live.reasoning += d.text;
          else if (d.type === "content") live.content += d.text;
          else if (d.type === "check") live.check = (live.check || "") + d.text;
          else if (d.type === "phase") live._phase = d.phase;
          else if (d.type === "answer_replace") live.content = "";   // a corrected answer follows
          else if (d.type === "checked") live._checked = d.outcome;
          else if (d.type === "error") live.content += `\n\n_(${d.error})_`;
          else if (d.type === "start") live._meta = d;
          else if (d.type === "tool_call") live.tools.push({ name: d.name, args: d.args });
          else if (d.type === "tool_result") {
            // match the pending call rather than appending, so the trace shows
            // one line per call with its outcome
            const pend = [...live.tools].reverse().find(t => t.name === d.name && !t.summary);
            if (pend) { pend.summary = d.summary; pend.took_ms = d.took_ms; }
            else live.tools.push({ name: d.name, summary: d.summary });
          }
          else if (d.type === "sources") live.sources = d.sources;
          else if (d.type === "note") live.content += `\n\n_(${d.text})_`;
          paint();
        }
      }
    } catch (err) {
      live.content += `\n\n_(${err.message})_`;
      paint();
    }
    streaming = false;
    live._live = false;
    live._openR = false;          // collapse the thinking once the answer stands
    const btn = $("ch-send");
    if (btn) { btn.disabled = false; btn.textContent = "Send"; }
    await loadSessions();
    if (cur) await loadSession(cur.session.id);
  }

  /* ---------------------------------------------------------------- picker */
  async function openPicker() {
    $("chat-picker").classList.remove("hidden");
    if (!library) {
      try { library = (await (await fetch("/book/api/library")).json()).books || []; } catch { library = []; }
    }
    renderPicker();
  }
  function closePicker() { $("chat-picker").classList.add("hidden"); }

  function renderPicker(filter = "") {
    const f = filter.toLowerCase();
    const tabs = [["books", "Books & page ranges"], ["concepts", "Concepts"],
                  ["search", "A search"], ["note", "A note"]];
    let inner = "";
    if (pickerTab === "books") {
      const rows = (library || [])
        .map(b => ({ b, c: window.Cite ? Cite.parse(b.book_id) : { cite: b.book_id } }))
        .filter(x => !f || x.c.cite.toLowerCase().includes(f) || x.b.book_id.toLowerCase().includes(f))
        .slice(0, 60);
      inner = `<div class="ch-pick-list">${rows.map(({ b, c }) => `
        <div class="ch-pick-row" data-book="${esc(b.book_id)}" data-label="${esc(c.cite)}">
          <div class="ch-pick-main"><b>${esc(c.cite)}</b>
            <span class="ch-pick-sub">${b.pages || "?"} pages${b.has_txt ? " · text edition" : ""}</span></div>
          <span class="ch-pick-range">
            pp. <input class="ch-pf" type="number" min="1" max="${b.pages || 9999}" placeholder="1">
            – <input class="ch-pt" type="number" min="1" max="${b.pages || 9999}" placeholder="${b.pages || "end"}">
          </span>
          <button class="ch-pick-add">add</button>
        </div>`).join("") || `<p class="ch-none">No book matches.</p>`}</div>
        <p class="ch-pick-hint">Leave the range blank for the whole book. A long book can fill a large part
          of the window on its own — the meter on the right shows how much.</p>`;
    } else if (pickerTab === "concepts") {
      const nodes = (typeof S !== "undefined" && S.nodes) ? S.nodes : [];
      const rows = nodes.filter(n => !f || n.label.toLowerCase().includes(f)
        || (n.aliases || []).some(a => a.toLowerCase().includes(f))).slice(0, 60);
      inner = `<div class="ch-pick-list">${rows.map(n => `
        <div class="ch-pick-row" data-concept="${esc(n.id)}" data-label="${esc(n.label)}">
          <div class="ch-pick-main"><b>${esc(n.label)}</b>
            <span class="ch-pick-sub">${esc((n.category || []).join(" › "))} · ${n.books} books</span></div>
          <button class="ch-pick-add">add</button>
        </div>`).join("") || `<p class="ch-none">No concept matches.</p>`}</div>
        <p class="ch-pick-hint">A concept brings its definition, aliases, every relation the map records
          for it, and the verbatim quotes attesting it.</p>`;
    } else if (pickerTab === "search") {
      const q = (window._lastQuery || "").trim();
      inner = `<div class="ch-pick-form">
          <label>Query<input id="ch-sq" value="${esc(q)}" placeholder="e.g. liberty and necessity"></label>
          <label>How many passages<select id="ch-sn">
            <option>10</option><option selected>20</option><option>40</option><option>60</option></select></label>
          <button class="ch-pick-add" id="ch-sadd">add these results</button>
        </div>
        <p class="ch-pick-hint">Runs the hybrid search and attaches the full text of every hit, so the model
          reads the passages themselves rather than a summary of them.</p>`;
    } else {
      inner = `<div class="ch-pick-form">
          <label>Label<input id="ch-nl" placeholder="what this note is"></label>
          <label>Text<textarea id="ch-nt" rows="7" placeholder="anything you want the model to have in front of it"></textarea></label>
          <button class="ch-pick-add" id="ch-nadd">add note</button>
        </div>`;
    }
    $("chat-picker").innerHTML = `
      <div class="ch-pick-card">
        <div class="ch-pick-bar">
          <b>Add to context</b>
          <span class="ch-pick-tabs">${tabs.map(([k, l]) =>
            `<button class="${pickerTab === k ? "active" : ""}" data-tab="${k}">${l}</button>`).join("")}</span>
          <button id="ch-pick-close" title="Close">×</button>
        </div>
        ${pickerTab === "books" || pickerTab === "concepts"
          ? `<input id="ch-pick-f" class="ch-pick-filter" placeholder="filter…" value="${esc(filter)}">` : ""}
        ${inner}
      </div>`;
    $("ch-pick-close").onclick = closePicker;
    $("chat-picker").querySelectorAll(".ch-pick-tabs button").forEach(b => {
      b.onclick = () => { pickerTab = b.dataset.tab; renderPicker(); };
    });
    const ff = $("ch-pick-f");
    if (ff) { ff.oninput = () => renderPicker(ff.value); ff.focus(); ff.setSelectionRange(ff.value.length, ff.value.length); }
    $("chat-picker").querySelectorAll(".ch-pick-add").forEach(b => {
      b.onclick = async () => {
        b.disabled = true; b.textContent = "adding…";
        try { await addFromPicker(b); } catch (e) { alert(e.message); }
        b.disabled = false; b.textContent = "add";
      };
    });
    $("chat-picker").onclick = (e) => { if (e.target === $("chat-picker")) closePicker(); };
  }

  async function addFromPicker(btn) {
    let item = null;
    const row = btn.closest(".ch-pick-row");
    if (row && row.dataset.book) {
      const pf = row.querySelector(".ch-pf").value, pt = row.querySelector(".ch-pt").value;
      item = { kind: "book", book_id: row.dataset.book, label: row.dataset.label,
               page_from: pf ? +pf : null, page_to: pt ? +pt : null };
    } else if (row && row.dataset.concept) {
      item = { kind: "concept", concept_id: row.dataset.concept, label: row.dataset.label };
    } else if (btn.id === "ch-sadd") {
      const q = $("ch-sq").value.trim();
      if (!q) return;
      item = { kind: "search", query: q, top_k: +$("ch-sn").value };
    } else if (btn.id === "ch-nadd") {
      const t = $("ch-nt").value.trim();
      if (!t) return;
      item = { kind: "note", label: $("ch-nl").value.trim() || "note", text: t };
    }
    if (!item) return;
    await addContext([item]);
  }

  /* Public: other views attach things without opening the picker. */
  async function addContext(items) {
    if (!user) { await open(); return; }
    if (!cur) await loadSessions();
    await api(`/sessions/${cur.session.id}/context/add`, { items });
    await loadSession(cur.session.id);
    flash(`${items.length} item${items.length === 1 ? "" : "s"} added to context`);
  }

  function flash(msg) {
    let el = $("ch-flash");
    if (!el) {
      el = document.createElement("div");
      el.id = "ch-flash";
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("on");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("on"), 2200);
  }

  /* --------------------------------------------------------------- account */
  function renderAccount(msg, isErr) {
    $("chat-body").innerHTML = `
      <div class="ch-auth">
        <h2>Your account</h2>
        ${msg ? `<div class="ch-msg ${isErr ? "err" : "ok"}">${esc(msg)}</div>` : ""}
        <form id="ch-acct-form">
          <label>Username <span class="opt">cannot be changed</span>
            <input value="${esc(user.username)}" disabled></label>
          <label>Display name<input name="display_name" value="${esc(user.display_name || "")}"></label>
          <label>Email<input name="email" type="email" value="${esc(user.email)}"></label>
          <label>New password <span class="opt">leave blank to keep it</span>
            <input name="password" type="password" minlength="8" autocomplete="new-password"></label>
          <label>Current password <span class="opt">needed to change email or password</span>
            <input name="current_password" type="password" autocomplete="current-password"></label>
          <button type="submit" class="ch-primary">Save changes</button>
        </form>
        <div class="ch-auth-alt">
          <button id="ch-back">Back to the conversation</button>
          <button id="ch-signout">Sign out</button>
        </div>
      </div>`;
    $("ch-acct-form").onsubmit = async (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target).entries());
      Object.keys(fd).forEach(k => { if (!fd[k]) delete fd[k]; });
      try {
        const d = await api("/auth/update", fd);
        user = d.user;
        paintHeader();
        renderAccount("Saved.");
      } catch (err) { renderAccount(err.message, true); }
    };
    $("ch-back").onclick = () => render();
    $("ch-signout").onclick = signOut;
  }

  /* ------------------------------------------------------------------ init */
  /* Ask about the results you are looking at: attach them, then open. */
  async function askAboutResults() {
    if (!window._lastQuery) { await open(); return; }
    if (!user) {
      try { user = (await api("/auth/me")).user; } catch { user = null; }
    }
    if (!user) { await open(); return; }     // sign in first, nothing to lose
    await open();
    try {
      if (!cur) await loadSessions();
      const already = (cur.context || []).some(c => c.kind === "search" && c.ref === window._lastQuery);
      if (!already) {
        await api(`/sessions/${cur.session.id}/context/add`, {
          items: [{ kind: "search", query: window._lastQuery, top_k: 30 }],
        });
        await loadSession(cur.session.id);
        flash("these results are now in the context");
      }
      const ta = $("ch-input");
      if (ta) { ta.placeholder = `Ask about “${window._lastQuery}”…`; ta.focus(); }
    } catch (e) { flash(e.message); }
  }
  window.askAboutResults = askAboutResults;

  function init() {
    // the app bar's Ask button routes through Nav.go("ask")
    const ask = $("gres-ask");
    if (ask) ask.onclick = askAboutResults;
    // a query is usually already a proposition; offer to argue it out
    const dbtq = $("gres-debate");
    if (dbtq) dbtq.onclick = async () => {
      await open();
      openDebate();
      const box = $("dbt-motion");
      if (box && window._lastQuery) { box.value = window._lastQuery; box.focus(); }
    };
    const cl = $("chat-close");
    if (cl) cl.onclick = close;
    const dbt = $("chat-debate");
    if (dbt) dbt.onclick = openDebate;
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (!$("chat-picker").classList.contains("hidden")) { closePicker(); e.stopPropagation(); return; }
      if (!$("chat-panel").classList.contains("hidden")) { close(); e.stopPropagation(); }
    }, true);
    // restore the signed-in user quietly so the chip can say who you are
    paintAccount();
    if (tok()) api("/auth/me").then(d => { user = d.user; paintAccount(); }).catch(() => {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  return { open, close, addContext, openDebate, runDebate, stopDebate, mdish,
    get user() { return user; } };
})();

window.Chat = Chat;
