# Adversarial review — TREB (3-foot backyard trebuchet)

**VERDICT: MERGE-WITH-NITS.**

The branch is honest end-to-end. Geometry is exact and independently reproduced;
the pivot's escape hatches declare only true facts; the connection-type nouns fit
their claims (or disclose the stretch); the tests pin literal contracts; the doc
claims nothing the model doesn't prove; the v2 design pass is merit-first over
real, cited prior art; and the machine will physically work as a hinged-
counterweight trebuchet. The three nits below are documentation-consistency
issues, not engineering defects — none blocks merge, none changes a part.

Nits to fix (in descending order):
1. **MINOR** — cleat_screwed noun-stretch disclosure is on the two upright laps
   but MISSING on the two gusset laps, while DS4's resolution claims "both
   connections carry the disclosure."
2. **MINOR (nit)** — the safety block's "clear the launch lane for 40+ yards" is
   the only concrete distance in a doc that otherwise reads performance NOT
   ANALYZED.
3. **NIT** — a spec comment describes a thrust-washer/rod overlap that is
   (correctly) not declared and does not exist.

---

## Independent verification (commands + outputs)

All commands run from the worktree with the shim PYTHONPATH; never against the
main checkout.

**Compile gate — CLEAN, 57 parts.**
```
$ python -m detailgen.spec details/trebuchet.spec.yaml
DetailSpec: trebuchet  → parts placed: 57 · validation: CLEAN
compression 3.7:1 genuine (4.7:1 raw-inclusive)
```

**E2E — 9/9 pass.** `pytest tests/test_trebuchet_e2e.py -q` → `9 passed`.

**Report-consumer regression (the additive `extra_sections` hook).**
`pytest tests/test_review_report.py tests/test_armchair_caddy_e2e.py -q` →
`22 passed`. Caddy and stool docs rebuild clean; `extra_sections` defaults to
`()` for all four prior consumers (verified in the diff and by build).

**Geometry probed off the compiled model (bounding boxes, inches):**
```
throwing arm   X[-0.500, 0.500] Y[-38.400, 9.600] Z[29.188, 34.688]
axle rod       X[-12.000,12.000] Y[ -0.312, 0.312] Z[31.688, 32.313]
upright +X     X[ 7.000, 8.000]                    Z[ 0.000, 35.000]
upright -X     X[-8.000,-7.000]
runway plate   X[-6.000, 6.000] Y[-16.000,28.500] Z[ 1.500,  2.250]
base rail +X                    Y[-18.000,30.000] Z[ 0.000,  3.500]
cross member rear               Y[ 25.000,28.500]
```
Every governing/derived number checks:
- Axle centerline (31.688+32.313)/2 = **32.0in**. ✓
- Arm split **-38.4 / +9.6** on a 48in stick = exactly 4:1. ✓
- Counterweight lane: upright inner faces at **±7 → 14in clear**. ✓
- Hanging pose: arm centerline **31.9375**, rod centerline 32.0 → drop **0.0625 =
  1/16in** = (bore_arm 0.75 − rod 0.625)/2. The bore top (31.9375+0.375 = 32.3125)
  is tangent to the rod top (32.0+0.3125 = 32.3125) — physically how a loose arm
  parks, and the offset is the honest sign of "hangs," not concentric-faked. ✓
- Runway top **2.25in**; cw_low = 32−9.6−17.5 = **4.9in**; clearance 4.9−2.25 =
  **2.65in**. Matches the spec's derived `cw_clearance` and the doc prose. ✓
- Rear rail run 30in; cocked long-arm tip lands ~27.7in behind the axle (hand
  calc, report-level) — inside the 30in run, near the rear cross (Y-center 26.75)
  where the trigger eyes align. Geometrically the trigger works. ✓

---

## Attack lines — results

**1. Geometry truth — PASS.** Reproduced above. No drift; the through-hole probe
(center 0,0,32; axis X; span 18) spans ±9in, covering both upright bores (±7..8)
and the arm bore (±0.5). Bore feature at local `long_arm` lands the axle bore at
world (0,0), consistent with the through-hole center and the dimension checks.

**2. Pivot honesty — PASS (no false facts).** No ConnectionType touches `arm` or
`axle_rod` (asserted by the e2e). The escape-hatch declarations are all real:
- `bonds`/`contacts` `arm↔axle_rod`: the bore rides tangent on the rod top — a
  genuine touch at Z=32.3125. ✓
- `bonds`/`expected_overlaps` rod↔nuts (8): nut threads engage the rod — real
  designed interpenetration. ✓
- washer↔nut and nut↔nut bonds: jam pairs and thrust washers press together — real
  adjacency at the derived stack stations. ✓
- Thrust washers are **not** in `expected_overlaps` — correct: bore 0.6875 over
  rod 0.625 = 0.03in radial clearance, no overlap, so no false allowlist (and the
  compile would have flagged one). ✓
Nothing rides these declarations as a load-path or capacity claim; the doc says so
explicitly. No claim exceeds what the hatches can carry.

**3. Connection-type fit — PASS with one disclosure gap (MINOR-1).**
- `butt_screwed` (6× cross ends): docstring covers END/EDGE grain generally
  (exemplar is ply, claim class is end/edge). 2x4 end-grain butt fits; each
  connection discloses "screws bite END grain — weaker in withdrawal, NOT
  analyzed." Honest. ✓
- `cleat_screwed` (2× upright→rail, 2× gusset→upright): claims face-grain both
  sides, pull_out+shear, NO gravity seat. Both lap zones are genuine face-to-face
  (upright broad face on rail broad face; ply face on board face). Claims are the
  joint's exact truth. ✓ **But** the noun-stretch disclosure ("cleat_screwed is
  used as a generic face-lap word — a dedicated post-to-rail lap ConnectionType is
  a recorded work order") is present on the two **upright** laps and **absent** on
  the two **gusset** laps (whose only assumption is "Ply face to board face; knee
  bracing capacity NOT analyzed"). DS4's resolution note asserts "both connections
  carry the disclosure in their assumptions" — that overstates coverage. → **MINOR-1.**
- `rail_cap_screwed` (3× runway→cross): claims a gravity seat (bears_on) +
  lateral_push. The seat is real (runway rests on the crosses, proven by three
  declared bearings). The type assumes end-grain screw bite; here the screws enter
  the flat 2x4's broad face (face grain) — i.e. the real substrate is *stronger*
  than the type assumes, so the claim is conservative, not overstated. Honest. ✓

**4. Novel-spec generality — PASS.** `extra_sections` is a keyword defaulting to
`()`, threaded through `build_single_detail_html`/`build_document` and read via
`consumer.get("extra_sections", ())`. The other four consumers pass no such key,
so their output is byte-unchanged (caddy/stool rebuilt clean; 22 report/caddy
tests green). The hook injects the rigging+safety `<section>`s only for TREB.

**5. Test honesty — PASS.** Governing guards use LITERAL constants
(`GOV_AXLE_H_IN=32.0`, `GOV_ARM_LEN_IN=48.0`, `GOV_ARM_RATIO=4.0`,
`GOV_CLEAR_W_IN=14.0`) and `HANG_DROP_IN=(0.75-0.625)/2` computed from literal
stock sizes — never read back from the spec's own params (the sitreach MINOR-1
lesson). `_EXPECTED_STEPS` pins each member's fabrication ops (the three deck
boards carry their one bore; hardware/ground carry none). BOM row assertions are
literal (2x4: 48×2,16×3; 5/4x6: 35×2,48×1; ply: 24×2,44.5×1 with the "12.00 wide"
one-strip nesting; 8 nuts, 6 washers, 1 rod, 30 screws). The pivot test pins the
escape-hatch shape (no connection on arm/rod; bond+contact+through-hole present).
These pin records legitimately; none reads its own governing param, none overfits
in a way that would mask real drift.

**6. Doc truthfulness — PASS with one nit (MINOR-2).** "NOT ANALYZED" ×11,
"UNKNOWN" ×16. Support/Stability, Load-path, Structural capacity all read UNKNOWN —
NOT ANALYZED; kinematics/firing dynamics disclosed as ANALYSIS-v1's first
mechanism. The rigging arithmetic matches the derived model (cw_low 4.9, clearance
2.65, hang 17.5, arm split 38.4/9.6). The buy list matches the DERIVED cut plan:
1× 10ft 5/4x6 (35+35+48 = 118 ≤ 120), 2× 8ft 2x4 (2×48 rails + 3×16 crosses = 144
≤ 192, nests in two boards), one 24×48 ply panel ripped to two 12in strips (runway
44.5 on one, two 24in knees on the other). The mass ratios (190:1, 25:1) are
tuning ratios / arithmetic, not range claims. **MINOR-2:** the safety block says
"keep the launch lane clear for 40+ yards on a full bucket" — the single concrete
distance in the doc. It is framed as a clearance buffer (erring toward *more*
clearance = the safe direction), but reads as an implied range capability while
everything else is NOT ANALYZED. Soften to "clear a wide margin downrange," or
mark it explicitly as a conservative guess.

**7. Design-pass compliance — PASS.** All four steps present and in order: prior-
art survey with named sources (stormthecastle, medieval.mrugala.net tennis-ball
plans at 30in axle / 4:1, instructables, hurlingforums, obsessedwoodworking);
function brief (water balloon as the binding fragile-payload constraint);
whole-form candidates A/B/C (hinged-CW / fixed-CW / floating-arm) with a scorecard;
merit pick stated to win "WITHOUT any expressibility column." Vocabulary gaps are
recorded as work orders, never as selectors. The CW rope-hitch's partly-vocabulary-
driven nature (one bore per board) is disclosed consistently across the spec
header, the doc's honest-limits + rigging prose, and the task report. No post-hoc
rationalization.

**8. Physics sanity of the design — PASS (will work when built).** 4:1 arm on a
32in axle; the ~25lb bucket at bottom-dead-center reaches 4.9in, clearing the
2.25in runway by 2.65in; the 9.5in bucket clears the 14in lane (2.25in/side) and
never reaches the gusset X-station (bucket half-width 4.75 < gusset inner 6.25);
cocked long-arm tip ~27.7in behind the axle sits inside the 30in rear run and near
the rear cross where the trigger eyes align. Nothing about the geometry prevents
the machine from throwing. Rod-bending / lap-shock / racking capacity are hand-
sized in the task report only and correctly claimed as NOT ANALYZED in the doc.

**9. View coverage — PASS (audited both directions).** High-complexity/low-
visibility areas get zooms: the pivot occlusion is solved by role-splitting into
z_pivot (arm hidden → rod + clamp stacks read) and z_arm (uprights hidden → arm on
the shank between thrust stacks) — the V1 fix, confirmed in the rendered PNGs. The
base corner cluster (upright lap + gusset knee + cross butt) reads in z_lap.
Over-generation is guarded the other way: mirror -X corner, governing dims (on the
side callouts), runway joints, rigging (unmodelable), kinematics (single pose),
and empty bores (rod-occupied) all carry recorded why-nots. The renders match the
model I probed (side elevation shows axle ~812mm, mast ~890mm, runway ~57mm, 4:1
split). No gap and no redundant zoom.

---

## Findings (numbered; severity)

1. **MINOR** — cleat_screwed noun-stretch disclosure missing on the two gusset→
   upright connections (present on the two upright→rail ones); DS4's resolution
   claims "both connections carry the disclosure." *Fix:* add the noun-stretch
   line to the gusset connections' `assumptions`, OR, if a plywood gusset knee is
   judged a legitimate cleat/gusset rather than a stretch, narrow DS4's finding to
   the upright laps only. Either restores spec↔design-store consistency. (No false
   engineering claim — the face-grain/pull_out/shear/no-seat claims are true for
   the gusset too.)
2. **MINOR (nit)** — doc operating-safety block: "keep the launch lane clear for
   40+ yards on a full bucket" is the only concrete distance and reads as an
   implied range while capacity/kinematics are NOT ANALYZED throughout. *Fix:*
   soften to a non-numeric wide margin, or explicitly tag it a conservative guess.
3. **NIT** — spec comment above `expected_overlaps` ("each thrust washer's loose
   bore laps the rod's exaggerated display threads") describes an overlap that is
   correctly NOT declared and does not exist (0.03in radial clearance). Harmless
   stale prose; trim it so the comment matches the (correct) declarations.

No MAJOR findings. No blocking findings.
