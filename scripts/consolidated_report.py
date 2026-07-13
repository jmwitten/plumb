#!/usr/bin/env python3
"""Generate the consolidated, model-backed zipline build document.

ONE self-contained HTML file that reproduces the original hand-drawn build
drawing (title block, one panel per element, combined buy list, field notes,
provenance footer) with every drawing, dimension, quantity and status claim
generated from the four validated construction details, each compiled from its
declarative spec:

    rock_anchor, tree_attachment, trolley_launch, platform (details/*.spec.yaml)

Run:  .venv/bin/python scripts/consolidated_report.py

Output: outputs/consolidated/zipline-build-document.html  (images embedded as
base64 data URIs; no external resources). Renders (GLB/manifest/STEP/PNG) land
in outputs/consolidated/renders/<detail>/. Pass ``--vault-copy`` to also copy
the document into the owner's Obsidian vault (off by default).
"""

from __future__ import annotations

import argparse
import base64
import gzip
import html
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"

# _site_overview.py is a plain sibling module — but this file is sometimes loaded
# by explicit file path under a distinct sys.modules name (tests), which does NOT
# put scripts/ on sys.path for a plain ``import``. Ensure it's there before
# importing, regardless of how THIS module itself was loaded.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import _site_overview
from _site_overview import is_context_stub_lumber, is_existing
from detailgen.rendering.part_labels import part_labels
OUT_DIR = ROOT / "outputs" / "consolidated"
RENDERS = OUT_DIR / "renders"
HTML_OUT = OUT_DIR / "zipline-build-document.html"
VAULT_DIR = Path(
    "/Users/joelwitten/Code/JoelBrain/05_Attachments/Organized/"
    "Zipline Platform Drawings")
#: The design REVISION date (rev 4) — the state of the design, not the build
#: moment. Shown in the header's Date row. A1: the build moment is a separate,
#: live "Generated" stamp (below), and the vault filename carries the BUILD date.
DOC_DATE = "2026-07-06"


def _now_est():
    """Current time in America/New_York (falls back to naive local if zoneinfo
    is unavailable). One call site drives both the header stamp and the vault
    filename so they never disagree."""
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now()


def generated_stamp() -> str:
    """A1: the visible "Generated: <YYYY-MM-DD HH:MM EST>" header stamp — the
    moment this document was BUILT. Deliberately EXCLUDED from byte-reproducibility
    comparisons and the presentation-golden text layer (normalized out in
    tests/test_spec_presentation_equiv.py), so rebuilding at a new time is not a
    spurious content change."""
    now = _now_est()
    tzname = now.tzname() or "EST"
    return now.strftime(f"%Y-%m-%d %H:%M {tzname}")


def vault_out() -> Path:
    """A1: the vault filename carries the BUILD date, so a rebuild lands beside a
    dated file rather than overwriting the stale hardcoded one. The previous
    hardcoded name was '...Zipline Build Document (model-backed) 2026-07-06.html'
    — report it at build time so the stale copy is removed on vault commit."""
    return VAULT_DIR / (
        f"Zipline Build Document (model-backed) "
        f"{_now_est().strftime('%Y-%m-%d')}.html")

#: Hard ceiling on the single self-contained HTML file. The doc must stay one
#: file (file:// in the vault; possibly a strict-CSP artifact), so a runaway
#: embed budget is a build failure, not a warning.
MAX_HTML_BYTES = 8_000_000

#: Coarse mesh tolerances for the *separate* per-detail web GLB (detail.web.glb)
#: the viewer embeds — deliberately coarser than the fine detail.glb (0.08/0.12,
#: owned by each detail's _export and NOT touched here) to keep the embed small.
#: Tried in order; the doc is rebuilt at the next-coarser step only if it blows
#: past MAX_HTML_BYTES (it doesn't today — all four gzip to ~0.5 MB combined).
WEB_GLB_TOLERANCES = ((0.25, 0.3), (0.3, 0.4), (0.4, 0.6))


# --------------------------------------------------------------------------- #
# Load the four details by compiling their declarative specs (details/*.spec.yaml)
# through the spec compiler — each detail's spec is its single source.
# --------------------------------------------------------------------------- #
def load_details() -> dict:
    from detailgen.spec.compiler import compile_spec_file

    return {
        "platform": compile_spec_file(DETAILS / "platform.spec.yaml"),
        "tree_attachment": compile_spec_file(DETAILS / "tree_attachment.spec.yaml"),
        "rock_anchor": compile_spec_file(DETAILS / "rock_anchor.spec.yaml"),
        "trolley_launch": compile_spec_file(DETAILS / "trolley_launch.spec.yaml"),
    }


def load_site():
    """Compile the ONE site model (``details/site.spec.yaml``) — the
    site-overview section is driven by this, not by the ``_site_overview.py``
    composition. It composes all four subsystems (platform, rock_anchor, tree,
    trolley) into one model, and the section absorbs their findings directly."""
    from detailgen.spec.site import compile_site_file

    return compile_site_file(DETAILS / "site.spec.yaml")


# --------------------------------------------------------------------------- #
# Rendering: VTK PNG views -> base64 data URIs.  (VTK is the reliable path and
# is presentation-quality here; Blender is available but not required.)
# --------------------------------------------------------------------------- #
def png_data_uri(path: Path) -> str:
    """Read an on-disk PNG straight to a base64 ``data:`` URI (no re-render).
    Used by the hash-gated reuse path, where the existing PNG already depicts
    the current geometry."""
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def render_png_data_uri(assembly, view: str, size=(1200, 900)) -> str:
    from detailgen.rendering.export import export_png

    slug = "".join(c if c.isalnum() else "_" for c in assembly.name.lower()).strip("_")
    path = RENDERS / slug / f"{slug}_{view}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    export_png(assembly, path, view=view, size=size, background=(1.0, 1.0, 1.0))
    return png_data_uri(path)


def web_glb_b64(assembly, out_dir: Path, tolerances) -> tuple[str, int, int]:
    """Export the coarse per-detail web GLB (``detail.web.glb``), gzip it, and
    return ``(base64_str, raw_bytes, gz_bytes)``.

    This is a SEPARATE, coarser artifact from the fine ``detail.glb`` each
    detail's ``_export`` writes — that one (and ``core/buildinfo``'s hash mesh
    constants) is never touched here. The base64 rides a ``text/plain`` script
    tag (not JSON) so the megabytes never pass through ``JSON.parse``; the
    browser gunzips it with ``DecompressionStream``."""
    from detailgen.rendering.export import export_glb

    lin, ang = tolerances
    glb_path = out_dir / "detail.web.glb"
    export_glb(assembly, glb_path, tolerance=lin, angular_tolerance=ang)
    raw = glb_path.read_bytes()
    gz = gzip.compress(raw, compresslevel=9)
    return base64.b64encode(gz).decode("ascii"), len(raw), len(gz)


# --------------------------------------------------------------------------- #
# BOM aggregation with the reconciliation's double-count guard.
#
# ``is_existing``/``is_context_stub_lumber`` moved to ``_site_overview.py``
# (imported above) so the site-overview composition below can share the exact
# same predicates instead of re-deriving them — see that module's docstring.
# --------------------------------------------------------------------------- #
def combined_bom(details: dict, *, stub_guard: bool = True):
    """Return (purchased_rows, existing_rows), with the context-stub double-count
    guard applied (see :func:`is_context_stub_lumber`).

    ``stub_guard`` (default True) is the ZIPLINE double-count guard: it drops
    structural-lumber rows from every non-``platform`` detail because in the
    four-detail site those are context stubs of a platform member. That guard is
    ONLY meaningful across the composed site — for a SINGLE standalone detail
    (``single_detail_report``) there is no cross-detail double count, and the
    detail's own lumber is real, so callers building one non-platform detail pass
    ``stub_guard=False`` to keep it. ``is_existing`` still applies either way."""
    purchased: dict[tuple, dict] = {}
    existing: dict[str, dict] = {}

    def add(store, row, origin):
        key = (row["item"], row["dimensions"])
        if key not in store:
            store[key] = {**row, "qty": 0, "origin": set()}
        store[key]["qty"] += row["qty"]
        store[key]["origin"].add(origin)

    def add_existing(row, origin):
        # Existing site features (the live tree, the boulder) are modeled as
        # context in more than one detail — the trunk in both the tree and
        # platform models, the boulder in both the rock-anchor and platform
        # models. They are ONE physical feature, so key on the item label alone
        # and don't sum quantities across details (that would read "2x boulder").
        key = row["item"]
        if key not in existing:
            existing[key] = {**row, "origin": set()}
        existing[key]["qty"] = max(existing[key]["qty"], row["qty"])
        existing[key]["origin"].add(origin)

    for name, d in details.items():
        for row in d.bom_table():
            if is_existing(row):
                add_existing(row, name)
                continue
            if stub_guard and is_context_stub_lumber(name, row):
                continue  # guard: already counted in the platform BOM
            add(purchased, row, name)

    return list(purchased.values()), list(existing.values())


# --------------------------------------------------------------------------- #
# Stock & cut plan (src/core/cutplan.py) — ADDS a section alongside the
# combined BOM above; never replaces it. Lumber/linear-stock rows only —
# hardware rows (``length_mm is None``) stay exactly as-is in the BOM.
# --------------------------------------------------------------------------- #
def lumber_cut_items(purchased: list[dict], details: dict) -> list:
    """Expand each already double-count-guarded lumber/decking BOM row (from
    :func:`combined_bom`'s ``purchased`` list) into individual cut instances
    for :func:`detailgen.core.cutplan.pack`.

    Each row's ``dimensions`` string (e.g. ``'2x6 x 48.0"'``) is display-only
    — not parsed here. The machine-readable length instead comes from
    ``length_mm``, a field :func:`bom_table` now carries per row (added to
    ``Component.bom_length_mm``, overridden on ``Lumber``/``DeckBoard``;
    ``None`` for parts with no single cut-length axis, e.g. every hardware
    component) precisely so this doesn't have to scrape ``describe()``.

    Source labels resolve each row's ``ids`` (the stable ``Placed.id`` of
    every part folded into that row, e.g. ``"lumber-3"``) back to the part's
    own display name (e.g. ``"joist 0"``) via the *same* detail(s) recorded
    in the row's ``origin`` — giving cut-map labels like "platform: joist 0"
    instead of a generic per-row tag repeated for every cut.
    """
    from detailgen.core.cutplan import CutItem

    id_to_label, id_to_part = _cut_id_maps(details)

    items: list[CutItem] = []
    for row in purchased:
        if row["length_mm"] is None:
            continue
        for part_id in row["ids"]:
            source, _comp = _resolve_cut(row, part_id, id_to_label, id_to_part)
            items.append(CutItem(row["item"], row["length_mm"], source))
    return items


def _cut_id_maps(details: dict) -> tuple[dict, dict]:
    """``(id_to_label, id_to_part)`` for every part in every detail, keyed on the
    stable ``(detail_name, Placed.id)`` — the label is the part's display name
    (for cut-map sources), the part is the ``Component`` (for its
    ``ProcessRecord``, so a cut line can name the same operations the geometry
    folds)."""
    id_to_label: dict = {}
    id_to_part: dict = {}
    for name, d in details.items():
        labels = part_labels(d.assembly.parts)
        for p in d.assembly.parts:
            id_to_label[(name, p.id)] = labels[p.id].reader_name
            id_to_part[(name, p.id)] = p.component
    return id_to_label, id_to_part


def _resolve_cut(row: dict, part_id: str, id_to_label: dict, id_to_part: dict):
    """Resolve a purchased-row part to ``(source, component)`` from the SAME
    origin — so the cut-map source string and the fabrication note both come from
    one resolution and cannot point at different parts."""
    for origin in sorted(row["origin"]):
        if (origin, part_id) in id_to_label:
            return f"{origin}: {id_to_label[(origin, part_id)]}", id_to_part.get((origin, part_id))
    return f"{'+'.join(sorted(row['origin']))}: {row['item']}", None


def _cutlist_fab_note(record) -> str:
    """The carpenter-readable fabrication note for a cut-list line — a thin
    delegate to :meth:`ProcessRecord.fab_note`, the SINGLE authoritative
    fab-note derivation (fab-design §6.2, the seam that retired retro R28).
    The viewer's hover tooltip reads that same method, so a part's cut list and
    its tooltip can never describe different fabrication. This wrapper stays so
    the cut-plan renderer and the ``smoke_progression`` era probe keep their
    stable call site; the derivation itself lives on the record."""
    return record.fab_note()


def cutlist_fab_notes(purchased: list[dict], details: dict) -> dict:
    """Per-cut fabrication notes for the cut-plan renderer, keyed on
    ``(profile, source)`` — the same profile+source a :class:`PlacedCut` carries
    after packing, so the renderer can re-attach each note to its cut without the
    packer ever having to carry it (the ``cutplan.py`` packer is untouched; only
    the note's association is reconstructed on the far side, exactly as the
    source label already is). Only cuts whose part has a non-empty note appear."""
    id_to_label, id_to_part = _cut_id_maps(details)
    notes: dict = {}
    for row in purchased:
        if row["length_mm"] is None:
            continue
        for part_id in row["ids"]:
            source, comp = _resolve_cut(row, part_id, id_to_label, id_to_part)
            if comp is None:
                continue
            fn = getattr(comp, "fabrication_record", None)
            record = fn() if fn is not None else None
            if record is None:
                continue
            note = _cutlist_fab_note(record)
            if note:
                notes[(row["item"], source)] = note
    return notes


def assert_details_fabrication_sound(details: dict) -> None:
    """Production guard (fab-design §8; the FIX-FIRST obligation the FAB-1
    adversarial review handed to the consumer task): before the doc build emits a
    cut list / BOM from each part's :class:`ProcessRecord`, assert the
    fabrication-fold invariant on every fabricated part. A component whose
    installed geometry has drifted from its declared steps — a "mystery cut" with
    no operation behind it, R28 running the other way — fails the build LOUDLY,
    naming the part, instead of shipping a cut list that disagrees with the
    solid. This is what makes CAT-4's "the build must reject it" literally true.

    Parts are enumerated by CAPABILITY (``verify_assembly_fabrication`` skips any
    part whose ``fabrication_record()`` is ``None``), never by type name, so a
    future non-delegating fabricated component is covered the moment it exists.
    The guard builds each part fresh (``_build()``) rather than reading a
    cached ``.solid`` — a BREP reload's re-tessellation would false-positive a
    byte-identity check against a fresh ``fold`` (fab-design; FAB-1 report)."""
    from detailgen.core.process_graph import verify_assembly_fabrication

    for d in details.values():
        verify_assembly_fabrication(d.assembly)


# --------------------------------------------------------------------------- #
# HTML assembly
# --------------------------------------------------------------------------- #
def esc(s: str) -> str:
    return html.escape(str(s))


PANELS = {
    "platform": {
        "letter": "A",
        "title": "Overall Platform",
        "sub": "free-standing: four legs (2 launch + 2 tree-end)",
        "views": ["iso", "iso_back", "front", "top"],
        "captions": {
            "iso": "Whole platform, launch edge open to the right. Rails + galv "
                   "wire-mesh infill on both long sides; two short tree-end legs "
                   "(left) carry the back down to pier blocks, and the two launch "
                   "legs carry the front — the +Y leg on the boulder, the -Y leg on "
                   "a pier block. The beams pass the trunk with a growth gap and "
                   "never touch it.",
            "iso_back": "Same frame from behind — the mesh panels and the two "
                        "diagonal 2x4 braces (both axes) read here.",
            "front": "Side elevation. Deck surface, rail top, and the leg drop to "
                     "the boulder are the checked heights below.",
            "top": "Deck plan, looking straight down. All six 5/4 deck boards are "
                   "notched around the round trunk at the tree end — the scalloped "
                   "opening is the on-site cut each board carries in the cut plan. "
                   "The trunk passes through with its growth gap; joists run "
                   "crosswise beneath.",
        },
        "why": ("WHY FREE-STANDING (NOT HUNG ON THE TREE)?",
                "The platform carries its own load on four legs. At the launch "
                "edge, where the rider's weight goes, the +Y leg is epoxy-anchored "
                "to the boulder and the -Y leg bears on a precast pier block; at "
                "the tree end, two short legs bear on their own pier blocks. The "
                "beams only pass the live trunk, clearing it by a growth gap, so "
                "the tree can sway and grow without ever bearing the deck."),
        "narrative": [
            "Two 2x6 PT beams (60\" stock) straddle the trunk with a growth gap on each side — never touching it — extend 12\" past its centerline to the tree-end legs, and run 48\" from the tree face out to the legs. "
            "5/4 deck boards run the long way over 2x6 joists on hangers.",
            "36\" rails + welded-wire mesh on both long sides and the tree end, no "
            "gap over 4\". The launch edge (right) is the only opening — open, "
            "closed only by a clip-on strap gate.",
            "Access is at the launch end: two 2x4 steps beside the boulder rise to "
            "the deck at the gate (or just step off the boulder). The trunk and "
            "boulder are shown for reference — existing site features, not purchased.",
            "Deck height is set to the grab bar on site — hang a kid on the bar, "
            "measure, then cut the legs (expect 28-30\").",
        ],
        "fieldnotes": [
            ("Steps at the launch end, beside the boulder.", "The tree end and both "
             "long sides are sealed by rail + mesh (the mesh wraps to the trunk); "
             "the strap gate at the launch edge is the only opening, so the steps "
             "land there. Two 2x4 posts stand just outboard of the launch edge, on "
             "the near half of the gate span (clear of the grab-handle corner), and "
             "rise to the deck in even risers."),
            ("Joists: 3 @ 12\" O.C.", "Three 2x6 joists on hangers, first at 11.75\" "
             "from the tree end, last at 35.75\". The first clears the trunk plus 1\" "
             "bark; the last clears the leg lap. Two hangers per joist."),
            ("Decking: 6 boards, butt-tight, 48\" long.", "5/4x6 at 5.5\" each = 33\" "
             "deck width, boards butt tight with no side overhang so a board edge "
             "can’t foul the outboard legs. Boards run the long way (parallel to the "
             "beams), full 48\". Notch the board that meets the trunk around it on "
             "site, leaving room for the tree to grow."),
            ("Deck run: 48\".", "Tree face to launch end. The deck-board cut list "
             "assumes this 48\" run; beam stock is 60\" (48\" deck run + 12\" "
             "continuing past the tree centerline to reach the tree-end legs) — "
             "confirm both on site before cutting."),
        ],
    },
    "tree_attachment": {
        "letter": "B",
        "title": "Tree Clearance",
        "sub": "beams clearing the live trunk",
        "views": ["iso", "front", "top"],
        "captions": {
            "iso": "Two 2x6 beams passing the round trunk on opposite sides, each "
                   "standing a growth gap clear of the bark — nothing fastens to the "
                   "tree.",
            "front": "Trunk seen at true 20\" diameter with a beam passing each side; "
                     "each beam inner face stands ~5\" clear of the trunk surface (the "
                     "growth gap).",
            "top": "Down the trunk: one beam each side, joists span between them past "
                   "the trunk on the launch side.",
        },
        "why": ("WHY CLEAR THE TREE?",
                "A live trunk sways and adds girth every year. The beams pass it with "
                "a growth gap on each side and never touch it, so the tree can move "
                "and grow while the platform stands free on its own posts and legs — "
                "nothing to pry loose, nothing to re-seat."),
        "partial_view_note": "Beams shown are the trunk-end portion of the platform’s "
                              "continuous 60\" beams — full run in the platform detail.",
        "narrative": [
            "The beams don’t attach to the trunk at all: each inner face stands a "
            "growth gap (~5\") clear of the bark, so the round live trunk is free to "
            "sway and swell inside the gap.",
            "The joists between the beams keep 1\" bark clearance to the trunk; the "
            "growth gap on the beams is sized so a swaying, growing trunk still never "
            "reaches them.",
            "The tree’s only structural job is the zipline cable anchor above — a "
            "separate, deferred detail. It carries none of the platform.",
        ],
        "fieldnotes": [
            ("Beam underside sits at 22.5\" above ground.", "This is the same "
             "continuous 2x6 that runs out to the legs (deck 29\" − 1\" decking − "
             "5.5\" beam depth). Set this height off the deck height once it’s fixed "
             "to the grab bar."),
            ("Growth gap: ~5\" per side, keep it ≥4\".", "The platform detail proves "
             "each beam inner face clears the trunk by at least the growth gap. Check "
             "the clearance from each beam to the bark on site, and shift the beams "
             "out if the trunk is fatter than modeled."),
        ],
    },
    "rock_anchor": {
        "letter": "C",
        "title": "Rock Anchor",
        "sub": "leg-to-boulder anchor",
        "views": ["iso", "front", "right"],
        "captions": {
            "iso": "One leg base: 2x6 leg, galv L-angle each wide face, thru-bolts, "
                   "and the leveling / lock-nut stack on the epoxied rod.",
            "front": "Looking at the leg edge (1-1/2\" wide). Two rods straddle the "
                     "leg centerline; the leg floats ~1/2\" off the rock.",
            "right": "Along the beam: the two thru-bolts sit side by side through "
                     "angle + leg + angle.",
        },
        "why": ("WHY TWO RODS?",
                "One rod = the leg can pivot around it / kick sideways. Two rods plus "
                "clamped angles mean the base cannot rotate."),
        "partial_view_note": "Leg shown is the base portion of the platform’s "
                              "continuous 63.5\" launch leg — full run in the platform "
                              "detail.",
        "narrative": [
            "2× 1/2\" galv all-thread epoxied 8\" into sound rock (holes ≥6\" "
            "from any rock edge). Buy 12\" rod: ~8\" in + ~3\" out, trim after the lock "
            "nut. Exterior anchoring epoxy (Quikrete or Simpson SET).",
            "Galv L-angle 3\"×3\"×1/4\", 3-1/2\" long, one per wide face. "
            "Fender washer + nut under each flange = leveling; washer + 2 jammed nuts "
            "= lock. The flange rides on the nut, not on the rock.",
            "2× 3/8\"×2-1/2\" fully-threaded galv thru-bolts through "
            "angle + 1-1/2\" leg + angle, side by side, ≥2\" up from the leg "
            "bottom.",
        ],
        "fieldnotes": [
            ("Leg stops ~1/2\" above the rock.", "The leveling-nut stack holds the "
             "leg end grain ~1/2\" off the rock so it never sits in water. Buy leg "
             "stock long (65-68\") and trim to the deck height on site — the extra "
             "over the ~63.5\" above-rock length covers this air gap plus a cut "
             "allowance."),
            ("Rod stick-out and embed are cut on site.", "8\" embed is deep on purpose "
             "— margin for field rock. Grind a small flat pad at each rod so the "
             "washers seat; brush and blow ALL dust before injecting epoxy."),
        ],
    },
    "trolley_launch": {
        "letter": "D",
        "title": "Trolley / Launch Edge",
        "sub": "grab bar, handle & strap gate",
        "views": ["iso", "front", "right"],
        "captions": {
            "iso": "Launch corner: the existing cable / trolley / grab bar above, the "
                   "new grab handle on the post, and the clip-on strap gate at the "
                   "rail line.",
            "front": "Heights that matter: grab bar 75\" above ground, deck at 29\", "
                     "grab handle 26\" above the deck.",
            "right": "The strap gate spans the two launch posts at the 65\" rail line; "
                     "the launch edge itself stays open.",
        },
        "why": ("WHY AN OPEN LAUNCH EDGE?",
                "The rider steps off here. A fixed rail would be in the way, so the "
                "edge is open and closed only by a clip-on strap gate between rides."),
        "narrative": [
            "The zipline cable, trolley wheel, hanger and grab bar are existing site "
            "hardware — shown for placement, not purchased.",
            "New here: the grab handle on the launch post and the strap gate across "
            "the launch posts. Grab bar sits 75\" above ground (≈46\" above the "
            "deck); the rider reaches up to it.",
        ],
        "fieldnotes": [
            ("Grab handle: 26\" above the deck.", "Mount both 1/4\" structural screws "
             "into the launch leg — the upper screw lands ~31\" above the deck (60\" "
             "above ground), below the ~63.5\" leg top. A rider grabs it low."),
            ("The launch posts are the platform’s legs.", "The two launch-corner posts "
             "the gate and grab handle mount to are the platform’s launch legs (2x "
             "2x6, ~63.5\" above the rock). They’re bought once, in the platform buy "
             "list — the strap gate, grab handle and screws are the only new items "
             "here."),
        ],
    },
}

FIELD_FIT = [
    ("Cut leg stock to fit (buy 65-68\")",
     "Trim the legs on site to the deck height once it’s set to the grab bar. The "
     "~63.5\" above-rock length plus the ~1/2\" air gap off the rock plus a cut "
     "allowance is why the stock runs 65-68\"."),
    ("Confirm deck run before cutting",
     "The deck-board cut list assumes a 48\" run; beam stock assumes 60\" (the 48\" "
     "run plus 12\" continuing past the tree centerline). Verify the desired run on "
     "site before cutting beams."),
    ("Deck butts tight, no side overhang",
     "Deck boards butt tight to the beam outer faces so a board edge can’t foul the "
     "outboard legs. If a side overhang is wanted, use wider decking than the 33\" "
     "deck width."),
    ("Deck width lands on whole 5.5\" boards",
     "Butt-tight 5/4x6 boards are 5.5\" each, so keep the deck width a multiple of "
     "5.5\". 33\" = 6 boards exactly; the launch-edge detail uses the same 33\"."),
    ("Joists: 3 @ 12\" O.C.",
     "Three 2x6 joists on hangers at a true 12\" O.C., first at 11.75\" from the tree "
     "end, last at 35.75\". The first clears the trunk plus 1\" bark; the last clears "
     "the leg lap. Two hangers per joist."),
    ("Access steps at the launch end",
     "The tree end and both long sides are sealed by rail + mesh (the mesh wraps to "
     "the trunk); the strap gate at the launch edge is the only opening. The two 2x4 "
     "steps stand just outboard of the launch edge, beside the boulder, on the near "
     "half of the gate span (clear of the grab-handle corner), and rise to the deck "
     "in even risers — or a rider just steps off the boulder."),
    ("Launch-edge decking cantilever ~12.25\"",
     "The decking runs ~12.25\" past the last joist at the launch edge (the highest-load "
     "zone) — within 16\" residential norms. Add an extra launch-edge rim/nailer under "
     "the board ends if a stiffer edge is wanted."),
    ("Structural lumber is bought once",
     "The buy list carries every structural member once — beams, legs, joists, "
     "decking, rails and braces. The launch legs also serve as the grab-handle / "
     "strap-gate posts and the tree-end beams; don’t buy those a second time. The "
     "connection hardware (epoxy, rods, angles, nuts, washers, bolts, strap "
     "gate, grab handle, screws) is the rest of the list."),
    ("Beams clear the trunk — check the growth gap",
     "The beams pass the trunk with a growth gap (~5\" per side, at least 4\"); "
     "nothing fastens to the tree. Confirm the clearance from each beam inner face "
     "to the bark on site, and shift the beams out if the trunk is fatter than "
     "modeled."),
    ("Existing (not purchased) features",
     "Cable, trolley wheel, hanger, grab bar, the tree trunk and the boulder are "
     "existing site features — shown so everything lands in the right place, but not "
     "purchased (see the second table)."),
    ("Leg-to-beam bolts are distinct from anchor thru-bolts",
     "The leg-to-beam bolts are 3/8\"×4\"; the rock-anchor thru-bolts are "
     "3/8\"×2-1/2\". They are separate buy-list lines."),
]


#: Where per-detail visual-review stores live (task VISREVSTORES). The reviewer
#: writes suspicions into ``<name>-findings.yaml``; this doc is the ZIPLINE's
#: consumer, so it reads the ``zipline`` store off the enumeration surface rather
#: than hand-pointing a filename (the store was the bare ``findings.yaml``).
REVIEWS_DIR = ROOT / "reviews" / "visual"


def build_review_block() -> str:
    """Render the visual-review status block from the committed zipline findings
    store, cross-referenced against a manifest of THIS build's on-disk renders (so
    the block can report staleness + never-reviewed images). Read-only over the
    renders dir — it never exports, so it can't mutate model geometry.

    Degrades to an empty string (no section) if the store is absent — the block
    is an additive honesty surface, never a hard build dependency."""
    from detailgen.review import (
        build_review_manifest,
        find_detail_store,
        load_findings_file,
        render_visual_review_block_html,
    )

    store_path = find_detail_store(REVIEWS_DIR, "zipline", "visual")
    if store_path is None:
        return ""
    store = load_findings_file(store_path)
    manifest = build_review_manifest(RENDERS, repo_root=ROOT) if RENDERS.exists() else None
    return render_visual_review_block_html(store, manifest)


def _render_verdict_headline(detail_reports, site_report) -> str:
    """The header's PRIMARY verdict, DERIVED from the actual validation reports —
    never a hardcoded literal.

    Owner directive (Joel, 2026-07-08 §3): a top-line "CLEAN" visually
    communicates more confidence than the system possesses. The reader-facing
    headline therefore LEADS with the per-family breakdown — what has actually
    been established, family by family — rolled up across all four detail models
    and the composed site model (``aggregate_coverage_matrix``): a family reads
    NOT ANALYZED only when nothing in the whole document examined it. The
    breakdown comes straight from the coverage machinery, so it can never diverge
    from the per-model matrices further down.

    "CLEAN"/require_clean is demoted to a SECONDARY internal-verdict line (it
    stays the internal/API verdict; only its prominence changes). The ladder rung
    and the NOT-ANALYZED disclaimer stay in plain reader language: validation
    covers representation, never structural adequacy. Blocking (not merely FAIL)
    is the gate measure — an UNKNOWN support obligation blocks require_clean too,
    so it counts against "CLEAN" here."""
    from detailgen.validation.coverage import (
        aggregate_coverage_matrix, render_headline_html)

    reports = list(detail_reports.values()) + [site_report]
    headline = render_headline_html(aggregate_coverage_matrix(reports))

    n_details = len(detail_reports)
    dirty = [name for name, r in detail_reports.items() if not r.ok]
    n_block = len(site_report.blocking)
    if not dirty and n_block == 0:
        internal = (
            f"Internal export verdict: CLEAN &mdash; all {n_details} detail "
            "models and the composed site model pass require_clean for the "
            "families analyzed.")
    else:
        bits = []
        if dirty:
            bits.append(
                f"{', '.join(sorted(dirty))} hold(s) open finding(s) "
                "(see the detail sections)")
        if n_block:
            bits.append(
                f"the composed site model holds {n_block} open "
                "finding(s) that block the render gate (see the site section)")
        internal = "Internal export verdict: NOT CLEAN &mdash; " + "; ".join(bits) + "."
    ladder = (
        "Validation reaches support-REPRESENTED (rung 3): a supported occupied "
        "region is REPRESENTED, not proven safe &mdash; structural capacity "
        "&amp; code compliance are NOT ANALYZED (the per-family verdicts above "
        "roll up the coverage matrices below).")
    return (
        f"{headline}"
        f'<p class="verdict-note">{ladder}</p>'
        f'<p class="verdict-note verdict-internal">{internal}</p>')


def build_html(details, images, purchased, existing, cut_plans, manifests, payloads, glb_b64,
                site, site_report, detail_reports, review_block: str = "",
                pier_images=None) -> str:
    # ``site_report`` / ``detail_reports`` are validated ONCE in main from the exact
    # compiled geometry, BEFORE the coarse web-GLB export runs. That export
    # re-tessellates the shared solids and leaves a coarse triangulation cached on
    # them, which can bulge a cylinder's bounding box a few hundredths of an inch
    # (the trunk reads ~20.06" vs its exact 20.00"), tripping tight dimension checks
    # with a spurious FAIL. Rendering every verdict — the site findings AND the
    # per-detail coverage matrices — from these pre-export reports keeps the
    # document honest (the exact-geometry count) and reproducible run-to-run. Never
    # re-derive a verdict here off the mutated ``site`` / ``details`` solids.
    status = _render_verdict_headline(detail_reports, site_report)

    parts = []
    parts.append(HEAD)
    parts.append('<div class="sheet">')

    # ---- title block ----
    parts.append(f"""
  <header>
    <div class="tb-title">
      <div class="eyebrow">Dacha &middot; Backyard Build</div>
      <h1>Zipline Launch Platform</h1>
      <p>Free-standing platform beside the cable-anchor tree. The beams pass the
      live trunk with a growth gap on each side and never touch it; two launch
      legs carry the front edge — the +Y leg epoxy-anchored to the boulder, the
      -Y leg on a pier block — and two short tree-end legs carry the back on
      their own pier blocks. Low deck sized to the grab bar. Every drawing and
      number below is generated from four validated parametric 3D models.</p>
    </div>
    <dl class="tb-meta">
      <div><dt>Date</dt><dd>{DOC_DATE} (rev 4)</dd></div>
      <div><dt>Generated</dt><dd>{generated_stamp()}</dd></div>
      <div><dt>Scale</dt><dd>Rendered to scale; verify on site</dd></div>
      <div class="tb-verdict"><dt>Verdict &mdash; by invariant family</dt>
        <dd class="status-ok">{status}</dd></div>
      <div><dt>Budget</dt><dd>~$350&ndash;400 + drill rental</dd></div>
      <div><dt>Riders</dt><dd>42&Prime; &amp; 46&Prime; kids</dd></div>
      <div><dt>Sheet</dt><dd>1 of 1</dd></div>
    </dl>
  </header>""")

    # ---- site overview (TOP of the document, before per-element panels) ----
    # Driven by the ONE compiled site model (details/site.spec.yaml).
    parts.append(render_site_model_section(site, site_report))

    # ---- element panels ----
    for name in ["platform", "tree_attachment", "rock_anchor", "trolley_launch"]:
        cfg = PANELS[name]
        d = details[name]
        callouts = d.rendered_callouts()
        slug = payloads[name]["slug"]
        parts.append(render_panel(name, cfg, d, images[name], callouts, slug))
        # Fastener-installation disclosure (resolved contracts + epistemic-
        # contract table + open axis verdicts) and the derived Build Sequence
        # — the same per-detail reader surfaces single_detail_report.py's
        # one-panel documents carry, placed right after this detail's own
        # panel so a reader sees them next to the geometry they describe.
        # Empty (no installation contracts / no event graph) is skipped, like
        # ``review_block`` below.
        install_section = _render_install_section(d, detail_reports[name])
        if install_section:
            parts.append(install_section)
        build_sequence_section = _render_build_sequence_section(d)
        if build_sequence_section:
            parts.append(build_sequence_section)

    # ---- pier foundations (Panel E): the view-coverage-directive zoom of the
    #      three precast piers, and the plain-language home of the site's three
    #      blocking foundation-capacity UNKNOWNs. ----
    parts.append(render_pier_foundation_section(details, site_report, pier_images))

    # ---- coverage matrix (honesty: what each model actually analyzed) ----
    parts.append(render_coverage_section(details, detail_reports))

    # ---- visual review (adversarial smell test — SECONDARY to the coverage
    #      matrix above; suspicions, never a verdict, and it flips nothing). Only
    #      appended when a block was supplied (the presentation golden + prose
    #      guard build without it, so both stay stable). ----
    if review_block:
        parts.append(review_block)

    # ---- combined buy list + existing ----
    parts.append(render_buylist(purchased, existing))

    # ---- consolidated stock & cut plan (ADDS to, doesn't replace, the buy list) ----
    # Each cut carries the fabrication ops its ProcessRecord declares (the trunk
    # notch, in v1) so the cut list names what the geometry folds — retro R28.
    parts.append(render_cutplan(cut_plans, cutlist_fab_notes(purchased, details)))

    # ---- field-fit & assumptions ----
    parts.append(render_fieldfit())

    # ---- provenance footer ----
    parts.append(render_footer(manifests))

    parts.append("</div>")

    # ---- interactive viewer: per-panel data, then styles + one script ----
    parts.append(render_viewer_assets(payloads, glb_b64))

    parts.append("</body></html>")
    return "\n".join(parts)


def render_viewer_assets(payloads, glb_b64) -> str:
    """The self-contained viewer block appended after the sheet: one payload
    (JSON) + one gzipped-GLB (base64, text/plain) script per panel, then the
    viewer CSS and one inline script (vendored three.js r147 + viewer.js).

    JSON is inlined with ``</`` escaped so a value can't close the script tag
    early; the base64 GLB is plain ASCII (no ``<``) and stays out of JSON so the
    megabytes never pass through ``JSON.parse``."""
    from detailgen.rendering.web_viewer import vendor_js, viewer_css, viewer_js

    blocks = []

    def emit(name):
        slug = payloads[name]["slug"]
        data_json = json.dumps(payloads[name], separators=(",", ":")).replace("</", "<\\/")
        blocks.append(
            f'<script type="application/json" id="detail-data-{slug}">{data_json}</script>'
        )
        blocks.append(
            f'<script type="text/plain" id="detail-glb-{slug}">{glb_b64[name]}</script>'
        )

    for name in ["platform", "tree_attachment", "rock_anchor", "trolley_launch"]:
        emit(name)
    # Panel E's scoped pier viewer, when its payload/GLB were built (main() adds
    # them; the text-layer golden and the escaping unit test stub only the four
    # per-detail panels, so this stays additive and never KeyErrors there).
    if PIER_FOUNDATION_SLUG in payloads and PIER_FOUNDATION_SLUG in glb_b64:
        emit(PIER_FOUNDATION_SLUG)
    blocks.append(f"<style>\n{viewer_css()}\n</style>")
    blocks.append(f"<script>\n{vendor_js()}\n{viewer_js()}\n</script>")
    return "\n".join(blocks)


def render_panel(name, cfg, d, image_uris, callouts, slug) -> str:
    letter = cfg["letter"]
    imgs = []
    for i, view in enumerate(cfg["views"]):
        cls = "hero" if i == 0 else "sub"
        cap = esc(cfg["captions"].get(view, ""))
        img = (
            f'<img src="{image_uris[view]}" '
            f'alt="{esc(cfg["title"])} — {esc(view)} view" loading="lazy">'
        )
        if i == 0:
            # Hero: the PNG stays in the DOM; the viewer (if the browser can run
            # it) drops a transparent canvas over it on demand. "Explore in 3D"
            # is the only affordance — no meta references, just the action.
            body = (
                f'<div class="viewer-slot" data-detail="{esc(slug)}">{img}'
                f'<button type="button" class="viewer-btn">Explore in 3D</button>'
                f"</div>"
            )
        else:
            body = img
        imgs.append(
            f'<figure class="{cls}">{body}<figcaption>{cap}</figcaption></figure>'
        )
    img_block = "\n".join(imgs)

    chips = "".join(
        f'<span class="chip">{esc(c["label"])}</span>' for c in callouts
    )

    why_title, why_body = cfg["why"]
    narrative = "".join(f"<li>{esc(n)}</li>" for n in cfg["narrative"])
    fieldnotes = "".join(
        f'<div class="fn"><strong>{esc(t)}</strong> {esc(b)}</div>'
        for t, b in cfg["fieldnotes"]
    )
    partial_note = cfg.get("partial_view_note")
    partial_block = (
        f'<div class="partial-note"><strong>Partial view</strong> {esc(partial_note)}</div>'
        if partial_note else ""
    )

    return f"""
  <section class="panel">
    <div class="panel-label">{letter} &middot; {esc(cfg['title'])}
      <span>&mdash; {esc(cfg['sub'])}</span></div>
    <div class="gallery">{img_block}</div>
    <div class="dims">
      <div class="dims-h">Model dimensions <span>(param-derived; pulled from the
      model’s callouts &mdash; no number retyped)</span></div>
      <div class="chips">{chips}</div>
    </div>
    {partial_block}
    <div class="panel-body">
      <div class="why">
        <div class="why-h">{esc(why_title)}</div>
        <p>{esc(why_body)}</p>
      </div>
      <ul class="narrative">{narrative}</ul>
    </div>
    <div class="fieldnotes">
      <div class="fn-h">Build notes &mdash; confirm on site</div>
      {fieldnotes}
    </div>
  </section>"""


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
        if step["why"] is not None:
            head += (" &mdash; authored build strategy, declared and "
                     "checked, never derived (why: "
                     f"{_html.escape(step['why'])})")
        subs = []
        for name, bom, fab in step["places"]:
            fab_txt = f" &mdash; fab: {_html.escape(fab)}" if fab else ""
            subs.append(f"<li>place {_html.escape(name)} "
                        f"({_html.escape(bom)}){fab_txt}</li>")
        for label in step["units"]:
            subs.append(f"<li>install {_html.escape(label)} &mdash; no "
                        f"fastener contract (a bond or connector install "
                        f"unit; its process facts live on the connection's "
                        f"own assumptions)</li>")
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


#: Pier-foundation zoom (view-coverage-directive.md): the three precast-pier
#: foundations are a HIGH install-complexity area (adjustable standoff post base,
#: end-grain air gap, block set on grade) that reads at a tiny, occluded scale in
#: the whole-platform iso/front — and they are exactly where the three blocking
#: ``foundation_capacity`` UNKNOWNs live. The directive's decision table therefore
#: demands a dedicated zoomed view; this panel renders one representative
#: foundation (identical hardware at all three piers) from the SAME compiled
#: platform parts — a scoped presentation view, no model/validation change. The
#: +Y launch leg is the DIFFERENT boulder anchor (Panel C).
_PIER_FOUNDATION_PARTS = ("leg tree +Y", "pier tree +Y", "post base pier tree +Y")

#: Slug for the Panel E interactive viewer slot / payload / GLB (a scoped 3D
#: viewer over the pier sub-assembly, additive to the existing stills).
PIER_FOUNDATION_SLUG = "pier_foundation"


#: Views rendered for the pier-foundation zoom (Panel E).
PIER_FOUNDATION_VIEWS = ("iso", "front")


def _pier_foundation_view_assembly(platform):
    """A view-only :class:`DetailAssembly` holding just one pier foundation's
    already-placed parts (leg base + precast block + standoff post base), so
    ``export_png`` auto-frames a zoom of the connection. Presentation only: it
    selects existing compiled parts, adds nothing and validates nothing."""
    from detailgen.assemblies.assembly import DetailAssembly

    by_name = {p.name: p for p in platform.assembly.parts}
    view = DetailAssembly("pier foundation")
    view.parts = [by_name[n] for n in _PIER_FOUNDATION_PARTS]
    return view


def pier_foundation_images(details: dict) -> dict:
    """Render the pier-foundation zoom PNGs (``{view: data_uri}``) from the
    scoped view assembly. Rendered here, in the render pass, and passed into
    :func:`build_html` — exactly like the per-detail panel images — so the
    presentation golden / prose guards can STUB the pixels and stay fast and
    render-free (the section prose is what those guards test)."""
    view = _pier_foundation_view_assembly(details["platform"])
    return {v: render_png_data_uri(view, v) for v in PIER_FOUNDATION_VIEWS}


def pier_foundation_payload(platform_payload: dict, details: dict) -> dict:
    """Scoped viewer payload for the Panel E interactive zoom: the three
    already-built platform part rows (leg + precast block + standoff post base),
    keyed by the SAME names their GLB nodes carry, so the viewer's raycast join
    works exactly as it does for a whole detail. Tooltip fields
    (item/dims/fab/specs) are the identical rows the platform panel shows — this
    reuses ``build_viewer_payload``'s output, never a second derivation. Only the
    ``explode`` offset is overridden to the clean VERTICAL pull-apart the
    standoff-gap view wants (``derive_vertical_stack_explode``): the platform
    overview's own contact-derived vectors splay these parts sideways, which
    reads wrong in an isolated three-part stack whose whole point is the gap."""
    from detailgen.rendering.web_viewer.explode import derive_vertical_stack_explode

    view = _pier_foundation_view_assembly(details["platform"])
    ev = derive_vertical_stack_explode(view)
    parts = {}
    for n in _PIER_FOUNDATION_PARTS:
        row = dict(platform_payload["parts"][n])
        row["explode"] = [float(v) for v in ev.get(n, (0.0, 0.0, 0.0))]
        parts[n] = row
    return {"slug": PIER_FOUNDATION_SLUG, "name": "Pier foundation",
            "parts": parts, "dimensions": []}


def pier_foundation_glb_b64(details: dict, tolerances) -> str:
    """Coarse web GLB (gzip+base64) of the scoped pier sub-assembly — the same
    artifact the per-detail panels ship, so the interactive Panel E decodes and
    renders through the identical viewer path."""
    view = _pier_foundation_view_assembly(details["platform"])
    return web_glb_b64(view, RENDERS / PIER_FOUNDATION_SLUG, tolerances)[0]


#: Stub URI when no rendered pier image is supplied (prose/golden guards). The
#: presentation golden strips every PNG URI to a placeholder, so a stubbed build's
#: text layer stays byte-identical to the fully-rendered document's.
_STUB_PNG = "data:image/png;base64,AAAA"


def render_pier_foundation_section(details: dict, site_report, images=None) -> str:
    """Panel E — the precast-pier foundations, zoomed (view-coverage-directive).

    The three tree-end / -Y legs land on precast pier blocks through adjustable
    standoff post bases; this panel zooms one so the standoff air gap, the block,
    and the leg seat read at a legible scale the whole-platform views can't show.

    It is also the plain-language home of the site's three blocking
    ``foundation_capacity`` findings: their capacity is NOT ANALYZED (engineer of
    record), so this reads **Structural capacity: UNKNOWN — UNRESOLVED** loudly and
    scoped — a represented foundation is never proven adequate. The count comes
    from the live ``site_report`` so the number can never drift from the model.

    ``images`` (``{view: data_uri}``) are the rendered zoom PNGs from
    :func:`pier_foundation_images`; when absent (prose/golden guards) a stub URI
    stands in — the section's prose and verdict render either way."""
    images = images or {}
    hero = images.get("iso", _STUB_PNG)
    sub = images.get("front", _STUB_PNG)

    n_cap = len(site_report.blocking)
    # The hero still doubles as an interactive 3D viewer slot (additive): the same
    # web_viewer machinery the per-detail panels use, scoped to the pier sub-
    # assembly, with a working vertical explode (block / base / leg pull apart).
    # The PNG stays in the DOM; the viewer drops a transparent canvas over it on
    # demand, and falls back to the still on a no-WebGL / print path.
    gallery = (
        f'<figure class="hero"><div class="viewer-slot" data-detail="{PIER_FOUNDATION_SLUG}">'
        f'<img src="{hero}" alt="Pier foundation — iso view" loading="lazy">'
        f'<button type="button" class="viewer-btn">Explore in 3D</button></div>'
        f'<figcaption>One precast-pier foundation: the 2x6 leg seats '
        f'in an adjustable galvanized standoff post base that holds the end grain '
        f'off the concrete, and the block spreads the load to grade. The two holes '
        f'are the post fasteners.</figcaption></figure>'
        f'<figure class="sub"><img src="{sub}" alt="Pier foundation — front view" '
        f'loading="lazy"><figcaption>Front: the standoff gap under the leg end and '
        f'the two post-base fasteners through the leg. Identical hardware at all '
        f'three pier legs.</figcaption></figure>'
    )

    return f"""
  <section class="panel">
    <div class="panel-label">E &middot; Pier Foundations
      <span>&mdash; three precast piers with adjustable standoff post bases</span></div>
    <div class="gallery">{gallery}</div>
    <div class="why warn">
      <div class="why-h">Structural capacity: UNKNOWN &mdash; UNRESOLVED</div>
      <p>Uplift, lateral, and soil-bearing capacity of all three pier foundations
      are <strong>NOT ANALYZED</strong> &mdash; that is an engineer-of-record
      question this document does not answer. A foundation drawn to real parts is
      REPRESENTED, never proven adequate; these are the {n_cap} findings that block
      a clean &ldquo;designed&rdquo; verdict for the whole site (see the site
      section). Have the pier sizing and bearing checked before anyone rides.</p>
    </div>
    <div class="panel-body">
      <div class="why">
        <div class="why-h">WHY A STANDOFF ON A BLOCK?</div>
        <p>The precast block spreads the leg load onto compacted grade; the
        adjustable standoff post base lifts the leg&rsquo;s end grain clear of the
        block so it never sits in water, and its thread takes up the small height
        differences between piers when the deck is leveled.</p>
      </div>
      <ul class="narrative">
        <li>Three 10.5&Prime; x 10.5&Prime; x 8&Prime; precast pier blocks, one under
        the -Y launch leg and one under each of the two short tree-end legs, set on
        compacted grade.</li>
        <li>A 3.5&Prime; x 3.5&Prime; adjustable galvanized standoff post base on each
        block; the leg seats in the saddle with a stand-off gap, fastened with the
        manufacturer&rsquo;s post screws and the block anchor.</li>
        <li>The +Y launch leg does NOT land here &mdash; it is epoxy-anchored to the
        boulder (Panel C). These three piers carry the other three legs.</li>
      </ul>
    </div>
    <div class="fieldnotes">
      <div class="fn-h">Build notes &mdash; confirm on site</div>
      <div class="fn"><strong>Field-verify seating + bearing on grade.</strong> The
      block is modeled as an exact prism on grade; a real precast pier is tapered
      with a cast-in saddle. Set each block level on firm, compacted soil and
      confirm it bears without rocking.</div>
      <div class="fn"><strong>Anchor + fasteners per the connector schedule.</strong>
      The post base&rsquo;s concrete anchor and post screws are field hardware on
      the buy-list line, not modeled as separate parts &mdash; install the count and
      embedment the manufacturer specifies.</div>
      <div class="fn"><strong>Capacity is not analyzed here.</strong> Nothing in this
      document sizes the piers for uplift, lateral load, or soil bearing. Treat the
      pier design as an open, engineer-of-record item.</div>
    </div>
  </section>"""


#: Preferred display titles for the coverage section; any detail not listed
#: falls back to its own ``Detail.name`` (so a future 5th detail is neither
#: dropped nor a KeyError — the reviewer's non-blocking minor).
_COVERAGE_TITLES = {
    "platform": "Zipline platform",
    "tree_attachment": "Tree-end attachment",
    "rock_anchor": "Rock anchor",
    "trolley_launch": "Trolley launch",
}


def render_coverage_section(details: dict, reports: dict) -> str:
    """Per-detail coverage matrices on the consolidated surface (Wave 3-1).

    One table per detail (every detail in ``details``, insertion order),
    sharing a single standing note. This is what keeps the document's
    "validated" claim honest: it names, per invariant family, exactly what each
    model analyzed — and marks Spatial intent, Functional use, Load-path
    representation, Structural capacity and Code compliance as UNKNOWN — NOT
    ANALYZED, so a clean interference sweep can't be overread as structural
    adequacy.

    ``reports`` are the per-detail verdicts validated ONCE by the caller from the
    exact compiled geometry, before the coarse web-GLB export re-tessellates the
    shared solids (which can bulge a cylinder's bbox and flip a tight dimension
    check to a spurious FAIL). Rendering from them — never re-validating here —
    keeps each matrix honest and the document reproducible; see ``build_html``."""
    from detailgen.validation.coverage import STANDING_NOTE, render_coverage_matrix_html

    tables = []
    for name, detail in details.items():
        report = reports[name]
        caption = _COVERAGE_TITLES.get(name, detail.name)
        tables.append(render_coverage_matrix_html(
            report, caption=caption, include_note=False))
    tables_html = "\n".join(tables)
    return f"""
  <section class="notes coverage-matrix">
    <h2>Coverage matrix &mdash; what each model actually analyzed</h2>
    <p class="lede">{esc(STANDING_NOTE)}</p>
    <div class="cov-grid">
      {tables_html}
    </div>
  </section>"""


#: Default (zipline) buy-list lede — kept as the fallback so the four-detail site
#: renders BYTE-IDENTICALLY (the embedded newlines + indentation match the former
#: inline literal exactly, so the golden is untouched). A single-detail consumer
#: passes its own one-line ``buy_lede``.
_ZIPLINE_BUY_LEDE = (
    "Everything to buy for the whole build. Each structural member\n"
    "      is listed once — the launch legs double as the grab-handle / strap-gate\n"
    "      posts and the tree-end beams, so they aren’t counted twice.")


def render_buylist(purchased, existing, *, buy_lede: str | None = None) -> str:
    rows = []
    for i, r in enumerate(purchased, start=1):
        rows.append(
            f'<tr><td class="n"><span class="bub">{i}</span></td>'
            f'<td class="qty">{r["qty"]}&times;</td>'
            f'<td class="item">{esc(r["item"])}</td>'
            f'<td class="buy">{esc(r["dimensions"])}</td></tr>'
        )
    buy_rows = "\n".join(rows)

    ex_rows = "\n".join(
        f'<tr><td class="qty">{r["qty"]}&times;</td>'
        f'<td class="item">{esc(r["item"])}</td>'
        f'<td class="buy">{esc(r["dimensions"])}</td></tr>'
        for r in existing
    )

    return f"""
  <section class="lower">
    <div class="legend">
      <h2>Buy list</h2>
      <p class="lede">{esc(buy_lede) if buy_lede else _ZIPLINE_BUY_LEDE}</p>
      <table>{buy_rows}</table>
    </div>
    <div class="existing">
      <h2>Existing &mdash; not purchased</h2>
      <p class="lede">Existing site features, shown so everything lands in the right
      place but not on the buy list.</p>
      <table>{ex_rows}</table>
    </div>
  </section>"""


def render_cutplan(cut_plans: dict, fab_notes: dict | None = None) -> str:
    """Render the "Consolidated stock & cut plan" section: for every lumber/
    decking profile, the sticks to buy and a per-stick cut map. ADDS to the
    buy list above — the same lines still show up there with their raw
    quantities; this section says how to actually get those quantities out
    of full-length stock.

    ``fab_notes`` (``{(profile, source): note}``, from :func:`cutlist_fab_notes`)
    names the fabrication operations each cut carries beyond a plain crosscut —
    the trunk notch, in v1. A cut with a note renders it inline so the cut list
    describes the SAME operations the geometry folds (retro R28). Omitted/empty:
    plain length only, the pre-note behaviour."""
    from detailgen.core.cutplan import KERF_MM, END_TRIM_MM
    from detailgen.core.units import fmt_in, feet

    if not cut_plans:
        return ""

    fab_notes = fab_notes or {}

    def fmt_ft(mm: float) -> str:
        ft = feet(mm)
        return f"{ft:.0f} ft" if abs(ft - round(ft)) < 1e-6 else f'{fmt_in(mm, 1)}'

    def cut_label(source: str) -> str:
        # "platform: joist 0" -> "joist 0" (the profile/detail are already
        # named by the surrounding heading; repeating them per cut is noise).
        return source.split(": ", 1)[-1]

    profile_blocks = []
    grand_purchased = 0.0
    grand_waste = 0.0

    for profile in sorted(cut_plans):
        plan = cut_plans[profile]
        grand_purchased += plan.total_purchased_mm
        grand_waste += plan.total_waste_mm

        by_length: dict[float, int] = {}
        for s in plan.sticks:
            by_length[s.stock_length_mm] = by_length.get(s.stock_length_mm, 0) + 1
        buy_line = "; ".join(
            f"{by_length[L]}&times; @ {fmt_ft(L)}" for L in sorted(by_length)
        )

        stick_rows = []
        for i, s in enumerate(plan.sticks, start=1):
            cut_strs = []
            for c in s.cuts:
                piece = f"{fmt_in(c.length_mm)} {esc(cut_label(c.source))}"
                note = fab_notes.get((profile, c.source))
                if note:
                    piece += f" &mdash; {esc(note)}"
                cut_strs.append(piece)
            cuts_str = ", ".join(cut_strs)
            stick_rows.append(
                f'<tr><td class="n"><span class="bub">{i}</span></td>'
                f'<td class="buy">{esc(fmt_ft(s.stock_length_mm))}</td>'
                f'<td class="item">{cuts_str}</td>'
                f'<td class="qty">{esc(fmt_in(s.waste_mm, 1))}</td></tr>'
            )

        profile_blocks.append(f"""
    <div class="cutprofile">
      <h3>{esc(profile)} &mdash; buy {buy_line}</h3>
      <table>
        <tr><th>Stick</th><th>Stock</th><th>Cuts (source)</th><th>Waste</th></tr>
        {"".join(stick_rows)}
      </table>
    </div>""")

    waste_pct = (grand_waste / grand_purchased * 100) if grand_purchased else 0.0

    return f"""
  <section class="notes cutplan">
    <h2>Consolidated stock &amp; cut plan</h2>
    <p class="lede">Every 2x/5&#8260;4 buy-list line above, packed into full-length
    sticks with a cut map per stick &mdash; buy the sticks below instead of
    ordering each length separately.</p>
    <div class="formula">
      <strong>Assumptions</strong>
      Kerf {fmt_in(KERF_MM, 3)} per interior saw cut &middot; {fmt_in(END_TRIM_MM, 2)}
      end-trim per stick (squares one end before the first measured cut) &middot;
      stock lengths 8/10/12/16 ft.<br>
      A stick whose cuts use its FULL length (no leftover to spare) isn&rsquo;t
      charged kerf/trim &mdash; that sub-1/8&Prime; shortfall on the last piece is
      inside ordinary cutting tolerance, not a reason to buy a longer, pricier stick.
    </div>
    {"".join(profile_blocks)}
    <div class="cutplan-totals">Total purchased: {fmt_ft(grand_purchased) if grand_purchased else "0 ft"}
    &middot; total waste: {fmt_in(grand_waste, 1)} ({waste_pct:.0f}%)</div>
  </section>"""


def render_fieldfit() -> str:
    items = "".join(
        f"<li><strong>{esc(t)}.</strong> {esc(b)}</li>" for t, b in FIELD_FIT
    )
    return f"""
  <section class="notes">
    <h2>Field-fit &amp; assumptions &mdash; check on site</h2>
    <p class="lede">Dimensions and choices to confirm on site before cutting or
    ordering.</p>
    <div class="formula">
      <strong>Deck height &mdash; set on site</strong>
      DECK = LOADED BAR HT &minus; KID REACH + 4&Prime;<br>
      &rarr; hang a kid on the bar, measure, then cut. Model uses 29&Prime;; expect 28&ndash;30&Prime;.
    </div>
    <ol>{items}</ol>
    <div class="build-notes">
      <h3>Before first ride</h3>
      <ul>
        <li>Adult bounce test on the deck <em>and</em> a ~200 lb lean test on the rails.</li>
        <li>Mesh infill closes every gap over 4&Prime;: both railed sides, below the
        bottom rail, and around the trunk.</li>
        <li>Seasonal: check the anchor nuts, confirm the beams still clear the growing trunk, top up the mulch.</li>
      </ul>
    </div>
  </section>"""


#: Default (zipline) footer strings — the four-detail site renders unchanged. A
#: single-detail consumer overrides these so the sheet closes with ITS byline and
#: count, not the zipline's (never another detail's identity).
_ZIPLINE_FOOTER = {
    "byline": "Witten Dacha &middot; Kids&rsquo; Zipline",
    "tagline": ("Drawings &amp; numbers generated from 4 parametric models "
                "&mdash; verdict by invariant family in the coverage matrix below"),
    "regen_cmd": ".venv/bin/python scripts/consolidated_report.py",
    "render_note": "renders: VTK offscreen (per-part material color)",
}


def render_footer(manifests, *, byline: str | None = None, tagline: str | None = None,
                  regen_cmd: str | None = None, render_note: str | None = None) -> str:
    f = _ZIPLINE_FOOTER
    byline = byline or f["byline"]
    tagline = tagline or f["tagline"]
    regen_cmd = regen_cmd or f["regen_cmd"]
    render_note = render_note or f["render_note"]

    versions = {}
    for m in manifests.values():
        versions.update(m.get("build", {}).get("versions", {}))
    vstr = " &middot; ".join(f"{k} {esc(v)}" for k, v in sorted(versions.items()))

    hashes = "".join(
        f'<tr><td class="item">{esc(name)}</td>'
        f'<td class="hash">{esc(m["build"]["assembly_hash"][:16])}</td></tr>'
        for name, m in manifests.items()
    )

    return f"""
  <section class="provenance">
    <h2>Provenance &mdash; this document is reproducible</h2>
    <p class="lede">Each detail’s whole-assembly geometry content-hash. Re-run the
    generator; if the geometry is unchanged, these hashes match. Regenerate with
    <code>{esc(regen_cmd)}</code>.</p>
    <table class="prov">
      <tr><th>Detail (model)</th><th>Assembly geometry hash</th></tr>
      {hashes}
    </table>
    <div class="stamp">Toolchain: {vstr} &middot; generated {DOC_DATE} &middot;
    {render_note}</div>
  </section>
  <footer>
    <span>{byline}</span>
    <span>{tagline}</span>
    <span>Not engineered drawings &mdash; verify on site</span>
  </footer>"""


HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zipline Launch Platform — Model-Backed Build Document</title>
<style>
  :root{
    --paper:#f6f5f0; --sheet:#fdfcf9; --ink:#26282a; --line:#3a3d40; --muted:#767a80;
    --faint:rgba(38,40,42,0.14); --grid:rgba(71,105,140,0.10); --acc:#c85a24;
    --acc-soft:rgba(200,90,36,0.10); --steel:#47698c; --chipbg:rgba(71,105,140,0.10);
  }
  @media (prefers-color-scheme: dark){:root{
    --paper:#16181b; --sheet:#1d2024; --ink:#e7e5df; --line:#cfccc4; --muted:#9297a0;
    --faint:rgba(231,229,223,0.16); --grid:rgba(127,163,199,0.08); --acc:#e8834e;
    --acc-soft:rgba(232,131,78,0.12); --steel:#7fa3c7; --chipbg:rgba(127,163,199,0.12);
  }}
  :root[data-theme="dark"]{
    --paper:#16181b; --sheet:#1d2024; --ink:#e7e5df; --line:#cfccc4; --muted:#9297a0;
    --faint:rgba(231,229,223,0.16); --grid:rgba(127,163,199,0.08); --acc:#e8834e;
    --acc-soft:rgba(232,131,78,0.12); --steel:#7fa3c7; --chipbg:rgba(127,163,199,0.12);
  }
  :root[data-theme="light"]{
    --paper:#f6f5f0; --sheet:#fdfcf9; --ink:#26282a; --line:#3a3d40; --muted:#767a80;
    --faint:rgba(38,40,42,0.14); --grid:rgba(71,105,140,0.10); --acc:#c85a24;
    --acc-soft:rgba(200,90,36,0.10); --steel:#47698c; --chipbg:rgba(71,105,140,0.10);
  }
  *{box-sizing:border-box}
  body{margin:0; background:var(--paper); color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.5;
    padding:clamp(12px,3vw,40px);}
  .sheet{max-width:1140px; margin:0 auto; background:var(--sheet);
    border:2px solid var(--ink); box-shadow:0 12px 32px rgba(0,0,0,0.10);}
  header{display:flex; flex-wrap:wrap; border-bottom:2px solid var(--ink);}
  .tb-title{flex:1 1 340px; padding:20px 24px 16px; border-right:1px solid var(--faint);}
  .tb-title .eyebrow{font-family:ui-monospace,Menlo,monospace; font-size:11px;
    letter-spacing:0.14em; color:var(--acc); text-transform:uppercase; margin-bottom:6px;}
  .tb-title h1{margin:0; font-size:clamp(22px,3.4vw,30px); font-weight:800;
    letter-spacing:-0.015em;}
  .tb-title p{margin:8px 0 0; color:var(--muted); font-size:13.5px; max-width:52ch;}
  .tb-meta{flex:1 1 320px; display:grid; grid-template-columns:1fr 1fr;
    font-family:ui-monospace,Menlo,monospace; font-size:11px;}
  .tb-meta>div{padding:10px 16px; border-left:1px solid var(--faint);
    border-top:1px solid var(--faint);}
  .tb-meta>div:nth-child(-n+2){border-top:none;}
  .tb-meta dt{letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin:0 0 2px;}
  .tb-meta dd{margin:0; font-size:12px;}
  .status-ok{color:var(--acc); font-weight:700;}
  /* Reader-facing verdict headline (owner directive §3): the per-family
     breakdown is the primary top-line; CLEAN is a demoted internal note. */
  .tb-meta>div.tb-verdict{grid-column:1 / -1;}
  .tb-verdict dd.status-ok{color:inherit; font-weight:400;}
  .verdict-headline{list-style:none; margin:4px 0 0; padding:0; display:grid;
    grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:0 16px;}
  .vh-row{display:flex; justify-content:space-between; gap:10px; align-items:baseline;
    padding:3px 0; border-bottom:1px solid var(--faint);}
  .vh-fam{color:var(--muted); font-weight:400; text-transform:none; letter-spacing:0.01em;}
  .vh-verdict{font-weight:700; white-space:nowrap;}
  .vh-verdict.cov-pass{color:var(--acc);}
  .vh-verdict.cov-fail{color:#b00020;}
  .vh-verdict.cov-unknown{color:var(--muted); font-style:italic;}
  .verdict-note{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
    text-transform:none; letter-spacing:normal; font-weight:400; color:var(--muted);
    font-size:11px; margin:9px 0 0; line-height:1.45;}
  .verdict-internal{color:var(--ink);}
  .panel{border-bottom:2px solid var(--ink); padding:18px 22px 22px;}
  .panel-label{font-family:ui-monospace,Menlo,monospace; font-size:12px; font-weight:700;
    letter-spacing:0.14em; text-transform:uppercase; margin-bottom:14px;}
  .panel-label span{color:var(--muted); font-weight:400; letter-spacing:0.04em;
    text-transform:none;}
  .gallery{display:grid; grid-template-columns:1.6fr 1fr; gap:12px; align-items:start;}
  .gallery .hero{grid-row:span 2;}
  figure{margin:0; border:1px solid var(--faint); background:var(--paper);}
  figure img{width:100%; height:auto; display:block;}
  figcaption{font-size:11.5px; color:var(--muted); padding:7px 10px 9px; line-height:1.35;}
  @media (max-width:760px){.gallery{grid-template-columns:1fr;} .gallery .hero{grid-row:auto;}}
  .dims{margin:14px 0 4px; padding:12px 14px; border:1px solid var(--faint);
    background:var(--acc-soft);}
  .dims-h{font-family:ui-monospace,Menlo,monospace; font-size:10.5px; font-weight:700;
    letter-spacing:0.12em; text-transform:uppercase; color:var(--acc); margin-bottom:8px;}
  .dims-h span{color:var(--muted); font-weight:400; text-transform:none; letter-spacing:0.02em;}
  .chips{display:flex; flex-wrap:wrap; gap:6px;}
  .chip{font-family:ui-monospace,Menlo,monospace; font-size:11.5px; padding:3px 9px;
    background:var(--chipbg); border:1px solid var(--faint); border-radius:3px;
    color:var(--ink); white-space:nowrap;}
  .partial-note{margin:10px 0 4px; padding:8px 12px; border:1px dashed var(--acc);
    font-size:12.5px; color:var(--ink);}
  .partial-note strong{font-family:ui-monospace,Menlo,monospace; font-size:10px;
    font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:var(--acc);
    margin-right:6px;}
  .siteoverview .gallery{grid-template-columns:1.4fr 1fr;}
  .overview-note{margin:14px 0; padding:10px 14px; border:1px solid var(--faint);
    background:var(--paper); font-size:12.5px; color:var(--ink);}
  .overview-note.warn{border:1.5px dashed var(--acc); background:var(--acc-soft);}
  .overview-note strong{display:block; font-family:ui-monospace,Menlo,monospace;
    font-size:10.5px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;
    color:var(--acc); margin-bottom:5px;}
  .panel-body{display:grid; grid-template-columns:1fr 1.4fr; gap:16px; margin-top:14px;}
  @media (max-width:760px){.panel-body{grid-template-columns:1fr;}}
  .why{border:1.5px solid var(--acc); padding:12px 14px; align-self:start;}
  /* Loud, full-width variant — the honestly-blocked capacity verdict (Panel E). */
  .why.warn{border:2px dashed var(--acc); background:var(--acc-soft); margin:14px 0;}
  .why.warn .why-h{font-size:12px; letter-spacing:0.1em; text-transform:uppercase;}
  .why-h{font-family:ui-monospace,Menlo,monospace; font-size:11px; font-weight:700;
    letter-spacing:0.08em; color:var(--acc); margin-bottom:6px;}
  .why p{margin:0; font-size:13px;}
  ul.narrative{margin:0; padding-left:18px; font-size:13.5px;}
  ul.narrative li{margin-bottom:8px;}
  .fieldnotes{margin-top:16px; padding-top:14px; border-top:1px dashed var(--faint);}
  .fn-h{font-family:ui-monospace,Menlo,monospace; font-size:10.5px; font-weight:700;
    letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin-bottom:10px;}
  .fn{font-size:13px; margin-bottom:8px; padding-left:14px; border-left:2px solid var(--acc);}
  .fn strong{color:var(--ink);}
  .lower{display:grid; grid-template-columns:1.35fr 1fr; border-bottom:2px solid var(--ink);}
  @media (max-width:760px){.lower{grid-template-columns:1fr;}}
  .legend{padding:20px 22px;} .existing{padding:20px 22px; border-left:2px solid var(--ink);}
  @media (max-width:760px){.existing{border-left:none; border-top:2px solid var(--ink);}}
  h2{font-family:ui-monospace,Menlo,monospace; font-size:12px; font-weight:700;
    letter-spacing:0.12em; text-transform:uppercase; margin:0 0 6px;}
  h3{font-family:ui-monospace,Menlo,monospace; font-size:11px; font-weight:700;
    letter-spacing:0.1em; text-transform:uppercase; margin:16px 0 6px;}
  .lede{font-size:12px; color:var(--muted); margin:0 0 12px; max-width:56ch;}
  table{border-collapse:collapse; width:100%; font-size:13px;}
  td,th{padding:6px 10px 6px 0; vertical-align:top; border-top:1px solid var(--faint); text-align:left;}
  tr:first-child td, tr:first-child th{border-top:none;}
  td.n{width:30px;} td.qty{width:34px; font-family:ui-monospace,Menlo,monospace; color:var(--muted);}
  th{font-family:ui-monospace,Menlo,monospace; font-size:10px; letter-spacing:0.1em;
    text-transform:uppercase; color:var(--muted);}
  .bub{display:inline-flex; width:21px; height:21px; border:1.5px solid var(--acc);
    border-radius:50%; color:var(--acc); font-family:ui-monospace,Menlo,monospace;
    font-size:11px; font-weight:700; align-items:center; justify-content:center;}
  td.item{font-weight:600; padding-right:14px;}
  td.buy{color:var(--muted); font-size:12.5px;}
  .notes{padding:20px 22px; border-bottom:2px solid var(--ink);}
  .formula{border:1.5px solid var(--acc); background:var(--acc-soft); padding:12px 14px;
    font-family:ui-monospace,Menlo,monospace; font-size:12.5px; margin:8px 0 16px;}
  .formula strong{display:block; letter-spacing:0.08em; font-size:10.5px;
    text-transform:uppercase; color:var(--acc); margin-bottom:6px;}
  .notes ol{margin:0; padding-left:20px; font-size:13px;}
  .notes ol li{margin-bottom:8px;} .notes ol li::marker{color:var(--acc); font-weight:700;}
  .cutprofile{margin-top:18px;} .cutprofile:first-of-type{margin-top:4px;}
  .cutprofile h3{margin:0 0 6px;}
  .cutplan-totals{margin-top:14px; font-family:ui-monospace,Menlo,monospace;
    font-size:11.5px; color:var(--muted);}
  .build-notes ul{font-size:13px; padding-left:18px;} .build-notes li{margin-bottom:6px;}
  .provenance{padding:20px 22px; border-bottom:2px solid var(--ink);}
  table.prov td.hash, .hash{font-family:ui-monospace,Menlo,monospace; color:var(--steel);}
  .stamp{margin-top:12px; font-family:ui-monospace,Menlo,monospace; font-size:10.5px;
    color:var(--muted); letter-spacing:0.04em;}
  code{font-family:ui-monospace,Menlo,monospace; font-size:11.5px; background:var(--chipbg);
    padding:1px 5px; border-radius:3px;}
  footer{padding:12px 22px; display:flex; justify-content:space-between; gap:12px;
    flex-wrap:wrap; font-family:ui-monospace,Menlo,monospace; font-size:10.5px;
    letter-spacing:0.08em; text-transform:uppercase; color:var(--muted);}
  .coverage-matrix .cov-grid{display:grid; grid-template-columns:1fr 1fr; gap:16px;
    margin-top:12px;}
  table.coverage{border-collapse:collapse; width:100%; font-size:11.5px;}
  table.coverage caption{text-align:left; font-weight:700; font-size:12.5px;
    padding-bottom:4px; letter-spacing:0.02em;}
  table.coverage th, table.coverage td{border:1px solid var(--ink); padding:3px 7px;
    text-align:left; vertical-align:top;}
  table.coverage th{background:var(--chipbg); font-size:10px; text-transform:uppercase;
    letter-spacing:0.04em;}
  table.coverage td.cov-pass{color:var(--acc); font-weight:700;}
  table.coverage td.cov-fail{color:#b00020; font-weight:700;}
  table.coverage td.cov-unknown{color:var(--muted); font-weight:700; font-style:italic;}
  .coverage-matrix .lede{font-size:12px; color:var(--muted);}
  @media (max-width:720px){ .coverage-matrix .cov-grid{grid-template-columns:1fr;} }
  .visual-review .vr-open-count{font-size:13px; margin:6px 0 12px;}
  .visual-review .dims{margin:12px 0 4px;}
  table.coverage td.vr-crit, table.coverage td.vr-open{color:#b00020; font-weight:700;}
  table.coverage td.vr-high, table.coverage td.vr-med{color:var(--acc); font-weight:700;}
  table.coverage td.vr-low{color:var(--muted); font-weight:700;}
  table.coverage td.vr-resolved{color:var(--muted);}
  table.coverage td.vr-fixed{color:#1a7f37; font-weight:700;}
</style>
</head>
<body>"""


def process_detail(name, d):
    """Return ``(manifest, images, reused)`` for one detail, hash-gated.

    The four models are unchanged run-to-run, and every ``outputs/consolidated/
    renders/<name>/`` already holds a manifest + PNGs from the last CLEAN
    render. So: build the assembly (``assemble()`` only — component solids +
    placement, no validation) and compute ``build_manifest``'s
    ``assembly_hash`` directly (the SAME call ``export_manifest`` makes
    during a real render). If that hash equals the on-disk manifest's
    ``assembly_hash``, the prior render still describes this EXACT geometry
    — and ``Detail.render`` only writes after a CLEAN validation report, so
    that manifest + those PNGs carry the prior CLEAN verdict and correct
    imagery forward. Reuse them and skip validation/render entirely. On any
    hash mismatch (or missing manifest/PNG) fall back to the full gated
    ``d.render()`` + fresh PNGs for that detail."""
    from detailgen.core.buildinfo import build_manifest

    outd = RENDERS / name
    outd.mkdir(parents=True, exist_ok=True)
    manifest_path = outd / "detail.manifest.json"
    views = PANELS[name]["views"]

    live_hash = build_manifest(d.assembly)["assembly_hash"]

    existing_manifest = None
    if manifest_path.exists():
        try:
            existing_manifest = json.loads(manifest_path.read_text())
        except Exception:
            existing_manifest = None

    pngs_present = all((outd / f"{name}_{v}.png").exists() for v in views)
    on_disk_hash = (
        (existing_manifest or {}).get("build", {}).get("assembly_hash")
    )

    if existing_manifest is not None and on_disk_hash == live_hash and pngs_present:
        images = {v: png_data_uri(outd / f"{name}_{v}.png") for v in views}
        print(f"  {name}: REUSE — hash {live_hash[:12]} matches on-disk render "
              f"(skipped validate + render)")
        return existing_manifest, images, True

    reason = "no manifest" if existing_manifest is None else (
        "no PNGs" if not pngs_present else "geometry hash changed")
    # DOCUMENTATION render (ungated): the consolidated build document is a
    # documentation surface, not a certified artifact export, so it must DRAW an
    # honestly-blocked detail and SURFACE its verdict (e.g. "Structural capacity:
    # UNKNOWN — UNRESOLVED", which build_html emits from the coverage matrix)
    # rather than crash at require_clean. Certified export to outputs/ stays behind
    # the gated Detail.render(); this path never certifies (base.py).
    d.render_documentation(outd)  # ungated: GLB + manifest + STEP + report + coverage
    manifest = json.loads(manifest_path.read_text())
    images = {v: render_png_data_uri(d.assembly, v) for v in views}

    # manifest["build"]["assembly_hash"] (computed post-export, via
    # export_manifest -> build_manifest) and live_hash (computed pre-export,
    # directly via build_manifest above) are two calls to the identical
    # function against the identical assembly state, so this should always
    # hold by construction. Kept as an assertion — not a tautology in
    # practice, since it's the regression check that would catch a future
    # change making build_manifest depend on prior export/hash history
    # (exactly the bug core.buildinfo.geometry_hash's Clean_s guards against
    # for the local digests build_manifest is built from).
    assert manifest["build"]["assembly_hash"] == live_hash, (
        f"{name}: manifest assembly_hash diverged from a fresh recompute — "
        "build_manifest should be export-order-independent (core/buildinfo)"
    )
    print(f"  {name}: RENDER ({reason}) — assembly_hash {live_hash[:12]}")
    return manifest, images, False


# --------------------------------------------------------------------------- #
# Site overview: compose all four details into one shared frame (a VIEW, not
# a validated assembly — see _site_overview.py's module docstring). Hash-gated
# the same way process_detail is, but there is no Detail/require_clean gate
# here (the composed DetailAssembly is never validated) — the gate is simply
# "does the composed geometry hash match the on-disk render."
# --------------------------------------------------------------------------- #
SITE_OVERVIEW_VIEWS = ("iso", "top")


def process_site_overview(details: dict):
    """Build the composed site-overview assembly and hash-gate its PNG
    renders. Returns ``(overview, manifest, images, reused)``."""
    from detailgen.core.buildinfo import build_manifest

    overview = _site_overview.build_site_overview(details)
    outd = RENDERS / "site_overview"
    outd.mkdir(parents=True, exist_ok=True)
    manifest_path = outd / "site_overview.manifest.json"

    live_hash = build_manifest(overview.assembly)["assembly_hash"]

    existing_manifest = None
    if manifest_path.exists():
        try:
            existing_manifest = json.loads(manifest_path.read_text())
        except Exception:
            existing_manifest = None

    pngs_present = all(
        (outd / f"site_overview_{v}.png").exists() for v in SITE_OVERVIEW_VIEWS
    )
    on_disk_hash = (existing_manifest or {}).get("assembly_hash")

    if existing_manifest is not None and on_disk_hash == live_hash and pngs_present:
        images = {v: png_data_uri(outd / f"site_overview_{v}.png") for v in SITE_OVERVIEW_VIEWS}
        print(f"  site_overview: REUSE — hash {live_hash[:12]} matches on-disk render")
        return overview, existing_manifest, images, True

    images = {v: render_png_data_uri(overview.assembly, v) for v in SITE_OVERVIEW_VIEWS}
    manifest = {
        "assembly_hash": live_hash,
        "kept_counts": overview.kept_counts,
        "dropped_counts": overview.dropped_counts,
    }
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"  site_overview: RENDER — assembly_hash {live_hash[:12]}")
    return overview, manifest, images, False


def render_site_overview(overview, images, details: dict) -> str:
    """The "Site overview" section: composed hero + plan-view renders, the
    placement table (transform basis + confidence per detail), the dedup
    rule + what it hid, the binding VIEW-NOT-VALIDATED wording, and the
    KNOWN Y-DIVERGENCE note the dedup rule would otherwise silently hide."""
    y = _site_overview.tree_vs_platform_beam_y(details)

    imgs = []
    for i, view in enumerate(SITE_OVERVIEW_VIEWS):
        cls = "hero" if i == 0 else "sub"
        cap = "Isometric — all four details in one shared frame." if view == "iso" \
            else "Plan (top) view — beam-run (X) and deck-width (Y) axes read here."
        imgs.append(
            f'<figure class="{cls}"><img src="{images[view]}" '
            f'alt="Site overview — {esc(view)} view" loading="lazy">'
            f'<figcaption>{esc(cap)}</figcaption></figure>'
        )
    img_block = "\n".join(imgs)

    rows = "".join(
        f'<tr><td class="item">{esc(p.detail)}</td>'
        f'<td>{p.basis}</td>'
        f'<td class="qty">{esc(p.confidence)}</td>'
        f'<td class="buy">{p.note}</td></tr>'
        for p in overview.placements
    )

    dropped_by_detail: dict[str, list[str]] = {}
    for d in overview.dropped:
        dropped_by_detail.setdefault(d["detail"], []).append(d["name"])
    hidden_line = "; ".join(
        f"{name} {len(parts)} ({', '.join(parts)})"
        for name, parts in dropped_by_detail.items()
    ) or "none"

    y_note = ""
    if y is not None:
        y_note = f"""
    <div class="overview-note warn">
      <strong>Known Y-divergence &mdash; not resolved here</strong>
      The tree connection's own beam geometry is drawn trunk-tangent, at
      Y=&plusmn;{y['tree_inner_y_in']:.1f}&Prime;/&plusmn;{y['tree_outer_y_in']:.1f}&Prime; &mdash;
      the dedup rule below hides that stub in favor of the platform's
      canonical beam (Y=&plusmn;{y['platform_outer_y_in']:.2f}&Prime;), so this is NOT the
      same Y position. That is an open design decision awaiting architect
      sign-off (see the provenance/build ledger) &mdash; this view shows only
      the platform's real member on purpose, not a silent resolution of the
      divergence.
    </div>"""

    return f"""
  <section class="panel siteoverview">
    <div class="panel-label">SITE &middot; Whole-Assembly Overview
      <span>&mdash; all four details composed into one shared frame</span></div>
    <div class="gallery">{img_block}</div>
    <div class="overview-note">
      <strong>View, not validated</strong> This composition is REPRESENTED for orientation;
      cross-detail validation is NOT ANALYZED (the overlap semantics between two
      details' context copies of the same physical feature aren't defined yet).
    </div>
    <div class="dims">
      <div class="dims-h">Placements <span>(site frame = the platform detail's own
      world frame; every other detail's placement below is derived, not measured)</span></div>
      <table><tr><th>Detail</th><th>Basis</th><th>Confidence</th><th>Field-verify note</th></tr>
      {rows}</table>
    </div>{y_note}
    <div class="overview-note">
      <strong>De-duplication rule</strong> The platform detail is always
      canonical. A part from another detail is hidden here if it carries
      <code>stub_of()</code> partial-member metadata, if it is an existing/
      context body (source marked existing/not-purchased) of a type the
      platform also models (the trunk, the boulder), or if it is structural
      lumber outside the platform detail (the same double-count guard the
      buy list applies) &mdash; never a hand list of part names. Existing
      hardware unique to one detail (the zipline cable, trolley wheel,
      hanger, grab bar) is kept. Hidden this render: {hidden_line}.
    </div>
  </section>"""


# --------------------------------------------------------------------------- #
# Site overview — driven by the ONE compiled site model. Placement/provenance
# comes from the model's own site_facts(); the composed render goes ONLY through
# the site-level render gate (blocked while the site is dirty — then this section
# lists the open findings, which are SYSTEM-derived, not a hand-written caveat);
# the coverage matrix is the site's own; and the divergence section is
# FINDINGS-DRIVEN, so whatever the four subsystems disagree on surfaces here as
# SYSTEM findings. Today those are the two launch-leg/end-joist bearing gaps, the
# pre-existing hanging-hardware island, and the grab-bar height — the deferred
# structure-design questions the site is deliberately left dirty to hold open.
#
# The OLD render_site_overview / process_site_overview above are retained (not
# called by main anymore) because tests/test_site_overview.py still exercises the
# _site_overview.py composition machinery through them (including its own
# tree_vs_platform_beam_y hand callout, now deprecated — see that function).
# --------------------------------------------------------------------------- #
def render_site_model_section(site, report, renders_dir=None) -> str:
    """The site-overview section, driven by the compiled :class:`SiteDetail`.

    ``report`` is the site's validation verdict, computed ONCE by the caller from
    the exact compiled geometry (before the coarse web-GLB export re-tessellates
    the shared solids). Rendering from it — rather than re-validating the possibly
    mutated ``site`` here — keeps the findings honest and reproducible; see
    ``build_html``.

    ``renders_dir`` is where the gated composed render would write — unused today
    because the site is dirty and the gate blocks.

    There is no hand-written divergence caveat: the section lists whatever the
    report holds, so every shared-member disagreement is a SYSTEM finding the one
    model derives, never a caption a person maintains by hand."""
    from detailgen.validation.coverage import (
        STANDING_NOTE, render_coverage_matrix_html)

    # -- placement / provenance table (the model's own site_facts()) ----------
    place_rows = []
    for sub in site.doc.subsystems:
        frame = site._transforms[sub.id]
        origin = tuple(round(c, 2) for c in frame.origin)
        conf = sub.confidence or "EXACT"
        conf_cls = "cov-pass" if conf == "EXACT" else "cov-unknown"
        place_rows.append(
            f'<tr><td class="item">{esc(sub.id)}</td>'
            f'<td class="buy">{esc(origin)}</td>'
            f'<td class="qty {conf_cls}">{esc(conf)}</td>'
            f'<td class="buy">{esc(sub.basis)}</td></tr>'
        )
    place_table = "".join(place_rows)

    # -- composed render: ONLY via the site-level gate ------------------------
    if report.ok:
        # (Not reached today — the site is dirty. When it goes clean, the
        # composed render is produced through the gate, e.g. site.render().)
        render_block = (
            '<div class="overview-note"><strong>Composed render</strong> '
            'The whole-site model validates CLEAN; the composed render is '
            'produced through the site-level gate.</div>')
    else:
        open_items = "".join(
            f'<li><code>{esc(f.check)}</code> {esc(f.subject)}'
            + (f' &mdash; {esc(f.detail)}' if f.detail else '')
            + '</li>'
            for f in report.blocking
        )
        render_block = f"""
    <div class="overview-note warn">
      <strong>Composed render BLOCKED &mdash; site-level gate</strong>
      A view renders only when the WHOLE site model is clean (one model, one
      verdict; rendering a clean-looking view of a model with an open
      contradiction is the dishonesty the site model exists to kill). The site
      is DIRTY: {len(report.blocking)} open finding(s), SYSTEM-derived (not a
      hand-written caveat) — each is listed below with the member it concerns:
      <ul class="narrative">{open_items}</ul>
    </div>"""

    # -- coverage matrix (the site's own, NOT re-derived per view) ------------
    cov = render_coverage_matrix_html(
        report, caption="Whole site — one model", include_note=False)

    # -- divergence section: FINDINGS-DRIVEN (system) + hand tree callout -----
    div_rows = "".join(
        f'<tr><td class="item">{esc(f.check)}</td>'
        f'<td class="buy">{esc(f.subject)}</td>'
        f'<td class="buy">{esc(f.detail)}</td></tr>'
        for f in report.blocking
    ) or '<tr><td class="buy" colspan="3">no open divergence findings</td></tr>'

    views_line = ", ".join(
        f"{v.name} ({len(v.parts())} parts)" for v in site.views()
    ) or "none"

    return f"""
  <section class="panel siteoverview">
    <div class="panel-label">SITE &middot; Whole-Assembly Overview
      <span>&mdash; ONE compiled site model (subsystems composed, shared members
      are one node)</span></div>
    <div class="overview-note">
      <strong>One model, not a composed picture</strong> This section is driven
      by the compiled site model (<code>details/site.spec.yaml</code>): a member
      two subsystems share is ONE node, so cross-subsystem disagreement is
      surfaced by the system, not papered over. Views declared on the model:
      {esc(views_line)}.
    </div>
    <div class="dims">
      <div class="dims-h">Placements <span>(declared model facts &mdash;
      site_facts(): basis + EXACT/ASSUMED confidence, site frame = the platform
      subsystem's frame)</span></div>
      <table><tr><th>Subsystem</th><th>Site origin (mm)</th><th>Confidence</th>
      <th>Basis</th></tr>{place_table}</table>
    </div>{render_block}
    <div class="dims">
      <div class="dims-h">Coverage <span>(the site's one verdict &mdash; a view
      presents it, never re-derives it)</span></div>
      {cov}
      <p class="lede">{esc(STANDING_NOTE)}</p>
    </div>
    <div class="dims">
      <div class="dims-h">Divergence findings <span>(SYSTEM-derived from the one
      model &mdash; every shared-member disagreement across the four
      subsystems)</span></div>
      <table><tr><th>Check</th><th>Subject</th><th>Detail</th></tr>{div_rows}</table>
    </div>
  </section>"""


def copy_to_vault(html_path: Path) -> None:
    """Copy the generated document into the owner's Obsidian vault. OFF by
    default and only ever reached when ``--vault-copy`` is passed — running the
    generator must not write outside this repo unless explicitly asked, so an
    unrelated repo isn't dirtied on every build. The copy is a pure side-effect;
    the document at ``html_path`` is already complete and byte-stable without
    it."""
    dest = vault_out()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(html_path, dest)
    print(f"  copied to {dest}")
    stale = VAULT_DIR / "Zipline Build Document (model-backed) 2026-07-06.html"
    if stale.exists() and stale != dest:
        print(f"  NOTE: stale prior vault copy present, remove on commit: {stale}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate the consolidated zipline build document.")
    ap.add_argument(
        "--vault-copy", action="store_true",
        help="also copy the generated HTML into the owner's Obsidian vault "
             "(default: off — no writes outside this repo).",
    )
    args = ap.parse_args(argv)

    t0 = time.time()
    print("Loading details...")
    details = load_details()

    # Validate each detail ONCE, on the freshly compiled (exact) geometry, before
    # any GLB export re-tessellates the shared solids. These clean verdicts drive
    # the coverage matrices; build_html never re-validates (see its docstring).
    detail_reports = {name: d.validate() for name, d in details.items()}

    # Fabrication-fold guard (fab-design §8): assert every fabricated part's
    # installed geometry is byte-identical to fold(stock, steps) BEFORE any cut
    # list / BOM is derived from those records — so a part whose geometry has
    # drifted from its declared operations fails the build loudly, naming the
    # part, rather than shipping a cut list that disagrees with the solid (R28).
    print("Asserting the fabrication-fold invariant on every fabricated part...")
    assert_details_fabrication_sound(details)

    print("Per-detail: hash-gate → reuse on-disk render or full render...")
    manifests, images, reused = {}, {}, {}
    for name, d in details.items():
        manifests[name], images[name], reused[name] = process_detail(name, d)

    print("Building viewer payloads + coarse web GLBs (gzip+base64)...")
    from detailgen.rendering.web_viewer import build_viewer_payload

    payloads = {name: build_viewer_payload(d) for name, d in details.items()}
    glb_sizes = {}

    # Pier-foundation zoom (Panel E, view-coverage-directive): one representative
    # foundation rendered from the platform's own placed parts, threaded into
    # build_html like the per-detail images so the golden can stub it. Its scoped
    # interactive viewer payload joins onto the SAME platform part rows.
    print("Rendering the pier-foundation zoom (Panel E)...")
    pier_images = pier_foundation_images(details)
    # Panel E is scoped to the platform's own pier parts, so build its viewer
    # payload/GLB only when the platform detail is present. A detail subset that
    # omits it (a stubbed main() in the script tests) skips Panel E's viewer
    # entirely and falls back to the stills — the doc build never crashes on a
    # subset. render_viewer_assets / the slot guard already tolerate the absence.
    has_pier = "platform" in details and "platform" in payloads
    if has_pier:
        payloads[PIER_FOUNDATION_SLUG] = pier_foundation_payload(payloads["platform"], details)

    def export_glbs(tolerances):
        b64 = {}
        for name, d in details.items():
            s, raw, gz = web_glb_b64(d.assembly, RENDERS / name, tolerances)
            b64[name] = s
            glb_sizes[name] = (raw, gz, len(s))
        if has_pier:
            b64[PIER_FOUNDATION_SLUG] = pier_foundation_glb_b64(details, tolerances)
        return b64

    print("Compiling the ONE site model (details/site.spec.yaml)...")
    site = load_site()
    site_report = site.validate()
    print(f"  site: {len(site.assembly.parts)} parts, "
          f"{len(site_report.blocking)} open finding(s) "
          f"({'CLEAN' if site_report.ok else 'DIRTY — composed render gated'})")

    print("Aggregating BOM (with double-count guard)...")
    purchased, existing = combined_bom(details)
    print(f"  purchased lines: {len(purchased)}; existing lines: {len(existing)}")

    print("Packing lumber/decking BOM lines into a stock-and-cut plan...")
    from detailgen.core.cutplan import pack

    cut_plans = pack(lumber_cut_items(purchased, details))
    for profile, plan in sorted(cut_plans.items()):
        print(f"  {profile}: {plan.stick_count} stick(s), "
              f"{plan.total_waste_mm:.0f}mm waste")

    # Visual-review smell-test block from the committed findings store, cross-
    # referenced against this build's renders. Built here (after the renders
    # land, before the GLB export mutates geometry) so its render manifest hashes
    # the CLEAN on-disk PNGs.
    review_block = build_review_block()

    # Build the doc; coarsen the web GLB only if it exceeds the hard ceiling.
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = None
    for i, tol in enumerate(WEB_GLB_TOLERANCES):
        glb_b64 = export_glbs(tol)
        doc = build_html(details, images, purchased, existing, cut_plans, manifests, payloads, glb_b64,
                          site, site_report, detail_reports, review_block=review_block,
                          pier_images=pier_images)
        HTML_OUT.write_text(doc, encoding="utf-8")
        size = HTML_OUT.stat().st_size
        if size <= MAX_HTML_BYTES:
            if i > 0:
                print(f"  web GLB coarsened to {tol} to fit the {MAX_HTML_BYTES/1e6:.0f}MB ceiling")
            break
        print(f"  {size/1e6:.2f}MB > {MAX_HTML_BYTES/1e6:.0f}MB at tol {tol}; coarsening...")
    else:
        raise SystemExit(
            f"HTML {HTML_OUT.stat().st_size/1e6:.2f}MB exceeds "
            f"{MAX_HTML_BYTES/1e6:.0f}MB even at the coarsest web-GLB tolerance"
        )

    _print_size_breakdown(images, glb_sizes)
    size = HTML_OUT.stat().st_size
    print(f"  wrote {HTML_OUT} ({size/1e6:.2f} MB)")

    if args.vault_copy:
        copy_to_vault(HTML_OUT)
    else:
        print("  (skipped vault copy — pass --vault-copy to also write it to the vault)")

    n_reused = sum(reused.values())
    print(f"Done in {time.time()-t0:.0f}s "
          f"({n_reused}/{len(details)} details reused on-disk renders)")


def _print_size_breakdown(images, glb_sizes):
    """Print where the HTML bytes go: three.js, per-detail GLB (gz+b64) and
    PNGs, so a regression in the embed budget is visible at a glance."""
    from detailgen.rendering.web_viewer import vendor_js, viewer_css, viewer_js

    three = len(vendor_js()) + len(viewer_js()) + len(viewer_css())
    print("  size breakdown:")
    print(f"    three.js + viewer JS/CSS : {three/1e6:6.2f} MB")
    for name in glb_sizes:
        raw, gz, b64 = glb_sizes[name]
        png = sum(len(images[name][v]) for v in images[name])
        print(f"    {name:16} GLB {b64/1e6:5.2f} MB (gz {gz/1e6:.2f}, raw {raw/1e6:.2f}) "
              f"| PNGs {png/1e6:.2f} MB")


if __name__ == "__main__":
    main()
