# Task SITREACH — sit-and-reach test box: v2 design pass + CL-first build report

Owner request (2026-07-10): "design me a sit and reach box, like for fitness."
Owner decisions: adult user; OFFICIAL-SPEC fidelity; finalist pick DELEGATED to the
controller on merit; deliver the finished build document.

## 1. v2 design pass (design-review-directive v2, all four steps in order)

### Prior-art survey (web research, 2026-07-10)
- **Official protocol geometry:** box height 12in (30.5cm) universal. Foot-line
  offset differs BY PROTOCOL: President's Challenge / FitnessGram **23cm (9in)** at
  the foot line; Eurofit 15cm; NHL combine 10in; Navy PRT/traditional zero-at-feet
  (negative scores). Protocol: shoes off, legs extended, hands stacked palms-down,
  reach held 1-2s.
- **Classic DIY spec** (topendsports.com/testing/sit-and-reach-box.htm): 3/4in
  plywood, five panels — 2x side 12x12, front/back 12x10, top 12x21 (9in overhang
  toward the sitter = the foot line lands at ~23cm), glue + screws, two coats
  poly, 1cm gradations, optional 1x3in handle hole in the top.
- **Commercial** (Baseline Sit n' Reach, ~$150-200): powder-coated steel
  ~21x12x13in, built-in footplate, sliding max-reach indicator that holds until
  reset, dual in/cm scale, adjustable start point.
- Sources: topendsports.com (box construction + test protocol pages), Baseline
  product listings (prohealthcareproducts.com, avacaremedical.com, rehabmart.com).

### Function brief
- **User:** one adult. Heels press the front face; box on a hard floor or rug.
- **Function (the contract):** administer the standard test with results
  comparable to published norms → the front (foot) face must sit EXACTLY at the
  23cm mark of a top-mounted scale; reach surface at 12in.
- **Loads (honest):** horizontal heel push on the foot face (est. 10-30 lbf,
  braced in normal use by the sitter's own body); downward hand pressure on the
  23cm overhang (est. <=10 lbf); occasional carry. NOT a step stool — no standing
  load claimed.
- **Reach surface:** smooth and CONTINUOUS from sitter edge past the foot line
  (it is the fingertip slide lane).
- **Max-reach indicator:** loose accessory; NOT modeled (no captive-slide
  vocabulary; the classic protocol works with any loose block). DS3.
- **Scale:** a FINISHING step, not geometry: cm gradations from 0 at the top
  plate's sitter edge; the geometry puts the foot face at 23.0cm; verify after
  assembly.
- **Economics (designer-directive north star):** Home Depot only, minimal cuts —
  one 3/4in 24x48in sanded-ply project panel covers all five panels.

### Whole-form candidates
- **Form A — classic five-panel open-bottom box** (prior-art standard). All butt
  joints, ~5 cuts from one project panel, exactly the geometry every norm assumes.
- **Form B — Baseline-style**: widened footplate + captive slider on rails. Nicer
  UX; no fidelity gain; the captive slide + track need vocabulary that does not
  exist (groove FEATURE, sliding-fit connection) — which may only SEQUENCE, never
  select (merit-first); loses on cost/cuts with no protocol gain.
- **Form C — closed six-panel box** (adds a bottom): stiffer + storage, but +1
  panel and weight for no fidelity gain; the classic spec omits it; heel-push
  bracing comes from the sitter, not box mass.

### Scorecard + merit pick: **Form A**
Fidelity: A = C > B(equal). Cost/cuts: A best. Function-brief loads: all three
adequate (none proven — ANALYSIS-v1). Prior-art precedent: A is the published
standard. Merit-first check: A wins WITHOUT the expressibility column; B's
vocabulary gaps are recorded as work orders (DS3), not selectors.

Two deliberate departures from the prior-art plan, both metrology-motivated (DS1):
1. The overhang is DERIVED from the protocol constant (23cm / 2.54 = 9.055in),
   not rounded to 9in — a 1.4mm foot-line correction.
2. The classic top handle slot is REJECTED — the whole top is the slide lane (an
   excellent adult reach passes 40cm of the 53cm surface); the box is light
   enough to carry by the overhang. A slot would also need an edge-slot FEATURE
   verb that does not exist (noted, not the reason).

Intent ruling: **FUNCTIONAL-DOMINANT — a measurement instrument.** Protocol
fidelity + unbroken reach surface are the canon; visible countersunk fasteners
are register-appropriate.

## 2. CL-first build (details/sit_reach_box.spec.yaml)

- **Derivation win:** four governing params (12in height, 23cm foot line, 12in
  depth, 12in width) drive every placement, the top-plate length (21.055in), the
  panel heights (11.25in) and widths (10.5in) via `derived:`. In-model dimension
  checks assert the protocol geometry; the e2e governing-dims guard measures the
  COMPILED model (both halves of the foot line: front face AT Y=0 and sitter edge
  AT -23cm).
- **MOUNT relations:** NOT used (stool residual R1 forms — in-plane offsets);
  placement is `raw`. FEATURE verbs: none honest here.
- **NEW MODEL VOCABULARY (route-by-class; both a normal implementation task):**
  - `plywood_panel` component (src/components/sheet.py) — sheet-goods panel,
    Lumber-contract, fold-derived geometry, BOM label carries the strip width.
    HONEST INTERIM: stock = "ripped ply strip <W>" (no rip step / sheet form in
    the process vocabulary — recorded work order); sheet nesting is disclosed
    prose, never a derived fact. Guarded by
    test_panel_stock_is_disclosed_ripped_strip.
  - `butt_screwed` connection (src/assemblies/connection.py) — the screwed box
    corner: face-member screwed into the butting member's PLY EDGE. Claims
    pull_out + shear ONLY, names the weaker EDGE-grain substrate, emits NO
    bears_on (no gravity seat smuggled through a fastener — the caddy D1b
    lesson; CleatScrewed could NOT be reused because its claims name FACE grain
    both sides). Guarded by test_butt_screwed_claims_and_edges.
- **Joinery:** 4x rail_cap_screwed (top plate down into the four walls' top ply
  edges, 8 screws) + 4x butt_screwed (box corners, 8 screws). Bearings: four
  walls flat on the floor (open bottom, prior art). No `ground:` terminal —
  loose object.
- **Materials:** new `plywood` material key (core/materials.py).

## 3. Verdict + honest residuals (CL v2 / ANALYSIS-v1 requirements data)

Suite state: 11/11 on tests/test_sit_reach_e2e.py; full-suite gate recorded in the
merge commit. Coverage: Physical geometry + Construction completeness PASS; all
other families UNKNOWN — NOT ANALYZED.

Residuals (all disclosed in the doc; none silent):
- **R1 (shared with stool):** in-plane-offset placement forms — all raw.
- **R-SHEET (new):** no rip step / sheet-stock form → no derived nesting diagram;
  panels billed as ripped strips with the one-project-panel plan as prose.
- **R-SLIDE (new, DS3):** captive slider = groove FEATURE verb + sliding-fit
  connection type; loose block serves the protocol meanwhile.
- **R-GLUE (shared with waterfall #22, DS4):** adhesive is not a declarable
  connection; glue-every-joint rides as a fabrication note.
- **ANALYSIS-v1 acceptance material:** slide-under-heel-push and
  tip-under-overhang-pressure join the stool tip-over / caddy rock-stability /
  pier capacity list.

## 4. Directives run
- design-review v2: this document §1 (survey w/ web research, function brief,
  whole-form candidates, scored pick). Intent ruling filed in
  reviews/visual/sit_reach_box-design-findings.yaml (DS1-DS4).
- view-coverage: reviews/visual/sit_reach_box-view-coverage.json (4 primaries,
  3 zooms, 6 recorded why-nots).
- visual review BY LOOKING: reviews/visual/sit_reach_box-findings.yaml (V1-V4;
  V1 corner-occlusion and V2 floor-dominance fixed-by-revision pre-merge).
- vocabulary-gap: two words ADDED (§2); three gaps recorded as work orders,
  none used to select the design.

---

# APPENDIX — Task SITFRAME: the 2x4 FRAME variant (2026-07-10, same session)

Owner request: "design one with a plywood panel at the top, but uses 2x4 for the
rest of it? I don't have a lot of plywood." Carried-over decisions: adult,
OFFICIAL-SPEC metrology, pick delegated, deliver doc.

## Design pass (v2, compressed — survey + brief carry over from SITREACH §1-2)
The constraint bites exactly one part-class decision: sheet stock is genuinely
needed only for the scale/slide surface. Candidates for the frame beneath:
- **FRAME-A "legs are the footplates"** (PICKED): four 2x4 legs, front pair
  stood FLAT to the foot plane = two full-height 3.5in bearing strips at
  protocol stance width (no toe-tip gap — better than the ply box's 10.5in
  face); two full-depth side rails cleat_screwed against the legs' inner
  EDGES (rail wide face to leg narrow edge — long grain both sides;
  review-sitframe MAJOR-1 corrected the original 'face grain both sides'
  wording), end grain flush in the foot plane; ply top caps the legs. ONE 8-ft stud
  (69in used). All joints honest in EXISTING vocabulary — rail_cap_screwed
  finally gets its true END-grain substrate.
- **FRAME-B stacked solid walls** (log-cabin flats): continuous face but ~2x
  the lumber, heavier, and every horizontal course is a new joint plane.
- **FRAME-C minimal crossbar frame**: least material but the foot bearing
  degenerates to one rail — protocol fidelity loss.
Merit: A wins on material (1 stud), foot bearing quality (full height at
stance width), and joint honesty; expressibility scored NOTHING (A also wins
without that column; no new vocabulary was needed or added).

New disclosed assumption (DS2/V2): stance width is baked into the structure —
strips centered ~8.5in apart cover the protocol stance; 1x4-across-the-legs
named as the narrow-stance revision. New unanalyzed load class (DS3): frame
RACKING (no panel shear) — ANALYSIS-v1 material; the ply-box/frame pair filed
as stiffness-comparison acceptance material.

## Build
details/sit_reach_frame.spec.yaml — 7 sticks + 12 screws, 8 connections
(4 rail_cap end-grain, 4 cleat face-grain), 6 bearings (4 leg-floor, 2
plate-rail). Same literal-expected protocol checks (MINOR-1 discipline) +
frame coplanarity checks (footplate faces + rail end grain at Y=0). e2e adds
the ONE-STUD GUARD (crosscut totals from the fabrication records + kerf must
fit 96in) and the no-new-words joinery probe. 10/10 local.

## Fix round (review-sitframe MAJOR-1) — substrate truthfulness
The cleat joint was described as "FACE grain both sides" in the spec
assumptions, the doc narrative and the z_rail caption; the compiled geometry is
rail FACE against leg narrow EDGE (the legs' wide faces are spent on the
front/back planes — the front IS the footplate — so the inward surface is
necessarily the edge). All reader- and spec-facing wording corrected to "long
grain both sides — rail face to leg edge" (no structural consequence: both are
side grain, far stronger in withdrawal than end grain; capacity NOT ANALYZED
regardless). NEW RESIDUAL (R-SUBSTRATE): CleatScrewed's class-level
transfer_claims text bakes "FACE grain both sides" — honest for its caddy/stool
consumers, generic-false here; substrate should become a per-connection
DECLARED fact the claims read (CL v2 material, filed with the stool residuals).
