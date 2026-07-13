# Adversarial review — SITFRAME (commit acc83ab, branch sdd/sitframe)

**VERDICT: FIX-FIRST**

One substantive defect: the reader-facing build document and the spec's own
connection assumptions claim the rail-to-leg cleat joint is **"FACE grain both
sides,"** but the compiled geometry shows the joint is rail **face grain** against
leg **narrow-edge grain** (edge grain, not face grain). Every other claim in the
change — metrology, foot-plane coplanarity, the one-stud contract, the honest
NOT-ANALYZED verdicts, joint geometry, no-new-vocabulary, view captions,
regression — was independently verified and holds. The defect is a substrate-
truthfulness error with no structural consequence (both faces are long grain, same
withdrawal class), but it is exactly the class of claim this project polices, it is
repeated in three places, and it ships in the document a builder reads. Fix the
wording, then merge.

All probes run against the compiled model with `.venv/bin/python`; mutations run on
throwaway copies of the spec; regression built against committed siblings.

---

## MAJOR-1 — the cleat joint is FACE-to-EDGE, not "face grain both sides"

**Claim (three places, all reader- or spec-facing):**
- `details/sit_reach_frame.spec.yaml`, cleat connection `assumptions`: *"Screws
  bite the leg's FACE grain through the rail."*
- `scripts/single_detail_report.py` SITFRAME narrative: *"cleat_screwed to its
  front and back leg (2 screws per corner, **FACE grain both sides**)."*
- SITFRAME z_rail caption (rendered into the doc): *"the rail cleat_screwed flat
  to **both legs' FACE grain**."*

**What the geometry actually is** (probe off the compiled model, inches):

```
LEG front+X  x[2.50,6.00](3.50)  y[0.00,1.50](1.50)  z[0.00,11.25](11.25)  # length runs Z
RAIL +X      x[1.00,2.50](1.50)  y[0.00,12.00](12.0) z[7.75,11.25](3.50)   # length runs Y

Contact plane at x=2.5 (leg inner face / rail outer face):
  Leg mating face spans Y=1.50 x Z=11.25  -> the leg's NARROW EDGE (1.5in) = EDGE grain
  Rail mating face spans Y=12.0 x Z=3.50  -> the rail's WIDE FACE (3.5in) = FACE grain
```

The screw axis is +X; it enters the leg through the leg's **narrow (1.5in) edge**,
not its wide (3.5in) face. The leg's wide faces are at y=0 / y=1.5 — and one of
them (y=0) is deliberately the footplate face pressed by the sole. The footplate
orientation (wide face forward) **forces** the narrow edge inward, so the cleat
joint cannot be face-to-face; it is structurally required to land on edge grain.
The design never acknowledges this and instead asserts "face grain both sides."

**Why this matters here specifically.** This project distinguishes end / edge /
face grain with intent — the same commit boasts "rail_cap_screwed finally gets its
true END-grain substrate" and the spec header contrasts "the ply box's edge-grain
caveat." The `CleatScrewed` type's baked `transfer_claims` text ("FACE grain both
sides") was honest for its original consumer (the caddy, where the side board's
inner face is a wide panel face); reused on a 2x4 leg, that generic claim becomes
false. So the review's own directive — "verify the rail-to-leg joint geometry
really is face-to-face long grain" and "check every connection's assumptions
strings for substrate truthfulness" — fails: it is face-to-**edge** long grain.

**Scope note (why MAJOR, not BLOCKER).** No structural or safety consequence:
edge grain and face grain are both side/long grain, and NDS withdrawal does not
distinguish them — the screw is perpendicular to the fibers either way, far
stronger than the end grain this joint replaces. Capacity is `NOT ANALYZED`
regardless. The transfer claims (`pull_out`, `shear`) hold. This is a
precision/honesty defect, and the fix is descriptive: change "FACE grain" to
"edge grain" (or "long grain both sides — face on the rail, edge on the leg;
strong withdrawal, unlike end grain") in the spec assumptions, the narrative, and
the caption. Verified reader-facing: the built doc shows "face grain" 3x
(2 substantive + the honest "ply edge grain is not face grain" note).

---

## Everything verified CLEAN (independent evidence)

**1. Metrology identical to the ply box — VERIFIED.** Compiled model:
`top.zmax = 12.000in`, `top.ymin = -9.05512in = -23.000cm`, `top.xlen = 12.000in`,
`top.ylen = 21.055in (= 12 + 23/2.54)`. The in-model dimension checks use LITERAL
expecteds (`"12 in"`, `"= -(23/2.54)"`, `"= 12 + 23/2.54"`), not the `$params`, so
they pin the protocol not the knob. **Mutation A** (temp copy, `top_surface_h`
12→13): `validate()` goes `ok=False`, dimension check RED *"actual 13.00" vs
expected 12.00""*. The e2e `test_governing_dims_guard` reads model zmax and would
fail identically. Guard bites by mechanism.

**2. "Front legs are the footplates" + coplanarity — VERIFIED.** `front leg +X/-X`
and `side rail +X/-X` all report `ymin = 0.000in` (coplanar in the foot plane
Y=0). Front-leg strips run `z[0.000, 11.250]` (floor to plate underside, no
toe-tip gap) and span `x[2.5,6]` / `x[-6,-2.5]`. **Mutation B** (leg_fp y→+1):
validate `ok=False`, dimension check RED *"actual 1.00" vs expected 0.00""*. The
"protocol stance width" description is honest-with-disclosure: centers ±4.25in
(8.5in apart), open 5in center; the narrow-stance limitation ("feet never land
there… add a 1x4 across the legs") is present in the rendered doc's honest-limits
prose and in findings V2/DS2. Not a defect — disclosed.

**3. One-stud contract — VERIFIED.** Fabrication records (the same records the
geometry folds from): four legs `crosscut = 11.250in`, two rails `12.000in` →
69.0in. The guard sums crosscuts + 2in kerf ≤ 96in (71 ≤ 96). **Mutation C**
(box_depth 12→40): 2x4 total = 127.0in > 96 → guard RED. The rendered BOM derives
`2x4 lumber — buy 1× @ 8 ft`; narrative states "one 8-ft 2x4 → 4 legs + 2 rails
(69in used)." Sum ≤ stock length is a sufficient one-stick packing condition for
linear cuts. Guard reads geometry, not hardcoded numbers.

**4a. rail_cap_screwed substrate — VERIFIED HONEST.** The leg is a 2x4 with length
along Z; its top at z=11.25 is a cross-cut = genuine END grain; the cap screw
drives −Z into it. `edges()` emits `bears_on(top→leg)` and the plate underside
(z=11.25) meets the leg top (z=11.25) with footprint overlap — a genuine seat.
This is the word's true substrate, as claimed (unlike the ply box's edge-grain
caveat). Connection edge kinds confirmed: `rail_cap_screwed` → `bears_on` present;
`cleat_screwed` → `fastened_by`, NO `bears_on` (the plate-on-rail seat is a
separately declared validation bearing, never smuggled through the fastener).

**5. Joint geometry / hardware — VERIFIED.** Rail screws span x[0.876, 4.000]:
head proud of the rail inner face (x=1.0) into the frame, through the 1.5in rail
(1.0→2.5), embedding 1.5in into the 3.5in leg (2.5→4.0). Cap screws span
z[10.5, 12.123]: through the 0.75 ply (12.0→11.25) and 0.75 into the leg end grain
(11.25→10.5); centered over each leg (x=4.25, y=0.75/11.25, inside the leg
footprint). `validate()`: 0 failures / 0 blocking; every screw↔wood overlap reports
"expected overlap" (allowlisted), **no unintended collisions**; 12 screws present
across 8 connections (hardware-presence PASS).

**6. Prose truthfulness — VERIFIED.** Rendered doc (temp `--out`): "NOT ANALYZED"
×11; no overclaims from a fixed-string scan (`proven stable`, `will not tip/slide/
rack`, `rigid enough`, `sturdy`, `strong enough`, `load-tested`, `certified` — all
absent). The **RACKING disclosure is reader-facing**, not store-only: *"An open
frame has no panel shear: its racking stiffness comes from eight rail screws and
four cap screws…"* and *"Slide/tip/racking under test loads and structural capacity
are honestly NOT ANALYZED."* "23cm" present. Coverage: Support/Stability,
Load-path, Structural capacity all `UNKNOWN — NOT ANALYZED`; Physical geometry +
Construction completeness PASS.

**7. Views / stores — VERIFIED.** Strict loader `detailgen.review.load_findings_file`
loads both stores (4 visual + 4 design findings). All 7 PNGs present. Read the
images: v2_side (12in surface, 23cm overhang to −Y sitter side), v3_front (two
darker footplate strips at stance width, open center, rail end grain above),
z_rail (+X corners inside, the −X side's screws floating per the disclosed x-ray
convention — matches finding V1), z_foot (full-height strips, plate overhead) —
captions match what the images show. View-coverage table audited both directions
(4 primaries justified; 10 candidate areas each ZOOM or recorded WHY-NOT). (The
z_rail caption carries the same "FACE grain" wording as MAJOR-1.)

**8. Regression — VERIFIED.** `test_step_stool_e2e` + `test_sit_reach_e2e`: 19
passed. `test_armchair_caddy_e2e`: 16 passed. The CONSUMERS edit is purely
additive (one new dict key + new module-level constants); the ply box builds clean
through the shared `single_detail_report.py` (1.47MB, identical headline verdicts).

**9. Test quality — VERIFIED by mutation.** Governing-dims guard (Mut A),
foot-plane coplanarity (Mut B), and one-stud guard (Mut C) each go RED under a
cheap mutation. The no-new-words probe is an equality on
`sorted(kinds) == 4×cleat + 4×rail_cap` — bites if any new word appears. New e2e:
10/10 local (reproduced: 10 passed in 23s).

**10. Lumber rotations — VERIFIED.** The `[Y,-90]` legs and `[Z,90]` rails produce
exactly the intended bounding boxes (legs 3.5×1.5 cross-section standing 11.25 in
Z; rails 12 in Y × 3.5 in Z × 1.5 in X). No placement/fold surprise.

---

## NIT

- **Cap-screw head models 0.123in proud of the reach surface** (`cap screw` zmax =
  12.123in vs plate top 12.000in) while the prose instructs "Countersink the four
  cap screws FLUSH in the slide lane." The GOVERNING reach-surface check measures
  the plate (12.000), so metrology is unaffected; this is the pre-existing screw-
  solid modeling convention (uncountersunk), not a defect. Same convention as the
  prior docs.

---

### Recommended fix (MAJOR-1)
Reword the leg-side substrate in the three reader/spec locations from "FACE grain"
to the truthful description — e.g. "rail face grain to leg **edge** grain (both
long grain — strong withdrawal, unlike the end-grain bite this replaces)." Consider
recording that `CleatScrewed`'s type-level "FACE grain both sides" `transfer_claims`
text is honest only when the member presents a wide face, and is imprecise when
reused on lumber edges (a type-reuse honesty note, sibling to the frame's own
substrate arc). No geometry change required.

---

## Fix-round verdict (commit f063d1b) — CONFIRM · MERGE

The MAJOR-1 fix is verified independently against the committed tree at
**f063d1b** (not the fix summary). It resolves the finding with no new defect.

**(a) The three flagged reader/spec-facing places are fixed** (`git show f063d1b`):
- `details/sit_reach_frame.spec.yaml` — all four cleat `assumptions` now read
  *"Screws pass through the rail's wide FACE and bite the leg's narrow EDGE —
  long grain both sides (unlike end grain)…"*; labels changed to "inner edge
  (screwed, long grain)"; header/rail-screw/connections-block/derived comments
  and the honest-limits prose all now state rail-face-to-leg-edge with the
  footplate-forces-the-edge rationale.
- `scripts/single_detail_report.py` — z_rail caption and narrative[0] corrected
  the same way; the caddy/stool text was correctly left untouched (their joints
  genuinely are face-to-face).
- `tests/test_sit_reach_frame_e2e.py` — both docstrings corrected.

**(b) The reworded claim "long grain both sides" is itself TRUE — attacked and
holds.** Geometry re-probed on the committed tree (byte-identical to before —
the fix touched only comments/labels/prose, no params/placements): the rail's
mating surface is its **wide FACE** (3.5×12, grain along Y) and the leg's is its
**narrow EDGE** (1.5×11.25, grain along Z). The screw axis is +X, perpendicular
to BOTH members' grain → **side/long grain on both sides** (far stronger in
withdrawal than end grain). No overclaim: the new wording asserts exactly the
side-grain reality and keeps capacity `NOT ANALYZED`. "wide FACE" (rail) and
"narrow EDGE" (leg) now match the model.

**(c) The rendered doc from the committed tree carries the correction.** Rebuilt
via the shared script: substantive "face grain" claims = **0**; the only
remaining "face grain" is the honest plywood note *"ply edge grain is not face
grain"* (correct). "long grain both sides" appears in both the caption and
narrative; "narrow edge"/"inner edge" present. The `CleatScrewed` class-level
`transfer_claims` text ("FACE grain both sides") does **NOT** leak into the
reader doc (only 1 total "face grain" hit, the plywood note) — the derivation
log does not render that reason string verbatim, so the R-SUBSTRATE residual is
genuinely a code-level (CL v2) concern, not a shipped-doc concern.

**R-SUBSTRATE residual — agreed, matches what I'd want.** The real structural
fix is exactly as filed: `CleatScrewed`'s substrate should become a
per-connection DECLARED fact the claims read, not a class-baked "FACE grain
both sides" that is honest for the caddy/stool but generic-false on a lumber
edge. Correctly scoped to CL v2; the prose fix is the right move for this branch.

**Regression:** frame e2e 10/10 on f063d1b (reproduced, 13.6s). Geometry
unchanged, so the metrology/coplanarity/one-stud/vocabulary verifications above
still hold verbatim.

The NIT (cap-screw head modeled 0.123in proud vs "countersink flush") is
unchanged and remains a non-blocking modeling convention.

**Verdict: CONFIRM — clear to MERGE.**
