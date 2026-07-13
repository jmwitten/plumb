# Task FIX-PLATFORM-TOE report — toe-screw contract adoption (Phase-0 flavor b, CAT-B/F-6)

Branch `sdd/fix-platform-toe` off master 8d1f1df. The platform fix arc of
INSTALL v1's Phase-0 trio: kill the undeclared-idealization flavor on the
zipline platform's six end-joist toe screws, and demonstrate the declared
tool-envelope override as F-6's first-class mechanism — with the verdict
outcome VERIFIED against the actual corridor geometry before pinning,
whichever way it landed. **NO geometry changed** (proof below).

## Import-path verification (environment)

The ledger's `.shim` recipe, verified before every run and printed at every
gate:

    cd <worktree> && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen
    export PYTHONPATH="$PWD/.shim"
    python -c "import detailgen; print(detailgen.__file__)"
    # -> <worktree>/.shim/detailgen/__init__.py   (worktree, every run)

## What the defect was, and what was already dead on master

Phase-0 flavor (b): the six toe screws (`toe_pY_/toe_mY_`) are modeled as
straight ±Y solids buried at the joist/beam interface while the REAL
technique is angled — and the idealization was undeclared in the model. By
this branch's base, most of that was already dead by mechanism, not by this
arc: `toe_screwed`'s DEFAULT contract declares `method=toe_screw`, the 30°
angled tool axis (`axis_idealized=True` — amendment #3's flagged display
simplification, never a waiver), and the display-idealization note rides the
contract into the derivation log and the doc disclosure section
(`render_install_disclosures_md` → validation_report.md + the HTML build
document). Verified on this worktree before changing anything: the platform
read per-contract — 6 termination REPRESENTED ("angled shank path not
analyzed … display idealization"), 4 access REPRESENTED-rung passes, 2
blocking `UNKNOWN — install-order dependent` naming the leg thru-bolts/nuts
(the sweep pins' exact state).

What remained undeclared was the TOOL: every verdict was judged against the
module-default 6in x 1in envelope — a generic value, not the technique
anyone would use between each leg's two thru-bolts (~3.5in clear gap).

## The fix (details/platform.spec.yaml only — no src/ change)

The two `toe_screwed` connections now author the F-6 first-class override:

    install: {tool: {length: "3 in", dia: "1 in"}}

— a real stubby/right-angle driver as the authored technique value, stamped
`authored_override` (guardrail #7) while every OTHER field keeps its honest
type-default stamps (the 30° angle and half-length embedment stay visibly
`assumption`-grade). The WHY is in each connection's `assumptions:` (it
rides every toe-screw hardware/overlap derivation fact as an assumption
sub-line), and a spec comment explains the declaration at the source.

Deliberately NOT authored: `method`/`angle`. The type default already says
the technique machine-readably, and re-authoring the 30° angle would
upgrade an assumption-grade technique value to `authored_override` — a
false provenance claim.

## Verdict verification (hand-probed BEFORE pinning)

Hand numbers (inches, worktree build): end joist x[44.25, 45.75],
screw heads at (45, ±15, 23.5/24.5/25.5) driving ±Y; leg thru-bolts at
x[42.925, 43.575] and x[46.425, 47.075], z[24.969, 25.531], protruding
inboard to y=14.077 with nuts at y[14.595, 14.923] (+Y side; -Y mirrors).

The declared 30° corridors leave the joist's ±X cheek faces (x=44.25 /
45.75) with direction (±0.5, ∓0.866, 0), radius 0.5:

- TOP screw (z=25.5): the -X corridor's axis enters bolt +Y0's
  envelope-inflated x-range (≤ 43.575 + 0.5 + r) at ~0.35in of corridor
  length, where its y≈14.70 sits INSIDE nut +Y0's y-span and the bolt's z
  band overlaps (25.5 vs 24.969–25.531). The +X corridor symmetrically
  fouls bolt/nut +Y1. **The four blockers sit in the FIRST INCH of the
  corridors — shortening the envelope 6in → 3in cannot clear them.**
- Lower screws (z=23.5/24.5): min axis-to-blocker distances 1.9"/1.06" vs
  the 0.82" hit radius (axes-report hand numbers, re-confirmed clear on
  this worktree) — a shorter corridor only removes swept material, so the
  passes cannot flip.

The re-run confirmed the prediction exactly: **verdict CONTENT is
unchanged** — 6 termination REPRESENTED + 4 access REPRESENTED-rung passes
+ 2 blocking `UNKNOWN — install-order dependent` naming bolt/nut ±Y0/±Y1 —
and every one of the 12 verdicts now prints the authored
`3.00" x 1.00" dia tool envelope`; the resolved contracts read
`tool_envelope=3.00" x 1.00" dia tool envelope [authored_override]`. This
is CAT-B/F-6's honest v1 end-state: the foreign-blocker order-dependence is
Phase-3 territory, stated by name (screw the joist before bolting the legs
— sequence knowledge v1 does not have).

## Before → after verdict flips

NONE — deliberately. The declared envelope was verified not to change any
verdict's content; what changed is EPISTEMIC: the tool is now a declared,
provenance-stamped technique value instead of a module default, the doc
discloses it, and the pins assert the authored value so a regression to the
default would fail loudly.

## Re-pin inventory (every change verified against probed geometry)

- `tests/test_install_sweep.py` — the 6 toe termination + 6 toe access pins
  now ALSO assert the authored `3.00" x 1.00"` envelope text (blocked AND
  clear); NEW `test_platform_toe_contracts_carry_the_authored_stubby_envelope`
  pins the mechanism itself (tool_envelope=authored_override; tool_axis/
  embedment stay `assumption`; method stays `connectiontype_default`;
  axis_idealized + display-idealization note still on the contract). Verdict
  counts/content pins untouched. Module: 20 passed.
- `tests/baselines/frozen_truth/platform.json` — re-frozen
  (refreeze_from_spec.py), reviewed field-by-field: findings triples,
  by_kind, bom, counts (derivation_log 762), ok, connection_kind_types and
  **geom_fingerprint all byte-identical** — the frozen transform corpus did
  not move (the arc's NO-geometry guarantee, stronger than the 1e-6 pin).
  Justified movers only: findings_fp (12 toe verdict texts), content_fp /
  content_fp_spec (contract fact + connection assumption line), base-SHA
  stamp. rock_anchor / tree_attachment / trolley_launch regens were pure
  SHA-stamp + sub-1e-6 float churn → REVERTED (same call the axes arc made).
- **SHARED baseline regenerated — `tests/baselines/consolidated_doc.textlayer.html`**:
  the consolidated document quotes the two toe UNKNOWN verdict texts; the
  diff was normalized-re-diffed and is EXACTLY the envelope value
  6.00 → 3.00 in those two texts, no other token. Controller must sequence
  sibling merges around this golden.
- `scripts/regen_baselines.py` ran: detail_counts / slice_accounting /
  site_divergence all byte-identical (derivation count unchanged at 762 —
  the override changes fact CONTENT, not fact count).
- Site-level pins (test_site_model / test_site_model_report / the sweep's
  site-composed test): unchanged on purpose — they pin counts/blocking sets,
  which did not move; green in the gate below.

## Inherited cosmetic nits (common brief §nits)

SKIPPED here per the first-toucher rule: all four live in
`tests/test_install_axes.py` / `src/validation/install.py`, which this arc
does not touch (the caddy arc's surface).

## Residuals / honest gaps

- The top toe screw per beam remains a blocking
  `UNKNOWN — install-order dependent` — the truthful v1 end-state; it
  resolves only by axis-3 sequence semantics (Construction Process Graph),
  not by any honest envelope. The build-order WHY is now stated in the
  connection's assumptions and in the doc.
- The 30° angle and the half-length embedment minimum remain
  assumption-grade (correctly stamped); the angled axis remains
  `axis_idealized` until angled-placement vocabulary (design work order #2)
  raises the REPRESENTED rung to GEOMETRY-PROVEN.
- The 3in x 1in stubby envelope is itself an authored technique value —
  honest provenance, not manufacturer data; a real driver spec could later
  refine it to `manufacturer_data`.

## Gates

- Import-path verification printed at every run (above).
- tests/test_install_sweep.py: 20 passed (19 + 1 new).
- Targeted affected modules (sweep, platform spec/detail, site model/report,
  presentation equiv, baselines, reproducible builds): **112 passed** in 34:06
  (controller-run in this worktree, import path verified).
- Full suite: deferred to the controller's merge gate (sequential-merge
  protocol; this branch merges third, after the stool and caddy arcs, and
  re-gates on the combined tree — where its frozen platform corpus must be
  re-frozen once more over the siblings' _fmt clamp texts).
