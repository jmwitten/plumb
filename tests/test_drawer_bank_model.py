"""Product-independent drawer-bank geometry and manufacturing semantics."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.packs import load_project_text
from detailgen.packs.cabinetry import FramelessCabinetryPack


BASE = Path(__file__).parent / "fixtures/cabinetry/frameless_base_cabinet.project.yaml"


def _declaration():
    raw = yaml.safe_load(BASE.read_text())
    raw["cabinetry"]["cabinets"] = [{
        "archetype": "drawer_base_three@1",
        "id": "DB40",
        "width": 40,
        "placement": {"against": "north_wall", "from_left_datum": 24},
        "conditions": {"left_end": "exposed", "right_end": "exposed"},
    }]
    doc = load_project_text(yaml.safe_dump(raw, sort_keys=False))
    return FramelessCabinetryPack().parse(doc).cabinets[0]


def _build(namespace="cabinetry.DB40", x=628.65):
    from detailgen.packs.cabinetry.drawers import build_drawer_bank

    cabinet = _declaration()
    return build_drawer_bank(
        cabinet.drawer_bank,
        namespace=namespace,
        opening_origin_mm=(x, 0.0, 101.6),
        opening_width_mm=977.9,
        opening_height_mm=774.7,
        inside_depth_mm=571.5,
        front_origin_mm=(x - 17.55, 0.0, 101.6),
        front_width_mm=1013.0,
        front_thickness_mm=19.05,
        mounting_part_ids=(f"{namespace}.left_end", f"{namespace}.right_end"),
        material_density_kg_m3=500.0,
    )


def test_db40_bank_derives_manufacturer_box_widths_and_progressive_cells():
    bank = _build()

    assert bank.opening_width_mm == pytest.approx(977.9)
    assert bank.outside_box_width_mm == pytest.approx(967.9)
    assert bank.inside_box_width_mm == pytest.approx(935.9)
    assert bank.box_length_mm == pytest.approx(533)
    assert [cell.cell_id for cell in bank.cells] == ["top", "middle", "bottom"]
    assert [cell.front_height_mm for cell in bank.cells] == pytest.approx(
        [158.75, 254.0, 354.95]
    )
    assert [cell.box_height_mm for cell in bank.cells] == pytest.approx(
        [101.6, 177.8, 254.0]
    )
    assert all(cell.contents_load_lb == 40 for cell in bank.cells)


def test_bank_generates_real_box_panels_fronts_and_stable_roles():
    bank = _build()

    assert [part.role for part in bank.parts] == [
        "drawer_top_side_left", "drawer_top_side_right", "drawer_top_front",
        "drawer_top_back", "drawer_top_bottom", "drawer_front_top",
        "drawer_middle_side_left", "drawer_middle_side_right",
        "drawer_middle_front", "drawer_middle_back", "drawer_middle_bottom",
        "drawer_front_middle", "drawer_bottom_side_left",
        "drawer_bottom_side_right", "drawer_bottom_front", "drawer_bottom_back",
        "drawer_bottom_bottom", "drawer_front_bottom",
    ]
    assert len([part for part in bank.parts if "drawer_front_" in part.role]) == 3
    assert len([part for part in bank.parts if "drawer_front_" not in part.role]) == 15
    assert all(part.part_id in bank.source_map for part in bank.parts)
    assert bank.part("drawer_top_side_left").thickness_mm == pytest.approx(16)
    assert bank.part("drawer_top_bottom").thickness_mm == pytest.approx(12)
    assert bank.part("drawer_front_bottom").width_mm == pytest.approx(354.95)


def test_bank_emits_required_drawer_and_runner_machining():
    bank = _build()
    kinds = [feature.kind for feature in bank.machining]

    assert kinds.count("drawer_bottom_groove") == 12
    assert kinds.count("runner_rear_notch") == 6
    assert kinds.count("runner_hook_bore") == 6
    assert kinds.count("locking_device_bore") == 6
    assert kinds.count("runner_fixing_station") == 12
    assert kinds.count("applied_front_attachment") == 12
    assert kinds.count("pull_bore") == 6
    assert all(feature.part_id in {part.part_id for part in bank.parts}
               or feature.part_id in bank.mounting_part_ids
               for feature in bank.machining)


def test_bank_pins_complete_hardware_set_for_each_drawer():
    bank = _build()

    assert [system.kind for system in bank.hardware] == [
        "drawer_runner_pair", "drawer_locking_device_pair",
        "drawer_lateral_stabilizer", "drawer_pull",
        "drawer_runner_pair", "drawer_locking_device_pair",
        "drawer_lateral_stabilizer", "drawer_pull",
        "drawer_runner_pair", "drawer_locking_device_pair",
        "drawer_lateral_stabilizer", "drawer_pull",
    ]
    assert [system.quantity for system in bank.hardware] == [2, 2, 1, 1] * 3
    assert all(cell.moving_mass_kg > 0 for cell in bank.cells)
    assert all(cell.rated_moving_load_lb < bank.runner.dynamic_rating_lb
               for cell in bank.cells)


def test_same_core_builds_future_vanity_namespace_without_parent_assumptions():
    db40 = _build()
    vanity = _build(namespace="vanity.V60.left_bank", x=100.0)

    assert vanity.outside_box_width_mm == pytest.approx(db40.outside_box_width_mm)
    assert vanity.inside_box_width_mm == pytest.approx(db40.inside_box_width_mm)
    assert [cell.front_height_mm for cell in vanity.cells] == pytest.approx(
        [cell.front_height_mm for cell in db40.cells]
    )
    assert all(part.part_id.startswith("vanity.V60.left_bank.")
               for part in vanity.parts)
    assert all("toe" not in part.role and "wall" not in part.role
               and "plumbing" not in part.role for part in vanity.parts)
