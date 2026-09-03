# 07 — Proposed Spec Mutations

## Proposed Spec Mutations
| Section | Current text | Proposed change | Rationale | Confidence |
|---------|-------------|-----------------|-----------|------------|
| §8 Testing | "Flakiness: any test touching timing… run 3+ times" | Add: "UI interaction claims (drag/select/focus) must be verified via state probes (internal flags/coords), not screenshots alone; synthetic pointer tests must compute element offsets via getBoundingClientRect" | Drag test false-positive from sim settling + viewport/canvas coordinate mismatch (this session) | [DERIVED] |
| §5 Research | "verify against the live internet" | Add: "when vendoring a library, verify its full dependency file set (split builds, peer files) by loading it in a real page, not just checking the HTTP 200" | three r179 module imports three.core.min.js — 200 on main file was insufficient | [DERIVED] |
| §6 Planning | Step spec "Test: how verified" | Add: "for UI steps, the test line must name the console-error assertion (zero pageerrors) explicitly" | console errors were caught only because playwright checks were habitual, not spec'd | [HYPOTHESIS] |
