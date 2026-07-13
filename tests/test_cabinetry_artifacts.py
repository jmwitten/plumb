"""Derived shop, assembly, and field-installation deliverables."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from detailgen.packs import load_project_file
from detailgen.packs.cabinetry import FramelessCabinetryPack

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "cabinetry"
    / "frameless_base_cabinet.project.yaml"
)


def test_cabinet_artifact_records_reject_unknown_evidence_levels():
    from detailgen.packs.cabinetry.artifacts import WorkStep
    from detailgen.packs.cabinetry.model import HardwareSystem

    with pytest.raises(ValueError, match="unknown evidence level"):
        WorkStep(10, "bad", "bad", evidence="specified")
    with pytest.raises(ValueError, match="unknown evidence level"):
        HardwareSystem("bad", "bad", "bad", 1, (), "specified")


def _built():
    from detailgen.packs.cabinetry.artifacts import build_artifacts
    from detailgen.packs.cabinetry.model import build_model
    from detailgen.packs.cabinetry.validation import validate_model

    doc = load_project_file(FIXTURE)
    model = build_model(FramelessCabinetryPack().parse(doc), project_name=doc.name)
    report = validate_model(model)
    return model, report, build_artifacts(model, report)


def test_cut_list_contains_every_fabricated_panel_with_provenance():
    model, _, artifacts = _built()
    expected = {
        part.part_id for part in model.parts
        if part.component_type == "plywood_panel"
        and not part.role.startswith("wall_stud_")
    }

    assert {item.part_id for item in artifacts.cut_list} == expected
    assert all(item.quantity == 1 for item in artifacts.cut_list)
    assert all(item.source_rule for item in artifacts.cut_list)
    assert any(item.part_id.endswith("left_end") for item in artifacts.cut_list)
    assert any(item.thickness_mm == 6.35 for item in artifacts.cut_list)


def test_edge_band_map_is_derived_from_surface_policy_not_reauthored():
    _, _, artifacts = _built()

    assert len(artifacts.edge_banding) == 13
    assert all(item.operation == "band" for item in artifacts.edge_banding)
    assert {
        item.edge for item in artifacts.edge_banding
        if item.part_id.endswith("door_left")
    } == {"left", "right", "top", "bottom"}
    assert [item.edge for item in artifacts.edge_banding
            if item.part_id.endswith("adjustable_shelf")] == ["front"]


def test_hardware_schedule_uses_pinned_blum_and_grk_products():
    _, _, artifacts = _built()
    by_kind = {item.kind: item for item in artifacts.hardware_schedule}

    assert by_kind["concealed_hinge_system"].quantity == 4
    assert by_kind["concealed_hinge_system"].product_id == (
        "blum_clip_top_blumotion_110_h002@2025.1"
    )
    assert by_kind["wall_anchor_system"].quantity == 2
    assert by_kind["wall_anchor_system"].product_id == (
        "grk_low_profile_cabinet_8x3_1_8@2026.1"
    )
    assert by_kind["adjustable_shelf_support_system"].quantity == 4
    assert by_kind["carcass_confirmat_system"].quantity == 26
    assert by_kind["toe_base_attachment_system"].quantity == 6
    assert by_kind["wood_adhesive"].product_id == "titebond_original_5064@2026.1"


def test_joinery_instructions_pin_count_spacing_pilot_and_countersink():
    _, _, artifacts = _built()
    text = " ".join(
        step.instruction.lower() for step in artifacts.fabrication_steps
        + artifacts.assembly_steps
    )

    for phrase in (
        "26",
        "7 x 50 mm confirmat",
        "5 mm blind pilot",
        "7 mm through-shank",
        "10 mm countersink",
        "6 grk #8 x 1-1/4",
        "titebond original",
        "6 mil",
    ):
        assert phrase in text


def test_canonical_machining_schedule_contains_every_model_feature():
    model, _, artifacts = _built()

    assert len(artifacts.machining_schedule) == len(model.machining)
    assert {item.feature_id for item in artifacts.machining_schedule} == {
        feature.feature_id for feature in model.machining
    }
    grooves = [item for item in artifacts.machining_schedule
               if item.kind == "captured_back_groove"]
    assert len(grooves) == 4
    assert all(item.coordinate_system == "part_local_xy_from_cut_list_origin"
               for item in grooves)


def test_shop_steps_cover_breakdown_machining_banding_and_dry_fit():
    _, _, artifacts = _built()
    text = " ".join(step.instruction.lower() for step in artifacts.fabrication_steps)

    for phrase in (
        "break down",
        "captured-back grooves",
        "edge band",
        "35 mm hinge cups",
        "system-32",
        "dry-fit",
    ):
        assert phrase in text
    assert [step.phase for step in artifacts.fabrication_steps] == sorted(
        step.phase for step in artifacts.fabrication_steps
    )


def test_assembly_steps_follow_conventional_shop_delivery_state():
    model, _, artifacts = _built()
    text = " ".join(step.instruction.lower() for step in artifacts.assembly_steps)

    assert model.profile.delivery_state == "carcass_assembled_doors_detached"
    assert "independent toe-kick" in text
    assert "square" in text
    assert "captured back" in text
    assert "ship the doors detached" in text


def test_installation_steps_cover_survey_level_anchor_countertop_and_commissioning():
    _, report, artifacts = _built()
    text = " ".join(step.instruction.lower() for step in artifacts.installation_steps)

    assert report.release_ready
    for phrase in (
        "field-verify stud",
        "highest floor point",
        "level and plumb",
        "shim",
        "anchor strip",
        "countertop",
        "adjust the blum hinges",
        "commission",
    ):
        assert phrase in text
    assert "drywall anchor" in text
    assert [step.phase for step in artifacts.installation_steps] == sorted(
        step.phase for step in artifacts.installation_steps
    )


def test_artifact_manifest_is_canonical_and_json_serializable():
    from detailgen.packs.cabinetry.artifacts import artifact_json

    _, _, a = _built()
    _, _, b = _built()
    encoded_a = artifact_json(a)
    encoded_b = artifact_json(b)

    assert encoded_a == encoded_b
    payload = json.loads(encoded_a)
    assert payload["schema"] == "detailgen/cabinetry-artifacts/v1"
    # Artifacts built from pack rules alone cannot claim release until the
    # ordinary base-geometry sweep also runs through PackedProject.
    assert payload["release_ready"] is False
    assert payload["profile"] == "frameless_plywood_shop_v1@1.0.0"
