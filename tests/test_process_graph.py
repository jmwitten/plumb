"""FAB-1 — the Construction Process Graph IR core (fab-design.md §12 FAB-1).

Each test here is a situation the system could not handle correctly before this
landed, and now handles for the right reason (the CAT discipline, fab-design
§11) — never "the function exists." Specifically:

- AC1 / CAT-3: the installed geometry of every fabricated part is DERIVED from
  its process steps, byte-identical to what the former inline ``_build`` produced
  — one authoritative path, not a second solid that can drift.
- AC2 / CAT-4: a solid carrying a material-removing feature no ``ProcessStep``
  describes is REJECTED at build time (clause 2), and geometry edited without
  editing its steps is rejected (clause 1). These are the two directions of the
  R28 defect (retro-index.md:65) — geometry and cut list describing different
  realities — made structurally impossible, the cross-output consistency the
  struct review had no shared representation to check.
- Identity: a step keys on authored content, not position, so inserting a step
  leaves the others' identities untouched (the ordinal trap INCR rejected one
  level up, incr-design.md:51-59); an identical-content collision is loud.
"""

from __future__ import annotations

import cadquery as cq
import pytest

from detailgen.components._geometry import axis_cylinder
from detailgen.components.lumber import Lumber
from detailgen.components.railing import DeckBoard
from detailgen.core.buildinfo import geometry_hash
from detailgen.core.units import IN
from detailgen.core.process_graph import (
    FabricationFoldError,
    ProcessRecord,
    ProcessStep,
    ProcessStepIdentityCollision,
    StockRef,
    UnknownProcessStepKind,
    assert_fabrication_fold_invariant,
    fold,
    notch_removes_material,
    verify_fabrication,
)
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_file
from detailgen.spec.site import compile_site_file

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
DETAILS = REPO / "details"


def _all_models():
    models = {d: compile_spec(load_spec_file(DETAILS / f"{d}.spec.yaml"))
              for d in ("platform", "rock_anchor", "tree_attachment", "trolley_launch")}
    models["site"] = compile_site_file(DETAILS / "site.spec.yaml")
    return models


def _fabricated_parts():
    """Every Lumber / DeckBoard placed across the four details and the composed
    site — the full population AC1 must hold for."""
    for mname, model in _all_models().items():
        for p in model.assembly.parts:
            if type(p.component).__name__ in ("Lumber", "DeckBoard"):
                yield mname, p


# --------------------------------------------------------------------------- #
# AC1 — installed geometry is DERIVED from steps, byte-identical to _build.
# --------------------------------------------------------------------------- #
def test_ac1_every_fabricated_part_folds_byte_identical_to_build():
    """For all 6 deck boards and every Lumber member across the 4 details and the
    composed site, ``fold(stock, steps)`` is byte-identical to what the part's
    ``_build`` produces. Because ``_build`` delegates to ``fold``, this proves
    there is ONE authoritative geometry path: the derived solid and the built
    solid are the same bytes, not two computations agreeing by luck."""
    parts = list(_fabricated_parts())
    assert parts, "expected fabricated parts to check"
    n_lumber = n_deck = 0
    for mname, p in parts:
        c = p.component
        record = c.fabrication_record()
        # Fresh on both sides (avoids the ~1e-10 BREP-reload re-tessellation noise
        # documented in core.buildinfo) so any mismatch is a real fold defect.
        assert geometry_hash(c._build()) == geometry_hash(fold(record.stock, record.steps)), (
            f"{mname}:{p.id} fold(stock, steps) diverged from _build")
        if type(c).__name__ == "Lumber":
            n_lumber += 1
        else:
            n_deck += 1
    assert n_deck == 12, f"expected 6 platform + 6 site deck boards, got {n_deck}"
    assert n_lumber >= 30


def test_ac1_crossing_board_names_the_notch_non_crossing_omits_it():
    """The board the trunk crosses carries a ``notch`` step; a board whose
    ``trunk_cut`` cylinder falls outside its own footprint (the §6.2 geometric
    no-op) carries NONE — the absence of the operation is the fact, so the cut
    list would read "plain" truthfully rather than showing a phantom op."""
    width = DeckBoard.WIDTH
    # Crossing board: trunk at board-local centre -> real notch.
    crossing = DeckBoard(length=48 * IN, name="deck cross",
                         trunk_cut=(0.0, width / 2, 305.0))
    steps = crossing.fabrication_record().steps
    assert [s.kind for s in steps].count("notch") == 1
    assert any(s.kind == "notch" and s.param("feature") == "trunk" for s in steps)

    # Non-crossing board: cylinder centred far past the footprint -> no notch op,
    # and its folded geometry is exactly the un-notched board.
    far = DeckBoard(length=48 * IN, name="deck far",
                    trunk_cut=(0.0, width + 5000.0, 305.0))
    far_steps = far.fabrication_record().steps
    assert not any(s.kind == "notch" for s in far_steps), (
        "a board the trunk does not cross must not carry a notch step")
    assert not notch_removes_material(0.0, width + 5000.0, 305.0, 48 * IN, width)
    plain = DeckBoard(length=48 * IN, name="deck plain", trunk_cut=None)
    assert geometry_hash(far._build()) == geometry_hash(plain._build())


# --------------------------------------------------------------------------- #
# CAT-3 — the compiler can explain how a stick becomes a part (capability).
# --------------------------------------------------------------------------- #
def test_cat3_chain_is_walkable_and_every_step_has_provenance():
    """Point at any fabricated part and the chain stock -> ordered steps ->
    installed geometry is a first-class walkable object, and each step's
    provenance answers "which design intent produced you." Before FAB the
    compiler knew only the two endpoints (a 5/4x6 and a finished solid) and
    nothing in between."""
    checked = 0
    for _mname, p in _fabricated_parts():
        record = p.component.fabrication_record()
        assert isinstance(record.stock, StockRef)
        assert record.stock.profile and record.stock.form == "linear_stick"
        assert record.steps and record.steps[0].kind == "crosscut"
        for step in record.steps:
            assert step.provenance, f"{p.id}: {step.kind} step has no provenance"
        # the endpoint of the chain is the installed geometry, derived from it
        assert record.installed_geometry().val().Volume() > 0
        checked += 1
    assert checked >= 40


# --------------------------------------------------------------------------- #
# CAT-4 / AC2 — a feature with no operation is rejected (new adversarial).
# --------------------------------------------------------------------------- #
class _MysteryCutBoard(DeckBoard):
    """A board whose installed solid carries a bored hole that NO ProcessStep
    describes — the reverse of R28 (retro-index.md:65): a cut a drawing would
    show but no cut instruction explains. Its ``fabrication_record`` (inherited)
    knows nothing of the extra hole, so its geometry has drifted from its steps.
    This is the divergence the struct review had no shared representation to
    catch (R28); the guard must catch it structurally."""

    def _build(self):
        wp = super()._build()  # == fold(record)
        return wp.cut(axis_cylinder(8.0, self.THICKNESS * 4,
                                    (600.0, 70.0, -self.THICKNESS), (0, 0, 1)))


def test_cat4_mystery_cut_fails_clause_two_naming_the_part():
    board = _MysteryCutBoard(length=48 * IN, name="mystery-3",
                             trunk_cut=(0.0, 0.0, 305.0))
    with pytest.raises(FabricationFoldError) as ei:
        verify_fabrication(board, part_id="mystery-3")
    msg = str(ei.value)
    assert "clause 2" in msg, "a mystery cut is a clause-2 (no-step-behind-it) failure"
    assert "mystery-3" in msg, "the teaching error must name the part"


class _MovedDrillLumber(Lumber):
    """A member whose installed solid drills a fully-interior hole at a DIFFERENT
    coordinate than its recorded ``holes`` entry — same removed volume, different
    location. Geometry edited without editing the ops: clause 2 (material balance)
    is satisfied, so clause 1 (byte identity) must be what bites."""

    def _build(self):
        wp = cq.Workplane("XY").box(self.length, self.thickness, self.depth,
                                    centered=False)
        return wp.cut(axis_cylinder(11.0 / 2, self.thickness * 4,
                                    (900.0, -self.thickness * 2, 70.0), (0, 1, 0)))


def test_forward_case_edited_geometry_fails_clause_one():
    part = _MovedDrillLumber("2x6", length=48 * IN, treated=True,
                             holes=((300.0, 70.0, 11.0),))
    with pytest.raises(FabricationFoldError) as ei:
        verify_fabrication(part, part_id="moved-leg")
    msg = str(ei.value)
    assert "clause 1" in msg and "clause 2" not in msg, (
        "a volume-preserving geometry edit must fail byte-identity (clause 1), "
        "not the material-balance clause")
    assert "moved-leg" in msg


def test_invariant_passes_on_every_real_fabricated_part():
    """The guard must not false-positive: every correctly-delegating shipped part
    satisfies both clauses (the invariant holds by construction)."""
    for _mname, p in _fabricated_parts():
        verify_fabrication(p.component, part_id=p.id)


# --------------------------------------------------------------------------- #
# Identity — content key, not ordinal (fab-design §9; incr-design.md:51-59).
# --------------------------------------------------------------------------- #
def test_inserting_a_fifth_drill_leaves_the_other_four_identities_untouched():
    """A leg carries four drills; inserting a fifth must NOT renumber the others.
    Keying identity on the authored ``(x, z)`` (not a slot ordinal) is what
    survives insertion — the exact defect INCR refused to build on when it
    rejected build-order ordinals as identity (incr-design.md:51-59)."""
    holes4 = [(100.0, 70.0, 11.0), (200.0, 70.0, 11.0),
              (300.0, 70.0, 11.0), (400.0, 70.0, 11.0)]
    r4 = Lumber("2x6", length=48 * IN, holes=tuple(holes4)).fabrication_record()
    holes5 = holes4[:2] + [(250.0, 70.0, 11.0)] + holes4[2:]  # inserted in the middle
    r5 = Lumber("2x6", length=48 * IN, holes=tuple(holes5)).fabrication_record()
    ids4 = {s.identity for s in r4.steps if s.kind == "drill"}
    ids5 = {s.identity for s in r5.steps if s.kind == "drill"}
    assert ids4 <= ids5, "the original four drills' identities must survive insertion"
    assert len(ids5 - ids4) == 1, "exactly one drill identity is new (an appeared op)"


def test_re_drilling_same_hole_larger_reads_as_a_change_not_a_new_hole():
    """Diameter is comparable content, not identity: re-drilling the same
    authored coordinate at a larger diameter keeps the same identity (a resized
    op), it does not read as a brand-new hole."""
    a = ProcessStep.drill(300.0, 70.0, 11.0)
    b = ProcessStep.drill(300.0, 70.0, 14.0)
    assert a.identity == b.identity
    assert a != b  # the step itself changed (diameter differs)


def test_identical_coordinate_drills_collide_loudly():
    """Two drills at the identical authored coordinate collide on the content
    key. FAB does not silently renumber or merge (INCR-3 precedent); it raises a
    loud teaching error."""
    with pytest.raises(ProcessStepIdentityCollision) as ei:
        Lumber("2x6", length=48 * IN,
               holes=((100.0, 70.0, 11.0), (100.0, 70.0, 14.0))).fabrication_record()
    assert "collide" in str(ei.value)


# --------------------------------------------------------------------------- #
# Value-type discipline — immutable, byte-stable, order-sensitive fold.
# --------------------------------------------------------------------------- #
def test_process_step_is_immutable_and_content_equal():
    s = ProcessStep.notch(0.0, 10.0, 300.0, feature="trunk", provenance="p")
    with pytest.raises(Exception):
        s.kind = "drill"  # frozen
    assert s == ProcessStep.notch(0.0, 10.0, 300.0, feature="trunk", provenance="p")


def test_fold_is_order_sensitive_ease_then_notch_differs_from_notch_then_ease():
    """Order is load-bearing (fab-design §3): a deck board is eased THEN notched;
    reversing them fillets edges the notch has already interrupted, a different
    solid. ``fold`` never reorders, so the two step orders must fold differently."""
    stock = StockRef("5/4x6 PT", "linear_stick",
                     (DeckBoard.WIDTH, DeckBoard.THICKNESS))
    crosscut = ProcessStep.crosscut(48 * IN)
    ease = ProcessStep.ease(0.125 * IN)
    notch = ProcessStep.notch(0.0, DeckBoard.WIDTH / 2, 60.0, feature="trunk")
    ease_then_notch = fold(stock, (crosscut, ease, notch))
    notch_then_ease = fold(stock, (crosscut, notch, ease))
    assert geometry_hash(ease_then_notch) != geometry_hash(notch_then_ease)


def test_fold_rejects_a_non_geometric_kind_and_a_missing_crosscut():
    stock = StockRef("2x6", "linear_stick", (38.1, 139.7))
    with pytest.raises(UnknownProcessStepKind):
        fold(stock, (ProcessStep.crosscut(48 * IN),
                     ProcessStep("cure", {"hours": 24.0}, provenance="p")))
    with pytest.raises(UnknownProcessStepKind):
        fold(stock, (ProcessStep.ease(1.0),))  # no crosscut to fix the length


@pytest.mark.parametrize("face", ["top", "bottom"])
def test_rectangular_groove_is_a_folded_material_removing_step(face):
    stock = StockRef(
        "19 mm plywood strip", "linear_stick", (100.0, 19.0),
        material_key="plywood",
    )
    groove = ProcessStep.groove(
        x=10.0, y=20.0, length=300.0, width=6.5, depth=9.0,
        feature=f"captured_back_{face}", face=face,
    )
    solid = fold(stock, (ProcessStep.crosscut(500.0), groove))

    expected = 500.0 * 100.0 * 19.0 - 300.0 * 6.5 * 9.0
    assert solid.val().Volume() == pytest.approx(expected)
    assert groove.identity == ("groove", f"captured_back_{face}")


def test_assert_invariant_signature_accepts_explicit_record():
    """The invariant is callable on any (part_id, installed_solid, record)
    triple, so a consumer or a whole-assembly guard can assert it without a
    Component in hand."""
    c = Lumber("2x6", length=48 * IN, treated=True, holes=((100.0, 70.0, 11.0),))
    record = c.fabrication_record()
    assert_fabrication_fold_invariant("leg-x", c._build(), record)  # passes, no raise
