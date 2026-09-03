# 04 — Decisions / Discoveries / Reversals

## Decisions
| ID | Decision | Rationale | Rejected |
|---|---|---|---|
| D1 | Serve static SPA from `graph-ui/` on :8788 via stdlib Python server | No build chain, no deps, intranet-friendly | Flask/FastAPI (unneeded), port 80/8080 (busy) |
| D2 | Vendor d3@7.9.0, 3d-force-graph@1.80.0, three@r179, fonts locally | Intranet clients may lack internet; verified live downloads | CDN loading |
| D3 | Canvas 2D for primary view; ForceGraph3D for 3D mode | 203 nodes trivial for canvas; 3D requested later → toggle | Cytoscape (heavier), WebGL-only |
| D4 | Data prep drops 5 dangling edges (of 1107) at build time | Source claims 1107 but 5 reference unknown ids post-dedup; source files untouched (A9) | Editing source data |
| D5 | Sliders map to observed data ranges (imp 0.73–0.96, str 0.55–0.97) | 0–1 sliders were dead zones (verified: all importances ≥ 0.73) | Fixed 0–1 range |
| D6 | Labels in 3D via vendored three ESM + import map + canvas-texture sprites | 3d-force-graph bundles three internally without exposing it; duck-typed flags make cross-instance sprites work (verified) | three-spritetext (extra dep), no-labels fallback |
| D7 | `Cache-Control: no-cache` + If-Modified-Since 304s | max-age=300 served stale app.js during iteration (real bug observed) | max-age caching |
| D8 | 3D force config deferred until first engine tick | Sync d3Force() right after graphData() breaks the animation cycle (bisected + verified) | immediate config |

## Discoveries
| ID | Finding | Impact |
|---|---|---|
| F1 | d3-quadtree visit: internal nodes are child-arrays, leaves are {data,next} linked lists | pickNode rewrite; generic lesson for d3 hit-testing |
| F2 | final/ importance range is 0.73–0.96; strength 0.55–0.97 | UI thresholds must follow data ranges |
| F3 | three ≥r167 splits module build: three.module.min.js imports ./three.core.min.js | vendored both; watch for this on any three vendoring |
| F4 | 3d-force-graph UMD (1.3MB) is self-contained (three bundled, not exposed) | custom THREE objects need separate three instance (works via duck-typing, warns "multiple instances") |
| F5 | WebGL works in headless Chromium (SwiftShader) | playwright can verify 3D |

## Reversals
| ID | What | From → To | Why |
|---|---|---|---|
| R1 | pickNode quadtree iteration | iterate node array → linked-list leaf walk | TypeError on internal nodes |
| R2 | esc() | assume string → String() coerce | page numbers are numeric |
| R3 | caching quadtree | cached → rebuild per pick | positions mutate during sim |
| R4 | update3DColors timing | sync in click handler → deferred setTimeout(0) | one-off .x TypeError racing controls listeners |
