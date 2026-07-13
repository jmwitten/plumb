# Task TREB — 3-foot backyard trebuchet: v2 design pass + CL-first build report

Owner request (2026-07-10): "Using my design construction tools, design me a 3'
trebuchet that we can build in one day that can shoot water balloons/tennis
balls." Autonomous session: finalist pick DELEGATED on merit (sitreach
precedent); constraints taken as the owner contract: ~3ft scale, ONE-DAY build,
DUAL payload (water balloons AND tennis balls).

## 1. v2 design pass (design-review-directive v2, all four steps in order)

### Prior-art survey (web research, 2026-07-10)

How this object class is actually built at backyard scale:

- **Hinged-counterweight (HCW) trebuchet** — THE canonical DIY form. A-frames or
  braced posts carrying a horizontal axle ~30in up; a 4:1 arm (published range
  3.75:1–5:1); counterweight HUNG (hinged) from the short arm — a bucket or box
  that stays roughly plumb through the swing; rope sling + pouch on the long
  arm with an open release pin; pull-pin trigger. Published tennis-ball plans
  (medieval.mrugala.net "Tennis Ball Trebuchet Plans") use exactly this: 30in
  axle height, 4:1 arm, counterweight box on a bolt hinge. Storm the Castle's
  free plan is the same form at tabletop scale. Instructables "The Insensible"
  scales it up. Counterweight-to-projectile mass guidance across sources:
  40:1 minimum for real throws, 80:1–133:1 typical for range.
- **Fixed-counterweight trebuchet** — weight rigidly bolted to the short arm.
  Simpler by one hinge; measurably less efficient (the CW arcs instead of
  falling) and it hammers the frame — the classic first-build mistake the
  hobby forums (hurlingforums.com) warn against.
- **Floating-arm trebuchet (FAT)** — axle rides on wheels along rails; the CW
  drops dead-vertical. Highest efficiency of the family, and the precision
  rail/wheel build is emphatically NOT a one-day casual project.
- **Torsion machines (mangonel/onager)** — different class: a rigid cup arm
  slamming a crossbar. The cup's acceleration spike is exactly what bursts a
  water balloon at launch; wrong machine for this payload.

Sources: stormthecastle.com trebuchet plan; medieval.mrugala.net Tennis Ball
Trebuchet Plans; instructables.com "The Insensible"; hurlingforums.com
counterweight/ratio threads; obsessedwoodworking.com backyard trebuchet
writeup.

### Function brief

- **Payloads (the contract):** tennis ball (~2 oz, robust) AND water balloon
  (~4–10 oz, FRAGILE — bursts under acceleration spikes and point loads). The
  water balloon is the binding constraint: it demands a SLING with a broad
  fabric pouch (distributed support, gentle whip) and a TUNABLE counterweight
  (heavy for tennis balls, lighter for balloons).
- **Scale:** "3-foot" — frame stands ~35in; axle at 32in. Sized so the
  counterweight can swing through bottom-dead-center with real clearance.
- **One-day build:** Home Depot stock only (designer-directive north star);
  square cuts only (NO miters — the miter vocabulary is also the open waterfall
  work order, but the FORM avoids them on merit: lapped/gusseted joints are the
  quick-build prior art); every joint screwed or nutted, no glue-wait, no
  welding.
- **Operators:** Joel + kids watching (6 and 4.5) — adults cock and fire; the
  falling-counterweight zone and the launch lane are the two hazards the doc
  must name.
- **Tuning:** counterweight mass, sling length, and release-pin angle are the
  three field knobs; the design must make all three adjustable without rework.
- **Portability:** loose object — carried out to the yard, nothing anchors to
  the ground.

### Whole-form candidates

- **Form A — hinged-counterweight, braced-post frame, bucket CW** (the pick).
  Two braced uprights on a ladder base carry a 5/8in threaded-rod axle at 32in;
  48in arm at 4:1 (38.4in throw / 9.6in CW side); a 2-gallon bucket of play
  sand hung on a rope hinge (0 to ~25 lb — the tuning knob: ~half a bucket for
  water balloons, full for tennis balls); rope sling + canvas pouch; pull-pin
  trigger. Every element cites prior art (survey above).
- **Form B — fixed-counterweight**: sandbag lashed to the short arm. Saves one
  hinge; loses range and shakes the frame; the CW cannot be swapped as fast.
  Prior art treats it as the beginner compromise, not the goal.
- **Form C — floating-arm**: best physics, but rails + rollers + a glide track
  are a multi-day precision build. Fails the one-day contract outright.

### Scorecard + merit pick: **Form A**

Water-balloon survival: A = C (sling launch) >> B (frame shock adds spike);
torsion rejected in survey. Range for a tennis ball: C > A > B — A's HCW at
80:1+ mass ratio throws far beyond a backyard need. One-day/cost: A ≈ B >> C.
Tunability: A best (swap sand mass in the bucket). Prior-art precedent: A is
the published standard at exactly this scale (30in axle, 4:1 arm). Merit-first
check: A wins WITHOUT any expressibility column; the vocabulary gaps it does
hit (below) are work orders, never selectors.

Intent ruling: **FUNCTIONAL-DOMINANT — a working machine.** Visible fasteners,
galvanized hardware and square-cut laps are register-appropriate; the canon
that matters is the MECHANISM's (arm ratio, drop height, sling length, release
geometry), not furniture joinery.

### Design numbers (Form A, resolved)

- Axle height **32in** (GOVERNING); uprights 35in (3in of wood above the bore).
- Arm **48in of 5/4x6 deck board on edge**, ratio **4:1** → 38.4in throw side,
  9.6in CW side (GOVERNING). 5/4x6 on edge puts 5.5in of depth in the swing
  plane (stiff where the throw bends it) at ~1.1 lb/ft (a light arm is a fast
  arm); the bore leaves 2.4in of wood each side.
- Clear width between uprights **14in** (GOVERNING) — a 2-gal bucket (~9.5in
  dia) swings through with margin; gusset knees intrude to 12.5in, still 1.5in
  a side, and the bucket's swing arc (|Y| ≤ ~7 at bucket depth) never reaches
  the gussets' fore-aft stations anyway.
- Counterweight lowest point ≈ 32 − 9.6 − 17.5 (rope hitch + bail + bucket)
  ≈ **4.9in** — 2.65in above the runway surface (2.25in). Derived, disclosed;
  the field note says shorten the hitch if the bucket kisses the deck.
- Axle: **5/8-11 zinc threaded rod, 24in**, nutted to both uprights
  (nut+washer inside and out = the rod also ties the frame tops); arm rides
  the shank between fender-washer thrust faces with jam-nut pairs. Threaded
  rod as a small-treb axle is standard prior art: no welding, and every
  element on it is positionable and captive. Rod bending at the ~16in free
  span under a ~4x dynamic bucket load ≈ 100 lb: M ≈ PL/4 ≈ 400 in·lb over
  S = 0.024 in³ ≈ 17 ksi — inside cheap allthread yield with margin (HAND
  BASIS ONLY — stated in the report, never claimed in the doc; capacity in
  the doc stays NOT ANALYZED).
- Cocked geometry: tip pulled to the runway ⇒ arm ~44° below level; tip
  reaches ~27.7in behind the axle — inside the 30in rear rail run. Sling
  (pivot-to-pouch) ≈ 0.8 × throw arm ≈ 30in; pouch starts on the runway
  under the axle.
- Ballpark performance (HAND estimate for the report only): full bucket
  (~25 lb) on a tennis ball ≈ 190:1 → tens of yards; half bucket (~12 lb) on
  a 8oz water balloon ≈ 25:1 → a gentle 15–30ft lob that survives launch.
  The build doc claims NONE of this; performance is NOT ANALYZED.

## 2. Vocabulary reality (route-by-class, merit-first — gaps are work orders)

- **Bores exist only on `deck_board`** (`apply_feature_cut`), and ONE cut per
  board. Consequence: arm and uprights are 5/4x6 deck boards (each needs
  exactly one axle bore — fits); the counterweight hitch CANNOT be a second
  bore, so it is a rope hitch on the arm end (rigging, prose). WORK ORDERS:
  feature support on `lumber`/`plywood_panel`; multi-feature boards; the
  `drill` fit/stackup rule (#25 — this build's through-hole probe carries
  hand clearances exactly as rock_anchor's does).
- **No pivot/journal ConnectionType.** The arm-on-axle joint is declared
  through the honest escape hatches, trolley-launch precedent: `bonds`
  (tangent adjacency), `contacts` (touch proofs), `expected_overlaps`
  (rod-thread/nut engagement), `through_holes` (rod clears every bore), plus
  bearings for the nut/washer clamp stacks. The build doc says plainly: the
  pivot is NOT a Connection; a rotating-joint word is a work order.
- **No kinematics.** The model is a single declared reference pose: arm LEVEL,
  and HANGING — the arm is placed a full radial clearance (0.0625in) BELOW the
  axle centerline so the bore's top surface sits tangent on the rod's top, the
  way gravity actually parks it. The pose is dimension-checked with literal
  expecteds. Rotation, swing clearance over time, release dynamics: NOT
  ANALYZED (ANALYSIS-v1 material — this build adds the first MECHANISM to
  that acceptance list).
- **No soft goods.** Sling cords, pouch, CW rope, bucket, trigger lanyard are
  real BOM items but not modelable components (the zipline `cable` is a
  straight-line special case, wrong here). They ship as a RIGGING section:
  buy list + step-by-step rigging + tuning + safety, clearly marked
  not-modeled. WORK ORDER: flexible/rigged element vocabulary.
- **No miters needed** — the form is all square cuts (merit, not avoidance:
  the quick-build prior art laps everything).

## 3. CL-first build (details/trebuchet.spec.yaml)

- GOVERNING params: axle_h 32 / arm_len 48 / arm_ratio 4 / clear_w 14, pinned
  by in-model dimension checks with LITERAL expecteds (sitreach MINOR-1
  lesson) and mirrored by tests/test_trebuchet_e2e.py.
- Every placement is DERIVED from the governing four + stock dimensions in
  `derived:` — the arm's hanging drop is `(bore_arm - rod_dia)/2`, so changing
  the fit class moves the modeled pose.
- 13 declared connections (6 butt_screwed cross-member ends, 2 cleat_screwed
  upright laps, 2 cleat_screwed gusset knees, 3 rail_cap_screwed runway
  straps); the pivot deliberately NOT among them (see §2).
- Honest bearing story: rails/uprights/gussets/crosses on the floor; runway on
  the crosses; washer/nut clamp stacks on the uprights; NO ground terminal —
  loose object like the stool and the box.

## 4. DRAWDIM follow-up (owner directive: systematic fixes + numbers ON the drawings)

Trigger: TWO independent naive-builder comprehension reviews (fresh agents
given ONLY the rendered document) — a NEW REVIEW CLASS worth repeating on
every future detail. Both verdicted BUILDABLE-WITH-GUESSES: frame perfect,
rigging guessed, trigger a genuine stall; shared top finding = the arm-bore
station absent from the cut plan (wrong-end bore builds a 1:4 arm).

Systematic fixes (owner: "so that any major issues would have been caught…
better if everything were in the drawing"):
1. COMPILER: `ProcessRecord._station_phrase` — every in-board bore/notch
   cut-plan line now carries its derived STATION (tape distances from BOTH
   stick ends + width position); off-board notch centers honestly omit it.
   Class-closer + off-board unit guards; textlayer golden regenerated
   (insertion-only, one line).
2. SHEETS: three derived 2D drawings in the renderer — D1 dimensioned side
   elevation (stations chained from one datum, screw map, WHICH END IS
   WHICH, launch direction), D2 pivot stack + threading order at modeled
   positions, D3 operating diagram (cocked pose as DECLARED derived
   arithmetic — tip pulled to 2in over the runway — with bucket/sling/
   pouch/trigger as dashed declared schematic; kinematics NOT ANALYZED).
   Every rectangle is a placed part's bbox; every number reads the compiled
   namespace; nothing hand-typed.
3. GUARDS: e2e prose guard asserts the stations and all three sheets ship
   in the document; coverage table revised (three WHY-NOTs upgraded to
   SHEET decisions with the honesty rationale); finding V5 filed
   (fixed-by-revision).

Residual (recorded, not built): a general "every load-bearing number must
appear on a drawing" invariant is Presentation-Graph material; the
naive-builder review is its manual stand-in and should run per detail.
