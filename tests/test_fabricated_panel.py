"""Reusable material-parameterized solid panel vocabulary."""

import json

import pytest

from detailgen.core.materials import MATERIALS, Material
from detailgen.core.registry import components
from detailgen.core.units import IN
from detailgen.rendering.export import export_manifest
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text


def test_fabricated_panel_is_registered_and_compiles_a_new_material(
    monkeypatch, tmp_path
):
    from detailgen.components import FabricatedPanel

    monkeypatch.setitem(
        MATERIALS,
        "mahogany_probe",
        Material("Select mahogany", (0.31, 0.12, 0.07)),
    )
    assert components.get("fabricated_panel") is FabricatedPanel
    doc = load_spec_text(
        """
name: generic panel probe
type: probe
units: in
components:
  - id: panel
    type: fabricated_panel
    name: select panel
    params:
      length: 8 in
      width: 5.5 in
      thickness: 0.75 in
      material_key: mahogany_probe
      stock_label: mahogany
      material_assumptions: >-
        Select mahogany panel for interior use; species, grade, moisture
        condition, finish, and structural capacity are not analyzed.
"""
    )

    detail = compile_spec(doc)
    detail.build()
    panel = detail._by_id["panel"].component
    row = detail.assembly.bom_table()[0]
    manifest_path = export_manifest(
        detail.assembly, tmp_path / "detail.manifest.json"
    )
    manifest_part = json.loads(manifest_path.read_text())["parts"][0]

    assert panel.material_key == "mahogany_probe"
    assert panel.fabrication_record().stock.profile == (
        "3/4 in mahogany panel, 5 1/2 in wide"
    )
    assert row["item"] == "3/4 in mahogany panel"
    assert row["material"] == "Select mahogany"
    assert "structural capacity are not analyzed" in panel.assumptions()
    assert manifest_part["rgba"] == [0.31, 0.12, 0.07, 1.0]


def test_fabricated_panel_rejects_unknown_material_and_lists_known_keys():
    from detailgen.components import FabricatedPanel

    with pytest.raises(ValueError, match="unknown panel material") as caught:
        FabricatedPanel(8 * IN, 5.5 * IN, 0.75 * IN, "does_not_exist")

    assert "cedar" in str(caught.value)
    assert "hardwood" in str(caught.value)


@pytest.mark.parametrize(
    "length,width,thickness",
    [(0, 4 * IN, 0.75 * IN), (4 * IN, 0, 0.75 * IN), (4 * IN, 4 * IN, 0)],
)
def test_fabricated_panel_reports_non_positive_dimensions(
    length, width, thickness
):
    from detailgen.components import FabricatedPanel

    panel = FabricatedPanel(length, width, thickness, "cedar")
    assert panel.check()


def test_fabricated_panel_rejects_unknown_miter_end():
    from detailgen.components import FabricatedPanel

    with pytest.raises(ValueError, match="near.*far"):
        FabricatedPanel(
            8 * IN,
            5.5 * IN,
            0.75 * IN,
            "cedar",
            miter_ends=("middle",),
        )


def test_fabricated_panel_retains_every_feature_in_record_and_cache_identity():
    from detailgen.components import FabricatedPanel

    panel = FabricatedPanel(8 * IN, 5.5 * IN, 0.75 * IN, "cedar")
    before = panel.cache_key()
    for index, step_kind in enumerate(("bore", "notch", "bore"), start=1):
        panel.apply_feature_cut(
            index * IN,
            2.75 * IN,
            0.125 * IN,
            noun=f"feature {index}",
            step_kind=step_kind,
            provenance=f"probe:{index}",
        )

    record = panel.fabrication_record("panel")

    assert [step.kind for step in record.steps] == [
        "crosscut",
        "bore",
        "notch",
        "bore",
    ]
    assert [
        step.param("feature") for step in record.steps[1:]
    ] == ["feature 1", "feature 2", "feature 3"]
    assert panel.cache_key() != before
    with pytest.raises(ValueError, match="bore.*notch"):
        panel.apply_feature_cut(
            4 * IN,
            2.75 * IN,
            0.125 * IN,
            noun="bad",
            step_kind="drillish",
            provenance="bad",
        )


def test_fabricated_panel_derives_stock_label_and_generic_assumptions(
    monkeypatch,
):
    from detailgen.components import FabricatedPanel

    monkeypatch.setitem(
        MATERIALS,
        "species_probe",
        Material("Species probe", (0.2, 0.3, 0.4)),
    )
    panel = FabricatedPanel(8 * IN, 5.5 * IN, 0.75 * IN, "species_probe")

    assert panel.fabrication_record().stock.profile == (
        "3/4 in species probe panel, 5 1/2 in wide"
    )
    assert panel.bom_label() == "3/4 in species probe panel"
    assumptions = panel.assumptions().lower()
    for phrase in ("grade", "moisture", "finish", "structural capacity"):
        assert phrase in assumptions
