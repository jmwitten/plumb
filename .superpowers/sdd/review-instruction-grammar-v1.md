# Adversarial review — STEPDOC +instruction-grammar v1

Reviewer: fresh-context adversarial agent, 2026-07-14, at HEAD `d51ecde`
(confirmed unchanged by `69546ed`/`d51ecde` deltas). Focused suites
97 passed / 1 deselected; existing DB40 + instruction suites 47 passed.
Contracts verified against the actual compiled DB40 data.

**Result: zero Critical, zero Important, four Minor.**

Verified contracts:
- **Typed numbers:** every caption/warning/tool number in all 16 frames
  traces to a typed fact (toe 6, box 8, runner 5/5, pull 2, reveals
  1.5/2, anchors 2); `#2 Phillips` correctly whitelisted.
- **Event ownership:** full ownership map dumped — every CPG `place` event
  claimed exactly once, none dropped.
- **Lettering merges** (fronts+toe GRK, carcass+box Confirmat,
  runner+locking 606N) are identical physical products; counts derive
  from model/schedule.
- **Byte-stability:** `technical` content keys and VTK path unchanged;
  feature-edge change gated off for the default style.
- **Safety:** HOLD gate page precedes caption/imagery with the typed stop
  notice; signed record and countertop hold preserved; no fabrication step
  feeds a frame.
- **No machine IDs:** zero raw-pattern hits in the generated artifact,
  including data attributes.
- **Order:** frame order matches released step order, including the
  runners-then-locking split of `assembly.drawer_hardware`.

## Minor findings and disposition

1. `validate_frame_ownership` collapsed cross-panel duplicate event
   identities into a set (a single claim could satisfy two panels).
   Unreachable today; **fixed** post-review with panel-multiset semantics
   plus a regression test.
2. `repeat_subject` reached the rendered badge without the caption audit.
   Safe today ("per drawer"); **fixed** post-review — now validated like
   caption/hold/warning/tool.
3. `_test_caption_override` test seam in a production signature.
   None-guarded, no runtime effect; retained (it is the loud-failure proof
   for stale hand-written counts), documented here.
4. Consumer captions drop some dimensional verifications the released
   steps carry (toe 101.6/76.2 setup dims, box 12 mm bottom, front Ø5 mm /
   6.00 mm engagement, commission 1.50/2.00 mm). Reviewer confirmed no
   action-changing loss (each is restated on another frame, fixed by the
   pre-cut kit, or subsumed by the HOLD / do-not-load disclaimers).
   **Accepted as the intended prepared-kit altitude**; the fabrication
   packet and technical sheet retain every dimension.
