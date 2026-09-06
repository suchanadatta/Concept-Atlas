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
    if (!user) {
      try { user = (await api("/auth/me")).user; } catch { user = null; }
    }
    if (!user) return renderAuth();
    await loadSessions();
    render();
  }
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
    paintHeader();
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
    cur = await api("/sessions/" + id);
    render();
  }

  function paintHeader() {
    const h = $("chat-user");
    if (!h) return;
    h.innerHTML = user
      ? `<button id="ch-acct" title="Account">${esc(user.display_name || user.username)}</button>`
      : "";
    if ($("ch-acct")) $("ch-acct").onclick = renderAccount;
  }

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

  function messageHTML(m, i) {
    if (m.role === "user") {
      return `<div class="ch-m ch-user"><div class="ch-bubble">${esc(m.content)}</div></div>`;
    }
    const hasR = (m.reasoning || "").trim().length > 0;
    return `<div class="ch-m ch-asst">
      ${hasR ? `
        <details class="ch-reason" ${m._openR ? "open" : ""}>
          <summary>Reasoning <span class="ch-rlen">${m.reasoning.length.toLocaleString()} chars</span></summary>
          <div class="ch-reason-body">${esc(m.reasoning)}</div>
        </details>` : ""}
      <div class="ch-answer">${mdish(m.content || "")}</div>
      ${(m.context_items || []).length ? `<div class="ch-used">grounded in ${
        m.context_items.map(c => esc(c.label)).join(" · ")}</div>` : ""}
    </div>`;
  }

  /* Just enough markdown for what the model actually emits: paragraphs,
     bullets, bold/italic and inline code. A full parser would be a dependency
     for no gain here. */
  function mdish(t) {
    const lines = esc(t).split("\n");
    let out = "", inList = false;
    for (let ln of lines) {
      const li = ln.match(/^\s*[-*]\s+(.*)$/);
      if (li) {
        if (!inList) { out += "<ul>"; inList = true; }
        out += `<li>${inline(li[1])}</li>`;
        continue;
      }
      if (inList) { out += "</ul>"; inList = false; }
      if (ln.trim()) out += `<p>${inline(ln)}</p>`;
    }
    if (inList) out += "</ul>";
    return out;
    function inline(x) {
      return x
        .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
        .replace(/(^|\W)\*([^*\n]+)\*/g, "$1<i>$2</i>")
        .replace(/`([^`]+)`/g, "<code>$1</code>");
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
      <form id="ch-form" class="ch-compose">
        <textarea id="ch-input" rows="1" placeholder="Ask about the attached sources…  (Enter to send, Shift+Enter for a new line)"></textarea>
        <button type="submit" id="ch-send" class="ch-primary">Send</button>
      </form>`;
    const ta = $("ch-input");
    ta.oninput = () => { ta.style.height = "auto"; ta.style.height = Math.min(200, ta.scrollHeight) + "px"; };
    ta.onkeydown = (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("ch-form").requestSubmit(); }
    };
    $("ch-form").onsubmit = onSend;
    body.querySelectorAll(".ch-reason").forEach(d => {
      d.addEventListener("toggle", () => { /* stays open across a re-render via _openR */ });
    });
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
    const live = { role: "assistant", content: "", reasoning: "", _openR: true, _live: true };
    cur.messages.push(live);
    renderThread();
    const thread = $("ch-thread");
    const node = thread.lastElementChild;

    const paint = () => {
      node.innerHTML = messageHTML(live).replace(/^<div class="ch-m ch-asst">|<\/div>$/g, "");
      scrollDown();
    };

    try {
      const r = await fetch("/book/api/chat/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Atlas-Token": tok() },
        body: JSON.stringify({ session_id: cur.session.id, message: text, max_tokens: 4096 }),
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
          else if (d.type === "error") live.content += `\n\n_(${d.error})_`;
          else if (d.type === "start") live._meta = d;
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
  function init() {
    const btn = $("btn-chat");
    if (btn) btn.onclick = () => ($("chat-panel").classList.contains("hidden") ? open() : close());
    const cl = $("chat-close");
    if (cl) cl.onclick = close;
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (!$("chat-picker").classList.contains("hidden")) { closePicker(); e.stopPropagation(); return; }
      if (!$("chat-panel").classList.contains("hidden")) { close(); e.stopPropagation(); }
    }, true);
    // restore the signed-in user quietly so the button can say who you are
    if (tok()) api("/auth/me").then(d => { user = d.user; paintHeader(); }).catch(() => {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  return { open, close, addContext, get user() { return user; } };
})();

window.Chat = Chat;
