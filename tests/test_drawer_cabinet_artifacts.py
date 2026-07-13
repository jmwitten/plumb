"""Fabrication, shipping, installation, and commissioning deliverables."""

from __future__ import annotations

from pathlib import Path

import yaml

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


def test_cut_list_contains_shell_three_fronts_and_fifteen_box_panels():
    project = _project()
    items = project.artifacts.cut_list
    roles = {item.role for item in items}

    assert len(items) == 29
    assert {"left_end", "right_end", "bottom", "captured_back",
            "front_stretcher", "rear_stretcher", "anchor_strip",
            "toe_front", "toe_rear", "toe_left", "toe_right"} <= roles
    assert len([role for role in roles if role.startswith("drawer_front_")]) == 3
    assert len([role for role in roles if role.startswith("drawer_")
                and not role.startswith("drawer_front_")]) == 15
    assert all(item.part_id in project.model.source_map for item in items)


def test_edge_map_and_hardware_schedule_are_complete_and_sourced():
    project = _project()
    edge_rows = project.artifacts.edge_banding
    schedule = project.artifacts.hardware_schedule
    by_kind = {}
    for item in schedule:
        by_kind.setdefault(item.kind, []).append(item)

    for cell in ("top", "middle", "bottom"):
        front_id = f"cabinetry.DB40.drawer_front_{cell}"
        assert {row.edge for row in edge_rows if row.part_id == front_id} == {
            "top", "bottom", "left", "right"
        }
    assert len(by_kind["drawer_runner_pair"]) == 3
    assert len(by_kind["drawer_locking_device_pair"]) == 3
    assert len(by_kind["drawer_lateral_stabilizer"]) == 3
    assert len(by_kind["drawer_pull"]) == 3
    assert len(by_kind["applied_front_fastener_system"]) == 3
    assert [item.quantity for item in by_kind["drawer_runner_pair"]] == [2, 2, 2]
    assert [item.quantity for item in by_kind["drawer_locking_device_pair"]] == [2, 2, 2]
    assert [item.quantity for item in by_kind["drawer_lateral_stabilizer"]] == [1, 1, 1]
    assert [item.quantity for item in by_kind["drawer_pull"]] == [1, 1, 1]
    assert [item.quantity for item in by_kind["applied_front_fastener_system"]] == [4, 4, 4]
    assert all(item.source_url for item in schedule)


def test_machining_schedule_includes_stabilizer_cuts_and_every_row_resolves():
    project = _project()
    rows = project.artifacts.machining_schedule
    kinds = [row.kind for row in rows]
    part_ids = {part.part_id for part in project.model.parts}

    assert kinds.count("drawer_bottom_groove") == 12
    assert kinds.count("runner_rear_notch") == 6
    assert kinds.count("runner_hook_bore") == 6
    assert kinds.count("locking_device_bore") == 6
    assert kinds.count("runner_fixing_station") == 12
    assert kinds.count("stabilizer_gear_rack_cut") == 3
    assert kinds.count("stabilizer_linkage_rod_cut") == 3
    assert kinds.count("applied_front_attachment") == 12
    assert kinds.count("pull_bore") == 6
    assert {row.length_mm for row in rows
            if row.kind == "stabilizer_gear_rack_cut"} == {560.0}
    assert {row.length_mm for row in rows
            if row.kind == "stabilizer_linkage_rod_cut"} == {659.9}
    assert all(row.part_id in part_ids for row in rows)


def test_workflow_is_specific_from_fabrication_through_empty_case_shipping():
    project = _project()
    fabrication = {step.step_id: step for step in project.artifacts.fabrication_steps}
    assembly = {step.step_id: step for step in project.artifacts.assembly_steps}

    assert {
        "fab.verify_material", "fab.breakdown", "fab.shell_back_grooves",
        "fab.drawer_bottom_grooves", "fab.drawer_rear_preparation",
        "fab.runner_fixing", "fab.stabilizer_preparation",
        "fab.fronts_and_pulls", "fab.joinery_step_drill", "fab.edge_band",
    } <= fabrication.keys()
    assert "560 mm" in fabrication["fab.stabilizer_preparation"].instruction
    assert "659.90 mm" in fabrication["fab.stabilizer_preparation"].instruction
    assert {
        "assembly.toe_base", "assembly.carcass", "assembly.back",
        "assembly.drawer_boxes", "assembly.drawer_hardware",
        "assembly.fronts_pulls", "shop.adjust_drawers",
        "ship.record_adjustment_identity", "ship.remove_drawers",
        "ship.empty_carcass",
    } <= assembly.keys()
    assert assembly["shop.adjust_drawers"].phase \
        < assembly["ship.record_adjustment_identity"].phase \
        < assembly["ship.remove_drawers"].phase \
        < assembly["ship.empty_carcass"].phase
    assert "side-to-side, height, tilt, and depth" in \
        assembly["shop.adjust_drawers"].instruction
    assert "empty carcass" in assembly["ship.empty_carcass"].instruction


def test_installation_reinstalls_by_identity_and_commissions_under_load():
    project = _project()
    steps = {step.step_id: step for step in project.artifacts.installation_steps}

    assert {
        "install.release_gate", "install.survey", "install.datum",
        "install.toe_base", "install.set_empty_carcass", "install.wall_anchor",
        "install.reinstall_by_identity", "install.commission_drawers",
    } <= steps.keys()
    assert steps["install.set_empty_carcass"].phase \
        < steps["install.wall_anchor"].phase \
        < steps["install.reinstall_by_identity"].phase \
        < steps["install.commission_drawers"].phase
    commissioning = steps["install.commission_drawers"].instruction
    for phrase in (
        "full extension", "BLUMOTION", "1.50 mm", "2.00 mm", "40 lb",
        "fastener", "acceptance record",
    ):
        assert phrase in commissioning
    assert "label" in steps["install.reinstall_by_identity"].instruction


def test_artifacts_never_hide_judgment_behind_adjust_as_needed():
    payload = _project().artifacts.to_dict()
    assert "adjust as needed" not in str(payload).lower()
    model_ids = {part.part_id for part in _project().model.parts}
    for collection in (
        payload["fabrication_steps"], payload["assembly_steps"],
        payload["installation_steps"],
    ):
        for step in collection:
            assert set(step["affected"]) <= model_ids
