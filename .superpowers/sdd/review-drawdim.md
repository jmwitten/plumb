# DRAWDIM review — sdd/drawdim @ b0f0341 (2 commits off master)

## VERDICT: MERGE-WITH-NITS

One LOW nit (fixable in one line, non-blocking). Every load-bearing claim I attacked held up under independent re-derivation from the compiled model. The station arithmetic is correct, the golden is insertion-only and true of the shipped model, every number on all three sheets traces to a bbox or the compiled namespace, D3's epistemics are honest, and the new guards bind (mutation-proven).

---

## NIT (MERGE-WITH-NITS)

**N1 — LOW — D3 sling length (30in) contradicts the doc's own rigging recipe (34in).**
`scripts/render_trebuchet_views.py` sets `SLING = 30.0` (line 366) and its comments (lines 321, 365) call it "the doc's declared recipe (… ~30in sling)" / "declared ~30in pivot-to-pouch recipe". But the recipe prose in `details/trebuchet.spec.yaml:726` says the sling is **"two 34in lengths of paracord."** The sheet prints a *derived* pouch station from this: `pouch_y = tip_y − SLING = 26.54 − 30 = −3.46` → the caption reads "POUCH starts here on the runway (~3" ahead of the axle)". With the recipe's 34in it would be ~7.5in ahead. So a number on the sheet is inconsistent with the recipe it claims to follow.

Why LOW / non-blocking: it is a hedged ("~3"), banner-labeled *declared-schematic* pointer ("where the pouch starts"), not a fabrication station a builder cuts to, on a sheet explicitly stamped "rigging = declared recipe; kinematics NOT ANALYZED". Fix: set `SLING = 34.0` (or better, single-source it from a namespace/prose value) so the sheet's derived pouch position matches the recipe. This is the only number I found on any sheet that contradicts the spec.

---

## Independent verification by attack line

### 1. STATION ARITHMETIC — VERIFIED CLEAN
Compiled `details/trebuchet.spec.yaml` and read the actual cut-plan lines out of the built doc:
- Arm bore: `center 38.4" from one end (9.6" from the other), on the width centerline` — 38.4 + 9.6 = 48 = crosscut length; cy = board_w/2 = 2.75 → centerline. Radius `0.375"` = bore_arm 0.75/2. ✓
- Uprights: `center 32" from one end (3" from the other), on the width centerline` — 32 + 3 = 35 = upright length; centerline. Radius `0.344"` = bore_up 0.6875/2. ✓

The station is computed entirely in **board-local** coordinates (`cx`, `cy`, `crosscut_length`, `section[0]`), so no world placement/rotation can corrupt it — a rotated part still marks the same tape distances on the bench. mm→inch via `inches()` is correct; centerline tolerance `0.254 mm` = exactly `0.01"` (matches its comment). Both tape distances are printed and the line never asserts *which* end is which — that stays a drawing fact, consistent with the docstring's stated contract.

Off-board omission rule attacked: it fires only for `notch` (bores are always inside the board by construction, so they always print); the boundary is inclusive (`0 ≤ cx ≤ length`, `0 ≤ cy ≤ width`). I could not construct an on-board real cut that wrongly loses its station, nor an off-board center that prints a bogus (negative) distance — the guard omits exactly those.

### 2. GOLDEN HONESTY — VERIFIED INSERTION-ONLY & TRUE OF THE MODEL
`git diff master...HEAD -- tests/baselines/consolidated_doc.textlayer.html`: one changed line, byte-identical prefix, station text **appended** to decks 2 and 3 only. No removed facts, no weakened text.
Confirmed this is TRUE of the shipped platform model — dumped all six deck notch centers:
- deck 0 cy=16.5, deck 1 cy=11.0, deck 4 cy=−5.5, deck 5 cy=−11.0 → **off-board** (correctly omitted).
- deck 2 cy=5.5 (= width), deck 3 cy=0.0 → **on-board** (correctly print `5.5"` / `0"` from one edge).
The trunk-notch center genuinely falls within only the two inner decks' own footprint; the outer decks' centers lie beyond their width. Honest.

### 3. SHEET HONESTY — VERIFIED; every number traced
`bb_in()` reads each part's world `BoundingBox`; every label reads `ns[...]` or a bbox. I recomputed independently and matched the rendered PNGs:
- D1 cross stations from the rear rail end: rear **3.25**, mid **20.25**, front **44.25**; axle plane **30** from rear / **18** from front; CW lane **14**; upright **35**; runway top **2.25**; screw map **2.5 / 2.25 / 1.625**; arm split **38.4 / 9.6** with the dimension arrows landing on the true axle plane (axle rod center Y = 0; arm bbox Y = −38.4…+9.6). D1's "9.6" from the CW end" correctly commits the end (the +9.6 end is the counterweight side) — a legitimate drawing fact that complements the end-agnostic cut-plan line.
- Declared schematic constants: `TIP_CLEAR=2.0` (labeled "assumes the tip pulled to 2" above the runway"); `BK_W/BK_H=9.5` (matches spec "~9.5in dia", line 74, not printed as a dim); and the rigging recipe values `1.5"` hitch, `#10` screw, `~30 deg` bend, `3/8"` bolt, `10 ft` cord, eye lags, `17.5"` hang — each cross-checked against `trebuchet.spec.yaml:724–732` and **consistent**. The one exception is `SLING=30` (N1).
- Legibility: all three PNGs render with readable, non-colliding labels; no truncation that changes meaning.

### 4. D3 EPISTEMICS — VERIFIED HONEST
Cocked pose is arithmetic: `theta = arcsin((axle_h 32 − tip_z 4.25)/long_arm 38.4) = 46.27°`; tip lands `tip_y = 38.4·cos θ = 26.5"` behind the axle, `tip_z = runway_top 2.25 + 2 = 4.25"` up; `cw_clearance = 2.65"` BDC (matches namespace). The trigger note reads "~26.5" behind the axle, ~4.25" up (assumes the tip pulled to 2" above the runway)" — matches the arithmetic and is explicitly hedged as an assumption. Title, both D3 captions, and the two coverage entries all frame it as "derived arithmetic / declared recipe / kinematics NOT ANALYZED." No text overclaims analyzed kinematics.

### 5. GUARDS — VERIFIED REAL (mutation-tested)
- Class-closer `test_material_removing_steps_carry_their_station` and `test_offboard_notch_center_omits_the_station` are present. I **mutation-tested** by stubbing `_station_phrase` to return `""`: the class-closer **fails** ("assert 'from one end' in ...") — it binds, not vacuous.
- e2e `test_prose_truthfulness_guard` new block asserts `"from one end"`, the specific `center 38.4" from one end`, and the three caption phrases ("the build sheet", "operating diagram", "pivot stack") in the **built** doc. It hardcodes the expected 38.4 and caption strings — it does not read its own governing params. The test builds the doc itself and passes.

### 6. REGRESSION — VERIFIED (targeted); full suite pending
- Doc builds clean: `single_detail_report.py details/trebuchet.spec.yaml` → exit 0, 9-view panel, 2.70 MB.
- Targeted tests: `test_fab2_cutlist.py`, `test_trebuchet_e2e.py`, `test_spec_presentation_equiv.py`, `test_review_report.py` → **32 passed**.
- The `_station_phrase` change is compiler-wide but only affects `bore`/`notch` fab notes. The **only** other spec with bore/notch is `armchair_caddy.spec.yaml`; its tests use `startswith("notch:")` and derivation-equality (`payload["fab"] == record.fab_note()`), both robust to an appended station. The **only** text baseline carrying fab-note strings is `consolidated_doc.textlayer.html` (regenerated). No other golden should move.
- Full suite (`pytest -q -x`) now **complete: 1022 passed, 3 skipped, 1 xfailed in 1411.93s (exit 0)**. No regression anywhere in the repo.

### 7. STORES — VERIFIED
- `load_findings_file('reviews/visual/trebuchet-findings.yaml')` loads → ids V1–V5; V5 is well-formed (HIGH, resolution status `fixed-by-revision`).
- `trebuchet-view-coverage.json` is valid JSON. Revised decisions tell the truth: "governing mechanism dims" WHY-NOT→**SHEET** (d1) with a REVISED note that callouts under-carried; "counterweight bucket…" WHY-NOT→**SHEET (schematic)** (d3) preserving the prior "cannot be modeled" truth and adding that D3 draws it dashed/declared; "cocked pose…" WHY-NOT→**SHEET** (d3) as derived arithmetic / NOT ANALYZED; new area "pivot hardware stack order" → **SHEET** (d2). Cosmetic only: the file was reformatted compact→pretty (diff noise, content-preserving) and lost its trailing newline.

---

## Bottom line
Merge after fixing N1 (or accept it knowingly — it is a hedged schematic pointer, not a fab dimension). The compiler-level station work is the load-bearing win and it is correct, guarded, and honest: the arm-bore station that a wrong-end build turns into a 1:4 arm now ships on the cut plan (38.4" / 9.6") and on D1, and the guard fails if it ever regresses.
