# 06 — Evolution Log

## Evolution Log
| Cycle | What I tried | What broke | What I learned | Spec change needed |
|---|---|---|---|---|
| 1 | Cached quadtree for hit-testing | TypeError on internal nodes | d3-quadtree visit semantics: leaves are linked lists | — |
| 2 | Trusted first "drag works" result | position delta was sim settling, not drag | re-test with state probes; synthetic test coords must include canvas offset (getBoundingClientRect) | verify interactions via state probes, not screenshots alone |
| 3 | 0–1 sliders for importance/strength | dead zones (data: 0.73–0.96 / 0.55–0.97) | always derive UI ranges from actual data distributions | — |
| 4 | max-age=300 caching during iteration | stale JS masked fixes | no-cache + 304 revalidation for active development assets | — |
| 5 | Sync d3Force config after graphData | animation cycle crash ('tick') | 3d-force-graph digests data async; configure forces after first engine tick | — |
| 6 | Custom sprites without THREE access | bundle hides three | vendor three ESM + import map; cross-instance objects work via duck-type flags | — |

## Mutation History
| From strategy | To strategy | Trigger | Outcome |
|---|---|---|---|
| 2D-only canvas view | 2D + 3D toggle (user request) | user: "have the graph in 3d view" | shipped, both modes share state/panels |
| CDN vendoring assumption | live-verify every download | A8 | caught three split-build (core/module) |

## Anti-patterns discovered
- Trusting a single positive interaction screenshot → probe internal state (fx, draggingId) for drag/selection claims
- Fixed-range UI controls for data-driven thresholds → derive from data quantiles
- Sync configuration of lazily-initialized engines → defer until ready callback/tick
- Long-lived browser cache during iterative development → revalidation-based caching

## Strengths confirmed
- Bisecting library failures with minimal repro pages (found d3Force timing in 3 tests)
- Vendored-asset strategy: zero runtime network deps, verified by request audit
- Shared DOM panels across render modes kept the 3D addition small
