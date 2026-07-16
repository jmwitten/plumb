"""Exterior cedar panel vocabulary and multi-bore fabrication truth."""

import math

import pytest

from detailgen.core.buildinfo import geometry_hash
from detailgen.core.registry import components
from detailgen.core.units import IN
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text


def test_cedar_panel_is_registered_with_exterior_truthful_language():
    from detailgen.components.cedar import CedarPanel

    assert components.get("cedar_panel") is CedarPanel
    panel = CedarPanel(8 * IN, 5.5 * IN, 0.75 * IN)

    assert panel.material_key == "cedar"
    assert panel.bom_label() == "3/4 in cedar panel"
    assert panel.bom_length_mm() == pytest.approx(8 * IN)
    assert "untreated" in panel.assumptions().lower()
    assert "indoor" not in panel.assumptions().lower()
    assert "pressure-treated" not in panel.assumptions().lower()


def test_cedar_panel_compatibility_surface_is_characterized():
    from detailgen.components.cedar import CedarPanel

    panel = CedarPanel(8 * IN, 5.5 * IN, 0.75 * IN, ease_radius=1 / 16 * IN)
    panel.apply_feature_cut(
        4 * IN,
        2.75 * IN,
        0.5 * IN,
        noun="probe",
        step_kind="bore",
        provenance="probe",
    )

    assert geometry_hash(panel.solid) == (
        "0cf648eaa0442878c6ceb3b13de6eb26f4eb72d7092c9561473ce1bc3747b1f2"
    )
    assert set(panel.datums) == {"origin", "base", "top", "end_near", "end_far"}
    assert panel.datum("base").origin == pytest.approx((4 * IN, 2.75 * IN, 0))
    assert panel.datum("top").origin == pytest.approx(
        (4 * IN, 2.75 * IN, 0.75 * IN)
    )
    assert panel.datum("end_near").origin == pytest.approx(
        (0, 2.75 * IN, 0.375 * IN)
    )
    assert panel.datum("end_far").origin == pytest.approx(
        (8 * IN, 2.75 * IN, 0.375 * IN)
    )
    record = panel.fabrication_record("probe")
    assert [step.kind for step in record.steps] == ["crosscut", "ease", "bore"]
    assert record.stock.profile == "3/4 in cedar panel, 5 1/2 in wide"
    assert record.stock.material_key == "cedar"
    assert panel.solid.val().Volume() == pytest.approx(530680.747769327)
    assert panel.bom_label() == "3/4 in cedar panel"
    assert panel.bom_length_mm() == pytest.approx(8 * IN)
    assert panel.assumptions() == (
        "Solid untreated exterior cedar panel; species, grade, weathering, "
        "and structural capacity are not analyzed."
    )


def test_cedar_panel_folds_every_distinct_bore_from_one_fabrication_record():
    from detailgen.components.cedar import CedarPanel

    panel = CedarPanel(8 * IN, 5.5 * IN, 0.75 * IN, ease_radius=1 / 16 * IN)
    bores = (
        (4 * IN, 4.5 * IN, 9 / 16 * IN, "entrance", "bore:entrance"),
        (1 * IN, 0.75 * IN, 5 / 16 * IN, "vent 1", "bore:vent_1"),
        (7 * IN, 0.75 * IN, 5 / 16 * IN, "vent 2", "bore:vent_2"),
    )
    for cx, cy, radius, noun, provenance in bores:
        panel.apply_feature_cut(
            cx,
            cy,
            radius,
            noun=noun,
            step_kind="bore",
            provenance=provenance,
        )

    record = panel.fabrication_record("front")
    assert [step.kind for step in record.steps] == [
        "crosscut",
        "ease",
        "bore",
        "bore",
        "bore",
    ]
    assert [step.param("feature") for step in record.steps if step.kind == "bore"] == [
        "entrance",
        "vent 1",
        "vent 2",
    ]
    assert record.stock.profile == "3/4 in cedar panel, 5 1/2 in wide"
    assert record.stock.material_key == "cedar"
    assert panel.solid.val().Volume() == pytest.approx(
        record.installed_geometry().val().Volume()
    )
    uncut_volume = panel.length * panel.width * panel.thickness
    expected_bores = sum(math.pi * radius**2 * panel.thickness for _, _, radius, _, _ in bores)
    assert panel.solid.val().Volume() < uncut_volume - 0.95 * expected_bores


def test_detail_spec_compiles_multiple_named_cedar_bores_without_overwriting():
    doc = load_spec_text(
        """
name: cedar feature probe
type: probe
units: in
components:
  - id: floor
    type: cedar_panel
    name: recessed floor
    params: {length: 4 in, width: 4 in, thickness: 0.75 in}
    features:
      - bore: {dia: 0.25 in, id: drain_fl, name: "front-left drain", at: [0.5 in, 0.5 in]}
      - bore: {dia: 0.25 in, id: drain_fr, name: "front-right drain", at: [3.5 in, 0.5 in]}
      - bore: {dia: 0.25 in, id: drain_rl, name: "rear-left drain", at: [0.5 in, 3.5 in]}
      - bore: {dia: 0.25 in, id: drain_rr, name: "rear-right drain", at: [3.5 in, 3.5 in]}
"""
    )

    detail = compile_spec(doc)
    detail.build()
    floor = detail._by_id["floor"].component
    record = floor.fabrication_record("floor")
    bore_steps = [step for step in record.steps if step.kind == "bore"]

    assert len(bore_steps) == 4
    assert [step.param("feature") for step in bore_steps] == [
        "front-left drain",
        "front-right drain",
        "rear-left drain",
        "rear-right drain",
    ]
    callout_facts = [
        fact for fact in detail.derivation_report()
        if fact.rule == "spec.feature.callout" and fact.connection == "floor"
    ]
    assert len(callout_facts) == 4
    (row,) = detail.assembly.bom_table()
    assert row["item"] == "3/4 in cedar panel"
    assert row["material"] == "Untreated exterior cedar"


@pytest.mark.parametrize(
    "length,width,thickness",
    [(0, 4 * IN, 0.75 * IN), (4 * IN, 0, 0.75 * IN), (4 * IN, 4 * IN, 0)],
)
def test_cedar_panel_reports_non_positive_dimensions(length, width, thickness):
    from detailgen.components.cedar import CedarPanel

    assert CedarPanel(length, width, thickness).check()
