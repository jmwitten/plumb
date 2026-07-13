# Task INSTALL-AXES report — axis-1 (geometric termination) + axis-2 (static tool access) + the Phase-0 sweep as pytest

Branch `sdd/install-axes` off master 267d91b (coverage family + contract
schema already merged). This is the heart of INSTALL v1: the checks that make
the shipped defect class impossible to ship silently. Every verdict DERIVES
from the fastener's resolved `FastenerInstallation` contract on
`ConnectionChecks.installs` (owner amendment #1 — no global geometric rules),
and every verdict speaks its rung (guardrail #6).

## Import-path verification (environment)

The ledger's `.shim` recipe, verified before every gate:

    cd <worktree> && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen
    export PYTHONPATH="$PWD/.shim"
    python -c "import detailgen; print(detailgen.__file__)"
    # -> <worktree>/.shim/detailgen/__init__.py   (worktree, every run)

## Mechanisms (`src/validation/install.py`, wired at `details/base.py:271`)

**Entry point** — `check_installability(assembly, connections, checks, tol)`
(install.py:309): consumes `checks.installs` (declaration order) +
`checks.edges`; runs after the connection findings inside `Detail.validate()`
(order is part of byte-identical determinism). It sees ALL connections at
once: party-vs-foreign classification of a corridor blocker needs global
membership, per-connection scope cannot do it.

**Axis 1 — `install_termination`** (install.py:454):
- A thin probe cylinder on the fastener's datum axis (`head_bearing`→`tip`;
  rods use `top`→`bottom`; neither pair = loud teaching error,
  install.py:288) is intersected per-member with `.vals()` multi-solid
  honesty. Probe radius = shank radius + 2.5 mm (`_HOLE_CLEARANCE`,
  install.py:100): a bolt/rod runs inside a MODELED clearance/epoxy hole, so
  an on-axis needle reads hole air — the `check_through_hole` "present"
  probe's lesson (bolt holes are shank + 0.25 mm; the rock anchor's epoxy
  annulus is 1.6 mm). The probe reaches 305 mm behind the head
  (`_BEHIND_SPAN` — a buried head's entry face lies BEHIND it; the caddy's
  is 4 in back) and 50 mm past the tip (a breach lies beyond it).
- Per-member chords (stations from intersection-solid bboxes projected onto
  the axis — exact for axis-aligned members; ≤ one probe radius off for a
  tilted member, a documented residual; no shipped shank-mode fastener is
  tilted) give the entry-face station, the tip's terminating member, the
  bite, and any far-face breach. The on-path filter is inclusive at the tip
  (`s_in < L + tol`): a blind hole drilled exactly shank-deep puts the
  terminating member's material AT the tip station (the rock anchor bore).
- Judged ONLY against the contract: `exit=none` FAILs an undeclared breach
  naming the exact face + coordinates + overshoot; `concealed_exit` PASSes a
  breach with the disclosure; `through_exit_required` FAILs a MISSING exit
  (and a wrong-member exit), and with an empty declared face-set degrades to
  honest UNKNOWN naming what is missing. Embedment: measured bite vs the
  declared minimum, the minimum's provenance printed (`[assumption]` for the
  half-length rule); `None` = judged only as declared (no minimum);
  `"through"` = the through-exit rule. Rung: GEOMETRY-PROVEN (worded) in
  shank mode; an `axis_idealized` angled contract is NOT measured — the
  drawn solid is the display simplification, not the technique — and reads
  "Installation method represented; angled shank path not analyzed"
  (install.py:439), never a bare PASS.

**Axis 2 — `install_access`** (install.py:627 shank, :750 angled):
- Head-station classification against the entry member's chord distinguishes
  the Phase-0 flavors mechanically: head strictly inside = "entry face
  buried … mid-plate … impossible joint as declared" (the caddy); head at
  the far-face joint plane (±1 mm) = "head stationed AT the joint interface
  … station-not-face" (the stool); a declared `recessed_in_pocket` /
  `flush_countersunk` head makes the burial REPRESENTED ("recess geometry
  not analyzed — judged as declared") and sweeps from the recess mouth.
- The CONTRACT's tool envelope (always resolved; its used value prints in
  every verdict) is swept as a cylinder along the CONTRACT's tool axis, per
  part, never fused — the verdict names the blocker. `through_bolt` sweeps
  BOTH ends (driver side from the head, wrench side from the tip past the
  nut; the stack order names which end is which).
- Blocker classification (install.py:573): party present at the joint's own
  step ⇒ FAIL naming it; party the connection's OWN `installed_before`
  closure orders strictly AFTER the fastener ⇒ disclosed, not blocked
  ("occupy the corridor in final geometry but this connection's own declared
  order installs them after this fastener (stage: own_connection)") — the
  design's `stage` field doing its v1 job; foreign part ⇒ blocking
  `UNKNOWN — install-order dependent` naming the blocker AND its owning
  connections. Same-role-group siblings are excluded from each other's
  corridors (co-driven at one step in free order; four hanger screws on a
  manufacturer schedule sit closer than a crude 1 in driver cylinder).
- Angled (idealized) axes sweep the DECLARED angle off the entry member's
  two cheek faces (the faces across its thinnest extent ⊥ the drive axis —
  where a toe/pocket screw physically enters, install.py:711). The joint's
  own two members are what the declared angle negotiates and are excluded
  AND SAID so; third-party material is judged; one clear cheek is a
  REPRESENTED-rung pass naming the face used.
- Prefilter honesty: every (probe, part) pair AABB-prefiltered or exactly
  intersected, `skipped + checked == total` asserted per call
  (install.py:251).
- Deliberately NOT cached: `_CHECKS_FP` fingerprints only `checks.py` +
  `core/config.py`; wiring these findings into the persistent verdict cache
  would serve stale verdicts across edits to this module. v1 recomputes.

**New construction knowledge** — `FaceMountHanger.edges()` now declares
`header screws installed_before the hung member` (connection.py, the
technique's real sequence: hanger to header first, joist drops in after).
This is what lets the hanger header screws — whose heads the hung member
buries in final geometry — read honestly clear at their own install step
instead of a false "impossible" FAIL. (+4 derivation facts per hanger
connection; platform 722 → 762.)

**Soundness fix found live** — the axis findings' subjects name only the
fastener, but their verdicts depend on a geometric NEIGHBORHOOD (shank
members, entry face, corridor blockers — cross-connection, and composed,
cross-detail). `test_affected_region` caught the one-sided-beam edit
changing bolt/header-screw termination details outside the region. The two
axis kinds now go DELIBERATELY unattributed in the evidence graph
(`EvidenceGraph._link_finding`, evidence.py:552) — the zero-attribution
floor, revisited on every non-empty edit — until the checks persist their
true dependency sets. `install_method` (contract resolution, no geometry)
keeps attribution.

## Per-detail verdicts (all hand-verified against probed geometry)

| Detail | Axis 1 (termination) | Axis 2 (static access) |
|---|---|---|
| armchair_caddy | **FAIL ×12** — up screws bite 0.50" into the top < 1.00" half-length min [assumption] (head z=−1.5", tip +0.5" into the 1" top); side screws bite 0.50" < 0.62" | **FAIL ×4** up screws: head 4.00" inside the rail (rail z −5.5..0, head −1.5) — mid-plate, impossible joint; **UNKNOWN ×8** side screws: corridor backs across the 0.25" reveal into the SOFA ARM (arm x ≤ 3.0, heads at 3.25) — foreign |
| step_stool | PASS ×8 (cleat screws bite 1.25" ≥ 0.62"; tread screws 1.00" = 1.00") | **FAIL ×4** cleat screws: head at x=4.50 = the cleat(3.75..4.50)/panel interface — station-not-face; PASS ×4 tread screws |
| platform | PASS ×82 — toe screws REPRESENTED ("angled shank path not analyzed"); 8 bolts exit the declared far plate (tip 0.92" past the free face — CAT-C verifier measured all 8 at 0.92"; an earlier 1.42" figure in this report came from a one-sided-edit test variant, not the shipped spec) | PASS ×80 (40 hanger header screws clear-by-own-declared-order; bolts two-sided clear; 4 lower toe screws' 30° cheek corridors clear); **UNKNOWN ×2** — TOP toe screw each beam (z=beam_bot+3): both 30° corridors foul the leg thru-bolts/nuts (bolts at x=43.25/46.75, z=beam_bot+2.75, protruding inboard to y=14.08) — foreign, F-6's flavor |
| sit_reach_box | PASS ×16 (bites exactly at the 0.75" minimum) | PASS ×16 |
| sit_reach_frame | PASS ×12 (rails bite exactly 1.5") | PASS ×4 cap screws; **UNKNOWN ×8** rail screws: 6" corridor crosses the ~2" interior gap into the OPPOSITE side's rail/legs (rail −X at x[−2.5,−1.0] vs heads at x=±1.0) — foreign connections |
| rock_anchor | PASS ×4 — rods terminate inside the boulder (tip at hole bottom −8", material to −11"; no declared minimum, adhesive-spec data); bolts exit the declared far bracket | PASS ×4 — rod corridors above the nut stacks clear; bolts two-sided clear |
| trebuchet | **FAIL ×18** — 12 butt screws bite 1.00" into the cross ends < 1.25" [assumption] (2.5" through the 1.5" rail); 6 upright lap screws bite 0.75" < 1.12" (2.25" through the 1.5" rail into the 1" upright); PASS ×12 (gussets/runway 0.88" ≥ 0.81") | PASS ×30 (heads on open faces) |
| tree_attachment | — (no Connection-declared fastener contracts) | — |
| trolley_launch | — (same) | — |
| **site (composed)** | as per fragments | **+1 UNKNOWN only visible composed**: rock-anchor rod 1's insertion corridor is obstructed by the platform's lowest ladder rung + hanger + screws (rung 0 spans z 6.17–9.67" directly over the rod at (45,15), rod top 2.75"; rod 0 at y=19.25 clears the rung's y ≤ 16.5). Total site blockers: 3 foundation_capacity + 3 install_access |

**Divergences from the brief's expectations, pinned as measured truth:**
- Platform toe screws: the brief expected all 6 ⇒ UNKNOWN; measured geometry
  says only the TOP screw per side is corridor-blocked at 30° (the two lower
  screws sit 1–2" below the bolt line; hand numbers: nut at z 24.97–25.53,
  screws at 23.5/24.5/25.5 — min axis-to-nut distances 1.06"/1.9" for the
  lower screws vs the 0.82" hit radius). F-6's reasoning was qualitative;
  the per-screw split is the honest per-contract result the brief's binding
  clause ("the platform must read per-contract") requires.
- Caddy: beyond the expected up-screw FAILs, the axis checks found honest
  embedment shortfalls on ALL 12 screws (assumption-grade minimum, printed
  as such) and the side screws' sofa-arm corridor UNKNOWNs. Phase-0's probe
  only checked head burial; these are new, verified truths.
- sit_reach_frame: expected "clean on both axes"; honestly 8 blocking
  corridor UNKNOWNs (opposite wall 2" behind each rail-screw head vs the
  declared 6" envelope). Real build order (screw the rails before closing
  the box) is exactly what v1 cannot know. **FLAG: the delivered frame doc's
  truthful state is BLOCKED** until a fix arc (declared stubby-driver
  `install: tool` override, or Phase-3 sequencing).
- **FLAG — trebuchet (never swept in Phase 0): 18 honest embedment FAILs.**
  The delivered doc's truthful state is BLOCKED. The screws are real-length
  shortfalls against the half-length assumption (butt screws 1.0" < 1.25";
  upright laps 0.75" < 1.12" — the lap screw is longer than the joint is
  thick). Fix arc: longer screws or an authored embedment override with a
  defensible WHY; not silently fixed here.

## Fix round (verification-fleet FIX-FIRST — geometry + honesty lenses)

The review fleet (committed: `review-install-axes-geometry.md`,
`review-install-axes-honesty.md`, `review-install-axes-regression.md`; all
six CATs independently CONFIRMED, regression MERGE) returned two FIX-FIRST
verdicts with confirmed counterexamples. Every required fix landed with a
pinned regression test reproducing the reviewer's probe verbatim
(`tests/test_install_axes.py` §FIX-FIRST regression pins;
`tests/test_trebuchet_e2e.py::test_install_disclosures_reach_the_per_detail_reader_surfaces`):

- **GEO-F1 (MAJOR)** — axis-1 termination now walks MEMBER chords only,
  anchored at the CONTRACT's entry member, merging while contiguous: the
  crediting span ends at the first air gap, foreign on-path material is
  disclosed and never credited, and the oversized (shank + 2.5 mm) probe is
  scoped to the connection's own members — a foreign slab past a gap
  (probe A/A2) or a parallel stud 2.2 mm off the shank surface (probe B,
  the fully-CLEAN masking flavor) can no longer swallow an undeclared
  breach. Fixing this surfaced one real type-knowledge gap: an epoxy rod
  threads its BRACKET's modeled hole before entering the boulder, so the
  walk starts at the entry member and pre-entry member material is a
  disclosed pass-through; and the FaceMountHanger's hanger now rides BOTH
  screw groups' stacks (each group drives through one of its flanges).
- **GEO-F2** — the through-bolt wrench-side sweep starts at the DECLARED
  exit face's station, covering the [far face → tip] nut zone (probe C: a
  nut-hugging foreign block previously read "wrench side: clear").
- **GEO-F3** — "N short of its far face" prints the part's true far extent
  (AABB projected on the axis); the stool up screws read the honest 8.25"
  where the 50 mm probe cap printed 1.97".
- **HON-F1** — `concealed_exit` matches the measured exit member against
  the declared face-set (the through-exit wrong-member rule's twin): a
  breach through an undeclared member FAILs naming both the actual and the
  declared faces; only a declared-face breach keeps the disclosed PASS.
- **HON-F2** — guardrail #7's doc half now reaches both per-detail reader
  surfaces: `render_install_disclosures_md` appends the resolved contracts
  (per-field provenance + assumption notes) and every OPEN axis verdict's
  full text to `validation_report.md` at the lifecycle level (like the
  coverage matrix), and `single_detail_report.py` carries the same section
  in the HTML build document. The earlier claim that `_fact_line` alone
  satisfied the doc-disclosure clause was wrong — the sampling cap kept
  contract facts off every page; this section is the fix, and the pin
  requires all 18 trebuchet verdict texts (with `[assumption]` and the
  envelope value) on paper.
- **GEO-F1 continuity refinement (controller-caught false alarm)** — the
  first continuity rule ("crediting span ends at the first air gap")
  falsely FAILed the CL3 tree-lag STANDOFF fixture: a free-standing member
  deliberately stands clear of its anchor, and the lag's bite across that
  gap is geometrically real (the gap is a BEARING fact the bearing checks
  already own and the fixture already pins as its expected divergence).
  Refined semantics: membership stays ABSOLUTE (foreign material is never
  credited — probes A/B keep failing), but a gap-cross into the
  connection's OWN member is CREDITED with the gap DISCLOSED by length and
  destination ("the shank crosses a 1.50\" air gap before entering beam
  +Y — a standoff joint's clearance (a bearing fact, judged by the
  bearing checks); gap disclosed, own-member bite beyond it credited").
  The breach test runs on the FULL member walk regardless of crediting: a
  tip past the LAST own-member material — open air (probe B) or foreign
  (probe A) — still FAILs. Pinned twice: the tree-lag fixture verbatim
  (`test_tree_lag_standoff_fixture_reads_the_honest_pass`) and a synthetic
  own-anchor standoff
  (`test_standoff_gap_cross_into_own_anchor_is_credited_with_disclosure`).
  NOTE for the re-verifying geometry reviewer: the fix-shape sketch in
  review-install-axes-geometry.md §F1 suggested treating ANY member beyond
  a gap as an exit — that half is superseded by these honest standoff
  semantics; the probes the review CONFIRMED (A/A2/B, foreign/open-air)
  keep their FAIL pins unchanged.
- **Fold-ins** — knife-edge interface tie resolves to the deepest-entered
  chord (honest ~zero bite); corridor stack skip narrowed to the
  fastener's own role group with same-group siblings DISCLOSED when
  bodily inside a corridor; the ordered-after clearance PASS stamps
  "geometry proven … occupants' later arrival is this connection's
  DECLARED order, not sequence-proven" (never a bare GEOMETRY-PROVEN on a
  declared-order premise); note-separator cosmetic; the tilted-chord
  error bound corrected to r·tan θ (≤ 45° for the ≈r reading) and the
  rotated-member cheek-plane AABB documented as ANTI-conservative for
  blocker detection (named residual — no rotated case ships).

Shipped verdict classes are unchanged by the fix round; detail texts moved
(honest corrections + disclosures), so platform + rock_anchor frozen truth
re-froze once more (justified: findings_fp/content_fp only).

## Trebuchet handoff (for the agent working the trebuchet — relayed by the controller)

The trebuchet was NEVER swept in Phase 0 (it postdates the sweep) and its doc
was delivered before the axis checks existed. This branch changed NOTHING in
`details/trebuchet.spec.yaml` (verified: the branch diff touches no file
under `details/`; master's copy is also unchanged as of 5feee8a) — it only
ran the new checks and pinned the honest verdicts. The trebuchet's truthful
state at this branch tip is **BLOCKED, 18 termination FAILs**:

- **12 base butt screws** (`butt screw ±X front/mid/rear 0-1`): 2.5 in screws
  driven through the 1.5 in base rail into the cross-member ends — measured
  bite **1.00 in < the 1.25 in half-length minimum [assumption]**.
  Hand-probe: rail +X spans x 8.00–9.50 in, head bearing at x=9.50 (on the
  free face — correct), tip at x=7.00, cross members span x −8.00–8.00, so
  the bite into the cross end is exactly 1.00 in.
- **6 upright lap screws** (`upright lap screw ±X 0-2`): 2.25 in screws
  through the 1.5 in rail into the 1 in-thick upright — measured bite
  **0.75 in < the 1.12 in half-length minimum [assumption]**. Hand-probe:
  head at x=9.50, tip at x=7.25, upright spans x 7.00–8.00 — the screw is
  longer than the joint is thick and stops 0.25 in short of breaching the
  upright's far face. Note also: the contract's default entry face is the
  UPRIGHT's free face (cleat_screwed semantics, screws through parts[0]),
  but the modeled screws enter through the RAIL — the head sits 1.5 in proud
  of the upright's entry face, which the checker accepts (proud-of-face),
  worth a look during the fix.
- Everything else is green on merit: gusset screws bite 0.88 ≥ 0.81 in,
  runway screws 0.88 ≥ 0.81 in, all 30 access corridors clear (heads on
  open faces), no UNKNOWNs.

The failing minimums are ASSUMPTION-grade (the half-under-head-length rule,
provenance printed in every verdict). Fix options for the owning agent:
longer screws, or an authored `install: embedment:` override with a
defensible WHY (which would carry `authored_override` provenance). The pins
live in `tests/test_install_sweep.py::test_trebuchet_honest_embedment_failures`
and `tests/test_trebuchet_e2e.py::test_compiles_and_validates_with_honest_embedment_failures`
— both assert the exact counts/messages, so the fix arc re-pins them to
green deliberately.

## The Phase-0 sweep as pytest + CATs

- `tests/test_install_sweep.py` (19 tests): all 9 standalone specs pinned
  per flavor (module-scoped compile-once fixture); `site.spec.yaml` loudly
  excluded per phase0-sweep-results.md and covered by a site-composed e2e
  instead (pins the 2 toe UNKNOWNs + the composed rod-vs-rung truth +
  through-bolt exits at site level — the brief's site-level install test).
  The synthetic axis-1 regression probe (the live-verified silent breach):
  `screw_len_h 1.25 → 1.75` as a spec-TEXT mutation ⇒ all 8 side screws FAIL
  "undeclared exit … side board's ±X face … by 0.25" — the shipped spec is
  untouched.
- `tests/test_install_axes.py` (12 tests): CAT-A both halves (driven_straight
  burial FAIL vs pocket-head REPRESENTED wording vs full angled-pocket
  contract, same joint); CAT-C (missing through-exit FAIL, present exit PASS
  with two-sided access, the exit=none INVERSE from the same checker, the
  empty-exit-faces honest UNKNOWN); CAT-E (unordered party FAIL / foreign
  named UNKNOWN / ordered-after disclosed PASS); CAT-F v1 half (foreign
  blocker named WITH its owning connection); unmappable-descriptor honesty.

## Re-pin inventory (every change is to the NEW truth, never weakened)

- `test_platform_spec.py` — blocking set 3 → {capacity×3, install_access×2};
  frozen truth REFROZEN (platform + rock_anchor; justified: the axis
  findings + the hanger-sequence edges; tree/trolley regens were pure
  SHA-stamp/float-noise churn and were REVERTED — no justified diff). The
  1e-6 transform pins did NOT move (no geometry changed).
- `baselines/detail_counts.json` — platform derivation_log 722 → 762.
- Presentation golden regenerated + reviewed: family row UNRESOLVED for
  platform/site (164/172 checks), PASS×8 for rock anchor; the site
  open-findings block 3 → 6.
- `test_armchair_caddy_e2e.py` — honest-red re-pin (16 FAILs/24 blocking,
  messages asserted); harness pin "failures: 16 blocking: 24"; NEW
  `test_render_refuses_but_documentation_still_renders` (render() raises
  naming both kinds and both verdict words; render_documentation still
  writes — the gate split, live).
- `test_step_stool_e2e.py` — 4 station-not-face FAILs asserted; not ok.
- `test_sit_reach_frame_e2e.py` / `test_trebuchet_e2e.py` — honest new
  states (above), each asserted specifically so unrelated regressions can't
  hide under the expected red.
- `test_platform_detail.py` — helper renamed to
  `_assert_no_fail_only_honest_unknowns` ({capacity×3, install_access×2}).
- `test_site_model.py` / `test_site_model_report.py` — site blocking
  {capacity×3, install_access×3} incl. the named rod-vs-rung finding; the
  blocked section lists all six.
- `test_foundation_obligation.py`, `test_doc_build_blocked_detail.py` —
  same widened blocking preconditions.
- `test_inspector_payload.py` — rock anchor unknown families 6 → 5 with the
  positive assertion that Fastener installability LEFT the unknown set.
- `test_cl3_expect_retire.py` — retire closure 8 → 10: retiring a connection
  retires its bolt's two axis verdicts too (asserted by name).
- `test_coverage_matrix.py` — stale "five unanalyzed families" comments
  corrected to six; positive `family_of()` pins for the three install kinds.
- `test_affected_region.py` — floor 45 → 209 (the 164 axis findings, floored
  deliberately — see Soundness fix above).
- Docstrings that became false: checks.py UNKNOWN emitters list,
  coverage.py UNRESOLVED emitters list.

## Inherited review items folded in

- Loader teaching error: authored `exit: through_exit_required` without
  `exit_faces` now refuses at load (the override REPLACES the type default's
  face-set); the checker's runtime half degrades an uncheckable exit to
  honest UNKNOWN naming what is missing (both tested).
- `_resolve_install`'s core-invariant UNKNOWN no longer hard-codes "the type
  declares no default contract" — the reason now distinguishes no-default
  from role-groups-not-covering (connection.py).
- `_fact_line` (spec/report.py) now surfaces `DerivedFact.assumptions` as
  sub-lines — the WHY behind assumption-grade fields (half-length rule, toe
  angle) reaches doc disclosures per guardrail #7.
- Site-level end-to-end install test: `test_site_composed_connections_drive_the_same_checks`.

## Rung-wording decisions

- Shank-mode results carry "(GEOMETRY-PROVEN against modeled geometry)".
- Idealized-axis and declared-void results lead with "Installation method
  represented; <X> not analyzed" (angled shank path / angled tool path /
  recess geometry) — never a bare PASS on a REPRESENTED-rung case.
- Foreign obstruction is verbatim "UNKNOWN — install-order dependent",
  names every blocker and its owning connection(s), and states the reason
  ("before a construction process graph exists (axis 3)").
- Party-ordered-after clearances are PASS with the stage disclosure — a
  deliberate reading of the design's `stage: own_connection` v1 semantics
  (the alternative, FAILing the hanger class's standard technique, would be
  a false alarm the design's own edges can and now do refute).
- The embedment verdict prints the minimum's provenance (`[assumption]`),
  so an assumption-grade FAIL is visibly assumption-grade.

## Residuals / honest gaps

- **Un-owned fastener scope gap**: fasteners placed outside any Connection
  (tree_attachment's lags, trolley's hardware, the trebuchet axle rod) are
  invisible to the axis checks — their docs' family row honestly reads
  UNKNOWN — NOT ANALYZED. Closing it needs connection adoption, not checker
  changes.
- Declared-but-unmodeled conditions stay REPRESENTED: angled axes (until
  angled-placement vocabulary, work order #2), pocket/countersink voids
  (work order #1).
- Tilted-member chord stations carry ≤ one probe radius of error (no
  shipped case; documented at `_Sweep.chords`).
- The angled sweep's cheek-face planes come from the world AABB — exact for
  the axis-aligned members every shipped detail uses, conservative outward
  for a rotated member.
- The epoxy rod's access corridor is the declared envelope from the rod's
  head end — true insertion needs rod-length + envelope clearance (axis-3 /
  richer insertability, P1 territory).
- Axis findings live in the affected-region floor (sound, coarse) until
  their dependency sets are persisted.
- The `-p no:xdist` single-module runs during development used the shared
  persistent solid cache; the final gate is the full `-n auto` suite.

## Performance

- Platform (148 parts, 82 contracted fasteners, 164 findings): warm-cache
  `validate()` 0.53 s without the axes → 8.36 s with (best of 2; the other
  checks hit the persistent verdict cache, the axes deliberately do not).
  Cold-compile platform end-to-end ~10.4 s. Small details: caddy 0.40 s,
  sit_reach_box 0.18 s total validate.
- Why uncached: `_CHECKS_FP` does not cover this module's source; a
  persistent verdict keyed without it would survive edits to the checker.
  Joining the fingerprint (and keying on the full corridor input surface)
  is a later, deliberate step.
- Full suite wall-clock: see Gates (the pre-branch baseline runs 1060 tests;
  this branch adds 31 and the platform-heavy modules pay the per-validate
  delta above).

## Gates

- Import-path verification printed at every run (above).
- New tests: test_install_sweep.py (19) + test_install_axes.py (12), green.
- Full suite from the worktree (`pytest -n auto -q`, venv python, shimmed
  PYTHONPATH, import path verified at run start):
  **1094 passed / 3 skipped / 1 xfailed** in 11:44 wall-clock (8 workers).
  Baseline inherited at 267d91b: 1060/3/1; growth +34 = the 31 new tests
  (test_install_sweep 19 + test_install_axes 12) + 2 parametrized cases of
  test_scripts_spec_rewire's per-test-file no-imperative-load guard over the
  two new modules + the new caddy render-refusal test. An intermediate
  whole-suite run at the core commit (before the re-pins) was
  1027 passed / 33 failed — every failure triaged into the re-pin inventory
  above; none silenced.
