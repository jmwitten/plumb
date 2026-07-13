"""CL-2 FEATURE verbs — the CONCEPTUAL acceptance test §7 Test 1 (THE FLAGSHIP:
a board that must clear a trunk), the declaration-time diagnostics (§3.5 slice),
and the determinism / derivation-table goldens (§8.7 executable documentation).

The bar (cl0-design §0/§7): success is NOT "the function exists." It is that a
class of wrongness becomes impossible — here R14, "placement and clearance-check
and prose disagree about the same notch." CL-2 makes that unwritable because the
cut geometry, the clearance invariant, the callout, the cut-list fact, and the
affected region are ALL derived from the ONE `clearance_cut` declaration; none is
a hand-authored surface that could drift from the others.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.core.units import IN
from detailgen.components.lumber import Lumber
from detailgen.components.railing import DeckBoard
from detailgen.components.tree import TreeTrunk
from detailgen.core.frame import Frame
from detailgen.spec.compiler import compile_spec, compile_spec_file
from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.spec.lowering import lower_feature, feature_identity
from detailgen.spec.schema import ComponentSpec, FeatureSpec
from detailgen.spec.semantics import SemanticError

ROOT = Path(__file__).resolve().parents[1]
CAT1 = ROOT / "tests" / "fixtures" / "cl2" / "clearance_cut_cat.spec.yaml"


# --------------------------------------------------------------------------- #
# §7 Test 1 — the flagship: ONE declaration -> every downstream surface derived
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def cat1():
    detail = compile_spec_file(CAT1)
    report = detail.validate()
    return detail, report


def test_cat1_one_declaration_derives_every_surface(cat1):
    """From the single `clearance_cut` relation the compiler derives ALL of: the
    board-local cut geometry, the ge clearance invariant, the dimension callout
    anchor, the cut-list/fabrication fact, and the affected-region edge."""
    detail, report = cat1
    board = detail._by_id["board"].component

    # (1) cut GEOMETRY derived — the board carries a notch whose board-local
    # center was DERIVED from the trunk's placed position (never authored). The
    # trunk sits at the world origin and the board is centered over it, so the
    # local center is the board's own center (board_len/2, WIDTH/2).
    assert board._trunk_cut is not None
    cx, cy, r = board._trunk_cut
    assert cx == pytest.approx(48 * IN / 2) and cy == pytest.approx(DeckBoard.WIDTH / 2)
    assert r == pytest.approx(20 * IN / 2 + 2 * IN)  # trunk radius + gap

    # (2) the ge CLEARANCE invariant derived AND it PASSES (min surface distance
    # == the gap): the notch and its proof are the one declaration.
    clr = [f for f in report.findings if f.check == "clearance"]
    assert len(clr) == 1 and clr[0].passed
    assert "clears trunk" in clr[0].subject

    # (3) the cut-list / FABRICATION fact derived — a real notch step that the cut
    # note renders, keyed on the feature (provenance), naming the member.
    rec = board.fabrication_record()
    notch = [s for s in rec.steps if s.kind == "notch"]
    assert len(notch) == 1 and notch[0].param("feature") == "trunk"
    assert notch[0].provenance == "clearance_cut:trunk"
    assert "clearance pocket around the trunk" in rec.fab_note()

    # (4) the dimension CALLOUT anchor derived (a queryable derivation fact).
    rules = [f.rule for f in detail.derivation_report()]
    assert "spec.feature.callout" in rules
    # (5) the affected-region + evidence edge derived (trunk is the region an
    # incremental recompile must touch if it moves).
    assert "spec.feature.evidence" in rules


def test_cat1_no_downstream_surface_is_hand_authored():
    """The class-closer, grep-style (FAB AC4 discipline): the ONLY thing the
    author writes for the notch is the `clearance_cut` relation. There is NO hand
    `trunk_cut` param, NO hand clearance/bearing/dimension check, NO hand overlap
    allowlist, NO hand callout for the notch. If any of these were present, the
    notch's geometry and its proof could drift — the R14 class. Their ABSENCE in
    the source is what makes the class unwritable."""
    text = CAT1.read_text()
    doc = load_spec_file(CAT1)
    board = next(c for c in doc.components
                 if isinstance(c, ComponentSpec) and c.id == "board")

    # the feature is the sole authored source; no hand cut center on the board.
    assert len(board.features) == 1 and board.features[0].kind == "clearance_cut"
    assert "trunk_cut" not in board.params and "trunk_cut" not in text

    # no hand-authored validation for the notch anywhere in the doc.
    v = doc.validation
    assert not v.bearings and not v.dimensions and not v.expected_overlaps
    assert not v.through_holes
    # the compiled clearance finding is DERIVED (from the feature), not authored:
    # the spec's validation block is empty, yet the detail proves the clearance.
    detail = compile_spec(doc)
    report = detail.validate()
    assert any(f.check == "clearance" for f in report.findings)


def test_cat1_moving_the_trunk_moves_the_derived_cut():
    """The derivation is REAL, not a coincidence: move the member and the
    board-local cut center follows automatically (the world->local negation is
    derived every build). A hand `trunk_cut` would have gone stale here — exactly
    the drift R9/R14 record. Shown on the pure lowering (the compiler path that
    consumes it is covered by the flagship above)."""
    part_frame = Frame.translation((-24 * IN, -DeckBoard.WIDTH / 2, 24 * IN))
    feat = FeatureSpec(kind="clearance_cut", around="trunk", gap=2 * IN)
    kw = dict(part_frame=part_frame, part_center_local=(0, 0),
              member_radius=10 * IN, member_name="trunk", gap=2 * IN, unit_factor=IN)
    at_origin = lower_feature(feat, member_axis_world=(0.0, 0.0, 0.0), **kw)
    at_shifted = lower_feature(feat, member_axis_world=(0.0, 5 * IN, 0.0), **kw)
    # the derived cut-center Y tracks the member's world Y move, EXACTLY (a 5"
    # member move re-expresses as a 5" shift of the notch center in the board's
    # local frame — the derivation, not a stale hand twin).
    assert abs(at_shifted.cut[1] - at_origin.cut[1]) == pytest.approx(5 * IN)
    assert at_shifted.cut[1] != at_origin.cut[1]
    assert at_origin.affected_region == ("trunk",)


# --------------------------------------------------------------------------- #
# §3.5 declaration-time diagnostics — teaching errors BEFORE any geometry
# --------------------------------------------------------------------------- #
_HEAD = "name: d\ntype: detail\nunits: in\nparams: {g: 2.0}\ncomponents:\n"


def _compile(body: str):
    return compile_spec(load_spec_text(_HEAD + body))


def test_dangling_clearance_member_is_a_teaching_error():
    with pytest.raises(SemanticError) as e:
        _compile(
            "  - {id: trunk, type: tree_trunk, name: trunk, params: {diameter: 20 in, height: 24 in}}\n"
            "  - id: b\n    type: deck_board\n    name: b\n    params: {length: 48 in}\n"
            "    features:\n      - clearance_cut: {around: trnk, gap: $g}\n")
    assert "trnk" in str(e.value) and "not a declared component" in str(e.value)
    assert "did you mean" in str(e.value)  # the near-miss hint names 'trunk'


def test_duplicate_authored_feature_id_across_parts_is_a_teaching_error():
    """An authored feature id is a detail-wide key (FAB/INCR/cut-notes reference
    it), so the same id on two different parts is a teaching error naming both."""
    with pytest.raises(SemanticError) as e:
        _compile(
            "  - {id: t, type: tree_trunk, name: t, params: {diameter: 20 in, height: 24 in}}\n"
            "  - id: b1\n    type: deck_board\n    name: b1\n    params: {length: 48 in}\n"
            "    features:\n      - clearance_cut: {around: t, gap: $g, id: dup}\n"
            "  - id: b2\n    type: deck_board\n    name: b2\n    params: {length: 48 in}\n"
            "    features:\n      - clearance_cut: {around: t, gap: $g, id: dup}\n")
    assert "dup" in str(e.value) and "unique" in str(e.value)


def test_two_features_colliding_on_identity_within_one_part_is_a_teaching_error():
    with pytest.raises(SemanticError) as e:
        _compile(
            "  - {id: t, type: tree_trunk, name: t, params: {diameter: 20 in, height: 24 in}}\n"
            "  - id: b\n    type: deck_board\n    name: b\n    params: {length: 48 in}\n"
            "    features:\n"
            "      - clearance_cut: {around: t, gap: $g, id: dup}\n"
            "      - bore: {dia: 2 in, id: dup}\n")
    assert "dup" in str(e.value) and "distinct identity" in str(e.value)


def test_negative_gap_is_a_teaching_error():
    from detailgen.spec.compiler import SpecCompileError
    with pytest.raises(SpecCompileError) as e:
        d = _compile(
            "  - {id: t, type: tree_trunk, name: t, params: {diameter: 20 in, height: 24 in}}\n"
            "  - id: b\n    type: deck_board\n    name: b\n    params: {length: 48 in}\n"
            "    features:\n      - clearance_cut: {around: t, gap: -1 in}\n")
        d.build()
    assert "negative" in str(e.value) and "gap" in str(e.value)


def test_noop_clearance_cut_is_a_teaching_note_not_a_silent_skip():
    """A clearance_cut whose member never reaches the board footprint is the §6.2
    geometric no-op — surfaced as a derivation NOTE (the board clears without a
    cut), never a silent skip. The board carries no notch step, truthfully."""
    d = _compile(
        "  - {id: t, type: tree_trunk, name: t, params: {diameter: 4 in, height: 24 in}}\n"
        "  - id: b\n    type: deck_board\n    name: b\n    params: {length: 48 in}\n"
        # place the board FAR from the trunk so its notch cylinder misses it.
        "    place: {raw: {at: [1000 in, 1000 in, 24 in]}}\n"
        "    features:\n      - clearance_cut: {around: t, gap: $g}\n")
    d.build()
    notes = [f for f in d.derivation_report() if f.rule == "spec.feature.noop"]
    assert len(notes) == 1 and "no-op" in notes[0].fact
    board = d._by_id["b"].component
    assert not any(s.kind == "notch" for s in board.fabrication_record().steps)


# --------------------------------------------------------------------------- #
# bore — the escalated designed-recess verb (vocabulary-gap directive)
# --------------------------------------------------------------------------- #
def test_bore_is_a_designed_recess_not_a_clearance():
    """A `bore` references NO member and mandates NO clearance invariant — it is a
    hole the design wants, named as itself. Its fabrication step is a `bore` kind
    (distinct from a clearance `notch`) so the cut note speaks the bore's own name,
    never trunk-clearance language."""
    d = _compile(
        "  - id: b\n    type: deck_board\n    name: b\n    params: {length: 20 in}\n"
        "    features:\n      - bore: {dia: 3.5 in, id: cup_hole, name: cup hole}\n")
    d.build()
    board = d._by_id["b"].component
    steps = board.fabrication_record().steps
    bore = [s for s in steps if s.kind == "bore"]
    assert len(bore) == 1 and bore[0].param("feature") == "cup hole"
    assert bore[0].provenance == "cup_hole"
    note = board.fabrication_record().fab_note()
    assert "cup hole" in note and "trunk" not in note and "clearance pocket" not in note
    # a bore mandates no clearance invariant.
    assert not any(f.check == "clearance" for f in d.validate().findings)


# --------------------------------------------------------------------------- #
# §8.7 determinism + identity
# --------------------------------------------------------------------------- #
def test_lower_feature_is_byte_stable_across_runs():
    beam = Lumber("2x6", length=48 * IN, treated=True)
    part_frame = Frame.translation((0.0, 100.0, 24 * IN))
    feat = FeatureSpec(kind="clearance_cut", around="trunk", gap=2 * IN)
    kw = dict(part_frame=part_frame, part_center_local=(0, 0),
              member_axis_world=(0.0, 0.0, 0.0), member_radius=10 * IN,
              member_name="trunk", gap=2 * IN, unit_factor=IN)
    a = lower_feature(feat, **kw)
    b = lower_feature(feat, **kw)
    assert a == b  # frozen dataclass, exact equality


def test_feature_identity_prefers_authored_id_else_content_key():
    named = FeatureSpec(kind="clearance_cut", around="trunk", gap=1, id="deck_notch")
    anon = FeatureSpec(kind="clearance_cut", around="trunk", gap=1)
    bore = FeatureSpec(kind="bore", dia=1, name="cup hole")
    assert feature_identity(named) == "deck_notch"
    assert feature_identity(anon) == "clearance_cut:trunk"
    assert feature_identity(bore) == "bore:cup_hole"
