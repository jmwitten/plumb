#!/usr/bin/env python3
"""Single-detail HTML build document — the reader-facing document for ONE detail.

The caddy smoke flow ends here: `validation_report.md` + PNGs is the machine
layer; THIS is the same kind of reader-facing HTML build document the four-detail
zipline site gets, for a standalone detail. It REUSES the consolidated report's
panel / coverage / BOM / cut-plan / headline / findings / 3D-viewer machinery —
no parallel implementation — by importing `consolidated_report` as a module and
assembling a one-panel sheet instead of the four-panel site. The caddy is the
first consumer; any spec detail can be the next.

Renders: this environment has no Blender/GPU path, so the panel's still images are
the matplotlib rasterizations from `render_caddy_views.py` (the same geometry the
GLB carries). The interactive "Explore in 3D" GLB viewer is exported by the same
CadQuery path the consolidated report uses (`web_glb_b64`) and works regardless.

Usage:  python scripts/single_detail_report.py [--out PATH] [--preview]
"""

from __future__ import annotations

import argparse
import html as _html
import json
import shutil
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
import consolidated_report as CR  # the machinery we REUSE (never edit here)

from detailgen.spec.compiler import compile_spec_file
from detailgen.core.cutplan import pack
from detailgen.rendering.part_labels import part_labels
from detailgen.rendering.web_viewer import (
    build_viewer_payload, vendor_js, viewer_css, viewer_js)
from detailgen.review import (
    find_detail_store, load_findings_file, render_visual_review_block_html)
from detailgen.validation.coverage import coverage_matrix, render_headline_line

CADDY_SPEC = _REPO / "details" / "armchair_caddy.spec.yaml"
#: Per-detail stores are DISCOVERED off this directory by the naming convention
#: (task VISREVSTORES); the caddy names itself "caddy" instead of hand-building
#: ``reviews/visual/caddy-findings.yaml`` / ``caddy-design-findings.yaml`` paths.
REVIEWS_DIR = _REPO / "reviews" / "visual"
CADDY_STORE = find_detail_store(REVIEWS_DIR, "caddy", "visual")
VIEWS_DIR = _REPO / "outputs" / "armchair_caddy" / "views"
DEFAULT_OUT = _REPO / "outputs" / "armchair_caddy" / "armchair_caddy_build_document.html"

TITLE = "Armchair Coffee Caddy — Model-Backed Build Document"

# Caddy-specific text passed into the reused (parametrized) site builders so the
# reader-facing document carries the CADDY's identity, not the zipline's (F1-F4).
CADDY_BUY_LEDE = (
    "Everything modeled to build the caddy: three matching 3/4-inch hardwood "
    "panels and four 3/8-inch hardwood corner-key dowels. Wood glue, finish, "
    "abrasives, and optional protective padding are shop consumables rather "
    "than geometry/BOM rows. Bring the intended cup and chair as fit templates. "
    "The sofa arm and upholstery are existing context, not bought.")

CADDY_FOOTER = {
    "byline": "Witten Dacha &middot; Armchair Coffee Caddy",
    "tagline": ("Drawings &amp; numbers generated from ONE parametric model "
                "&mdash; verdict by invariant family in the coverage matrix above"),
    "regen_cmd": ".venv/bin/python scripts/single_detail_report.py "
                 "details/armchair_caddy.spec.yaml",
    "render_note": "renders: matplotlib offscreen (no Blender in this environment)",
}

# The caddy's document header (unchanged from the original hardcoded _title_block).
CADDY_TITLE_BLOCK = {
    "eyebrow": "Furniture &middot; Weekend Build",
    "h1": "Armchair Coffee Caddy",
    "lede": ("A removable three-panel hardwood sleeve with dowel-reinforced miter "
             "corners. It fastens to nothing on the sofa and lifts straight off. "
             "Every drawing and number below comes from one validated parametric model."),
    "scale": "Rendered to scale; verify on your arm",
    "stock": ("3/4in hardwood panels + four 3/8in hardwood dowels + wood glue + "
              "intended cup and chair (fit templates)"),
}

# F4 (CLOSED by CL-2): the top board's cup hole is now a `bore` FEATURE that
# carries its OWN name through fabrication, so the cut note reads "cup hole bored
# clean through the thickness" — no trunk-clearance wording to explain away. The
# disclosure paragraph the residual once needed is gone; no context caveat is
# emitted, because there is nothing left to caveat.
_CUT_NOTE_CONTEXT = ""

# The caddy's panel config, same shape as consolidated_report.PANELS[*]. The HERO
# is the ARM-HIDDEN iso: the solid context arm occludes the subject in a plain iso
# (visual finding C1), so the document leads with the ghosted view that reads.
PANEL = {
    "letter": "A",
    "title": "Armchair Coffee Caddy",
    "sub": "a three-panel waterfall sleeve with keyed miter corners",
    "views": ["iso", "front", "top", "cup", "joint"],
    "captions": {
        "iso": "The three-panel caddy with the context arm hidden so the continuous waterfall form reads. Two diagonal corner keys reinforce each miter.",
        "front": "Along the arm: the matching side panels directly define the 6.5in clear opening around the modeled 6in arm. The 1/4in nominal gap at each side permits removal; sliding and insertion travel are not analyzed.",
        "top": "Straight down: the centered cup opening and flush wooden key ends on the hardwood show face. There are no rails, brackets, or metal fasteners.",
        "cup": "The full-thickness 3/4in cup bore acts as a locating ring; the intended cup and actual chair remain required fit checks.",
        "joint": "Underside with the arm hidden: each 45-degree corner is glued and crossed by two 3/8in hardwood keys; the dedicated cutaway view exposes their internal axes.",
    },
    "why": (
        "WHY A REINFORCED-MITER WATERFALL?",
        "The three matching panels create the conventional clean waterfall form supported by the retained furniture precedents. The side panels establish fit directly, while two dowels reinforce each glued miter without adding rails or visible metal. Sliding and tip resistance remain unproved.",
    ),
    "narrative": [
        "Three matching {panel_thk:g}in hardwood panels make the shell. The top's long point is {top_long_len:g}in; each side's long point is {side_long_len:g}in, leaving {side_drop:g}in below the top underside. The centered {cup_dia:g}in cup hole is bored through the top.",
        "Both corners are 45-degree glued miters. Two {dowel_dia:g}in hardwood corner keys cross each joint at {dowel_edge_station:g}in from the front and back edges. The four keys finish flush; no rail or metal fastener remains.",
        "All long edges are eased. The sofa arm is existing fit context and carries no structural claim.",
        "Support/stability, insertion travel, sliding resistance, and structural capacity are honestly NOT ANALYZED; see the coverage matrix.",
    ],
    "fieldnotes": [
        ("Panel cuts.", "Use one finished thickness ({panel_thk:g}in) and width ({panel_width:g}in) for all three show parts. Cut the top to a {top_long_len:g}in long point with both ends mitered; cut two sides to a {side_long_len:g}in long point with the joint ends mitered. Preserve the long-point dimensions while fitting the corners."),
        ("Corner-key layout.", "Dry-close each miter with front/back edges flush. Using a doweling jig that holds the {dowel_dia:g}in bore across the 45-degree joint, mark paired centers {dowel_edge_station:g}in from the front and back edges. Drill matched holes, dry-fit both keys, then glue and clamp square."),
        ("Cup hole.", "The {cup_dia:g}in full-thickness bore is centered on the {top_long_len:g}in top and on its width centerline. Confirm the intended cup enters, cannot fall through, clears its handle, and lifts out before cutting."),
        ("Tools and consumables.", "Use a tape, square, pencil, accurate 45-degree cutting setup, doweling jig, drill, clamps, sanding tools, and eye/hearing/dust protection. Select hardwood-compatible glue and a water-resistant finish; follow their labels."),
        ("Dry-fit and use gate.", "Before glue, test the empty shell over the actual arm and adjacent upholstery. Verify the {inner_span:g}in opening, cushion clearance, square bearing, cup fit, and movement in both directions. Do not use a hot drink unless the finished caddy passes a representative stability test."),
    ],
}

# panel view-key -> rendered PNG filename (arm-hidden variants ghost the context).
VIEW_FILES = {
    "iso": "g1_iso.png",
    "front": "v2_front.png",
    "top": "v4_top.png",
    "cup": "z1_cup.png",
    "joint": "g2_joint.png",
}

WEB_GLB_TOL = (0.4, 0.5)   # coarse web-viewer tolerance (same class as the site's)

# Per-detail "consumer" registry: how to document ONE detail. Each entry names the
# spec, its panel config, its rendered-view files, its visual-review store, and a
# callable that ensures the views exist. The caddy is the FIRST consumer; register
# another detail's panel + view renderer here to make it the next — the entry point
# and the reused machinery stay identical.
#: The design-review store (a SIBLING of the visual store), wired into the doc so
#: the document itself discloses the design review (design-review-directive.md).
CADDY_DESIGN_STORE = find_detail_store(REVIEWS_DIR, "caddy", "design")
DESIGN_TITLE = "Design review &mdash; aesthetic / intent register"
DESIGN_LEDE = (
    "The governed precedent-first review compares four genuinely different caddy "
    "architectures against the brief. The selected three-panel reinforced miter is "
    "now implemented: matching hardwood panels, four diagonal hardwood keys, no rails, "
    "and no metal fasteners. These visual findings remain recommendations and honest "
    "unknowns; the separate design-review artifact carries the provenance, comparison, "
    "novelty review, approval fingerprint, and still-pending delivery confirmation.")

# ------------------------------------------------------------------------------
# SECOND consumer: the kids' two-step step stool (task STOOLBUILD, the first
# CL-first detail). Registered ADDITIVELY — its own spec, panel, view files,
# stores, and reader-facing text; the caddy entry and shared machinery are
# unchanged. The caddy-hardcoded header/buy-lede/footer were parametrized above so
# this detail carries its OWN identity, not the caddy's.
# ------------------------------------------------------------------------------
STOOL_SPEC = _REPO / "details" / "step_stool.spec.yaml"
STOOL_STORE = find_detail_store(REVIEWS_DIR, "step_stool", "visual")
STOOL_DESIGN_STORE = find_detail_store(REVIEWS_DIR, "step_stool", "design")
STOOL_VIEWS_DIR = _REPO / "outputs" / "step_stool" / "views"
STOOL_RENDER_SCRIPT = _REPO / "scripts" / "render_stool_views.py"
STOOL_TITLE = "Kids' Two-Step Step Stool — Model-Backed Build Document"

STOOL_TITLE_BLOCK = {
    "eyebrow": "Kids' Furniture &middot; Weekend Build",
    "h1": "Kids' Two-Step Step Stool",
    "lede": ("A two-step stool for a bathroom sink or kitchen counter, sized for a "
             "4.5- and an almost-6-year-old — a 5.5in lower step and a 10.25in upper "
             "step. It rests on the floor and lifts straight off. Every drawing and "
             "number below is generated from one validated parametric 3D model."),
    "scale": "Rendered to scale; verify at your sink",
    "stock": "1x 2x10 (both panels) + 1x 5/4x6 (both treads) + 1x 1x2 (cleats) + 8 screws",
}

STOOL_BUY_LEDE = (
    "Everything to build the stool: one 2x10 cut into the two side panels, one 5/4x6 "
    "cut into the two treads, a short 1x2 for the cleats, and the joint screws. The "
    "floor is existing (listed below), not bought.")

STOOL_FOOTER = {
    "byline": "Witten Dacha &middot; Kids' Two-Step Step Stool",
    "tagline": ("Drawings &amp; numbers generated from ONE parametric model "
                "&mdash; verdict by invariant family in the coverage matrix above"),
    "regen_cmd": ".venv/bin/python scripts/single_detail_report.py "
                 "details/step_stool.spec.yaml",
    "render_note": "renders: matplotlib offscreen (no Blender in this environment)",
}

# The stool's panel config. HERO is the FLOOR-HIDDEN iso: the solid side panels
# occlude the two-step interior in a plain view (visual finding V1), so the
# document leads with the ghosted view where the whole form reads.
STOOL_PANEL = {
    "letter": "A",
    "title": "Kids' Two-Step Step Stool",
    "sub": "two solid side panels, a lower tread on cleats, an upper tread capping the tops",
    "views": ["iso", "front", "side", "cleat", "upper"],
    "captions": {
        "iso": "The two-step stool with the floor hidden (the solid side panels occlude "
               "the interior in a plain view — see the visual-review notes). Two panels "
               "straddle the depth; the lower tread sits between them on cleats; the "
               "upper tread caps the panel tops.",
        "front": "Head-on: the two step surfaces — 5.5in lower (front) and 10.25in upper "
                 "(back) — and the footprint width. The two heights are the pick's "
                 "contract: 5.5in boosts the younger child, 10.25in reaches the sink for both.",
        "side": "From the side: the depth and the front/back tread stagger (the near "
                "panel occludes the interior — see the floor-hidden iso). The footprint "
                "reaches at least as deep as the top is tall (the tip-over ratio).",
        "cleat": "A lower-tread cleat corner, from below/inside: a 1x2 cleat screwed to "
                 "the panel's inner FACE grain, with the lower tread resting on the cleat "
                 "top (a separately declared gravity bearing the cleat does not itself seat).",
        "upper": "An upper-tread corner: the tread caps the panel top and is screwed "
                 "straight DOWN into it (rail_cap_screwed) — the register is functional-"
                 "dominant, so the screws are visible and the joint is chosen to be TRUE.",
    },
    "why": ("WHY TWO STEPS (5.5in + 10.25in)?",
            "A single low step is a boost but a bathroom sink needs about 10in of reach; "
            "the ergonomic reality is that a 4.5-year-old climbs the 5.5in lower step and "
            "stands on the 10.25in upper step to reach the sink, while the almost-6-year-"
            "old reaches from the upper step directly. The wide, deep footprint keeps the "
            "centre of mass low; tip-over itself is NOT analyzed (ANALYSIS-v1)."),
    "narrative": [
        "Two 2x10 side panels (dressed 1.5in x 9.25in) stand on edge and straddle the "
        "11in depth. A 5/4x6 lower tread rides on two 1x2 cleats screwed to the panels' "
        "inner faces at 4.5in; a 5/4x6 upper tread caps the panel tops at 9.25in.",
        "The upper tread is screwed straight down into each panel top (rail_cap_screwed, "
        "2 screws per panel — a real gravity seat plus the lateral grab a child applies). "
        "The lower tread's cleats are screwed to the panel FACE grain (cleat_screwed); "
        "the cleat holds and registers but does not seat — the tread rests on the cleat "
        "tops as a separately declared bearing.",
        "All long edges are eased. The floor is shown for reference — existing context, "
        "not purchased, carrying no structural claim.",
        "Support/Stability and Structural capacity are honestly NOT ANALYZED — a step "
        "stool's headline risk is tip-over, which has no rung here (ANALYSIS-v1). The "
        "governing step heights and footprint ratio are pinned and guarded.",
    ],
    "fieldnotes": [
        ("Governing dims are pinned.", "Step surfaces 5.5in / 10.25in and footprint depth "
         "11in (at least the 10.25in upper height — the tip-over ratio that scored) are "
         "the owner contract, asserted in the model's dimension checks and guarded by the "
         "e2e test. Tread width/thickness and panel/cleat stock are free to tune."),
        ("Honest, visible joinery.", "Functional-dominant register: countersink the eight "
         "#10 structural screws (four capping the upper tread, four through the cleats). "
         "Visible screws are fine here; plugging is a nicety, not a requirement."),
        ("Tip-over is not analyzed.", "The wide, deep footprint and low centre of mass are "
         "the design's stability story, but detailgen has no stability rung — tip-over is "
         "named ANALYSIS-v1 and left UNKNOWN. Verify real-world stability before a child uses it."),
    ],
}

STOOL_VIEW_FILES = {
    "iso": "g1_iso.png",
    "front": "v2_front.png",
    "side": "v3_side.png",
    "cleat": "z_cleat.png",
    "upper": "z_upper.png",
}

STOOL_DESIGN_TITLE = "Design review &mdash; functional / intent register"
STOOL_DESIGN_LEDE = (
    "Design findings judge the construction against the piece's INTENT (this stool is "
    "FUNCTIONAL-DOMINANT — a wet, hard-use kids' object; painted SPF is the norm and the "
    "deciding canon is structural + safety, not show-surface finish). They are "
    "RECOMMENDATIONS against that intent, never invariant verdicts — they gate nothing "
    "and flip nothing; the owner picks the fix. Aesthetic/register quality maps to NO "
    "existing invariant family (the missing family a future Design Exploration Graph "
    "would add), so every family reads UNKNOWN here. DS1 (visible screws appropriate) is "
    "owner-confirmed; DS2 (tip-over) is deferred to ANALYSIS-v1; DS3 (toe-kick) is an "
    "open design + vocabulary residual.")

# THIRD consumer: the sit-and-reach test box (task SITREACH). Registered
# ADDITIVELY — its own spec, panel, view files, stores, and reader-facing text;
# the caddy/stool entries and shared machinery are unchanged.
# ------------------------------------------------------------------------------
SITREACH_SPEC = _REPO / "details" / "sit_reach_box.spec.yaml"
SITREACH_STORE = find_detail_store(REVIEWS_DIR, "sit_reach_box", "visual")
SITREACH_DESIGN_STORE = find_detail_store(REVIEWS_DIR, "sit_reach_box", "design")
SITREACH_VIEWS_DIR = _REPO / "outputs" / "sit_reach_box" / "views"
SITREACH_RENDER_SCRIPT = _REPO / "scripts" / "render_sitreach_views.py"
SITREACH_TITLE = "Sit-and-Reach Test Box — Model-Backed Build Document"

SITREACH_TITLE_BLOCK = {
    "eyebrow": "Fitness Equipment &middot; Weekend Build",
    "h1": "Sit-and-Reach Test Box",
    "lede": ("The standard adult flexibility-testing box: five 3/4in plywood panels, "
             "a 12in reach surface, and a top plate that overhangs the foot face by "
             "exactly 23cm — so a centimeter scale reads 23.0cm at the plane the feet "
             "press (the President's Challenge / FitnessGram convention) and scores "
             "compare to published norms. Every drawing and number below is generated "
             "from one validated parametric 3D model."),
    "scale": "Rendered to scale; verify the 23cm foot line after assembly",
    "stock": "1x 3/4in 24x48in sanded-ply project panel (all five panels) + 16 screws",
}

SITREACH_BUY_LEDE = (
    "Everything to build the box: one 3/4in 24x48in sanded-ply project panel cut into "
    "the five panels (two sides, front, back, and the top plate), and the sixteen "
    "joint screws. Wood glue for every joint is a fabrication note. The floor is "
    "existing (listed below), not bought.")

SITREACH_FOOTER = {
    "byline": "Witten Dacha &middot; Sit-and-Reach Test Box",
    "tagline": ("Drawings &amp; numbers generated from ONE parametric model "
                "&mdash; verdict by invariant family in the coverage matrix above"),
    "regen_cmd": ".venv/bin/python scripts/single_detail_report.py "
                 "details/sit_reach_box.spec.yaml",
    "render_note": "renders: matplotlib offscreen (no Blender in this environment)",
}

# The box's panel config. HERO is the FLOOR-HIDDEN iso: the closed five-panel
# form reads best without the context slab (visual finding V2 resized it; the
# hero drops it entirely).
SITREACH_PANEL = {
    "letter": "A",
    "title": "Sit-and-Reach Test Box",
    "sub": "five 3/4in ply panels: two sides, captured front/back, a capping top with a 23cm overhang",
    "views": ["iso", "side", "front", "corner", "overhang"],
    "captions": {
        "iso": "The five-panel box with the floor hidden: two side panels, the front "
               "(foot) and back panels captured between them, and the top plate capping "
               "the walls — flush at the back, overhanging 23cm toward the sitter.",
        "side": "THE protocol elevation: the reach surface at 12in and the top plate "
                "running 23cm (9.055in) past the foot face toward the sitter. Those two "
                "numbers are the design's contract — they are what makes a score "
                "comparable to published norms.",
        "front": "The foot face: a 12in-wide, 12in-tall plane the tester's soles press, "
                 "flat and coplanar (front panel + side edges, dimension-checked).",
        "corner": "A butt_screwed box corner with the near side panel hidden: the "
                  "screw's head hangs where the side's outside face was, its shank "
                  "biting the front panel's ply edge — the EDGE-grain joint the new "
                  "connection word states honestly. Glue the joint (fabrication note).",
        "overhang": "The cantilever from the sitter's side: 9.055in (23cm) of top plate "
                    "past the foot face with nothing beneath — that absence is the "
                    "design; the sitter's legs go there. Hand pressure lands here during "
                    "a reach; capacity is honestly NOT ANALYZED.",
    },
    "why": ("WHY A 23CM (9.055in) OVERHANG?",
            "Every published sit-and-reach norm assumes the President's Challenge / "
            "FitnessGram box: reach surface at 12in, and the measuring scale's 23cm "
            "graduation exactly at the plane the feet press. Building the overhang AT "
            "23cm means a centimeter scale laid from the top plate's sitter edge hits "
            "that convention with no offset arithmetic — touching your toes reads 23, "
            "and a 40cm reach is the same 40cm the norm tables mean. The classic DIY "
            "plan rounds this to 9in; this build derives it from the protocol constant "
            "instead (a 1.4mm foot-line correction in metrology's favor)."),
    "narrative": [
        "Two 3/4in ply side panels (12in deep x 11.25in tall) stand on edge 10.5in "
        "apart; the front and back panels are captured BETWEEN them, screwed through "
        "the sides' outside faces into the panels' ply edges (butt_screwed, 2 screws "
        "per corner — the box-corner word this build added). The front panel's outside "
        "face is the FOOT FACE.",
        "The top plate (12 x 21.06in) caps all four walls, screwed straight down into "
        "their top ply edges (rail_cap_screwed, 8 screws) — flush at the back, "
        "cantilevering 9.055in (23cm) past the foot face toward the sitter.",
        "Open bottom, like the prior art: the four walls bear directly on the floor. "
        "The box rests by gravity and lifts straight off; nothing fastens to the room.",
        "The measuring scale is a FINISHING step: after assembly and finish coats, lay "
        "a centimeter tape from the top plate's sitter edge — the geometry puts the "
        "foot face at exactly 23.0cm. Slide/tip under test loads and structural "
        "capacity are honestly NOT ANALYZED (ANALYSIS-v1).",
    ],
    "fieldnotes": [
        ("Governing dims are pinned.", "Reach surface 12in, foot line 23cm, box depth "
         "12in and width 12in are the protocol contract, asserted in the model's "
         "dimension checks and guarded by the e2e test. Ply thickness and screw "
         "stations are free to tune."),
        ("Countersink the top screws FLUSH.", "Eight screw heads land on the reach "
         "surface — the fingertip slide lane. Functional register: visible screws are "
         "fine, but they must sit flush or below so the slide is smooth. Fill and sand "
         "if you want a cleaner lane; two coats of poly make it slide-friendly."),
        ("Glue every joint.", "Ply-edge screw withdrawal is the joint's weak axis (the "
         "butt_screwed word says so honestly). Wood glue at every mating face is the "
         "prior-art norm and carries the joint; adhesive is not yet a declarable "
         "connection, so this is a fabrication note (design finding DS4)."),
        ("Slide/tip is not analyzed.", "Heel push and overhang hand-pressure are the "
         "real test loads; detailgen has no stability rung, so they are named "
         "ANALYSIS-v1 material and left UNKNOWN. In normal protocol use the sitter's "
         "own soles brace the foot face — stated as prose, not proven."),
    ],
}

SITREACH_VIEW_FILES = {
    "iso": "g1_iso.png",
    "side": "v2_side.png",
    "front": "v3_front.png",
    "corner": "z_corner.png",
    "overhang": "z_overhang.png",
}

SITREACH_DESIGN_TITLE = "Design review &mdash; functional / intent register"
SITREACH_DESIGN_LEDE = (
    "Design findings judge the construction against the piece's INTENT (this box is "
    "FUNCTIONAL-DOMINANT — a measurement instrument; the deciding canon is protocol "
    "fidelity + an unbroken reach surface, not show-surface finish). They are "
    "RECOMMENDATIONS against that intent, never invariant verdicts — they gate nothing "
    "and flip nothing; the owner picks the fix. Design/register quality maps to NO "
    "existing invariant family, so every family reads UNKNOWN here. DS1 (protocol "
    "fidelity over prior-art conveniences) is adopted as the design contract; DS2 "
    "(slide/tip) is deferred to ANALYSIS-v1; DS3 (captive slider) and DS4 (adhesive "
    "as a declarable connection) are open design + vocabulary residuals.")

# FOURTH consumer: the sit-and-reach box, 2x4 FRAME variant (task SITFRAME).
# Registered ADDITIVELY, same pattern as the previous three.
# ------------------------------------------------------------------------------
SITFRAME_SPEC = _REPO / "details" / "sit_reach_frame.spec.yaml"
SITFRAME_STORE = find_detail_store(REVIEWS_DIR, "sit_reach_frame", "visual")
SITFRAME_DESIGN_STORE = find_detail_store(REVIEWS_DIR, "sit_reach_frame", "design")
SITFRAME_VIEWS_DIR = _REPO / "outputs" / "sit_reach_frame" / "views"
SITFRAME_RENDER_SCRIPT = _REPO / "scripts" / "render_sitframe_views.py"
SITFRAME_TITLE = "Sit-and-Reach Test Box (2x4 Frame) — Model-Backed Build Document"

SITFRAME_TITLE_BLOCK = {
    "eyebrow": "Fitness Equipment &middot; Weekend Build",
    "h1": "Sit-and-Reach Test Box &mdash; 2x4 Frame",
    "lede": ("A sit-and-reach flexibility-testing box built as a 2x4 frame under a "
             "plywood reach surface — plywood only where sheet stock is genuinely "
             "needed. Its calibration geometry is a 12in reach surface and a top plate "
             "overhanging the foot plane by exactly 23cm, so a centimeter scale reads "
             "23.0cm at the plane the feet press. Those dimensions do not establish "
             "equivalence to a named assessment: verify the intended test protocol "
             "before marking the scale or interpreting a score. The two front legs "
             "ARE the footplates. Every drawing and number below is generated from one "
             "validated parametric 3D model."),
    "scale": "Rendered to scale; verify the 23cm foot line after assembly",
    "stock": ("1x 8-ft 2x4 + a 3/4in ply offcut ~12x22in + 12 screws + glue + "
              "adhesive metric rule + loose reach slider"),
}

SITFRAME_BUY_LEDE = (
    "Everything to build the frame variant: one 8-ft 2x4 cut into four 11.25in legs "
    "and two 12in rails, one 3/4in plywood offcut (~12 x 22in) for the top plate, and "
    "twelve joint screws. Add wood glue, finish, abrasives, and an adhesive metric "
    "rule. A required loose accessory — the reach slider specified by the intended "
    "test protocol — is not modeled as attached geometry. The "
    "floor is existing (listed below), not bought.")

SITFRAME_FOOTER = {
    "byline": "Witten Dacha &middot; Sit-and-Reach Test Box (2x4 Frame)",
    "tagline": ("Drawings &amp; numbers generated from ONE parametric model "
                "&mdash; verdict by invariant family in the coverage matrix above"),
    "regen_cmd": ".venv/bin/python scripts/single_detail_report.py "
                 "details/sit_reach_frame.spec.yaml",
    "render_note": "renders: matplotlib offscreen (no Blender in this environment)",
}

SITFRAME_PANEL = {
    "letter": "A",
    "title": "Sit-and-Reach Test Box — 2x4 Frame",
    "sub": "four 2x4 legs (the front pair are the footplates), two full-depth rails, a capping ply top",
    "views": ["iso", "side", "front", "rail", "foot"],
    "captions": {
        "iso": "The frame with the floor hidden: four 2x4 legs stood flat to the "
               "front/back planes, two full-depth side rails flush under the top, and "
               "the ply top plate — flush at the back, overhanging 23cm toward the "
               "sitter. One 8-ft 2x4 yields every stick.",
        "side": "Calibration elevation: the reach surface at 12in and the top plate "
                "running 23cm (9.055in) past the foot plane. This matches the modeled "
                "ply variant; protocol equivalence still requires an operating-manual check.",
        "front": "The foot plane: the two FRONT LEGS are the footplates — full-height "
                 "3.5in bearing strips at stance width, with the rails' end grain "
                 "landing flush between them at the top. The center is open; confirm "
                 "that both feet bear fully on the strips for the intended test.",
        "rail": "The +X rail corners from inside (the whole -X side hidden — its two "
                "screws float in frame, an x-ray convention): the rail runs full depth, "
                "cleat_screwed flat against both legs' inner EDGES — the rail's wide "
                "face to the leg's narrow edge, long grain both sides (the legs' wide "
                "faces are the front/back planes) — and the plate rides the rail top "
                "as a separately declared bearing.",
        "foot": "From the sitter's side, under the overhang: the footplate strips run "
                "floor to plate with no toe-tip gap, and the 23cm cantilever passes "
                "over the sitter's legs. Hand pressure lands on the overhang during a "
                "reach; capacity is honestly NOT ANALYZED.",
    },
    "why": ("WHY A FRAME — AND WHY THE LEGS ARE THE FOOTPLATES",
            "The owner's constraint: little plywood on hand, 2x4s available. Sheet "
            "stock is genuinely needed for exactly ONE part — the scale/slide surface. "
            "Everything else is structure, and structure is what a 2x4 does. In the "
            "modeled stance the tester's feet sit roughly hip-width apart, so the two front "
            "legs, stood flat to the front plane, put full-height 3.5in bearing strips "
            "exactly where the soles press — better toe-tip coverage than the classic "
            "stacked-board face, from one stud. The 23cm/12in metrology is untouched."),
    "narrative": [
        "Four 2x4 legs (11.25in) stand flat to the front and back planes; the front "
        "pair's faces ARE the foot plane (Y=0), dimension-checked coplanar. Two "
        "full-depth 2x4 rails lie flat against the legs' inner edges, flush under the "
        "top, each cleat_screwed to its front and back leg (2 screws per corner — "
        "through the rail's wide FACE into the leg's narrow EDGE, long grain both "
        "sides) — their front end grain lands flush in the foot plane.",
        "The 3/4in ply top plate (12 x 21.06in — the only plywood) caps the four leg "
        "tops, screwed straight down into each leg's END grain (rail_cap_screwed, 4 "
        "screws), and rests on the two rail tops as separately declared bearings. "
        "Flush at the back, cantilevering 9.055in (23cm) past the foot plane.",
        "The frame rests on the floor by gravity and lifts straight off; nothing "
        "fastens to the room. Cut plan: one 8-ft 2x4 -> 4 legs + 2 rails (69in used).",
        "The measuring scale is a FINISHING step: apply an adhesive metric rule from the top "
        "plate's sitter edge — the geometry puts the foot plane at exactly 23.0cm. "
        "Verify the intended test protocol, zero/orientation, and loose slider before "
        "interpreting scores. Slide/tip/racking under test loads and structural "
        "capacity are honestly NOT ANALYZED (ANALYSIS-v1).",
    ],
    "fieldnotes": [
        ("Calibration dims are pinned; verify the intended test protocol.", "Reach "
         "surface 12in, foot line 23cm, body 12x12in: asserted with LITERAL expecteds "
         "in the model's dimension checks and guarded by the e2e test. These dimensions "
         "alone do not certify protocol equivalence."),
        ("Rail screw stations.", "On each 12in rail, mark both screw columns "
         "{front_leg_mid_y:g}in from each rail end. Mark the rows "
         "{rail_screw_drop_u:g}in and {rail_screw_drop_l:g}in below the rail top. "
         "Predrill per the selected 3in #10-class screw maker's chart; the rail-side "
         "heads remain proud by the authored install contract, so keep them out of "
         "contact paths."),
        ("Cap screw stations.", "After both side frames are square and set upright, "
         "place the top flush at the back with its 23cm overhang toward the sitter. "
         "The four cap screws sit {cap_edge_x:g}in in from each side edge, centered "
         "over the front/back legs and {front_leg_mid_y:g}in from the front and back "
         "body edges. Predrill and countersink every head flush with or just below "
         "the reach surface."),
        ("Tools, consumables, and required loose accessory.", "Tools: tape measure, "
         "square, pencil, saw, drill/driver, pilot and countersink bit, clamps, sanding "
         "tools, and eye/hearing/dust protection. Consumables: wood glue, sandpaper, "
         "durable low-friction finish, adhesive metric rule, and applicators. Obtain "
         "the loose reach slider required by the intended test protocol."),
        ("Glue every mating face and hand-check for wobble.", "An open frame has no "
         "panel shear: its racking stiffness comes from eight rail screws and four cap "
         "screws plus whatever glue you add. Glue is the prior-art norm (not yet a "
         "declarable connection — design finding DS4); racking is named ANALYSIS-v1 "
         "material and left UNKNOWN."),
        ("The stance assumption is disclosed.", "The footplate strips (centers ~8.5in "
         "apart) cover the modeled hip-width stance at full height. For a "
         "narrower stance, screw a 1x4 across the legs' faces — a one-board revision, "
         "not modeled."),
        ("Prototype gate — do not use until checked.", "Support/Stability, structural "
         "capacity, slide, tip, and racking remain NOT ANALYZED. Do not use for scored "
         "or unsupervised testing until a qualified person has checked square, wobble, "
         "sliding, tipping, sharp edges, and response under the intended service load. "
         "Then verify the intended test protocol, scale zero/orientation, stance, and "
         "slider instructions before interpreting a score."),
    ],
}

SITFRAME_VIEW_FILES = {
    "iso": "g1_iso.png",
    "side": "v2_side.png",
    "front": "v3_front.png",
    "rail": "z_rail.png",
    "foot": "z_foot.png",
}

SITFRAME_DESIGN_TITLE = "Design review &mdash; functional / intent register"
SITFRAME_DESIGN_LEDE = (
    "Design findings judge the construction against the piece's INTENT (a "
    "FUNCTIONAL-DOMINANT measurement instrument under a MATERIAL CONSTRAINT — plywood "
    "only where sheet stock is genuinely needed). They are RECOMMENDATIONS, never "
    "invariant verdicts; the owner picks the fix. DS1 (constraint honored, metrology "
    "untouched) and DS2 (stance assumption disclosed) are adopted; DS3 (frame racking) "
    "is deferred to ANALYSIS-v1 with the ply-box/frame pair filed as comparison "
    "material; DS4 (adhesive) is the shared open vocabulary residual, third consumer.")

# FIFTH consumer: the 3-foot backyard trebuchet (task TREB).
# Registered ADDITIVELY, same pattern as the previous four.
# ------------------------------------------------------------------------------
TREB_SPEC = _REPO / "details" / "trebuchet.spec.yaml"
TREB_STORE = find_detail_store(REVIEWS_DIR, "trebuchet", "visual")
TREB_DESIGN_STORE = find_detail_store(REVIEWS_DIR, "trebuchet", "design")
TREB_VIEWS_DIR = _REPO / "outputs" / "trebuchet" / "views"
TREB_RENDER_SCRIPT = _REPO / "scripts" / "render_trebuchet_views.py"
TREB_TITLE = "3-Foot Backyard Trebuchet — Model-Backed Build Document"

TREB_TITLE_BLOCK = {
    "eyebrow": "Backyard Siege Engine &middot; One-Day Build",
    "h1": "3-Foot Backyard Trebuchet",
    "lede": ("A one-day, Home-Depot-stock hinged-counterweight trebuchet for water "
             "balloons and tennis balls: braced 5/4x6 uprights on a 2x4 ladder base "
             "carry a 5/8in threaded-rod axle at 32in; a 48in arm rides the rod at "
             "the published 4:1 ratio; a 2-gallon bucket of play sand on a rope hinge "
             "is the tunable counterweight (half a bucket lobs a water balloon, a "
             "full one sends a tennis ball). The sling, pouch and trigger are RIGGING "
             "— specified in full below, deliberately not modeled. Every drawing and "
             "number is generated from one validated parametric 3D model."),
    "scale": "Rendered to scale; modeled in the level-arm reference pose (declared)",
    "stock": "1x 5/4x6x10ft + 2x 2x4x8ft + 1x 3/4in 24x48in ply panel + 5/8 rod & hardware + 30 screws",
}

TREB_BUY_LEDE = (
    "Everything MODELED in the machine: one 10-ft 5/4x6 deck board (the arm and both "
    "uprights — the derived cut plan packs all three), two 8-ft 2x4s (rails and cross "
    "members), one 3/4in 24x48in sanded-ply project panel ripped into two 12in strips "
    "(runway + both gusset knees), the 5/8-11 x 24in threaded-rod axle with its eight "
    "nuts and six fender washers, and thirty structural screws. The RIGGING (bucket, "
    "sand, paracord, pouch canvas, trigger hardware) is listed in the rigging section "
    "— real purchases the model cannot hold. The ground is existing (listed below), "
    "not bought.")

TREB_FOOTER = {
    "byline": "Witten Dacha &middot; 3-Foot Backyard Trebuchet",
    "tagline": ("Drawings &amp; numbers generated from ONE parametric model "
                "&mdash; verdict by invariant family in the coverage matrix above"),
    "regen_cmd": ".venv/bin/python scripts/single_detail_report.py "
                 "details/trebuchet.spec.yaml",
    "render_note": "renders: matplotlib offscreen (no Blender in this environment)",
}

TREB_PANEL = {
    "letter": "A",
    "title": "3-Foot Backyard Trebuchet",
    "sub": "braced 5/4x6 uprights on a 2x4 ladder base, 5/8 rod axle at 32in, 48in arm at 4:1, tunable bucket counterweight (rigging)",
    "views": ["iso", "dims", "operate", "stack", "side", "front", "pivot",
              "arm", "lap"],
    "captions": {
        "dims": "D1, the build sheet: every station and length drawn from the "
                "compiled model — the arm split with WHICH END IS WHICH, the "
                "launch direction, the axle/bore stations, the cross-member "
                "chain from the rear rail end, and the screw map (length, "
                "count, drive side) for every joint. Build from this sheet; "
                "the prose repeats it.",
        "operate": "D3, the operating diagram (schematic over the modeled "
                   "geometry — the cocked pose is derived arithmetic, the "
                   "rigging is the declared recipe, kinematics NOT ANALYZED): "
                   "where the bucket hangs and swings, where the pouch starts "
                   "on the runway, where the trigger's three eyes mount, and "
                   "which way it throws.",
        "stack": "D2, the pivot stack drawn at the parts' modeled positions "
                 "with the threading order spelled out: washer+nut clamping "
                 "each upright inside and out, double jam nuts backing each "
                 "fender thrust washer at the arm. The arm must spin "
                 "dead-free before rigging.",
        "iso": "The complete MODELED machine with the ground hidden: 2x4 ladder base "
               "(rails on edge, three flat cross members), the plywood runway the "
               "sling pouch slides along, both bored uprights with their plywood "
               "gusset knees, the threaded-rod axle, and the 48in arm hanging level. "
               "The counterweight bucket, sling and trigger are rigging — specified "
               "below, deliberately not drawn.",
        "side": "THE mechanism elevation: axle centerline at 32in, the arm split 38.4in "
                "(throw side, launch direction) / 9.6in (counterweight side) — the "
                "published 4:1 ratio — the runway surface at 2.25in, and the gusset "
                "knees bracing the mast fore-aft. The derived callouts on this view "
                "carry the governing numbers.",
        "front": "Down the throw axis: the 14in clear lane between the uprights' inner "
                 "faces that the counterweight bucket (~9.5in dia) swings through. The "
                 "gusset knees intrude to 12.5in — still 1.5in a side at bucket depth, "
                 "and the bucket's swing arc never reaches their fore-aft stations.",
        "pivot": "The pivot with the ARM HIDDEN (it occludes everything — visual "
                 "finding V1): the 5/8 rod crosses both uprights through their 11/16 "
                 "bores. Stack order per upright: fender washer + nut OUTSIDE, nut + "
                 "fender washer INSIDE — the pairs clamp each upright and tie the "
                 "frame tops. The floating center cluster is the arm's thrust "
                 "hardware, waiting for the hidden arm.",
        "arm": "The arm on the rod with the uprights hidden: its 3/4 bore rides the "
               "5/8 shank between two fender-washer thrust faces, each backed by a "
               "double jam-nut pair. The arm is modeled HANGING — centerline exactly "
               "one radial clearance (1/16in) below the axle line, bore tangent on "
               "the rod's top. That offset is asserted by a dimension check; it is "
               "sub-pixel at render scale (visual finding V3).",
        "lap": "Three joint words in one base corner: the upright face-lapped to the "
               "rail's inner face (three screws driven from the RAIL side, so the "
               "upright's inner face stays clean), the gusset knee lapping that inner "
               "face with its foot on the ground, and a cross member butt-screwed "
               "through the rail into end grain. The runway plate's edge shows at "
               "left, riding the crosses.",
    },
    "why": ("WHY A HINGED COUNTERWEIGHT — AND WHY THE BUCKET",
            "The water balloon is the binding constraint: it bursts under acceleration "
            "spikes, so it demands a SLING launch (gentle whip, broad fabric pouch) — "
            "which rules out torsion machines — and a hinged counterweight that falls "
            "rather than arcs, which beats a fixed weight on both range and frame "
            "shock (the beginner mistake the hobby forums warn against). The bucket "
            "IS the tuning knob: sand in, sand out — ~25lb (190:1) sends a tennis "
            "ball; ~12lb (25:1) lobs a water balloon that survives launch. A "
            "floating-arm trebuchet throws farther but is a multi-day precision "
            "build; this is the published one-day form at exactly this scale."),
    "narrative": [
        "The base is a 2x4 ladder: two 48in rails on edge, three 16in cross members "
        "laid flat between them (butt_screwed through the rails' outer faces into end "
        "grain, 2 screws per end), and a 12 x 44.5in plywood runway screwed down onto "
        "the crosses (rail_cap_screwed, countersunk flush) — the smooth lane the "
        "sling pouch slides along at launch.",
        "Each 35in 5/4x6 upright stands on the ground lapping its rail's inner face "
        "(cleat_screwed, 3 screws driven from the rail side); a 12 x 24in plywood "
        "gusset knee laps each upright's inner face (cleat_screwed, 3 screws) with "
        "its foot on the ground, bracing the mast fore-aft. Square cuts only — no "
        "miters anywhere.",
        "The axle is a 5/8-11 x 24in threaded rod through 11/16 bores at 32in: washer "
        "+ nut outside and nut + washer inside each upright clamp the frame; the arm "
        "— 48in of 5/4x6 on edge, bored 3/4 at 9.6in from the counterweight end — "
        "hangs on the shank between fender-washer thrust faces backed by double jam "
        "nuts. Wax the rod; the arm must spin freely by hand.",
        "The RIGGING completes the machine (see the rigging section): rope-hitched "
        "2-gallon sand bucket on the short end (the derived lowest point clears the "
        "runway by 2.65in), a 34in paracord sling with a canvas pouch, a bent release "
        "pin at the tip, and a three-eye pull-pin trigger at the rear cross. "
        "Kinematics, capacity and firing dynamics are honestly NOT ANALYZED.",
    ],
    "fieldnotes": [
        ("Governing dims are pinned.", "Axle height 32in, arm 48in at 4:1, and the "
         "14in counterweight lane are the owner contract — asserted in the model's "
         "dimension checks with literal expecteds and guarded by the e2e test. Stock "
         "sizes, stations and runs are free to tune."),
        ("The arm must spin FREELY.", "The thrust washers are modeled flush against "
         "the arm faces; in the field, back the jam pairs off a paper's width, wax "
         "the rod, and check the arm swings dead-free before rigging. A binding "
         "pivot eats half the throw."),
        ("Never stand inside the frame.", "A ~25lb bucket free-falls through the "
         "counterweight lane every shot. Cock, load, clear everyone BEHIND the "
         "machine, fire from 10ft of pull cord. Uncock by hand before any "
         "adjustment. An adult runs the machine; the kids watch from behind."),
        ("If the mast works loose, shoe the knees.", "The gusset knees are screwed "
         "to the uprights and foot on the ground — deliberately not fastened to the "
         "base (design finding DS3). On soft ground, screw a 2x4 shoe under each "
         "knee into the nearest cross member. Racking capacity is honestly NOT "
         "ANALYZED."),
    ],
}

TREB_VIEW_FILES = {
    "iso": "g1_iso.png",
    "dims": "d1_dimensions.png",
    "operate": "d3_operating.png",
    "stack": "d2_pivot_stack.png",
    "side": "v2_side.png",
    "front": "v3_front.png",
    "pivot": "z_pivot.png",
    "arm": "z_arm.png",
    "lap": "z_lap.png",
}

# The RIGGING + SAFETY sections — the deliberately-unmodeled half of the machine
# (no soft-goods vocabulary; design finding DS1 rules it ships as first-class
# document prose, never as faked geometry). Injected via `extra_sections`.
TREB_RIGGING_HTML = """
  <section class="notes">
    <h2>Rigging &mdash; the unmodeled half the machine needs</h2>
    <p class="lede">Nothing in this section is in the 3D model (no soft-goods/rigging
    vocabulary &mdash; a recorded work order). It is half the machine; do not skip it.
    Rigging buy list: 2-gallon bucket, one 50lb bag of play sand, 50ft of 550
    paracord, a canvas/tarp scrap ~12x12in, a carabiner or S-hook, one #10 x 2in
    screw (release pin), three 1/4in eye lags + one 3/8 x 6in bolt (trigger), a
    candle stub or paste wax.</p>
    <ul>
      <li><strong>Counterweight (the hinge is a rope hitch).</strong> Tie a 3ft loop
      of paracord around the arm shaft ~1.5in from the counterweight end with a
      constrictor/clove hitch seated HARD, and hang the bucket bail from it with the
      carabiner. Keep total hang (hitch + bail + bucket) near 17.5in: the derived
      lowest point is 4.9in &mdash; 2.65in over the runway. If the bucket kisses the
      deck, shorten the hitch. (A second bore for a bolt hinge is not expressible
      &mdash; one designed bore per board; the hitch is the honest alternative.)</li>
      <li><strong>Tuning (the whole point of the bucket).</strong> Tennis ball: fill
      it (~25lb, ~190:1). Water balloon: start half (~12lb) and add sand until the
      lob is right &mdash; too much weight bursts the balloon at the whip.</li>
      <li><strong>Sling.</strong> Two 34in paracord legs + a pouch cut from canvas
      ~9x9in with the corners trimmed (a flattened diamond); tie a leg to each pouch
      corner pair. One leg ties through a 1/8in hole field-drilled at the arm tip
      (a rigging hole, disclosed &mdash; not in the cut plan); the other ends in a
      1in loop that slips over the release pin.</li>
      <li><strong>Release pin.</strong> The #10 x 2in screw into the arm tip's end
      grain, bent ~30&deg; toward the throw side, 3/4in proud. The loop slips off
      this pin at release: bend it forward for an earlier (higher) release, back for
      later (flatter). This is the range/angle knob.</li>
      <li><strong>Trigger.</strong> Two eye lags into the rear cross member, one into
      the arm's underside near the tip; cock, line up the three eyes, slide the 3/8
      bolt through as the pin, tie a pull cord to its head. Fire from 10ft back.</li>
      <li><strong>Wax</strong> the runway and the rod &mdash; the pouch slides and
      the arm spins noticeably freer. The arm must spin DEAD-FREE by hand before
      rigging; back the jam pairs off a paper's width.</li>
    </ul>
  </section>"""

TREB_SAFETY_HTML = """
  <section class="notes">
    <h2>Operating safety &mdash; read before the first shot</h2>
    <p class="lede">A cocked trebuchet is a loaded machine, and none of the loads
    below are analyzed &mdash; the model proves geometry and construction, never
    dynamics. Treat it as live.</p>
    <ul>
      <li><strong>The falling counterweight is the hazard.</strong> ~25lb drops
      ~16in through the counterweight lane every shot. NOBODY inside the frame or
      beside the lane when cocked &mdash; cock it, load the pouch, clear everyone
      BEHIND the machine, pull the trigger cord from 10ft.</li>
      <li><strong>Never leave it cocked; never reach into the lane.</strong> Uncock
      (lower the bucket by hand) before any adjustment.</li>
      <li><strong>An adult runs the machine; the kids watch from behind.</strong>
      Tennis balls leave fast enough to hurt at close range; keep a WIDE margin
      clear downrange &mdash; range is NOT ANALYZED, so err far past where the
      last shot landed.</li>
      <li><strong>First shots:</strong> half bucket, stand well back, watch the
      frame &mdash; if the uprights work loose at the laps, retighten and add a
      screw per lap; on soft ground, shoe the gusset knees (see build notes).</li>
    </ul>
  </section>"""

TREB_DESIGN_TITLE = "Design review &mdash; functional / intent register"
TREB_DESIGN_LEDE = (
    "Design findings judge the construction against the piece's INTENT (this machine "
    "is FUNCTIONAL-DOMINANT — a working mechanism; the deciding canon is axle height, "
    "arm ratio, counterweight swing and tunable rigging, not furniture joinery). They "
    "are RECOMMENDATIONS, never invariant verdicts; the owner picks the fix. DS1 "
    "(rigging ships as a first-class doc section) and DS2 (the pivot rides honest "
    "escape hatches; a pivot/journal ConnectionType is the leading work order) are "
    "adopted as disclosures; DS3 (knee-to-base tie) is accepted with a field note and "
    "deferred to ANALYSIS-v1; DS4 (cleat_screwed's noun stretched to face-laps) is "
    "adopted with per-connection disclosure and filed as CL v2 vocabulary material.")


# ------------------------------------------------------------------------------
# Built-up 2x4 member: a deliberately small Plumb consumer used to measure the
# workflow cost of producing a complete, governed document from a simple brief.
# ------------------------------------------------------------------------------
BUILT_SPEC = _REPO / "details" / "built_up_2x4.spec.yaml"
BUILT_STORE = find_detail_store(REVIEWS_DIR, "built_up_2x4", "visual")
BUILT_DESIGN_STORE = find_detail_store(REVIEWS_DIR, "built_up_2x4", "design")
BUILT_VIEWS_DIR = _REPO / "outputs" / "built_up_2x4" / "views"
BUILT_RENDER_SCRIPT = _REPO / "scripts" / "render_built_up_2x4_views.py"
BUILT_TITLE = "Built-Up 2×4 Member — Model-Backed Fabrication Document"

BUILT_TITLE_BLOCK = {
    "eyebrow": "Shop Fabrication &middot; Built-Up Lumber",
    "h1": "Built-Up 2×4 Member",
    "lede": (
        "Two straight eight-foot nominal 2×4s clamped wide-face to wide-face and "
        "joined by eight screws at twelve-inch centers, alternating drive faces. "
        "Every drawing and number below comes from one validated parametric model."
    ),
    "scale": "Dimensions govern; long member views are compressed for legibility",
    "stock": "2x nominal 2×4 × 8ft + 8x representative 0.22in × 2.5in structural wood screws",
}

BUILT_BUY_LEDE = (
    "Buy two straight, dry nominal 2×4s at least 96 inches long and eight compatible "
    "2.5-inch structural wood screws near the modeled 0.22-inch diameter envelope. "
    "Confirm the purchased screw's current manufacturer instructions, drive bit, "
    "coating, lumber-treatment compatibility, edge distances, and permitted use."
)

BUILT_FOOTER = {
    "byline": "Witten Dacha &middot; Built-Up 2×4 Experiment",
    "tagline": (
        "Drawings and numbers generated from one parametric model; geometry validation "
        "does not establish structural capacity"
    ),
    "regen_cmd": ".venv/bin/python scripts/built_up_2x4_documents.py --preview",
    "render_note": "renders: model-backed matplotlib shop views",
}

BUILT_PANEL = {
    "letter": "A",
    "title": "Two-Ply Built-Up 2×4",
    "sub": "wide-face lamination with alternating screw heads",
    "views": ["iso", "side_a", "side_b", "section", "stations"],
    "captions": {
        "iso": "The complete 96-inch member. The seam between plies remains visible; A/B labels identify the alternating screw-head faces.",
        "side_a": "Face A carries heads at 6, 30, 54, and 78 inches. Dashed rings locate the intervening screws driven from face B.",
        "side_b": "Face B carries heads at 18, 42, 66, and 90 inches. Dashed rings locate the intervening screws driven from face A.",
        "section": "Two actual 1.5 × 3.5-inch sections create a 3 × 3.5-inch assembly — closer to, but not dimensionally equal to, a nominal 4×4.",
        "stations": "Lay out every center from one reference end: 6-inch end offsets with seven 12-inch spaces between eight screws.",
    },
    "why": (
        "WHY ALTERNATE THE DRIVE FACES?",
        "Alternating the visible heads distributes the owner-selected mechanical fastening pattern across both broad faces and makes every consecutive station easy to audit. The pattern is a fabrication choice, not an engineered structural schedule.",
    ),
    "narrative": [
        "Two nominal 2×4s finish at {member_length:g}in long × {stud_thickness:g}in thick × {stud_depth:g}in deep. Their broad faces contact to create an actual {assembly_width:g}in × {stud_depth:g}in section.",
        "The {station_count:g} representative screws run from {first_station:g}in through {final_station:g}in at {station_spacing:g}in on center. Face A carries alternating stations beginning at the reference end; face B carries the intervening stations.",
        "Each modeled screw is {screw_diameter:g}in diameter × {screw_length:g}in long. Through a {stud_thickness:g}in entry ply, that leaves {modeled_embedment:g}in of geometric bite in the receiving ply.",
        "Species, grade, moisture, loads, supports, end connections, composite action, structural capacity, and code compliance are NOT ANALYZED.",
    ],
    "fieldnotes": [
        ("Select and orient stock.", "Choose two straight {member_length:g}in nominal 2×4s. Reject severe twist, bow, splits, decay, or damage. Place the broad faces together and choose one common reference end."),
        ("Mark from one datum.", "From the reference end, mark centers at {first_station:g}in and then every {station_spacing:g}in through {final_station:g}in. Carry each mark to the correct face before clamping."),
        ("Clamp fully closed.", "Align both ends and both long edges. Clamp the mating faces closed along the length; do not use screw driving to pull a large bow or twist into alignment."),
        ("Drive alternating faces.", "Drive the first screw from face A, then alternate A/B at each consecutive station. Seat each head on the surface per the screw manufacturer's instruction; do not countersink unless that product explicitly requires it."),
        ("Inspect before use.", "Verify {station_count:g} seated heads, straightness, flush ends and edges, a closed seam, no split lumber, and no protruding tips. Stop: this document does not approve the member for structural use."),
    ],
}

BUILT_VIEW_FILES = {
    "iso": "iso.png",
    "side_a": "side_a.png",
    "side_b": "side_b.png",
    "section": "section.png",
    "stations": "stations.png",
}

BUILT_DESIGN_TITLE = "Design review &mdash; built-up-member intent register"
BUILT_DESIGN_LEDE = (
    "The governed concept review compared three build methods. The owner selected "
    "two full-length 2×4 plies, no adhesive, and eight screws at 12 inches on center "
    "with alternating drive faces. That geometry is implemented exactly; capacity "
    "and use approval remain explicit unknowns."
)


def _render_compiled_built_up_2x4_views(detail, out_dir: Path) -> None:
    from render_built_up_2x4_views import render_built_up_2x4_views

    render_built_up_2x4_views(detail, out_dir)


def _render_compiled_caddy_views(detail, out_dir: Path) -> None:
    from render_caddy_views import render_caddy_views

    render_caddy_views(detail, out_dir)

CONSUMERS = {
    "built_up_2x4.spec.yaml": {
        "name": "built_up_2x4",
        "spec": BUILT_SPEC,
        "panel": BUILT_PANEL,
        "views_dir": BUILT_VIEWS_DIR,
        "view_files": BUILT_VIEW_FILES,
        "store": BUILT_STORE,
        "design_store": BUILT_DESIGN_STORE,
        "design_title": BUILT_DESIGN_TITLE,
        "design_lede": BUILT_DESIGN_LEDE,
        "title": BUILT_TITLE,
        "title_block": BUILT_TITLE_BLOCK,
        "buy_lede": BUILT_BUY_LEDE,
        "footer": BUILT_FOOTER,
        "cut_note_context": "",
        "render_views": _render_compiled_built_up_2x4_views,
        "ensure_views": lambda: _ensure_views(
            BUILT_VIEWS_DIR, BUILT_VIEW_FILES, BUILT_RENDER_SCRIPT),
    },
    "armchair_caddy.spec.yaml": {
        "name": "armchair_caddy",
        "spec": CADDY_SPEC,
        "panel": PANEL,
        "views_dir": VIEWS_DIR,
        "view_files": VIEW_FILES,
        "store": CADDY_STORE,
        "design_store": CADDY_DESIGN_STORE,
        "design_title": DESIGN_TITLE,
        "design_lede": DESIGN_LEDE,
        "title": TITLE,
        "title_block": CADDY_TITLE_BLOCK,
        "buy_lede": CADDY_BUY_LEDE,
        "footer": CADDY_FOOTER,
        "cut_note_context": _CUT_NOTE_CONTEXT,
        "render_views": _render_compiled_caddy_views,
        "ensure_views": lambda: _ensure_views(
            VIEWS_DIR, VIEW_FILES, _REPO / "scripts" / "render_caddy_views.py"),
    },
    "step_stool.spec.yaml": {
        "name": "step_stool",
        "spec": STOOL_SPEC,
        "panel": STOOL_PANEL,
        "views_dir": STOOL_VIEWS_DIR,
        "view_files": STOOL_VIEW_FILES,
        "store": STOOL_STORE,
        "design_store": STOOL_DESIGN_STORE,
        "design_title": STOOL_DESIGN_TITLE,
        "design_lede": STOOL_DESIGN_LEDE,
        "title": STOOL_TITLE,
        "title_block": STOOL_TITLE_BLOCK,
        "buy_lede": STOOL_BUY_LEDE,
        "footer": STOOL_FOOTER,
        "cut_note_context": "",
        "ensure_views": lambda: _ensure_views(
            STOOL_VIEWS_DIR, STOOL_VIEW_FILES, STOOL_RENDER_SCRIPT),
    },
    "sit_reach_box.spec.yaml": {
        "name": "sit_reach_box",
        "spec": SITREACH_SPEC,
        "panel": SITREACH_PANEL,
        "views_dir": SITREACH_VIEWS_DIR,
        "view_files": SITREACH_VIEW_FILES,
        "store": SITREACH_STORE,
        "design_store": SITREACH_DESIGN_STORE,
        "design_title": SITREACH_DESIGN_TITLE,
        "design_lede": SITREACH_DESIGN_LEDE,
        "title": SITREACH_TITLE,
        "title_block": SITREACH_TITLE_BLOCK,
        "buy_lede": SITREACH_BUY_LEDE,
        "footer": SITREACH_FOOTER,
        "cut_note_context": "",
        "ensure_views": lambda: _ensure_views(
            SITREACH_VIEWS_DIR, SITREACH_VIEW_FILES, SITREACH_RENDER_SCRIPT),
    },
    "sit_reach_frame.spec.yaml": {
        "name": "sit_reach_frame",
        "spec": SITFRAME_SPEC,
        "panel": SITFRAME_PANEL,
        "views_dir": SITFRAME_VIEWS_DIR,
        "view_files": SITFRAME_VIEW_FILES,
        "store": SITFRAME_STORE,
        "design_store": SITFRAME_DESIGN_STORE,
        "design_title": SITFRAME_DESIGN_TITLE,
        "design_lede": SITFRAME_DESIGN_LEDE,
        "title": SITFRAME_TITLE,
        "title_block": SITFRAME_TITLE_BLOCK,
        "buy_lede": SITFRAME_BUY_LEDE,
        "footer": SITFRAME_FOOTER,
        "cut_note_context": "",
        "ensure_views": lambda: _ensure_views(
            SITFRAME_VIEWS_DIR, SITFRAME_VIEW_FILES, SITFRAME_RENDER_SCRIPT),
    },
    "trebuchet.spec.yaml": {
        "name": "trebuchet",
        "spec": TREB_SPEC,
        "panel": TREB_PANEL,
        "views_dir": TREB_VIEWS_DIR,
        "view_files": TREB_VIEW_FILES,
        "store": TREB_STORE,
        "design_store": TREB_DESIGN_STORE,
        "design_title": TREB_DESIGN_TITLE,
        "design_lede": TREB_DESIGN_LEDE,
        "title": TREB_TITLE,
        "title_block": TREB_TITLE_BLOCK,
        "buy_lede": TREB_BUY_LEDE,
        "footer": TREB_FOOTER,
        "cut_note_context": "",
        "extra_sections": (TREB_RIGGING_HTML, TREB_SAFETY_HTML),
        "ensure_views": lambda: _ensure_views(
            TREB_VIEWS_DIR, TREB_VIEW_FILES, TREB_RENDER_SCRIPT),
    },
}


def _format_reader_data(value, namespace):
    """Format reader configuration from the compiled model namespace.

    Panel prose used to repeat dimensions as Python literals, so a spec change
    could move geometry while leaving shop instructions stale. Strings may now
    name compiled params/derived values with ordinary ``str.format`` fields;
    containers are copied recursively so the module-level consumer registry is
    never mutated. Literal braces remain available as ``{{`` / ``}}``.
    """
    if isinstance(value, str):
        return value.format_map(namespace)
    if isinstance(value, dict):
        return {key: _format_reader_data(item, namespace)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_format_reader_data(item, namespace) for item in value]
    if isinstance(value, tuple):
        return tuple(_format_reader_data(item, namespace) for item in value)
    return value


def _relative_html_basename(value: str, field: str) -> str:
    if (not isinstance(value, str) or not value
            or Path(value).name != value
            or "/" in value or "\\" in value
            or not value.endswith(".html")):
        raise ValueError(
            f"{field} must be a relative HTML basename; got {value!r}")
    return value


def _title_block(detail, headline: str, tb: dict,
                 companion_href: str | None = None,
                 companion_summary: str | None = None) -> str:
    """The document header, from the consumer's ``title_block`` dict (eyebrow / h1 /
    lede / scale / stock) — parametrized so a second detail carries its OWN identity,
    not the caddy's (the caddy dict is unchanged from the hardcoded original)."""
    from detailgen.rendering.export import export_manifest  # noqa: F401 (parity)
    companion = ""
    if companion_href is not None:
        href = _relative_html_basename(companion_href, "companion_href")
        summary = companion_summary or (
            "Model-backed assembly panels with ghosted prior work, numbered "
            "parts, placement marks, tools, hardware, and stop gates."
        )
        companion = f"""
      <div style="margin-top:1rem;padding:.85rem 1rem;border:2px solid #1d4ed8;
                  border-radius:8px;background:#eff6ff">
        <a href="{_html.escape(href, quote=True)}"
           style="font-weight:800;color:#1d4ed8;text-decoration:none">
          Open the illustrated step-by-step assembly manual &rarr;
        </a>
        <div style="margin-top:.25rem;font-size:.9rem;color:#334155">
          {_html.escape(summary)}
        </div>
      </div>"""
    return f"""
  <header>
    <div class="tb-title">
      <div class="eyebrow">{tb['eyebrow']}</div>
      <h1>{tb['h1']}</h1>
      <p>{tb['lede']}</p>
      {companion}
    </div>
    <dl class="tb-meta">
      <div><dt>Generated</dt><dd>{CR.generated_stamp()}</dd></div>
      <div><dt>Scale</dt><dd>{tb['scale']}</dd></div>
      <div class="tb-verdict"><dt>Verdict &mdash; by invariant family</dt>
        <dd class="status-ok">{headline}</dd></div>
      <div><dt>Stock</dt><dd>{tb['stock']}</dd></div>
      <div><dt>Sheet</dt><dd>1 of 1</dd></div>
    </dl>
  </header>"""


def build_single_detail_html(name: str, detail, views_dir: Path, panel_cfg: dict,
                             view_files: dict, store_path: Path, work_dir: Path,
                             design_store: Path | None = None,
                             design_title: str | None = None,
                             design_lede: str | None = None,
                             title: str = TITLE,
                             title_block: dict = CADDY_TITLE_BLOCK,
                             buy_lede: str = CADDY_BUY_LEDE,
                             footer: dict = CADDY_FOOTER,
                             cut_note_context: str = _CUT_NOTE_CONTEXT,
                             extra_sections: tuple = (),
                             companion_href: str | None = None,
                             instruction_manual=None) -> str:
    """Assemble the one-panel HTML build document, reusing consolidated_report's
    section builders. ``detail`` must be compiled + validated. ``design_store``
    (optional) is a SIBLING design-review store rendered as a second findings
    block via the SAME renderer, so the document itself discloses the design
    review (design-review-directive.md)."""
    namespace = detail.namespace
    panel_cfg = _format_reader_data(panel_cfg, namespace)
    title_block = _format_reader_data(title_block, namespace)
    buy_lede = _format_reader_data(buy_lede, namespace)
    footer = _format_reader_data(footer, namespace)
    report = detail.report or detail.validate()

    # documentation render (the REAL ungated path) -> manifest + GLB source parity.
    detail.render_documentation(work_dir)
    manifest = json.loads((work_dir / "detail.manifest.json").read_text())

    # panel still images: matplotlib rasterizations -> data URIs (REUSE png_data_uri).
    image_uris = {v: CR.png_data_uri(views_dir / view_files[v])
                  for v in panel_cfg["views"]}
    callouts = detail.rendered_callouts()
    labels_by_id = part_labels(detail.assembly.parts)
    payload = build_viewer_payload(
        detail, instruction_manual=instruction_manual)
    # A rectangular geometry primitive may approximate context such as a sofa
    # arm or floor, but its domain metadata must not leak into the reader as
    # "Boulder / natural stone / leveling nuts". Preserve the model-derived
    # envelope/specs while labeling every existing body as context.
    for _machine_name, row in payload["parts"].items():
        if not row.get("existing"):
            continue
        reader_name = labels_by_id[row["id"]].reader_name
        row["type"] = "Existing context"
        row["item"] = f"{reader_name} (existing)"
        row["material"] = "Existing context — material not specified"
        row["group"] = f"Existing context|{row.get('dims', '')}"
        row["assumptions"] = (
            "Existing context approximated by its model envelope for fit and "
            "interference checks; not purchased and not structurally qualified.")
    slug = payload["slug"]

    # interactive GLB (CadQuery path, no Blender) for "Explore in 3D".
    glb_b64, _raw, _gz = CR.web_glb_b64(detail.assembly, work_dir, WEB_GLB_TOL)

    # BOM + cut plan, single-detail — the SAME builders the site uses. stub_guard
    # OFF: the zipline double-count guard drops any non-platform lumber as a
    # context stub of a platform member — false for a standalone caddy, whose 1x6
    # side boards are real, purchased parts (bug F3).
    purchased, existing = CR.combined_bom({name: detail}, stub_guard=False)
    # Plywood strips pack against 48in stock — the length of the project panel
    # they are ripped from — never the 8/10/12/16-ft LUMBER stick lengths (which
    # would print a buy line for an 8-ft ply strip, a SKU that does not exist:
    # review-sitreach follow-on). Split by profile; a no-op for all-lumber
    # details (caddy/stool). The rip itself stays a disclosed work order (no
    # rip/sheet vocabulary yet) — this only stops the stick packer from
    # asserting a false stock length for sheet goods.
    cut_items = CR.lumber_cut_items(purchased, {name: detail})
    ply_items = [i for i in cut_items if "plywood" in i.profile.lower()]
    stick_items = [i for i in cut_items if "plywood" not in i.profile.lower()]
    cut_plans = pack(stick_items)
    if ply_items:
        cut_plans.update(pack(ply_items, stock_lengths_mm=(48 * 25.4,)))
        cut_plans = dict(sorted(cut_plans.items()))
    fab_notes = CR.cutlist_fab_notes(purchased, {name: detail})

    # Domain labels (F4): the arm is modeled on the `boulder` primitive, whose
    # bom_label is "Boulder (existing)". Relabel every EXISTING row through the
    # shared reader projection so BOM and hover use the same authored name rather
    # than the modeling primitive.
    for row in existing:
        names = sorted({
            labels_by_id[part_id].reader_name
            for part_id in row["ids"]
            if part_id in labels_by_id
        })
        if names:
            label = ", ".join(names)
            row["item"] = label if "(existing)" in label else f"{label} (existing)"

    # visual-review block from THIS detail's sibling store (any store, real renderer).
    review_html = ""
    if store_path and Path(store_path).exists():
        review_html = render_visual_review_block_html(load_findings_file(store_path))

    # design-review block — the SAME renderer, retitled, from the sibling DESIGN
    # store (design-review-directive.md: the document itself discloses the review).
    design_html = ""
    if design_store and Path(design_store).exists():
        design_html = render_visual_review_block_html(
            load_findings_file(design_store), title=design_title, lede=design_lede,
            section_class="notes visual-review design-review")

    headline = render_headline_line(coverage_matrix(report))
    head = CR.HEAD.replace(
        "Zipline Launch Platform — Model-Backed Build Document", title)
    responsive_style = """
  @media (max-width:760px){
    body{padding:6px;}
    .tb-title{flex:1 1 100%;border-right:none;padding:16px 14px;}
    .tb-meta{flex:1 1 100%;}
    .panel,.notes,.legend,.existing,.provenance{padding-left:14px;padding-right:14px;}
    table{display:block;max-width:100%;overflow-x:auto;}
  }
  @media print{
    body{padding:0;background:white;}
    .sheet{border:0;box-shadow:none;max-width:none;}
    .viewer-btn,.v-controls{display:none!important;}
  }
"""
    head = head.replace("</style>", responsive_style + "</style>", 1)

    parts = [
        head,
        '<div class="sheet">',
        _title_block(
            detail,
            headline,
            title_block,
            companion_href,
            (
                f"{len(instruction_manual.panels)} model-backed assembly "
                f"panel{'s' if len(instruction_manual.panels) != 1 else ''} "
                "with ghosted prior work, numbered parts, tools, hardware, "
                "and stop gates."
            ) if instruction_manual is not None else None,
        ),
        CR.render_panel(name, panel_cfg, detail, image_uris, callouts, slug),
        CR.render_coverage_section({name: detail}, {name: report}),
        _render_install_section(detail, report),
        _render_build_sequence_section(detail),
        review_html,
        design_html,           # design-review disclosure (sibling store, additive)
        # F3: detail-specific buy-list lede (not the zipline "launch legs double as …").
        CR.render_buylist(purchased, existing, buy_lede=buy_lede),
        CR.render_cutplan(cut_plans, fab_notes),
        cut_note_context,      # F4 (CLOSED, CL-2 for the caddy): per-consumer, empty when the feature names itself
        # Per-consumer extra sections (additive; the trebuchet's rigging +
        # safety blocks — the deliberately-unmodeled half of a machine, shipped
        # as first-class document prose per design finding DS1).
        *extra_sections,
        # F1: NO CR.render_fieldfit() — that section is hardcoded zipline field
        # notes (bounce-test the deck, check anchor nuts). The caddy's own build
        # notes are the panel's "Build notes" (cfg["fieldnotes"]) above.
        # F2: detail byline + one-model tagline, not "Kids' Zipline / 4 models".
        CR.render_footer({name: manifest}, **footer),
        "</div>",
        _viewer_assets(slug, payload, glb_b64),
        "</body></html>",
    ]
    return "\n".join(p for p in parts if p)


def _render_install_section(detail, report) -> str:
    """Fastener-installation disclosure on the single-detail reader surface
    (owner guardrail #7's doc half, honesty review F2): the resolved
    contracts with per-field provenance and every OPEN (blocking/red)
    installability verdict's full text — the measured numbers, the
    [assumption] embedment provenance, and the used tool-envelope value a
    reader of a blocked doc previously could not see on paper. Empty for a
    detail with no installation contracts (the coverage matrix row is that
    detail's whole truth)."""
    import html as _html

    checks = getattr(detail, "_connection_checks", None)
    installs = checks.installs if checks is not None else []
    if not installs:
        return ""
    rows = []
    for ri in installs:
        notes = "".join(
            f"<div class='install-note'>assumption: {_html.escape(n)}</div>"
            for n in ri.notes)
        rows.append(f"<li><code>{_html.escape(ri.describe())}</code>{notes}</li>")
    open_findings = [f for f in report.findings
                     if f.check in ("install_method", "install_termination",
                                    "install_access") and not f.passed]
    if open_findings:
        open_html = "".join(
            f"<li><strong>[{_html.escape(f.verdict)}]</strong> "
            f"<code>{_html.escape(f.check)}</code> "
            f"{_html.escape(f.subject)} &mdash; {_html.escape(f.detail)}</li>"
            for f in open_findings)
        open_block = (f"<h3>Open installability verdicts (blocking)</h3>"
                      f"<ul class='narrative'>{open_html}</ul>")
    else:
        open_block = ("<h3>Open installability verdicts</h3><p>none &mdash; "
                      "every axis check on every contracted fastener passed "
                      "(the coverage matrix row above carries the family "
                      "verdict and its rung).</p>")
    from detailgen.validation.install import (
        EPISTEMIC_TABLE_CODA, EPISTEMIC_TABLE_HEADER, EPISTEMIC_TABLE_LEDE,
        EPISTEMIC_TABLE_TITLE, epistemic_contract_rows)

    # Epistemic-contract table (STEPDOC owner amendment 2) — the same rows
    # the markdown surface renders, near the top of the axis-3 disclosure.
    head_html = "".join(f"<th>{_html.escape(h)}</th>"
                        for h in EPISTEMIC_TABLE_HEADER)
    row_html = "".join(
        "<tr>" + "".join(f"<td>{_html.escape(cell)}</td>" for cell in row)
        + "</tr>" for row in epistemic_contract_rows(checks))
    epistemic_block = (
        f"<h3>{_html.escape(EPISTEMIC_TABLE_TITLE)}</h3>"
        f"<p>{_html.escape(EPISTEMIC_TABLE_LEDE)}</p>"
        f"<table class='epistemic-contract'><thead><tr>{head_html}</tr>"
        f"</thead><tbody>{row_html}</tbody></table>"
        f"<p>{_html.escape(EPISTEMIC_TABLE_CODA)}</p>")

    return (
        "<section class='notes install-disclosure'>"
        "<h2>Fastener installation &mdash; contracts and axis verdicts</h2>"
        "<p>Every fastener's installation method is DECLARED by a resolved "
        "contract (each field stamped with its provenance, so assumption-"
        "grade values are visible) and judged by the installability axis "
        "checks. A represented method is a declared claim, not proof the "
        "fastener can be driven.</p>"
        f"{epistemic_block}"
        f"<ul class='narrative install-contracts'>{''.join(rows)}</ul>"
        f"{open_block}</section>")


def _render_build_sequence_section(detail) -> str:
    """Derived Build Sequence on the HTML build document (task CPGCORE —
    the STEPDOC v1-core reader surface, mirroring how the install
    disclosures reach both per-detail surfaces). Rendered from the SAME
    content model as validation_report.md's section
    (detailgen.validation.build_sequence.build_sequence_model), so the two
    surfaces cannot disagree; nothing here is hand-typed. Empty for a
    detail with no event graph."""
    import html as _html

    from detailgen.validation.build_sequence import (
        SEQUENCE_INTRO, build_sequence_model, unordered_note)

    model = build_sequence_model(detail)
    if model is None:
        return ""
    steps, loose_names = model
    items = []
    for step in steps:
        title = _html.escape(step["title"])
        head = f"<strong>{title}</strong>"
        if step["claim"] == "stage":
            head += (" &mdash; authored build strategy, declared and "
                     "checked, never derived (why: "
                     f"{_html.escape(step['why'])})")
        elif step["claim"] == "staging":
            head += (" &mdash; authored staging claim, declared and "
                     "checked (why: "
                     f"{_html.escape(step['why'])})")
        subs = []
        for name, bom, fab in step["places"]:
            fab_txt = f" &mdash; fab: {_html.escape(fab)}" if fab else ""
            subs.append(f"<li>place {_html.escape(name)} "
                        f"({_html.escape(bom)}){fab_txt}</li>")
        for label in step["units"]:
            subs.append(f"<li>install {_html.escape(label)} &mdash; no "
                        f"fastener contract (a bond or connector install "
                        f"unit; any typed process fact follows as its own "
                        f"reader step)</li>")
        if step["process"] is not None:
            fact = step["process"]["fact"]
            subs.append(
                f"<li>process fact: {_html.escape(fact.provenance)} "
                f"(why: {_html.escape(fact.why)})</li>")
            subs.extend(
                f"<li>{_html.escape(instruction)}</li>"
                for instruction in fact.instructions)
            if fact.completion == "selected_label_full_cure":
                subs.append(
                    "<li>complete only when the selected adhesive label's "
                    "full-cure/full-strength condition is met under the "
                    "actual shop conditions. No generic duration is "
                    "represented.</li>")
            else:
                subs.append(
                    f"<li>completion condition: "
                    f"{_html.escape(fact.completion)} (no generic duration "
                    f"is represented)</li>")
        for claim in step["order_claims"]:
            if claim["role"] == "source":
                text = (
                    f"do not install {claim['target']} until this "
                    f"{claim['process_kind']} completes — "
                    f"{claim['provenance']} (why: {claim['why']})")
            else:
                text = (
                    f"complete {claim['process_kind']} for "
                    f"{claim['source']} before installing "
                    f"{claim['target']} — {claim['provenance']} "
                    f"(why: {claim['why']})")
            subs.append(f"<li>{_html.escape(text)}</li>")
        for unit in step["joins"]:
            subs.append(
                f"<li>set {_html.escape(unit)} in place &mdash; join the "
                f"completed bench unit into the root assembly</li>")
        for d in step["drives"]:
            subs.append(f"<li>drive: <code>{_html.escape(d)}</code></li>")
        items.append(f"<li>{head}<ul>{''.join(subs)}</ul></li>")
    loose_html = ""
    if loose_names:
        loose_html = f"<p>{_html.escape(unordered_note(loose_names))}</p>"
    return (
        "<section class='notes build-sequence'>"
        "<h2>Build sequence (derived)</h2>"
        f"<p>{_html.escape(SEQUENCE_INTRO)}</p>"
        f"<ol class='narrative'>{''.join(items)}</ol>"
        f"{loose_html}</section>")


def _viewer_assets(slug: str, payload: dict, glb_b64: str) -> str:
    """One-panel version of consolidated_report.render_viewer_assets: the same
    vendored three.js + viewer.js, one payload + one gzipped-GLB script."""
    data_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return "\n".join([
        f'<script type="application/json" id="detail-data-{slug}">{data_json}</script>',
        f'<script type="text/plain" id="detail-glb-{slug}">{glb_b64}</script>',
        f"<style>\n{viewer_css()}\n</style>",
        f"<script>\n{vendor_js()}\n{viewer_js()}\n</script>",
    ])


def _ensure_views(views_dir: Path, view_files: dict, render_script: Path) -> None:
    """Render the matplotlib views if they are not already on disk (per-consumer:
    each detail names its own view files + render script)."""
    needed = set(view_files.values())
    if not views_dir.exists() or not needed.issubset({p.name for p in views_dir.glob("*.png")}):
        import subprocess
        subprocess.run([sys.executable, str(render_script)], check=True)


def _views_complete(consumer: dict) -> bool:
    views_dir = consumer["views_dir"]
    needed = set(consumer["view_files"].values())
    return views_dir.exists() and needed.issubset(
        path.name for path in views_dir.glob("*.png"))


def _ensure_consumer_views(consumer: dict, detail) -> None:
    """Fill a clean view directory without recompiling when a renderer exists."""
    if _views_complete(consumer):
        return
    renderer = consumer.get("render_views")
    if renderer is not None:
        renderer(detail, consumer["views_dir"])
        if not _views_complete(consumer):
            raise RuntimeError(
                f"{consumer['name']} view renderer did not produce every "
                "registered view")
        return
    consumer["ensure_views"]()


def _consumer_for(spec_path: Path) -> dict:
    """Look up the registered single-detail consumer for ``spec_path`` (keyed by
    spec filename). Errors helpfully — naming how to register — for an
    unregistered detail, rather than silently producing an empty page."""
    consumer = CONSUMERS.get(spec_path.name)
    if consumer is None:
        raise SystemExit(
            f"no single-detail panel config registered for {spec_path.name!r}. "
            f"The caddy is the first consumer; register a panel + view renderer "
            f"in single_detail_report.CONSUMERS to add another. Known: "
            f"{sorted(CONSUMERS)}")
    return consumer


def build_document(out: Path, spec_path: Path = CADDY_SPEC,
                   preview: bool = False,
                   companion_href: str | None = None,
                   *, compiled_detail=None, instruction_manual=None,
                   document_notice: str | None = None) -> dict:
    """Compile + validate the detail named by ``spec_path``, build its
    single-detail HTML build document (reusing consolidated_report's machinery),
    write it to ``out``, and return a summary dict
    {path, size_bytes, headline, panels, preview}. The reusable seam the
    progression harness calls to report on the REAL HTML."""
    spec_path = Path(spec_path)
    consumer = _consumer_for(spec_path)
    detail = compiled_detail
    if detail is None:
        detail = compile_spec_file(consumer["spec"])
        report = detail.validate()
    else:
        report = detail.report or detail.validate()
    _ensure_consumer_views(consumer, detail)

    with tempfile.TemporaryDirectory() as td:
        html = build_single_detail_html(
            consumer["name"], detail, consumer["views_dir"], consumer["panel"],
            consumer["view_files"], consumer["store"], Path(td),
            design_store=consumer.get("design_store"),
            design_title=consumer.get("design_title"),
            design_lede=consumer.get("design_lede"),
            title=consumer.get("title", TITLE),
            title_block=consumer.get("title_block", CADDY_TITLE_BLOCK),
            buy_lede=consumer.get("buy_lede", CADDY_BUY_LEDE),
            footer=consumer.get("footer", CADDY_FOOTER),
            cut_note_context=consumer.get("cut_note_context", _CUT_NOTE_CONTEXT),
            extra_sections=consumer.get("extra_sections", ()),
            companion_href=companion_href,
            instruction_manual=instruction_manual)

    if document_notice:
        notice = _html.escape(document_notice)
        banner = (
            '<aside role="status" style="position:sticky;top:0;z-index:9999;'
            'padding:12px;text-align:center;background:#7f1d1d;color:white;'
            'font:800 16px/1.2 system-ui">'
            f'{notice}</aside>'
        )
        html = html.replace("<body>", f"<body>{banner}", 1)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    info = {"path": str(out), "size_bytes": out.stat().st_size,
            "headline": render_headline_line(coverage_matrix(report)),
            "panels": html.count('<section class="panel"'),
            "preview": None}
    if preview:
        pv = out.parent / ("PREVIEW - " + out.name)
        shutil.copyfile(out, pv)
        info["preview"] = str(pv)
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", nargs="?", default=str(CADDY_SPEC),
                    help="detail spec to document (default: the armchair caddy)")
    ap.add_argument("--out", default=None,
                    help="output HTML path (default: outputs/<name>/<name>_build_document.html)")
    ap.add_argument("--preview", action="store_true",
                    help="also drop a preview copy next to the output for Joel")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec)
    consumer = _consumer_for(spec_path)
    out = Path(args.out) if args.out else (
        _REPO / "outputs" / consumer["name"] / f"{consumer['name']}_build_document.html")

    info = build_document(out, spec_path, preview=args.preview)
    print(f"wrote {info['path']} ({info['size_bytes']/1e6:.2f} MB, "
          f"{info['panels']} panel(s))")
    print(f"headline: {info['headline']}")
    if info["preview"]:
        print(f"preview: {info['preview']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
