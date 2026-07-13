"""Adversarial one-fact mutations for the DB40 release-rule boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from detailgen.packs import load_project_text
from detailgen.packs.cabinetry import FramelessCabinetryPack
from detailgen.packs.cabinetry.drawer_base import build_drawer_base_model
from detailgen.packs.cabinetry.validation import validate_model


BASE = Path(__file__).parent / "fixtures/cabinetry/frameless_base_cabinet.project.yaml"

DRAWER_RULES = {
    "cabinetry.drawer.front_allocation",
    "cabinetry.drawer.width_formula",
    "cabinetry.drawer.side_thickness",
    "cabinetry.drawer.inside_depth",
    "cabinetry.drawer.box_height",
    "cabinetry.drawer.bottom_geometry",
    "cabinetry.drawer.rear_preparation",
    "cabinetry.drawer.runner_fixing",
    "cabinetry.drawer.locking_devices",
    "cabinetry.drawer.lateral_stabilizer",
    "cabinetry.drawer.stabilizer_capacity_credit",
    "cabinetry.drawer.moving_load",
    "cabinetry.drawer.front_fastener_stack",
    "cabinetry.drawer.closed_reveals",
    "cabinetry.drawer.extended_clearance",
    "cabinetry.drawer.ship_install_sequence",
}


def _model():
    raw = yaml.safe_load(BASE.read_text())
    raw["name"] = "DB40 three-drawer clothing cabinet"
    raw["cabinetry"]["cabinets"] = [{
        "archetype": "drawer_base_three@1",
        "id": "DB40",
        "width": 40,
        "placement": {"against": "north_wall", "from_left_datum": 24},
        "conditions": {"left_end": "exposed", "right_end": "exposed"},
    }]
    doc = load_project_text(yaml.safe_dump(raw, sort_keys=False))
    section = FramelessCabinetryPack().parse(doc)
    return build_drawer_base_model(section, project_name=doc.name)


def _replace_part(model, role: str, **changes):
    old = model.part(role)
    new = replace(old, **changes)
    model_parts = tuple(new if part.part_id == old.part_id else part
                        for part in model.parts)
    bank_parts = tuple(new if part.part_id == old.part_id else part
                       for part in model.drawer_bank.parts)
    return replace(
        model,
        parts=model_parts,
        drawer_bank=replace(model.drawer_bank, parts=bank_parts),
    )


def _replace_machining(model, machining):
    return replace(
        model,
        machining=tuple(machining),
        drawer_bank=replace(model.drawer_bank, machining=tuple(
            item for item in machining if item in model.drawer_bank.machining
        )),
    )


def _finding(model, rule):
    return validate_model(model).by_rule(rule)


def _assert_required_fail(model, rule, text):
    finding = _finding(model, rule)
    assert finding.verdict == "FAIL"
    assert finding.severity == "required"
    assert finding.evidence_level in {"derived", "calculated", "manufacturer_rated"}
    assert finding.affected
    assert text in finding.message


def test_valid_db40_has_complete_drawer_rules_without_door_checks_or_overclaim():
    report = validate_model(_model())
    rules = {finding.rule for finding in report.findings}

    assert DRAWER_RULES <= rules
    assert all(report.by_rule(rule).verdict == "PASS" for rule in DRAWER_RULES)
    assert not {"cabinetry.hardware.hinge_fit", "cabinetry.shelf.deflection"} & rules
    capacity = report.by_rule("cabinetry.performance.whole_cabinet_capacity")
    assert capacity.verdict == "UNKNOWN"
    assert capacity.severity == "advisory"
    assert capacity.evidence_level == "unknown"
    assert report.release_ready


def test_front_height_mutation_breaks_exact_reveal_equation():
    model = _model()
    front = model.part("drawer_front_top")
    model = _replace_part(model, front.role, width_mm=front.width_mm + 1)
    _assert_required_fail(
        model, "cabinetry.drawer.front_allocation", "768.70 mm"
    )


def test_box_width_mutation_breaks_runner_formula():
    model = _model()
    model = replace(model, drawer_bank=replace(
        model.drawer_bank, inside_box_width_mm=936.9
    ))
    _assert_required_fail(
        model, "cabinetry.drawer.width_formula", "935.90 mm"
    )


def test_side_thickness_over_product_maximum_fails():
    model = _replace_part(_model(), "drawer_top_side_left", thickness_mm=17.0)
    _assert_required_fail(
        model, "cabinetry.drawer.side_thickness", "17.00 mm"
    )


def test_usable_depth_below_selected_runner_minimum_fails():
    model = _model()
    model = replace(model, drawer_bank=replace(model.drawer_bank, inside_depth_mm=552.0))
    _assert_required_fail(
        model, "cabinetry.drawer.inside_depth", "552.00 mm"
    )


def test_box_height_over_allocated_opening_limit_fails():
    model = _replace_part(_model(), "drawer_top_side_left", width_mm=136.0)
    _assert_required_fail(
        model, "cabinetry.drawer.box_height", "136.00 mm"
    )


def test_bottom_recess_or_clearance_mutation_fails():
    model = _model()
    bottom = model.part("drawer_top_bottom")
    model = _replace_part(
        model, bottom.role,
        at_mm=(bottom.at_mm[0], bottom.at_mm[1], bottom.at_mm[2] + 1),
    )
    _assert_required_fail(
        model, "cabinetry.drawer.bottom_geometry", "14.00 mm"
    )


@pytest.mark.parametrize("kind", ["runner_rear_notch", "runner_hook_bore"])
def test_missing_rear_notch_or_hook_bore_fails(kind):
    model = _model()
    removed = next(item for item in model.machining if item.kind == kind)
    model = _replace_machining(
        model, tuple(item for item in model.machining if item != removed)
    )
    _assert_required_fail(
        model, "cabinetry.drawer.rear_preparation", kind
    )


def test_missing_required_runner_fixing_station_fails():
    model = _model()
    removed = next(item for item in model.machining
                   if item.kind == "runner_fixing_station")
    model = _replace_machining(
        model, tuple(item for item in model.machining if item != removed)
    )
    _assert_required_fail(
        model, "cabinetry.drawer.runner_fixing", "11 of 12"
    )


def test_missing_handed_locking_device_pair_fails():
    model = _model()
    hardware = tuple(system for system in model.hardware
                     if not (system.kind == "drawer_locking_device_pair"
                             and ".top." in system.system_id))
    model = replace(model, hardware=hardware)
    _assert_required_fail(
        model, "cabinetry.drawer.locking_devices", "top"
    )


def test_missing_wide_drawer_stabilizer_fails():
    model = _model()
    hardware = tuple(system for system in model.hardware
                     if not (system.kind == "drawer_lateral_stabilizer"
                             and ".middle." in system.system_id))
    model = replace(model, hardware=hardware)
    _assert_required_fail(
        model, "cabinetry.drawer.lateral_stabilizer", "middle"
    )


def test_stabilizer_can_never_credit_runner_capacity():
    model = _model()
    stabilizer = replace(model.drawer_bank.stabilizer, capacity_increase_lb=25.0)
    model = replace(model, drawer_bank=replace(
        model.drawer_bank, stabilizer=stabilizer
    ))
    _assert_required_fail(
        model, "cabinetry.drawer.stabilizer_capacity_credit", "25.00 lb"
    )


def test_moving_assembly_plus_contents_over_dynamic_rating_fails():
    model = _model()
    cells = tuple(
        replace(cell, moving_mass_kg=40.0, rated_moving_load_lb=128.18)
        if cell.cell_id == "bottom" else cell
        for cell in model.drawer_bank.cells
    )
    model = replace(model, drawer_bank=replace(model.drawer_bank, cells=cells))
    _assert_required_fail(
        model, "cabinetry.drawer.moving_load", "128.18 lb"
    )


def test_front_fastener_longer_than_material_stack_fails():
    model = _model()
    model = replace(model, front_fastener=replace(
        model.front_fastener, length_mm=40.0
    ))
    _assert_required_fail(
        model, "cabinetry.drawer.front_fastener_stack", "40.00 mm"
    )


def test_closed_front_gap_outside_target_fails():
    model = _model()
    front = model.part("drawer_front_middle")
    model = _replace_part(
        model, front.role,
        at_mm=(front.at_mm[0], front.at_mm[1], front.at_mm[2] + 1),
    )
    _assert_required_fail(
        model, "cabinetry.drawer.closed_reveals", "3.00 mm"
    )


def test_extended_drawer_envelope_collision_with_declared_obstruction_fails():
    from detailgen.packs.cabinetry.drawer_base import ObstructionEnvelope

    model = _model()
    front = model.part("drawer_front_bottom")
    obstruction = ObstructionEnvelope(
        obstruction_id="room.bed",
        bounds_mm=(front.at_mm[0], front.at_mm[1] - 400.0, front.at_mm[2],
                   front.at_mm[0] + front.length_mm,
                   front.at_mm[1] - 300.0,
                   front.at_mm[2] + front.width_mm),
    )
    model = replace(model, declared_obstructions=(obstruction,))
    _assert_required_fail(
        model, "cabinetry.drawer.extended_clearance", "room.bed"
    )


def test_removal_before_adjustment_identity_is_recorded_fails_sequence():
    model = _model()
    sequence = tuple(
        "ship.remove_drawers" if item == "ship.record_adjustment_identity"
        else "ship.record_adjustment_identity" if item == "ship.remove_drawers"
        else item
        for item in model.drawer_process_sequence
    )
    model = replace(model, drawer_process_sequence=sequence)
    _assert_required_fail(
        model, "cabinetry.drawer.ship_install_sequence", "record adjustment identity"
    )
