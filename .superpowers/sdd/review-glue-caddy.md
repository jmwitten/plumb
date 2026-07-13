# Adversarial review — branch `sdd/glue-caddy` (glued ConnectionType + caddy rail->top re-spec)

Reviewer: fresh adversarial pass, independent probes only. Tree: worktree at
ae0799d, base master ab11af4. Import path verified before every probe
(`detailgen.__file__` -> the worktree shim). Targeted tests only (controller
gates the full suite).

## VERDICT: MERGE

Zero blocking findings. Every claim in `task-glue-caddy-report.md` that I
probed reproduced exactly; the two residuals I stress-tested are real gaps
honestly filed, not solved-and-overclaimed; the reversion probe discriminates.

## Attack 1 — `bonded_to` in `LOAD_BEARING_EDGE_KINDS` (the highest-leverage change)

**Finding: the edge cannot over-route anything today, and the gate is the
transfer claims, not the kind list — verified live, not by reading.**

- Key discovery: `downward_load` is the ONLY currently-provable load class
  (`LOAD_CLASSES.require` raises `OntologyError` for `shear`/`pull_out` —
  "reserved for the construction ontology, not yet provable"). `Glued`
  claims only pull_out + shear, so for every provable proof
  `transfers_by_connection` yields `None` on a glued connection and
  `_adjacency` DROPS the edge. Adding `bonded_to` to the kind set is
  provably inert for gravity until some connection claims downward_load —
  which Glued deliberately never does (no gravity seat).
- Synthetic probe: support board glued (only) to ground board,
  `check_load_path(downward_load)` -> **FAIL** "downward-load path BROKEN:
  support board reaches no ground/Support (reached: nothing); … glue joint
  (no transfer claim)". The break names the glued connection in the audit
  trail. Honest.
- Mutation: forcing `transfers={'glue joint': True}` flips it to
  "REPRESENTED: support board -> ground board" — demonstrating the gate
  lives in the claims and the wording stays REPRESENTED (a reachability
  statement), never adequacy. The house rule holds.
- The shipped caddy declares no roles -> **0 load_path findings** on both
  master and branch spec (measured), so the caddy itself never exercises
  the new eligibility. Nothing claims more than the placeholder
  pull_out+shear anywhere.

## Attack 2 — the deleted up screws

- Parts 18 -> **14** (4 screw solids gone), BOM screw rows: **one row,
  qty 8, 0.19" dia x 1.25in (31.75mm)** — no 2in row. (Display prints
  "1.2\"" — pre-existing rounding convention, not this arc.)
- Dangling refs: repo-wide grep for `vscrew|screw_len_v|screw_dy_v|
  upscrew_z|rail_mid_x` — only hits are the reversion probe's intentional
  `vscrew_ghost` and OTHER details' own same-named params. The spec's
  `validation:` block carries no stale allowlist entries.
- **Rail->top mate measured flush**: rail zmax = 0.000000000, top board
  zmin = 0.000000000 — zero air gap at the bond plane. Not the inverted
  tree-lag.
- The top's separately-declared gravity bearings all PASS:
  top<->arm (22.02 in²), top<->side +X / -X (3.95 in² each) — untouched.

## Attack 3 — verdict flips + the NOT-ANALYZED semantics

- Reproduced live, branch spec vs master spec under branch code:
  install findings 24 -> **16** (12 PASS + 12 UNKNOWN -> 8+8), failures
  **0**, blocking 12 -> **8**. The 16 side-screw finding texts
  (verdict, detail) are **16/16 byte-identical** across the two compiles.
  Shipped caddy family row: "Fastener installability | UNKNOWN —
  UNRESOLVED | checks_run: 16" — content driven by the side screws only.
- Synthetic glued-only spec's `UNKNOWN — NOT ANALYZED` (checks_run 0):
  **I judge this the truthful row.** Reasoning: the family's verdict
  vocabulary offers PASS (something proven), UNKNOWN — UNRESOLVED
  (judged, unanswerable), and NOT ANALYZED (no checks ran). For a detail
  whose only joints are glued, no fastener exists, so no check can run —
  "checks_run: 0 -> NOT ANALYZED" is literally true. A vacuous PASS would
  assert what nothing proved (over-claim, the forbidden direction). The
  most precise verdict would be a "NOT APPLICABLE — no fasteners declared"
  row, which the vocabulary does not have; inventing it is separate
  vocabulary work, and the machine-side distinction is already preserved
  by `install_contract() == ()` vs `None`. Mild under-claim, correct side
  of the line, and residual 5 files exactly this. Agreed.

## Attack 4 — reversion probe discriminates

- Ran the ghost mutation by hand outside pytest: the D6 defect re-added to
  the SHIPPED spec produces the verbatim originals —
  install_access **FAIL** "entry face buried … mid-plate, … 4.00\" inside
  registration rail +X … impossible joint as declared (GEOMETRY-PROVEN…)"
  and install_termination **FAIL** "embedment below the declared minimum:
  0.50\" bite into top board < 1.00\" minimum [assumption]". The 8 shipped
  side screws keep PASS.
- No vacuous pass: the shipped spec has **0** install FAILs, so the
  probe's FAILs come only from the re-added defect.
- Blind-checker mutation: monkeypatched install_access findings to forced
  PASS -> ghost access FAILs drop to 0 -> the probe's `len==1 and
  verdict==FAIL` assertions trip. The probe discriminates.

## Attack 5 — type honesty

- Guards verified in tests (ran green: test_glued_connection 8/8 within a
  45-pass batch incl. test_connection/test_loadpath/test_evidence_graph)
  and exercised live via my probes: exactly-2 raises a teaching error,
  hardware raises "expected 0 hardware".
- Transfer claims are mechanism-only (unit-pinned: no "grain"/
  "face-to-face" in claim text); substrate lives on the two caddy
  connections' assumptions (long-grain top edge to face grain, capacity
  NOT analyzed) — R-SUBSTRATE honored.
- `install_contract() == ()` and `is not None` unit-pinned.
- Clamp/cure process fact reaches BOTH surfaces: derivation report
  contains clamp/cure/glued/bonded_to; rendered validation_report.md has
  clamp x11, cure x6, glue x31.

## Attack 6 — doc prose truth + stale PNGs

- Rendered the doc via `render_documentation`: **zero** "pocket" mentions,
  off-the-sofa assembly note retained, glue-and-clamp instructions
  standalone, one 8-qty screw row, no 2in screws, glue/clamps disclosed as
  shop consumables (the sit-reach convention). `single_detail_report.py`'s
  caddy panel rewritten to match ("Hidden rail joints — glue, then screws,
  all off the sofa").
- Stale-PNG claim verified in the MAIN checkout:
  `outputs/armchair_caddy/views/*.png` mtimes 2026-07-10 00:44–00:45; the
  geometry-changing commit 0f95b4c is 2026-07-11 09:06. The PNGs predate
  the up-screw deletion (they still draw 4 up screws) — the controller's
  forced re-render is justified.

## Attack 7 — round-trip + evidence

- `load(dump(doc)) == doc` **True**, re-dump byte-equal **True**.
- Evidence graph builds with `bonded_to: 2` carried verbatim among the
  construction kinds; orphan guards exercised by the green
  test_evidence_graph batch and by building the caddy graph live.
- `what_depends_on('top board')` returns both rails as construction
  neighbors via `bonded_to` with the connection labels as provenance, and
  invalidates the `Glued.bonded_pairs`/`Glued.edges` derived facts.
- `incremental/affected_region.py` imports `_CONSTRUCTION_EDGE_KINDS` from
  evidence (line 80) and filters on it (201, 212) — bonded_to flows in
  transitively, as the report claims.

## Attack 8 — residuals stress-tested (both REAL, neither overclaimed)

- **Residual 2 (bond-plane contact unproven) — confirmed real by
  mutation**: dropped both rails 0.5in (`rail_bot_z = -rail_drop - 0.5`)
  so the "glued" joint floats over a half-inch air gap -> compile +
  validate produce **ZERO failures**. Exactly the honesty gap the residual
  states, with the right upgrade path (contact-proof ≠ bears_on). The
  shipped spec's measured gap is 0.0, so the delivered detail is truthful.
- **Residual 4 (bare `install:` on a `()`-contract type silently
  ignored) — confirmed real by mutation**: added `install: {method:
  pocket_screw, angle: 15}` to a glued caddy connection -> compiles and
  validates with zero glued-joint install findings, no error. Pre-existing
  (standoff_post_base shares it); note it now has a second consumer, which
  nudges the shared-resolution nit's priority up.
- Residuals 1 (capacity unanalyzed), 3 (clamp/cure prose not process), and
  5 (family row) are accurate as filed — see attacks 1, 5, 3 respectively.

## Numbers measured (all independently, live)

- parts 18 -> 14; edges: bonded_to 2, fastened_by 2, installed_before 16
  (master spec: fastened_by 4, installed_before 24, no bonded_to)
- install findings 24 -> 16 = 8 termination-PASS + 8 access-UNKNOWN;
  failures 0; blocking 12 -> 8; side-screw texts 16/16 byte-identical
- load_path findings on the caddy: 0 (both sides — no roles declared)
- glued-only chain: downward_load FAIL ("no transfer claim"); forced-True
  mutation -> REPRESENTED (gate = claims, not edge kind)
- targeted suites: 45 passed (glued/connection/loadpath/evidence) +
  37 passed (install_sweep + caddy e2e); full suite left to the controller
- bearings: 3/3 PASS (22.02 / 3.95 / 3.95 in²); BOM: one screw row qty 8
- air-gap mutation: 0 FAILs (residual 2 real); install-override mutation:
  silently ignored (residual 4 real)
- round-trip: byte-stable both directions
- PNGs Jul 10 00:44 < geometry commit Jul 11 09:06 (regen justified)

Also verified: `regen_baselines.py --check` -> "baselines are current."
from the worktree (shimmed), and no file in tests/baselines/ mentions the
caddy. Not independently verified: the report's full-suite 1116/3/1
(controller gates it).
