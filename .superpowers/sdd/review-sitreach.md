# Adversarial review — SITREACH (commit fc364c5, branch sdd/sitreach)

## VERDICT: MERGE

One MINOR (a prose/mechanism overstatement about *which* guard pins the protocol
constants) and one NIT. Neither blocks: the shipped artifact is geometrically
exact, every new-vocabulary claim matches its mechanism, and the protocol pin is
in fact held — by the e2e test's hardcoded constants, which I verified bites.
Every claim below was reproduced independently (my own probes off the compiled
model, throwaway degenerate specs, a temp-spec drift that I confirmed goes RED).

Reviewed one commit off master @83479b2. Full gate re-run on the tip:
**999 passed, 3 skipped, 1 xfailed** (`.venv/bin/python -m pytest -q`, 22m41s,
exit 0). New suite `tests/test_sit_reach_e2e.py`: 11/11. No regression in the
shared consumers (`test_armchair_caddy_e2e` 16/16, `test_step_stool_e2e` 18/18,
`test_connection` within the green full run).

---

## What I verified, and how (independently)

### Attack B — butt_screwed claim-vs-mechanism: HOLDS
- `transfer_claims` == `{("pull_out", True), ("shear", True)}` and nothing else.
  No `downward_load`, no bearing/`bears_on` class. Verified by reading
  `ButtScrewed.transfer_claims` off the class in my own probe.
- On the four compiled box corners, `kind.edges(conn)` emits only
  `{"fastened_by", "installed_before"}` — **no `bears_on`**; `bearing_pairs(conn)`
  is `[]`. So the box's captured-panel joinery claims *hold-together*, never a
  gravity seat. This is the exact CleatScrewed honesty the docstring cites (the
  caddy D1b lesson), and the code matches the docstring line for line.
- Role enforcement bites: a `butt_screwed(n_screws=2)` fed 1 screw raises
  `ValueError` ("expected 2 hardware item(s) … got 1"); fed a `PlywoodPanel`
  where a screw belongs, raises ("hardware slot 0 must be a StructuralScrew, got
  PlywoodPanel"). Both via `_require_hardware_roles`.
- `fastened_by` direction is `butting -> face_member` (front panel fastened by
  the side), the sensible analogue of CleatScrewed's `cleat -> member`.
- `TransferClaim` positional construction matches the dataclass field order
  (`load_class, transfers, confidence="placeholder", source_type=
  "verified_heuristic", reference`) — honest placeholder confidence for a
  capacity that is explicitly NOT analyzed.

### Attack C — fabrication fold invariant + single-source: HOLDS
- `verify_assembly_fabrication(detail.assembly)` runs clean (no raise) on the
  compiled box.
- `PlywoodPanel.bom_length_mm()` reads `self.fabrication_record().crosscut_length()`
  — the SAME record `_build()` folds its geometry from. I mutated `panel.length`
  in-memory and both the built solid's X-length and `bom_length_mm` moved to the
  new value together (30in → 30in). There is no second stored length to drift;
  single-source is by construction. (The fold invariant is trivially satisfied
  here because `_build` *is* `fold` — that is the intended "holds by construction
  for any component whose `_build` delegates to fold," not a gap.)

### Attack D — protocol metrology: EXACT
Measured off the COMPILED model in my own script (not the test's assertions):
- reach surface `top.zmax` = **12.000000 in** (pin 12).
- foot line: `front.ymin` = **0.000000 mm** (foot face on Y=0) and `top.ymin` =
  **−230.000000 mm = 23.000000 cm = −9.055118 in** forward (pin 23cm; = 23/2.54).
- box body 12.000000 × 12.000000 in.
The derivation `foot_line_offset = foot_line_cm/2.54` is real; the "not rounded
to 9in" claim is true to six decimals.

**Drift goes RED — verified, not trusted (see MINOR-1 for the caveat):**
- Geometry drift: I edited a temp spec to move the front panel off Y=0. The
  in-model dimension check "foot face plane at Y=0" went **FAIL / blocking**,
  `report.ok=False`. Fixed-expected checks bite.
- Param drift: I edited a temp spec `top_surface_h: 12→13`. The e2e guard
  `test_governing_dims_guard` (hardcoded `GOV_TOP_SURFACE_IN=12.0`, measured off
  the compiled model) would fail — I reproduced its assertion: measured 13.000in
  vs `approx(12.0, abs=0.02)` → False. So the protocol pin *is* enforced.

### Attack A — novel-spec generality / check() honesty: HOLDS
Throwaway `PlywoodPanel` configs (not used by the box):
- `check()` fires honestly: non-positive length/width flagged; 2in thickness →
  "thicker than any stocked plywood"; 100×50 and 200×200 → "cannot come out of a
  4x8 sheet"; 96×48 (exact full sheet) → clean; 96×49 (1in over) → flagged.
- Degenerate geometry (zero/negative dim) **raises** (OCCT `Standard_Failure`)
  rather than silently building garbage — and `check()` catches it before build
  anyway. See NIT-1.

### Attack E — prose truthfulness + nesting: HOLDS
- Built the doc to a temp path
  (`scripts/single_detail_report.py … --out <tmp>/doc.html`, 1.47 MB). Grepped
  for `proven stable | stability verified | will not tip | will not slide |
  certified | load-tested | guaranteed safe | structurally sound`: **none**.
  Stability / Support / Structural capacity / Load-path all read
  `UNKNOWN — NOT ANALYZED`.
- Every number in the reader prose matches the model: sides 12×11.25, front/back
  10.5×11.25, top 21.06×12, overhang 9.055in / 23cm, 16 screws, 8 connections.
  The one "9in" in prose is the doc honestly noting the classic DIY plan *rounds*
  to 9in while this build derives 9.055 — not a contradiction.
- Nesting claim ("all five panels in ONE 24×48 project panel") is TRUE. Total
  panel area 759 of 1152 sq in (66%); a concrete packing fits with margin: top
  12×21.06 in one column, the two 11.25-wide sides stacked and the two 11.25-wide
  front/back stacked in the adjacent column, max run ~42in of 48. Comfortable
  even with a 1/8in kerf.

### Attack F — view-coverage: HOLDS (both directions)
- `reviews/visual/sit_reach_box-view-coverage.json` audits 9 candidate areas.
  High-complexity + low-visibility gets a ZOOM (the `butt_screwed` corner
  `z_corner.png`, the 23cm cantilever `z_overhang.png`, hero `g1_iso.png`);
  redundant mirrors (other 3 corners, rail_cap joints, protocol-dim callouts,
  wall-floor bearing, interior embedment) are recorded WHY-NOTs. No
  high-complexity area is left with neither a zoom nor a why-not.
- All named view files exist in `outputs/sit_reach_box/views/`
  (v1–v4 primaries + g1_iso, z_corner, z_overhang).
- I opened the two key zooms. Captions match the renders: `z_corner` shows the
  near side hidden with a butt screw head hanging where that face was and its
  shank in the panel edge (plus a rail_cap top screw); `z_overhang` shows the top
  plate cantilevering past the foot face with empty space beneath. Honest.

### Attack G — store validity: HOLDS
Both `sit_reach_box-findings.yaml` (V1–V4) and `-design-findings.yaml` (DS1–DS4)
load through the real strict loader `detailgen.review.load_findings_file`
(→ `FindingStore`). Findings are framed as suspicions/recommendations that gate
nothing; V3/DS-family `invariant_family: UNKNOWN` maps design/register quality to
no existing invariant, honestly.

### Attack H — regression surface: CLEAN
The `single_detail_report.py` edit is **purely additive** (149 insertions, 0
deletions; only a new `sit_reach_box` key added to `CONSUMERS`, caddy/stool
entries and shared machinery untouched — confirmed by reading the diff for `-`
lines). `materials.py` adds one `plywood` key; `components/__init__.py`'s single
deletion is the `__all__` line rewrite. Caddy + stool e2e (which build their docs
in-test) still green.

### Attack I — test quality: tests bite
- `test_governing_dims_guard` measures the compiled model against hardcoded
  protocol constants — confirmed it catches a 12→13 param drift.
- `test_bom_rows_and_cut_lengths` pins `len(panel_rows)==3` and
  `by_len=={12.0:2, 10.5:2, 21.06:1}` — a lost or mis-lengthed panel row changes
  the map and fails.
- `test_butt_screwed_claims_and_edges` asserts the exact claim set and the
  absence of `bears_on` on all four compiled corners.

---

## Findings

### MINOR-1 — the in-model dimension checks do NOT pin the protocol constants; only the e2e test does, but the doc prose implies both do
The four "GOVERNING …" dimension checks in the spec use self-referential
expecteds: `expected: "$top_surface_h"`, `"$box_width"`, `"$top_len"`, and
`"= -foot_line_offset"` (which tracks `foot_line_cm`). So they assert
*geometry-matches-parameter*, not *parameter-matches-protocol-value*. I verified
this: on a temp spec with `top_surface_h: 13`, `report.ok=True` and the check
named **"GOVERNING reach surface height = 12in"** reports *"actual 13.00 vs
expected 13.00 — PASS"* — a check literally titled "= 12in" passing at 13in.

The real protocol pin lives in the e2e test's hardcoded constants (verified to
bite), and the doc prose does say "…and guarded by the e2e test." But the same
sentence says the pinned dims are "**asserted in the dimension checks**," and the
doc's dimension section is headed "**governing protocol dims asserted in-model**."
That overstates what the in-model checks prove — they prove internal consistency
(and two fixed-expected checks, foot-face Y=0 and walls Z=0, do bite real
geometry drift), not the 12in/23cm values themselves.

Why it's only MINOR: nothing ships wrong (the artifact is exactly 12in/23cm), and
the e2e test genuinely blocks any param drift from merging. But this is precisely
the prose-vs-mechanism gap this project polices, so it is worth closing.

Recommended fix (either):
- (a) soften the header/assumption prose to "geometry-vs-parameter consistency
  asserted in-model; the protocol constants (12in, 23cm) are pinned by the e2e
  guard"; or
- (b) give at least the reach-surface and foot-line checks literal expecteds
  (`expected: "12 in"`, `expected: "-9.0551 in"`) so the in-model check truly
  pins the protocol number and the "= 12in" name becomes self-honest.

### NIT-1 — degenerate PlywoodPanel geometry raises a raw OCCT error
A zero/negative dimension reaches `fold` → `cq…box()` and surfaces as a bare
`Standard_Failure` with an empty message, rather than a friendly diagnostic.
`check()` already flags "non-positive length/width" first, and the spec path
can't produce this (dims derive from positive governing params), so it is not
reachable in practice — purely a robustness nicety if a future caller builds a
panel before calling `check()`.

---

## Bottom line
The two new words are honest: `butt_screwed` claims only pull_out + shear on
named edge grain with no smuggled gravity seat, and `plywood_panel` reads its
BOM length and its geometry from one ProcessRecord. The metrology is exact to six
decimals and derived from the 23cm constant. The doc makes no capacity/stability
overclaim, the nesting claim is geometrically true, view-coverage is audited both
directions with captions that match the renders, and the full gate is green with
no regression. MERGE; address MINOR-1 (a one-line prose softening or two literal
expecteds) either in this branch or as a fast follow.
