"""Semantic expansion and lowering into the unchanged DetailSpec language."""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.core.registry import components
from detailgen.core.units import IN
from detailgen.packs import load_project_file
from detailgen.packs.cabinetry import FramelessCabinetryPack

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "cabinetry"
    / "frameless_base_cabinet.project.yaml"
)


def _model():
    from detailgen.packs.cabinetry.model import build_model

    section = FramelessCabinetryPack().parse(load_project_file(FIXTURE))
    return build_model(section, project_name="B30 frameless base cabinet")


def test_b30_expands_to_named_real_parts_with_stable_ids():
    model = _model()
    roles = {part.role for part in model.parts}

    assert roles >= {
        "left_end",
        "right_end",
        "bottom",
        "captured_back",
        "front_stretcher",
        "rear_stretcher",
        "adjustable_shelf",
        "door_left",
        "door_right",
        "anchor_strip",
        "toe_front",
        "toe_rear",
        "toe_left",
        "toe_right",
        "wall_anchor_stud_32",
        "wall_anchor_stud_48",
    }
    cabinet_parts = [p for p in model.parts if not p.role.startswith("wall_stud_")]
    assert all(p.part_id.startswith("cabinetry.B30.") for p in cabinet_parts)
    assert model.source_map["cabinetry.B30.left_end"].rule == "carcass.left_end"


def test_model_derives_paired_door_width_and_surface_edge_policy():
    model = _model()
    profile = model.profile
    door_left = model.part("door_left")
    expected = (
        30 * IN
        - 2 * profile.door_side_reveal_mm
        - profile.door_center_gap_mm
    ) / 2

    assert door_left.length_mm == pytest.approx(expected)
    assert door_left.edge_bands == ("left", "right", "top", "bottom")
    assert model.part("adjustable_shelf").edge_bands == ("front",)
    assert model.part("left_end").surface_class == "exposed_exterior"
    assert model.part("right_end").surface_class == "semi_exposed"
    assert model.derived_value("door_width").inputs == (
        "cabinet_width",
        "side_reveals",
        "center_gap",
    )


def test_model_contains_manufacturer_hinge_and_system32_machining():
    model = _model()
    cup_features = [f for f in model.machining if f.kind == "hinge_cup"]
    plate_features = [f for f in model.machining if f.kind == "mounting_plate"]
    pin_rows = [f for f in model.machining if f.kind == "shelf_pin_row"]

    assert len(cup_features) == 4
    assert len(plate_features) == 4
    assert len(pin_rows) == 4
    assert all(f.diameter_mm == 35.0 and f.depth_mm == 13.0
               for f in cup_features)
    assert all(f.source == "blum_clip_top_blumotion_110_h002@2025.1"
               for f in cup_features + plate_features)
    assert all(f.diameter_mm == 5.0 and f.pitch_mm == 32.0 for f in pin_rows)


def test_captured_back_blank_and_four_grooves_share_one_derivation():
    model = _model()
    back = model.part("captured_back")
    grooves = [f for f in model.machining if f.kind == "captured_back_groove"]

    assert len(grooves) == 4
    assert {f.part_id.rsplit(".", 1)[-1] for f in grooves} == {
        "left_end", "right_end", "bottom", "rear_stretcher"
    }
    assert all(f.width_mm == pytest.approx(model.profile.back_groove_width_mm)
               for f in grooves)
    assert all(f.depth_mm == pytest.approx(model.profile.back_groove_depth_mm)
               for f in grooves)
    assert back.length_mm == pytest.approx(
        30 * IN - 2 * model.profile.carcass_thickness_mm
        + 2 * model.profile.back_groove_depth_mm
    )
    expected_height = (
        34.5 * IN - 4 * IN - 2 * model.profile.carcass_thickness_mm
        + 2 * model.profile.back_groove_depth_mm
    )
    assert back.width_mm == pytest.approx(expected_height)

    doc = __import__(
        "detailgen.packs.cabinetry.lowering", fromlist=["lower_model"]
    ).lower_model(model)
    grooved = {
        component.id: component.params["grooves"]
        for component in doc.components
        if component.params.get("grooves")
    }
    assert set(grooved) == {feature.part_id for feature in grooves}


def test_anchor_targets_must_land_on_anchor_strip_not_cabinet_edges():
    import yaml
    from detailgen.packs import load_project_text
    from detailgen.packs.cabinetry.model import build_model

    raw = yaml.safe_load(FIXTURE.read_text())
    raw["site"]["wall"]["studs"].extend([
        {"id": "edge_left", "position": 24, "verified": True},
        {"id": "edge_right", "position": 54, "verified": True},
    ])
    doc = load_project_text(yaml.safe_dump(raw, sort_keys=False))
    model = build_model(
        FramelessCabinetryPack().parse(doc), project_name=doc.name
    )

    assert model.anchor_stud_ids == ("stud_32", "stud_48")


def test_wall_anchors_only_target_verified_studs_inside_cabinet_span():
    model = _model()

    assert model.anchor_stud_ids == ("stud_32", "stud_48")
    screws = [p for p in model.parts if p.role.startswith("wall_anchor_")]
    assert [round(p.at_mm[0] / IN) for p in screws] == [32, 48]
    assert all(p.component_type == "structural_screw" for p in screws)


def test_lowered_doc_uses_only_existing_base_component_vocabulary():
    from detailgen.packs.cabinetry.lowering import lower_model

    before = tuple(components.names())
    doc = lower_model(_model())
    after = tuple(components.names())

    assert after == before
    assert {component.type for component in doc.components} <= {
        "plywood_panel",
        "lumber",
        "structural_screw",
    }
    assert all(component.type in components for component in doc.components)
    assert doc.name == "B30 frameless base cabinet"
    assert doc.units == "mm"


def test_lowered_doc_preserves_stable_ids_and_installation_relationships():
    from detailgen.packs.cabinetry.lowering import lower_model

    model = _model()
    doc = lower_model(model)
    ids = {component.id for component in doc.components}

    assert ids == {part.part_id for part in model.parts}
    overlap_pairs = {
        frozenset((item.a, item.b)) for item in doc.validation.expected_overlaps
    }
    for stud_id in model.anchor_stud_ids:
        assert frozenset(
            (
                f"cabinetry.B30.wall_anchor_{stud_id}",
                f"site.north_wall.{stud_id}",
            )
        ) in overlap_pairs
    assert doc.context_grounds == frozenset(
        f"site.north_wall.{stud_id}" for stud_id in model.anchor_stud_ids
    )


def test_model_and_lowered_doc_are_deterministic():
    from detailgen.packs.cabinetry.lowering import lower_model

    a = _model()
    b = _model()

    assert a == b
    assert lower_model(a) == lower_model(b)
