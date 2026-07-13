# Adversarial review — STEPDOC/CPG +staging

Date: 2026-07-13
Branch reviewed: `codex/stepdoc-staging`
Disposition: **CLEAN after fixes**

## Scope attacked

The review exercised the approved +staging increment rather than accepting
the shipped examples as proof: typed subassemblies/frames/join authoring,
R-1 bench-events-before-join, presence semantics, explicit `in_situ`,
`bench_then_set` sugar, loud multi-membership errors, reader derivation, and
the CAT-G/CAT-H reversion mirrors.

## Findings fixed

1. Root-context presence initially followed a late authored placement event,
   which could make an already-present obstacle disappear. Root context now
   follows the whole-detail join; a deliberately late placement cannot clear
   a corridor.
2. Hardware listed in a bench unit could inherit the unit frame even when its
   own drive event belonged elsewhere, creating a false PASS. Event-mapped
   hardware now uses its drive event's frame, and explicit cross-unit hardware
   membership is rejected loudly.
3. `bench_then_set` legitimately enumerates all non-context parts, including
   root hardware. Its mechanical expansion remains legal, and root hardware
   is governed by its own drive event rather than the unit join.
4. Reader grouping could erase a part-authored stage inside a bench unit.
   Such stages now retain their authored title, order, why, and ownership.
5. Reserved `root`, duplicate units, null names/whys, and staging language
   that implied an unmodeled cure-before-drive fact now fail or print honestly.

Each issue received a focused regression construction. The final confirmation
re-ran the exact cross-unit, root-hardware, context-presence, and reader-stage
cases and found no remaining false PASS or false FAIL in that bounded attack.

## Acceptance evidence

- Caddy shipped state: 8 install-order verdicts clear at the declared-order
  rung; removing staging restores the 8 blocking UNKNOWNs with all four Q9
  properties; explicit `in_situ` produces the honest 8 FAIL mirror.
- Frame shipped state: both bench frames clear all 8 rail corridors; explicit
  `in_situ` produces the required 4 PASS / 4 FAIL symmetric mirror.
- Caddy's connection-free sofa-arm absence is visibly **DECLARED TRUST**, not
  presented as proof.
- Reader surfaces derive bench, join, placement, and drive steps from the same
  construction process graph used by installability.
- Geometry hashes and existing view PNG hashes did not change.

## Document comprehension reviews

Fresh document-only builder reviews were run for both delivered details. The
caddy review's two blockers were fixed: it now specifies the intended cup as
the fit template with explicit acceptance criteria, and it gives a safe,
tool-dependent 3.5-inch bore procedure. The frame review found the woodworking
instructions buildable; the document continues to block scored or unsupervised
use because calibration, continuous foot support, stability/racking, and
capacity are not analyzed.

## Gate

Verified worktree import:
`/Users/joelwitten/Code/construction-detail-generator/.worktrees/stepdoc-staging/.shim/detailgen/__init__.py`

Binding full suite:
`1337 passed, 3 skipped, 1 xfailed in 1183.90s (0:19:43)`

