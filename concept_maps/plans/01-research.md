# 01 — Research

## Topic: graph viz library for 203-node concept graph, offline intranet

Queries: 1. `d3-force@3 dist` → jsdelivr 200, 8.3KB UMD (requires d3-quadtree/d3-dispatch as UMD deps)
2. `d3@7.9.0 dist/d3.min.js` → jsdelivr 200, 279,706B, verified `require()` loads, exports format/formatPrefix/... (full bundle v7)

Findings:
- Full d3 v7 bundle includes d3-selection, d3-zoom, d3-force, d3-quadtree, d3-scale, d3-drag — everything needed in ONE vendored file (Source: jsdelivr, verified live this session).
- 203 nodes / 1107 edges is small: canvas rendering with d3-force ticks will hold 60fps easily. [DERIVED: O(n²) repulsion at n=203 ≈ 41k pair-checks/tick with quadtree Barnes-Hut ≈ far less]
- Fonts: Google Fonts CSS2 API returns variable woff2; latin subsets extracted and downloaded (EB Garamond 400/600+italic, Inter 400/500/600) — verified 200s this session.

Conflicts: none.

Conclusion: **vendor d3@7.9.0 full bundle + 3 woff2 fonts locally**; no CDN at runtime. Confidence: [VERIFIED].

## Topic: hosting without sudo

Findings:
- No sudo → cannot install system systemd units or change firewall.
- Ports 8788/8899/7331/9090 free (verified via ss).
- Many services already bind 0.0.0.0 (5000, 8080, 5173…) → host firewall evidently permissive. [HYPOTHESIS: chosen port reachable from LAN — will verify by curling http://10.20.113.88:PORT]
- Persistence plan: `setsid nohup` + PID file + start/stop scripts; attempt `crontab @reboot` as boot persistence if crontab writable.

Conclusion: custom threaded Python HTTP server on **:8788**, bind 0.0.0.0, gzip + cache headers. Confidence: [VERIFIED env facts] / [HYPOTHESIS LAN reachability → test].

## Topic: UI design direction (creative pass)

- Aesthetic: "scholarly atlas" — warm parchment background, ink text, EB Garamond display, muted category palette, hairline edges, LOD labels (top-importance labeled by default, more at higher zoom).
- Canvas rendering + DOM panels; custom quadtree hit-testing; neighborhood highlight on hover; pinned selection on click.
- Query mode: 43 curated corpus queries as first-class search entries.
