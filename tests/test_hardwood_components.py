"""Indoor hardwood panel and corner-key dowel components."""

import math

import pytest

from detailgen.core.registry import components
from detailgen.core.units import IN
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text


def test_hardwood_panel_folds_miters_and_a_compiler_style_bore_from_one_record():
    from detailgen.components.hardwood import HardwoodPanel

    panel = HardwoodPanel(
        8 * IN,
        5.5 * IN,
        0.75 * IN,
        miter_ends=("near", "far"),
        ease_radius=0,
    )
    panel.apply_feature_cut(
        4 * IN,
        2.75 * IN,
        1.75 * IN,
        noun="cup opening",
        step_kind="bore",
        provenance="bore:cup_opening",
    )

    record = panel.fabrication_record("top")
    assert [step.kind for step in record.steps] == [
        "crosscut",
        "miter_crosscut",
        "miter_crosscut",
        "bore",
    ]
    assert record.stock.profile == "3/4 in hardwood panel, 5 1/2 in wide"
    assert record.stock.material_key == "hardwood"
    assert panel.material_key == "hardwood"
    assert panel.solid.val().Volume() == pytest.approx(
        record.installed_geometry().val().Volume()
    )
    assert "cup opening" in record.fab_note()


def test_hardwood_panel_and_dowel_are_registered_with_truthful_bom_language():
    from detailgen.components.hardwood import HardwoodPanel, WoodDowel

    assert components.get("hardwood_panel") is HardwoodPanel
    assert components.get("wood_dowel") is WoodDowel

    panel = HardwoodPanel(8 * IN, 5.5 * IN, 0.75 * IN)
    dowel = WoodDowel(0.375 * IN, math.sqrt(2) * 0.75 * IN)

    assert panel.bom_label() == "3/4 in hardwood panel"
    assert panel.bom_length_mm() == pytest.approx(8 * IN)
    assert "SPF" not in panel.assumptions()
    assert "pressure-treated" not in panel.assumptions().lower()
    assert dowel.bom_label() == "3/8 in hardwood dowel"
    assert dowel.bom_length_mm() == pytest.approx(math.sqrt(2) * 0.75 * IN)


def test_wood_dowel_is_a_finished_cylinder_along_local_positive_x():
    from detailgen.components.hardwood import WoodDowel

    length = math.sqrt(2) * 0.75 * IN
    diameter = 0.375 * IN
    pin = WoodDowel(diameter, length)
    bb = pin.solid.val().BoundingBox()

    assert bb.xmin == pytest.approx(0.0)
    assert bb.xlen == pytest.approx(length)
    assert bb.ylen == pytest.approx(diameter)
    assert bb.zlen == pytest.approx(diameter)
    assert pin.solid.val().Volume() == pytest.approx(
        math.pi * (diameter / 2) ** 2 * length
    )
    assert pin.material_key == "hardwood"


def test_miter_flush_dowel_has_skewed_ends_inside_the_corner_envelope():
    from detailgen.components.hardwood import WoodDowel

    thickness = 0.75 * IN
    length = math.sqrt(2) * thickness
    pin = WoodDowel(0.375 * IN, length, end_trim="miter_flush")
    rotated = pin.solid.rotate((0, 0, 0), (0, 1, 0), 45)
    bb = rotated.val().BoundingBox()

    assert bb.xmax == pytest.approx(thickness)
    projected_radius = pin.diameter / math.sqrt(2)
    assert bb.xmin == pytest.approx(-projected_radius)
    assert bb.zmin == pytest.approx(-thickness - projected_radius)
    assert bb.zmax == pytest.approx(0.0, abs=1e-6)
    assert pin.solid.val().Volume() == pytest.approx(
        math.pi * (pin.diameter / 2) ** 2 * length)
    assert "trim" in pin.assumptions().lower()


def test_detail_spec_compiles_a_mitered_hardwood_panel_with_a_bore_feature():
    doc = load_spec_text(
        """
name: hardwood feature probe
type: probe
units: in
components:
  - id: top
    type: hardwood_panel
    name: top panel
    params:
      length: 8 in
      width: 5.5 in
      thickness: 0.75 in
      miter_ends: [near, far]
    features:
      - bore: {dia: 3.5 in, id: cup_opening, name: "cup opening"}
"""
    )

    detail = compile_spec(doc)
    detail.build()
    panel = detail._by_id["top"].component
    record = panel.fabrication_record("top")
    bore = [step for step in record.steps if step.kind == "bore"]

    assert len(bore) == 1
    assert bore[0].param("feature") == "cup opening"
    assert bore[0].param("cx") == pytest.approx(4 * IN)
    assert bore[0].param("cy") == pytest.approx(2.75 * IN)
    (row,) = detail.assembly.bom_table()
    assert row["item"] == "3/4 in hardwood panel"
    assert row["material"] == "Indoor hardwood"
