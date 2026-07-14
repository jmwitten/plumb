# Fresh confirmation — STEPDOC/CPG +presentation

**Branch:** `codex/stepdoc-presentation`

**Base:** `aa8cd90`

**Reviewed head:** `339d945`

**Final verdict:** APPROVE — no Critical or Important defects remain.

## Initial findings

The first adversarial pass found five release blockers:

1. the fasten image annotated only one of the two registration rails;
2. hidden future-panel parts remained raycastable and a pinned tooltip could
   outlive the part's panel visibility;
3. an interrupted overlay pass could publish a poisoned PNG cache entry;
4. missing ignored legacy views caused the document-pair path to compile the
   detail twice; and
5. typed hardware/tool icon names all rendered as a generic bullet.

It also requested the promised footer link, a plain blocking-failure release
rule, and a fresh document-only handyman read.

## Correction round

Commit `339d945` closes those findings:

- all four fastener stations across both rails reach the overlay and the PNG
  records both rail reference ids;
- raycast and tooltip visibility follow ancestor visibility and the current
  panel while retaining a valid pin for restoration;
- VTK, PIL overlays, and metadata write to a same-directory temporary PNG,
  validate it, and atomically replace the keyed destination;
- missing legacy views render in-process from the already compiled detail;
- the manual uses a closed, typed inline-SVG icon vocabulary and rejects an
  unknown icon;
- header/footer links are reciprocal and the manual states both the release
  rule and the prototype proof boundary.

The builder-read corrections also derive actual member dimensions, side-board
registration witness faces, the 6-1/2-inch clear opening, rail ordinals, and
both rails' hardware stations from compiled geometry. Adhesive and unresolved
fastener/tool choices are visible selection gates. The manual does not invent a
product, timer, clamp count, pilot size, torque, finish, capacity, or hot-drink
safety claim.

## Independent confirmation

The fresh reviewer generated a new pair under
`/tmp/detailgen-caddy-confirmation-339`, inspected the images and HTML, replayed
the clean-checkout compile path, and exercised the staged viewer in a live
WebGL browser.

- Fresh fasten PNG: four stations and both `lumber-2,lumber-3` reference ids.
- Compile probe: `compile_calls=1`, `render_calls=1`, identical detail object,
  and no missing views.
- Viewer probe: a Sofa-arm pin made on panel 5 hid on panel 1, restored on
  panel 5, and the same panel-1 ray subsequently selected a visible rail rather
  than the hidden Sofa arm.
- Typed-icon inspection: 15 SVG instances, 10 typed labels, and 10 distinct
  path geometries.
- Focused confirmation: **62 passed / 3 skipped**; the skips are the opt-in
  four-detail GLB sweep.
- `node --check src/rendering/web_viewer/viewer.js` passed.

## Semantic non-change

Compared with `aa8cd90`:

- assembly hash unchanged;
- all 122 validation finding tuples unchanged;
- all 13 event identities unchanged;
- legacy viewer payload unchanged;
- the edge set changes only by the two intended cross-rail cure-to-fasten
  authored constraints that make the declared caddy batch workflow explicit.

The remaining notes are non-blocking: the live WebGL behavior is supported by
source-level regression tests plus the recorded runtime probe rather than an
always-on browser test, and the initial review file deliberately retains its
historical `REVISE` verdict.
