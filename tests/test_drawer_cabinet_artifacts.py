"""Fabrication, shipping, installation, and commissioning deliverables."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from detailgen.packs import load_project_text
from detailgen.packs.cabinetry import FramelessCabinetryPack
from detailgen.packs.cabinetry.artifacts import build_artifacts
from detailgen.packs.cabinetry.validation import validate_model


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
    assert len(by_kind["drawer_runner_installation_screw"]) == 3
    assert len(by_kind["drawer_locking_device_pair"]) == 3
    assert len(by_kind["drawer_locking_device_screw"]) == 3
    assert len(by_kind["drawer_lateral_stabilizer"]) == 3
    assert len(by_kind["drawer_pull"]) == 3
    assert len(by_kind["drawer_pull_mounting_screw"]) == 3
    assert len(by_kind["applied_front_fastener_system"]) == 3
    assert [item.quantity for item in by_kind["drawer_runner_pair"]] == [2, 2, 2]
    assert [item.quantity for item in by_kind["drawer_runner_installation_screw"]] == [4, 4, 4]
    assert [item.quantity for item in by_kind["drawer_locking_device_pair"]] == [2, 2, 2]
    assert [item.quantity for item in by_kind["drawer_locking_device_screw"]] == [4, 4, 4]
    assert [item.quantity for item in by_kind["drawer_lateral_stabilizer"]] == [1, 1, 1]
    assert [item.quantity for item in by_kind["drawer_pull"]] == [1, 1, 1]
    assert [item.quantity for item in by_kind["drawer_pull_mounting_screw"]] == [2, 2, 2]
    assert {item.product_id for item in by_kind["drawer_pull_mounting_screw"]} == {
        "hafele_handle_screw_m4x26_022_35_261@2026.1"
    }
    assert [item.quantity for item in by_kind["applied_front_fastener_system"]] == [4, 4, 4]
    assert all(item.source_url for item in schedule)


def test_machining_schedule_includes_stabilizer_cuts_and_every_row_resolves():
    project = _project()
    rows = project.artifacts.machining_schedule
    kinds = [row.kind for row in rows]
    part_ids = {part.part_id for part in project.model.parts}
    hardware_ids = {system.system_id for system in project.model.hardware}

    assert kinds.count("drawer_bottom_groove") == 12
    assert kinds.count("runner_rear_notch") == 6
    assert kinds.count("runner_hook_bore") == 6
    assert kinds.count("locking_device_bore") == 12
    assert kinds.count("runner_fixing_station") == 12
    assert kinds.count("stabilizer_gear_rack_cut") == 3
    assert kinds.count("stabilizer_linkage_rod_cut") == 3
    assert kinds.count("applied_front_attachment") == 12
    assert kinds.count("pull_bore") == 6
    assert {row.length_mm for row in rows
            if row.kind == "stabilizer_gear_rack_cut"} == {560.0}
    assert {row.length_mm for row in rows
            if row.kind == "stabilizer_linkage_rod_cut"} == {659.9}
    assert all(row.part_id in part_ids | hardware_ids for row in rows)
    attachments = [row for row in rows if row.kind == "applied_front_attachment"]
    assert all("drawer_front_" not in row.part_id for row in attachments)
    assert {row.diameter_mm for row in attachments} == {5.0}
    assert {row.depth_mm for row in attachments} == {16.0}
    assert {
        row.part_id for row in rows if row.kind.startswith("stabilizer_")
    } == {
        f"cabinetry.DB40.{cell}.lateral_stabilizer"
        for cell in ("top", "middle", "bottom")
    }
    locking = [row for row in rows if row.kind == "locking_device_bore"]
    assert {row.diameter_mm for row in locking} == {2.5}
    assert {row.depth_mm for row in locking} == {10.0}
    assert {row.coordinate_system for row in locking} == {
        "Blum T65.1600.01 template at drawer front corner"
    }


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
    assert "T65.1600.01" in fabrication["fab.locking_device_preparation"].instruction
    assert "2.5 mm" in fabrication["fab.locking_device_preparation"].instruction
    assert "606N" in fabrication["fab.runner_fixing"].instruction
    assert "2 screws per runner" in fabrication["fab.runner_fixing"].instruction
    assert "Lay out and mark" in fabrication["fab.runner_fixing"].instruction
    assert "Do not drill an unsourced clearance or pilot diameter" in \
        fabrication["fab.runner_fixing"].instruction
    assert "Ø5 mm through-clearance holes in each box front" in \
        fabrication["fab.fronts_and_pulls"].instruction
    assert "never drill attachment holes through the decorative applied front" in \
        fabrication["fab.fronts_and_pulls"].instruction
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
    assert "from inside the drawer box" in \
        assembly["assembly.fronts_pulls"].instruction


def test_shop_instructions_project_selected_adapter_dimensions_not_literals():
    project = _project()
    bank = project.model.drawer_bank
    model = replace(project.model, drawer_bank=replace(
        bank,
        runner=replace(
            bank.runner,
            bottom_recess_mm=14.0,
            minimum_rear_notch_mm=51.0,
            hook_bore_mm=(7.0, 11.0),
            front_setback_mm=4.0,
            required_rear_fixing_stations_mm=(262.0, 358.0),
        ),
        stabilizer=replace(
            bank.stabilizer,
            gear_rack_length_mm=561.0,
            linkage_rod_cut_deduction_mm=319.0,
        ),
        pull_product=replace(bank.pull_product, hole_spacing_mm=225.0),
        locking_device=replace(
            bank.locking_device,
            left_sku="TEST-LOCK-L",
            right_sku="TEST-LOCK-R",
        ),
        front_edge_reveal_mm=1.75,
        front_gap_mm=2.25,
    ))

    artifacts = build_artifacts(model, validate_model(model))
    fabrication = {step.step_id: step.instruction
                   for step in artifacts.fabrication_steps}

    assert "14 mm bottom recess" in fabrication["fab.drawer_bottom_grooves"]
    assert "51 mm" in fabrication["fab.drawer_rear_preparation"]
    assert "7 x 11 mm" in fabrication["fab.drawer_rear_preparation"]
    assert "4 mm setback" in fabrication["fab.runner_fixing"]
    assert "262 mm and 358 mm" in fabrication["fab.runner_fixing"]
    assert "561 mm" in fabrication["fab.stabilizer_preparation"]
    assert "minus 319 mm" in fabrication["fab.stabilizer_preparation"]
    assert "658.90 mm" in fabrication["fab.stabilizer_preparation"]
    assert "225 mm center-to-center" in fabrication["fab.fronts_and_pulls"]
    assembly = {step.step_id: step.instruction for step in artifacts.assembly_steps}
    assert "TEST-LOCK-L" in assembly["assembly.drawer_hardware"]
    assert "TEST-LOCK-R" in assembly["assembly.drawer_hardware"]
    assert "T51.7601" not in assembly["assembly.drawer_hardware"]
    installation = {
        step.step_id: step.instruction for step in artifacts.installation_steps
    }
    assert "1.75 mm perimeter reveals" in assembly["shop.adjust_drawers"]
    assert "2.25 mm inter-front gaps" in assembly["shop.adjust_drawers"]
    assert "1.75 mm perimeter reveals" in installation["install.commission_drawers"]
    assert "2.25 mm inter-front gaps" in installation["install.commission_drawers"]


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
    assert steps["install.commission_drawers"].phase \
        < steps["install.countertop"].phase
    assert steps["install.countertop"].phase == max(
        step.phase for step in project.artifacts.installation_steps
    )
    commissioning = steps["install.commission_drawers"].instruction
    for phrase in (
        "full extension", "BLUMOTION", "1.50 mm", "2.00 mm", "40 lb",
        "fastener", "acceptance record",
    ):
        assert phrase in commissioning
    assert "label" in steps["install.reinstall_by_identity"].instruction


def test_artifacts_never_hide_judgment_behind_adjust_as_needed():
    project = _project()
    payload = project.artifacts.to_dict()
    assert "adjust as needed" not in str(payload).lower()
    model_ids = (
        {part.part_id for part in project.model.parts}
        | {system.system_id for system in project.model.hardware}
    )
    for collection in (
        payload["fabrication_steps"], payload["assembly_steps"],
        payload["installation_steps"],
    ):
        for step in collection:
            assert set(step["affected"]) <= model_ids
