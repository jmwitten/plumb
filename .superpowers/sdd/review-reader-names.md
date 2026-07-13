# Reader-facing part names — final adversarial review

Date: 2026-07-13

Final reviewed feature tip: `7beb0df`  
Merge commit: `0c7d291`

## Initial verdict

FIX-FIRST. The presentation/machine-identity split was sound, but four
cross-surface constructions remained:

1. **Important — fabrication-note identity still used a visible cut label.**
   Two same-profile parts with the same canonical reader name could collide in
   the cut-plan note map even though they were machine-distinct.
2. **Important — duplicate ordinals were computed but discarded on some
   surfaces.** Build sequence, cut plan, and inspector could each print two
   indistinguishable `Registration rail` rows.
3. **Important — inspector fallback/navigation leaked machine names.** The
   selected heading used the reader projection, but picker and neighboring
   construction/load-path links still rendered the machine selection target.
4. **Minor — site-overview reconstruction dropped `reader_name`.** A copied
   `Placed` retained geometry and machine identity but reset presentation
   metadata.

## Fix confirmation

CONFIRMED. The final diff closes all four without moving machine identity:

- cut planning carries an optional `(detail origin, Placed.id)` `source_key`
  separate from its visible source label;
- shared `PartLabel.display_name` owns stable `(index of count)` formatting;
- all inspector human labels resolve through the payload's display projection
  while every selection/query/GLB key remains the machine name;
- the site-overview copy preserves only the presentation field in addition to
  its previous machine/geometry fields.

Adversarial regressions pin duplicate-name/different-fabrication-note parts,
caddy rails and eight screw ordinals, legacy payload fallback, selection-key
stability, and site-overview copy identity. No suffix parser, cache key,
geometry key, evidence key, connection label, or raw technical contract label
depends on reader names.

## Evidence

- Focused affected modules: **114 passed**.
- Expanded reader/spec/viewer/caddy set: **197 passed / 3 skipped**.
- JavaScript syntax and `git diff --check`: clean.
- Final binding gate: **1366 passed / 3 skipped / 1 xfailed** in 857.91s.
- Regenerated caddy HTML SHA-256:
  `c89e91ad085c257599147cc6ad4ca4acd21ef846b2f85c2309d3fd4e6fc90ce3`.
- Browser check: document loaded from the stable local server, 3D viewer
  opened, hover displayed `Side board 1 of 2` plus stock text, and the browser
  console had no warnings/errors.

Final verdict: **READY / CLEAN**.

