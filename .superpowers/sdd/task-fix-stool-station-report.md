# Task FIX-STOOL-STATION report — Phase-0 flavor (c) fix arc

Branch `sdd/fix-stool-station` off master 8d1f1df. The stool's four cleat
screws were the measured station-at-interface flavor: heads MODELED at the
cleat-panel interface (x = ±side_inner_x = ±4.5) instead of on the cleat's
free face, the whole 1.25 in shank inside the panel — drawn unbuildably while
documented buildably. Axis-2 FAILed all four on master (station-not-face).

## Import-path verification (environment)

    cd <worktree> && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen
    export PYTHONPATH="$PWD/.shim"
    python -c "import detailgen; print(detailgen.__file__)"
    # -> <worktree>/.shim/detailgen/__init__.py  (verified before every gate,
    #    printed at the top of every probe run)

## What changed (details/step_stool.spec.yaml only; no checker changes)

1. **Station move (the briefed four lines):** cscrew_p0/p1 `at` X
   `"$side_inner_x"` → `"= side_inner_x - cleat_thk"`; cscrew_m0/m1
   `"= -side_inner_x"` → `"= -(side_inner_x - cleat_thk)"` (sign care: the
   mirror is `-(a-b)`, the -X screws' rotate [["Y",90]] drives -X).
2. **DEVIATION FROM THE BRIEF — screw_len_h 1.25 → 1.75** (flagged to the
   controller mid-arc). The brief expected the station move alone to yield
   "GEOMETRY-PROVEN PASS both axes"; it does NOT. At the buildable station
   the honest bite into the panel is 1.25 − 0.75 = **0.50 in < the 0.62 in
   half-length minimum [assumption]** → 4 honest `install_termination`
   FAILs. Master's "PASS ×4 (cleat screws bite 1.25 ≥ 0.62)" was an
   ARTIFACT of the unbuildable station (the whole shank sat inside the
   panel, so the checker measured a 1.25 in panel bite). A pure four-line
   change leaves the stool truthfully BLOCKED — the opposite of the arc's
   purpose. Resolution: the trebuchet handoff's sanctioned fix menu
   ("longer screws, or an authored embedment override with a defensible
   WHY"); chose the longer screw because it is green on merit rather than
   by waiver, and `screw_len_h` is a DETAILING dim the spec's own
   governing-dims contract declares free to tune.

   **OWNER FLAG — the shopping list changes.** The stool doc was DELIVERED
   2026-07-09; the re-delivered document's buy list moves the four cleat
   screws **4× #10 × 1.25 in → 4× #10 × 1.75 in** (the four up screws stay
   2 in; still two screw rows of 4). If 1.25 in screws were already bought,
   they are the wrong length for the buildable joint. (Display nit, pre-existing repo-wide: the rendered BOM prints screw lengths at one decimal — the row reads 0.19" dia x 1.8" for the 1.75 in screw; queued as an owner nit — quarter-inch-honest screw-length display — for the doc-regen phase.)

## Why the new verdicts are true (hand-probe evidence, +X side; -X mirrors)

- cleat +X spans X [3.750, 4.500]; panel +X spans X [4.500, 6.000].
- Screw solid X [3.627, 5.500]: head cap 3.627–3.750, **head bearing plane
  exactly on the cleat free face x = 3.750**; shank 3.750 → 5.500.
- Termination: 0.75 in through the cleat, **1.00 in bite into the panel ≥
  0.88 in minimum [assumption]** (half of 1.75); tip at 5.50 = **0.50 in
  short of the panel's outer show face (6.00)** — no exit, contract
  exit=none satisfied. Verdict text printed by the checker matches these
  numbers verbatim; rung GEOMETRY-PROVEN.
- Access: 6 in corridor behind the head runs x 3.75 → −2.25 at
  z 3.585–3.915 (r = 0.5 in around cleat_mid_z 3.75): the lower tread's
  underside is at z 4.5 (0.25 in clear above the corridor), the opposite
  cleat's face is at −3.75 and the opposite screws' caps reach only
  −3.627 — the 9.0 in inner span is clear. PASS ×4 GEOMETRY-PROVEN.
- The interference allowlists (screw↔cleat, screw↔panel) are now
  geometrically TRUE rather than vacuous: the shank genuinely crosses both.

## Verdict flips (before → after)

| Finding set | master 8d1f1df | this branch |
|---|---|---|
| cleat screws, install_access | FAIL ×4 "head stationed AT the joint interface … station-not-face" | PASS ×4 "clear tool corridor … (GEOMETRY-PROVEN)" |
| cleat screws, install_termination | PASS ×4 (artifact 1.25" bite) | PASS ×4 "1.00\" bite ≥ 0.88\" minimum [assumption] … no undeclared exit" |
| up screws, both axes | PASS ×8 | PASS ×8 (unchanged) |
| report | not ok (4 blocking) | **ok**, require_clean() passes, Fastener installability family PASS |

## Re-pin inventory

- `tests/test_install_sweep.py` flavor-(c) section:
  `test_stool_cleat_screws_fail_access_station_not_face` →
  `test_stool_clean_both_axes_after_station_move` (pins the full 16-finding
  Counter + the probed verdict texts + require_clean);
  `test_stool_blocks_clean_export` folded into it (clean is now the pin);
  NEW `test_stool_synthetic_interface_station_fails_station_not_face` —
  spec-TEXT mutation back to the interface station reproduces the Phase-0
  defect and pins the station-not-face FAIL ×4 (owner amendment #5: the
  flavor's coverage survives the fix; the caddy-synthetic precedent). Net
  module count unchanged (19).
- `tests/test_step_stool_e2e.py`:
  `test_compiles_and_validates_with_honest_install_failures` →
  `test_compiles_and_validates_clean` (asserts the clean state is the
  PROVEN one: 16 install findings all PASS, GEOMETRY-PROVEN on the cleat
  screws, no failures/blocking); coverage test additionally pins
  `Fastener installability == PASS`; perf test asserts `report.ok`.
- Baselines: NONE regenerated — step_stool appears in no shared baseline
  (not in detail_counts.json, frozen_truth/, or the consolidated textlayer;
  `regen_baselines.py --check` → "baselines are current"). No sibling-arc
  surface touched (caddy/platform specs, their tests, frozen truth).

## Inherited cosmetic nits (this arc finished first — all four taken)

1. `test_geo_probe_c_nut_zone_obstruction_is_swept`: blocker dims corrected
   `Boulder(2, 22.4, 20)` → `Boulder(22.4, 2.0, 20)` (width→Y, length→X:
   the old dims straddled the bolt axis, x 49.8–72.2; the corrected block
   is the documented radial nut-hugger, x 60–62, y 78.8–101.2) and the
   comment's radial figure corrected to 10–12 mm. Test still passes on the
   intended geometry.
2. `install.py _fmt` clamps negative zero (a knife-edge residual printed
   `-0.00"`); pinned by a new `assert "-0.00" not in term.detail` in the
   CAT-A knife-edge test.
3. `far_face_station` docstring: rotated-member AABB projection now
   documented as ANTI-conservative in presentation (overstates the
   "N short of its far face" margin), matching the cheek-plane residual's
   wording; no shipped shank-mode fastener is rotated.
4. HON-F3 qualified-rung wording ("DECLARED order, not sequence-proven")
   now has a direct string assertion in
   `test_cat_e_party_ordered_after_the_fastener_is_disclosed_not_blocked`.

## Residuals

- The half-length embedment minimum remains ASSUMPTION-grade (printed as
  such in every verdict); 1.00 in face-grain bite is judged only against
  that assumption — withdrawal capacity is still NOT analyzed (ANALYSIS-v1),
  which the spec's own assumptions lines already state.
- The synthetic interface-station mutation keeps screw_len_h 1.75, so its
  axis-1 verdicts differ from the historical Phase-0 state (the 1.75 in
  shank from the interface would also breach the outer show face); the pin
  deliberately asserts only the access station-not-face flavor, which is
  station-driven and length-independent.
- Doc regeneration is downstream (controller, post-merge) — nothing copied
  to the vault or ~/Downloads from this arc.

## What a fresh adversarial reviewer should attack

- Re-derive the probe numbers independently (cleat/panel spans, head plane,
  corridor extents) from the spec's value language rather than my probe.
- The screw-length deviation: is 1.75 in the right member of the fix menu,
  or should the owner prefer an authored embedment override keeping the
  1.25 in screw (common cleat practice) with a defensible WHY?
- The synthetic mutation's blast radius: confirm asserting only axis-2
  there is honest given the length-coupled axis-1 difference noted above.
- Whether `require_clean()` passing now hides any non-install family that
  was previously masked by the red state (the e2e asserts the full
  16-finding install Counter and the coverage families to prevent this).

## Gates

- Import path verified into the worktree at every run (recipe above).
- `pytest tests/test_install_axes.py` — 20 passed (nits round).
- `pytest tests/test_step_stool_e2e.py tests/test_install_sweep.py` —
  27 passed.
- `regen_baselines.py --check` — baselines are current.
- Full suite (`pytest -n auto -q`, venv python, shimmed PYTHONPATH):
  see final section below (run at branch tip).
