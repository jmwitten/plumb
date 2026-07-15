# Cutting Guide v1 — arc report (DB40, homeowner-first)

**Deliverable:** `frameless_three_drawer_40_cutting_guide.html` — the
primary buying/cutting path for the homeowner builder, per the owner's
2026-07-14 homeowner-first ruling. 11 printed Letter pages
(Chrome-verified 11=11), 15 steps over all 13 released `fab.*` WorkSteps,
1333 visible instructional words (≤1500, counting diagram titles and
captions). Branch `fable/instruction-grammar-v1`; the accepted DB40
document set is untouched except the consumer manual's kit gate, which
now names the cutting guide as the first document (the fabrication packet
remains the linked mm-exact shop alternate).

## What the document contains

1. Cover — finished-cabinet render, build-order caption, links (assembly
   manual next; fabrication packet as shop copy).
2. Wood list — 29 parts in four purchased-thickness groups, tape-register
   sizes (clean sixteenth → fraction; otherwise ≈fraction with the exact
   mm bound unbreakably beside it), banded edges named per row, tools
   list, before-you-start boundaries (hardware kit first; nesting is the
   reader's; ≈ rule).
3. Fifteen machining frames — every groove, bore, notch, and layout mark
   with a typed plan diagram where geometry matters; every value printed
   in-document.
4. Purchasing/cutting release record — per-thickness product/lot lines
   plus face/grain, labels, and approval closers.

## Honesty mechanisms (all machine-checked)

- Frame AND diagram prose pass the caption contract: ≤50 words, machine
  tokens forbidden, every digit backed by `allowed_numbers` from typed
  facts. Counts are interpolated, never number-words.
- Diagrams draw only machining-schedule rows; every mark carries
  `model_point_mm` + `fact_ref`; axis orientation comes from each row
  set's typed coordinate system ("up" plots vertically; typed origin
  words become the datum line); every mark is bounds-checked against the
  blank (this guard's absence hid a real axis-convention bug during the
  build — runner rows declare `+X=cut-list width`).
- Uniformity claims ("each of the N parts gets K", "identical on both
  ends", "same setup") are `_uniform`/equality-guarded and die loudly on
  divergent rows; physical-word claims are guarded where typed data
  exists (front edge = banded edge; groove near-edge flip check; toe
  drawing anchored to the banded front edge).
- 41 tests: budgets, fab-step completeness, tape register, unbreakable
  size blocks, diagram honesty (plotted centers == compiled rows),
  self-containment (no step defers to the packet), and mutation flow
  (counts move with the model; stale hand counts fail the build).

## Review trail

- **Adversarial review:** FIX-FIRST — 1 Critical (diagram prose bypassed
  the caption contract), 2 Important (single-representative uniformity;
  word budget missed titles), 3 Minor. All fixed with regression tests;
  verification pass **CONFIRMED**. (`review-cutting-guide-v1.md`)
- **Naive-builder loop, fresh reader per round**
  (`naive-reader-cutting-guide-round{1..4}.md`):
  - Round 1 **FAIL** — six operations deferred their centers to the
    fabrication packet. Every number now prints in the guide.
  - Round 2 **CONDITIONAL PASS** — clipped/overflowing note lines, tiny
    digits, per-part origins untied. Fixed: wrapped notes, typed-origin
    datum lines, groove flip check.
  - Round 3 **CONDITIONAL PASS** — its major claim (wrong mm on the wood
    list) was verified FALSE (a wrapped continuation line misattributed
    across columns); size blocks are now unbreakable and the three
    densest diagrams enlarged after two independent digit misreads.
  - Round 4 **CONDITIONAL PASS** — both hard claims verified FALSE
    against the compiled model (the captured back occupies one world
    plane, so the four groove positions reconcile; the ≈ marks are
    present). Fixed the real gap it exposed: banded-edge marking at the
    saw, mirror-pair orientation notes on end-panel steps.

## Honest residuals (disclosed, not bugs)

- **Mirror-blank orientation** (which corner is "lower-left" on a handed
  blank; which face is inside) is communicated by prose anchors (banded
  edge, mirror-pair notes, flip check), not by typed per-blank
  orientation facts. Closing this fully is a compiler vocabulary work
  order: declared front/rear/inside orientation per fabricated blank,
  same class as counterbore/angled placement.
- Sheet nesting/kerf/yield are not modeled; the guide says so up front
  and never claims a sheet count.
- Pilot depths the sources don't specify stay unclaimed (depth-stop
  wording only).
- Show-face/grain selection is the reader's, by owner design (release
  record captures it).
- The "drawer box — front" vs "drawer front" naming collision is shared
  reader vocabulary across all DB40 surfaces; renaming is out of this
  arc's scope. Captions carry explicit never-drill-the-decorative-front
  warnings.

Loop closed at CONDITIONAL PASS ×3 with all mechanical findings fixed —
matching the accepted consumer-manual precedent ("passes on words, not
pictures"). Final acceptance rests with the owner; round 4's wrong-build
list is the recommended pre-build read.
