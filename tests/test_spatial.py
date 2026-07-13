"""Spatial-intent invariants (task SPATIAL, P6): SymmetricAbout and
FacesToward/FacesAway — VALIDATION-ONLY assertions that survive the raw-transform
escape hatch where the two motivating real bugs lived.

Both bug reproductions are here as the TDD anchor:

* the RAILFIX class — a ``-Y`` member left as an UNMIRRORED copy of its ``+Y``
  twin (the real "-Y top rail overhung outboard" defect) — ``symmetric_about``
  must FAIL naming the pair and plane;
* the ladder-at-wrong-end class (the Wave-1 step-placement miss) — a part whose
  access opens toward the wrong end — ``faces_toward``/``faces_away`` must FAIL.

Plus the tolerance knife-edge (just-inside passes / just-outside fails) and the
reserved-name teaching diagnostic (parallel/perpendicular/aligned_with are
documented vocabulary, NOT parse-and-noop stubs).
"""

from __future__ import annotations

import pytest

from detailgen.assemblies import DetailAssembly
from detailgen.components import Lumber
from detailgen.core import DEFAULT, IN
from detailgen.validation import validate_assembly
from detailgen.validation.spatial import (
    FacesAway,
    FacesToward,
    SymmetricAbout,
    check_faces,
    check_symmetric_about,
)


# -- SymmetricAbout: the RAILFIX bug class ------------------------------------

_T2X4 = 1.5 * IN  # a 2x4's dressed thickness — its Y footprint from the corner
                  # origin (Lumber's local frame is a bottom-left end corner).


def _mirror_pair(y_plus: float, y_minus: float | None = None):
    """Two identical 2x4s (length along X). ``rail +Y``'s Y footprint is
    ``[y_plus, y_plus + t]``. Omit ``y_minus`` for a TRUE mirror about the XZ
    plane — ``rail -Y`` placed so its footprint is the exact Y-reflection
    ``[-(y_plus+t), -y_plus]``. Pass ``y_minus`` explicitly (e.g. ``y_plus``) to
    reproduce the RAILFIX defect: a -Y member left as an unmirrored copy that
    overhangs the same world side as its twin."""
    d = DetailAssembly("mirror-test")
    a = d.add(Lumber("2x4", 12 * IN, name="rail +Y"), at=(0, y_plus, 0))
    if y_minus is None:
        y_minus = -(y_plus + _T2X4)  # origin that reflects the +Y footprint
    b = d.add(Lumber("2x4", 12 * IN, name="rail -Y"), at=(0, y_minus, 0))
    return d, a, b


def test_symmetric_about_passes_for_a_true_mirror():
    d, a, b = _mirror_pair(10 * IN)
    f = check_symmetric_about(a, b, "XZ", tol=DEFAULT.dimension_tolerance)
    assert f.passed, f
    assert f.check == "symmetric_about"


def test_symmetric_about_fails_the_railfix_unmirrored_copy():
    # the real bug: rail -Y placed at the SAME +Y as its twin (unmirrored).
    d, a, b = _mirror_pair(10 * IN, 10 * IN)
    f = check_symmetric_about(a, b, "XZ", tol=DEFAULT.dimension_tolerance)
    assert not f.passed, f
    assert f.check == "symmetric_about"
    # names the pair AND the plane (P1 provenance).
    assert "rail +Y" in f.subject and "rail -Y" in f.subject
    assert "XZ" in f.subject or "XZ" in f.detail


def test_symmetric_about_via_stage_and_mirror_selector():
    # end-to-end through the sweep: a mirror-by-name selector discovers the
    # +Y/-Y pair and proves it, activating the finding in report.findings.
    d, a, b = _mirror_pair(10 * IN)
    report = validate_assembly(
        d, spatial=[SymmetricAbout(plane="XZ", mirror=("+Y", "-Y"))])
    sym = [f for f in report.findings if f.check == "symmetric_about"]
    assert len(sym) == 1 and sym[0].passed, report

    d2, a2, b2 = _mirror_pair(10 * IN, 10 * IN)
    report2 = validate_assembly(
        d2, spatial=[SymmetricAbout(plane="XZ", mirror=("+Y", "-Y"))])
    sym2 = [f for f in report2.findings if f.check == "symmetric_about"]
    assert len(sym2) == 1 and not sym2[0].passed, report2


def test_symmetric_about_zero_match_selector_is_a_loud_failure():
    """A mirror selector that matches NO part-name pairs must not silently
    noop — it emits one FAILING finding so the Spatial family can't pass on an
    invariant that never ran (task CLEANUP item 6)."""
    d, a, b = _mirror_pair(10 * IN)          # names are 'rail +Y' / 'rail -Y'
    report = validate_assembly(
        # a substitution that appears in no part name -> discovers nothing
        d, spatial=[SymmetricAbout(plane="XZ", mirror=("+LEFT", "-RIGHT"))])
    sym = [f for f in report.findings if f.check == "symmetric_about"]
    assert len(sym) == 1 and not sym[0].passed, report
    assert "ZERO part pairs" in sym[0].detail
    assert not report.ok                     # the clean report is now dirtied


def test_symmetric_about_empty_declaration_is_a_loud_failure():
    """A declaration with neither explicit pairs nor a mirror selector likewise
    resolves to zero and must read as unproven, not proven."""
    d, a, b = _mirror_pair(10 * IN)
    report = validate_assembly(d, spatial=[SymmetricAbout(plane="XZ")])
    sym = [f for f in report.findings if f.check == "symmetric_about"]
    assert len(sym) == 1 and not sym[0].passed, report
    assert "ZERO part pairs" in sym[0].detail


def test_symmetric_about_tolerance_boundary():
    tol = 0.5  # mm
    # just inside: -Y off by tol/2 -> the reflected AABB matches within tol.
    _, a, b = _mirror_pair(10 * IN, -(10 * IN + _T2X4) - 0.25)
    assert check_symmetric_about(a, b, "XZ", tol=tol).passed
    # just outside: off by well over tol -> fails.
    _, a2, b2 = _mirror_pair(10 * IN, -(10 * IN + _T2X4) - 1.0)
    assert not check_symmetric_about(a2, b2, "XZ", tol=tol).passed


# -- FacesToward / FacesAway: the ladder-at-wrong-end class --------------------

def _ladder_scene(rung_x: float):
    """A minimal launch-platform stand-in: a beam spanning the deck run in X
    (centroid near mid-deck) and a full-width ladder rung at ``rung_x``. At the
    real launch end (``rung_x`` large) the rung's launch-outboard access (+X)
    points AWAY from the beam's deck-interior centroid; a rung at the tree end
    (``rung_x`` ~0) reverses that — the ladder-at-wrong-end defect."""
    d = DetailAssembly("ladder-test")
    # beam runs X = -12in .. +48in, centroid ~ +18in.
    d.add(Lumber("2x6", 60 * IN, name="beam +Y"), at=(-12 * IN, 5 * IN, 0))
    rung = d.add(Lumber("2x4", 20 * IN, name="rung 0"),
                 at=(rung_x, -10 * IN, 0), rotate=[("Z", 90)])
    return d, rung


def test_faces_away_passes_when_ladder_is_at_the_launch_end():
    d, rung = _ladder_scene(rung_x=45 * IN)
    report = validate_assembly(
        d, spatial=[FacesAway(part="rung 0", facing=(1, 0, 0), target="beam +Y")])
    faces = [f for f in report.findings if f.check == "faces_away"]
    assert len(faces) == 1 and faces[0].passed, report


def test_faces_away_fails_when_ladder_is_at_the_wrong_end():
    d, rung = _ladder_scene(rung_x=0.0)  # tree end — the wrong end.
    report = validate_assembly(
        d, spatial=[FacesAway(part="rung 0", facing=(1, 0, 0), target="beam +Y")])
    faces = [f for f in report.findings if f.check == "faces_away"]
    assert len(faces) == 1 and not faces[0].passed, report
    assert "rung 0" in faces[0].subject and "beam +Y" in faces[0].subject


def test_faces_toward_direction_and_datum_facing():
    # facing derived from a body-fixed datum: end_far's +Z is local +X, so an
    # unrotated lumber's far end faces world +X. faces_toward(+X) holds; a 180°
    # spin flips the datum axis and the same assertion fails (orientation, not
    # position — the complement of the faces_away position check above).
    d = DetailAssembly("facing-test")
    d.add(Lumber("2x4", 12 * IN, name="bar"))
    f_ok = check_faces_toward_dir(d, "bar", "end_far", (1, 0, 0))
    assert f_ok.passed, f_ok

    d2 = DetailAssembly("facing-test-2")
    d2.add(Lumber("2x4", 12 * IN, name="bar"), rotate=[("Z", 180)])
    f_bad = check_faces_toward_dir(d2, "bar", "end_far", (1, 0, 0))
    assert not f_bad.passed, f_bad


def check_faces_toward_dir(assembly, part_name, datum, direction):
    """Helper: FacesToward with a datum facing and a world-direction target,
    evaluated through the stage, returning the single faces finding."""
    report = validate_assembly(
        assembly,
        spatial=[FacesToward(part=part_name, facing=datum, target=tuple(direction))])
    faces = [f for f in report.findings if f.check == "faces_toward"]
    assert len(faces) == 1
    return faces[0]


def test_faces_tolerance_boundary():
    # the zero-projection knife-edge: with a target direction of +Y, a facing
    # nearly perpendicular but tilted a hair toward +Y passes; a hair toward -Y
    # fails. tol raises the margin off zero.
    d = DetailAssembly("faces-boundary")
    p = d.add(Lumber("2x4", 12 * IN, name="p"), at=(0, 0, 0))
    target_dir = (0.0, 1.0, 0.0)
    just_toward = check_faces(p, (1.0, 0.001, 0.0), target_dir, "toward",
                              "+Y", tol=0.0)
    assert just_toward.passed, just_toward
    just_away = check_faces(p, (1.0, -0.001, 0.0), target_dir, "toward",
                            "+Y", tol=0.0)
    assert not just_away.passed, just_away
    # a projection of +0.001 no longer clears a tol margin of 0.01.
    assert not check_faces(p, (1.0, 0.001, 0.0), target_dir, "toward",
                           "+Y", tol=0.01).passed


# -- reserved names: teaching error, NOT a parse-and-noop stub ----------------

@pytest.mark.parametrize("reserved", ["parallel", "perpendicular", "aligned_with"])
def test_reserved_spatial_names_raise_a_teaching_error(reserved):
    from detailgen.spec.loader import load_spec_text
    from detailgen.spec.schema import SpecSchemaError

    text = f"""
name: reserved-test
components:
  - id: a
    imperative: detailgen.components.lumber.Lumber
    params: {{nominal: "2x4", length: "12 in"}}
spatial:
  {reserved}:
    - {{a: a, b: a}}
"""
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text(text)
    msg = str(e.value)
    assert reserved in msg
    assert "reserved" in msg.lower()
    # the teaching error lists what IS currently provable.
    assert "symmetric_about" in msg and "faces_toward" in msg


def test_spatial_block_round_trips():
    from detailgen.spec.loader import load_spec_text
    from detailgen.spec.serialize import dump_yaml, dump_json

    text = """
name: spatial-rt
components:
  - id: rail_pY
    imperative: detailgen.components.lumber.Lumber
    name: "rail +Y"
    params: {nominal: "2x4", length: "12 in"}
    place: {raw: {at: ["0 in", "10 in", "0 in"]}}
  - id: rail_mY
    imperative: detailgen.components.lumber.Lumber
    name: "rail -Y"
    params: {nominal: "2x4", length: "12 in"}
    place: {raw: {at: ["0 in", "-10 in", "0 in"]}}
spatial:
  symmetric:
    - {plane: XZ, mirror: ["+Y", "-Y"]}
  faces:
    - {part: rail_pY, facing: [1, 0, 0], away: rail_mY}
"""
    doc = load_spec_text(text)
    assert load_spec_text(dump_yaml(doc)) == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc
