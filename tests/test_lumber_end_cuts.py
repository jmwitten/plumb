"""Public dimensional-lumber miter-cut authoring semantics."""

import math

import pytest

from detailgen.assemblies import DetailAssembly
from detailgen.components import Lumber
from detailgen.core import IN
from detailgen.spec import compile_spec, load_spec_text


def _mitered_member():
    doc = load_spec_text(
        """
name: angled lumber probe
type: probe
units: in
components:
  - id: member
    type: lumber
    name: angled member
    params:
      nominal: 2x4
      length: 48 in
      length_semantics: long_point_to_long_point
      end_cuts:
        - {end: near, miter_angle_degrees: 30, long_face: top}
        - {end: far, miter_angle_degrees: 30, long_face: top}
"""
    )
    detail = compile_spec(doc)
    detail.build()
    return detail, detail._by_id["member"].component


def test_detail_spec_compiles_lumber_miters_as_long_point_length_and_cut_steps():
    detail, member = _mitered_member()
    record = member.fabrication_record("member")
    miters = [step for step in record.steps if step.kind == "miter_crosscut"]

    assert member.length == pytest.approx(48 * IN)
    assert member.length_semantics == "long_point_to_long_point"
    assert member.bom_length_mm() == pytest.approx(48 * IN)
    assert "long-point to long-point" in member.describe()
    assert [step.param("miter_angle_degrees") for step in miters] == [30.0, 30.0]
    assert [step.param("angle_degrees") for step in miters] == [60.0, 60.0]
    assert record.fab_note().count("30\N{DEGREE SIGN} off square") == 2

    solid = member.solid
    vertices = solid.val().Vertices()
    top_x = sorted(
        {round(vertex.X, 6) for vertex in vertices
         if vertex.Z == pytest.approx(member.depth)}
    )
    bottom_x = sorted(
        {round(vertex.X, 6) for vertex in vertices
         if vertex.Z == pytest.approx(0.0)}
    )
    setback = member.depth * math.tan(math.radians(30.0))
    assert top_x == pytest.approx([0.0, 48 * IN])
    assert bottom_x == pytest.approx([setback, 48 * IN - setback])
    assert len(detail.assembly.bom_table()) == 1


def test_mitered_lumber_has_physical_cut_face_datums_and_reference_end_planes():
    _, member = _mitered_member()
    setback = member.depth * math.tan(math.radians(30.0))

    near = member.datum("cut_near")
    far = member.datum("cut_far")

    assert near.origin == pytest.approx(
        (setback / 2, member.thickness / 2, member.depth / 2)
    )
    assert far.origin == pytest.approx(
        (member.length - setback / 2, member.thickness / 2, member.depth / 2)
    )
    assert near.z_axis == pytest.approx((-0.5, 0.0, -math.sqrt(3) / 2))
    assert far.z_axis == pytest.approx((0.5, 0.0, -math.sqrt(3) / 2))
    assert member.datum("end_near").origin[0] == pytest.approx(0.0)
    assert member.datum("end_far").origin[0] == pytest.approx(member.length)


def test_lumber_end_cuts_require_explicit_unambiguous_length_semantics():
    cut = {"end": "near", "miter_angle_degrees": 30, "long_face": "top"}

    with pytest.raises(ValueError, match="length_semantics.*long_point_to_long_point"):
        Lumber("2x4", 48 * IN, end_cuts=(cut,))

    with pytest.raises(ValueError, match="same long_face"):
        Lumber(
            "2x4",
            48 * IN,
            end_cuts=(cut, {**cut, "end": "far", "long_face": "bottom"}),
            length_semantics="long_point_to_long_point",
        )


def test_mitered_lumber_bom_identity_does_not_collapse_into_square_lumber():
    _, mitered = _mitered_member()
    assembly = DetailAssembly("lumber BOM probe")
    assembly.add(mitered)
    assembly.add(Lumber("2x4", 48 * IN, name="square member"))

    rows = assembly.bom_table()

    assert len(rows) == 2
    assert {row["length_mm"] for row in rows} == {48 * IN}
    assert sum("long-point to long-point" in row["dimensions"] for row in rows) == 1


def test_square_lumber_keeps_its_existing_public_identity():
    member = Lumber(
        "2x4", 48 * IN, name="square member", ease_radius=0.125 * IN
    )

    assert member.bom_group() == f"Lumber|2x4|{round(48 * IN, 1)}|False"
    assert "end_cuts" not in member.params()
    assert "length_semantics" not in member.params()
    assert member.assumptions().endswith('; end grain square.')
