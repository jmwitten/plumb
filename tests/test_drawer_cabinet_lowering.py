"""DB40 composition and lowering through the unchanged base vocabulary."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.core.registry import components
from detailgen.packs import load_project_text
from detailgen.packs.cabinetry import FramelessCabinetryPack


BASE = Path(__file__).parent / "fixtures/cabinetry/frameless_base_cabinet.project.yaml"


def _project():
    raw = yaml.safe_load(BASE.read_text())
    raw["name"] = "DB40 three-drawer clothing cabinet"
    raw["cabinetry"]["cabinets"] = [{
        "archetype": "drawer_base_three@1",
        "id": "DB40",
        "width": 40,
        "placement": {"against": "north_wall", "from_left_datum": 24},
        "conditions": {"left_end": "exposed", "right_end": "exposed"},
    }]
    return FramelessCabinetryPack().compile(
        load_project_text(yaml.safe_dump(raw, sort_keys=False))
    )


def _bbox(placed):
    box = placed.world_solid().val().BoundingBox()
    return (box.xmin, box.ymin, box.zmin, box.xmax, box.ymax, box.zmax)


def test_db40_composes_common_shell_with_real_drawer_bank():
    project = _project()
    model = project.model
    roles = {part.role for part in model.parts}

    assert type(model).__name__ == "DrawerBaseModel"
    assert roles >= {
        "left_end", "right_end", "bottom", "captured_back",
        "front_stretcher", "rear_stretcher", "anchor_strip",
        "toe_front", "toe_rear", "toe_left", "toe_right",
        "drawer_front_top", "drawer_front_middle", "drawer_front_bottom",
    }
    assert not roles & {
        "door_left", "door_right", "adjustable_shelf", "shelf_pin_row"
    }
    assert len([role for role in roles if role.startswith("drawer_")
                and not role.startswith("drawer_front_")]) == 15
    assert len([role for role in roles if role.startswith("drawer_front_")]) == 3
    assert all(part.part_id in model.source_map for part in model.parts)


def test_db40_front_allocation_closes_exact_reveal_equation():
    model = _project().model
    cabinet = model.section.cabinets[0]
    front_bottom = model.part("drawer_front_bottom")
    front_middle = model.part("drawer_front_middle")
    front_top = model.part("drawer_front_top")
    body_bottom = model.shell.base_z_mm + cabinet.toe_kick_height_mm
    body_top = body_bottom + model.shell.body_height_mm

    assert front_bottom.at_mm[0] - model.shell.x0_mm == pytest.approx(1.5)
    assert cabinet.width_mm - 1.5 - front_bottom.length_mm == pytest.approx(1.5)
    assert front_bottom.at_mm[2] - body_bottom == pytest.approx(1.5)
    assert front_middle.at_mm[2] - (
        front_bottom.at_mm[2] + front_bottom.width_mm
    ) == pytest.approx(2.0)
    assert front_top.at_mm[2] - (
        front_middle.at_mm[2] + front_middle.width_mm
    ) == pytest.approx(2.0)
    assert body_top - (front_top.at_mm[2] + front_top.width_mm) == pytest.approx(1.5)


def test_db40_has_pinned_hardware_and_required_machining_per_drawer():
    model = _project().model
    kinds = [system.kind for system in model.hardware]

    assert kinds.count("drawer_runner_pair") == 3
    assert kinds.count("drawer_locking_device_pair") == 3
    assert kinds.count("drawer_lateral_stabilizer") == 3
    assert kinds.count("drawer_pull") == 3
    assert kinds.count("applied_front_fastener_system") == 3
    assert all(set(system.related_parts) <= {part.part_id for part in model.parts}
               for system in model.hardware
               if system.kind.startswith("drawer_")
               or system.kind == "applied_front_fastener_system")
    assert model.drawer_bank.inside_depth_mm >= model.drawer_bank.runner.minimum_inside_depth_mm
    assert len([item for item in model.machining
                if item.kind == "runner_fixing_station"]) == 12


def test_db40_lowers_one_for_one_without_new_component_vocabulary():
    project = _project()
    model_ids = {part.part_id for part in project.model.parts}
    lowered_ids = {component.id for component in project.lowered_doc.components}

    assert lowered_ids == model_ids
    assert {component.type for component in project.lowered_doc.components} <= {
        "plywood_panel", "lumber", "structural_screw"
    }
    assert all(component.type in components
               for component in project.lowered_doc.components)

    bonds = {
        frozenset((item.a, item.b)) for item in project.lowered_doc.validation.bonds
    }
    for cell_id in ("top", "middle", "bottom"):
        prefix = "cabinetry.DB40."
        assert frozenset((prefix + f"drawer_{cell_id}_bottom",
                          prefix + f"drawer_{cell_id}_side_left")) in bonds
        assert frozenset((prefix + f"drawer_{cell_id}_front",
                          prefix + f"drawer_front_{cell_id}")) in bonds


def test_db40_build_has_oriented_fronts_and_full_depth_boxes():
    project = _project()
    assembly = project.build()
    placed = {part.name: part for part in assembly.parts}

    top_front = _bbox(placed["DB40 drawer front top"])
    bottom_side = _bbox(placed["DB40 drawer bottom side left"])
    bottom_panel = _bbox(placed["DB40 drawer bottom bottom"])

    assert top_front[3] - top_front[0] == pytest.approx(1013.0)
    assert top_front[4] - top_front[1] == pytest.approx(19.05)
    assert top_front[5] - top_front[2] == pytest.approx(158.75)
    assert bottom_side[3] - bottom_side[0] == pytest.approx(16.0)
    assert bottom_side[4] - bottom_side[1] == pytest.approx(533.0)
    assert bottom_side[5] - bottom_side[2] == pytest.approx(254.0)
    assert bottom_panel[3] - bottom_panel[0] == pytest.approx(947.9)
    assert bottom_panel[4] - bottom_panel[1] == pytest.approx(513.0)


def test_db40_preserves_common_anchor_overlap_contract():
    project = _project()
    overlaps = {
        frozenset((item.a, item.b))
        for item in project.lowered_doc.validation.expected_overlaps
    }

    for stud_id in project.model.anchor_stud_ids:
        assert frozenset((
            f"cabinetry.DB40.wall_anchor_{stud_id}",
            f"site.north_wall.{stud_id}",
        )) in overlaps
