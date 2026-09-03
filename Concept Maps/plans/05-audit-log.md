# 05 — Audit Log

## Micro-audits (per step)
| Step | Result | Evidence |
|---|---|---|
| 1 Data prep | PASS | integrity assertions in prepare_data.py (203/1102/43, no dangling edges, no dup ids); 523KB output |
| 2 UI shell | PASS | page loads, 0 console errors, 0 failed requests (playwright network audit) |
| 3 Graph engine | PASS | nodes render, hover/tooltip, click select, drag (state-probed: draggingId set, fx pinned, released), zoom/pan/fit |
| 4 Panels & interactions | PASS | search→select (Conscience/Self-Love/Benevolence), related-concept navigation, category toggles (203→155→203), sliders (imp ≥0.96→1 node; str ≥0.89→178 edges), query highlight (rank badges), Esc/close |
| 5 Server + hosting | PASS | curl 200 on 10.20.113.88:8788 (intranet bind proof), gzip (523KB→135KB), 304 revalidation, 404 path, healthz; restart via stop/start verified; crontab @reboot installed |
| 6 3D mode (added mid-task) | PASS | toggle 2D⇄3D, 203 nodes + 1102 links rendered, labels (sprites), selection dimming, query highlight, search focus, fit/zoom, back to 2D |

## Bugs found & fixed (all verified fixed)
| # | Bug | Root cause | Fix | Verify |
|---|---|---|---|---|
| B1 | TypeError reading 'x' on click | d3-quadtree visit API misuse | leaf linked-list walk | click battery clean |
| B2 | TypeError replace not a function | esc() got numeric page | String() coerce | detail panel renders evidence |
| B3 | stale app.js after edits | max-age=300 caching | no-cache + 304 | reload picks fresh assets |
| B4 | tooltip stuck after pointer leaves canvas | no pointerleave handler | added | visual |
| B5 | importance slider dead zone | fixed 0–1 range vs data 0.73–0.96 | range maps to data min/max | ≥0.96 → 1 node |
| B6 | 404 three.core.min.js | three r179 split module build | vendored core file | module loads, Atlas3D ready |
| B7 | 3D animation cycle TypeError 'tick' | d3Force() before engine digest | defer to first engine tick | 3D renders, 0 errors |
| B8 | one-off .x TypeError on 3D click | refresh() inside pointer handler racing controls | deferred setTimeout(0) | click battery clean |

## Macro-audit checklist (final wave — all PASS)
- [x] Every To-Do item completed or documented
- [x] Full interaction battery from clean reload: 0 pageerrors, 0 failed/4xx requests
- [x] Intranet reachability: curl on 10.20.113.88:8788 → 200 + healthz JSON
- [x] Server restart survives (stop.sh/start.sh, pidfile managed)
- [x] Boot persistence: crontab @reboot entry installed (existing entries preserved)
- [x] Data integrity: 203 nodes / 1102 edges / 43 queries / 202 concepts with evidence
- [x] Zero runtime CDN dependencies (all vendored, verified served locally)
- [x] Source data untouched (read-only consumption; no deletions anywhere)
- [x] [HYPOTHESIS] resolved: LAN firewall open (curl on intranet IP 200)
- [x] Screenshots: 2D initial/selected/evidence/search/query/filters, 3D initial/selected/query/final

## Verification waves
| Wave | Scope | Result |
|---|---|---|
| 1 | HTTP + first render | PASS (after B1/B2 fixes) |
| 2 | Full 2D interaction battery | PASS (after B3–B5) |
| 3 | 3D mode battery | PASS (after B6–B8) |
| 4 | Clean-reload full battery 2D+3D | PASS — final |
