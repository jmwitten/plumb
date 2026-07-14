"""Wall-hung vanity contract, geometry, evidence, and installation output."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.packs import (
    ProjectReleaseError,
    ProjectSchemaError,
    compile_project_file,
    load_project_text,
)
from detailgen.packs.cabinetry import FramelessVanityPack

FIXTURE = (
    Path(__file__).parent / "fixtures" / "cabinetry"
    / "floating_vanity.project.yaml"
)


def _raw() -> dict:
    return yaml.safe_load(FIXTURE.read_text())


def _compile(raw: dict, tmp_path):
    path = tmp_path / "vanity.project.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return compile_project_file(path)


def _parse(raw: dict):
    return FramelessVanityPack().parse(
        load_project_text(yaml.safe_dump(raw, sort_keys=False))
    )


def test_registry_exposes_opt_in_vanity_pack():
    from detailgen.packs.registry import default_pack_registry

    assert "vanity.frameless@1" in default_pack_registry().available()


def test_vanity_schema_resolves_wall_backing_keepout_and_mount_evidence():
    section = _parse(_raw())

    assert section.vanity.vanity_id == "V36"
    assert section.vanity.bottom_elevation_mm == pytest.approx(10 * 25.4)
    assert section.plumbing.width_mm == pytest.approx(12 * 25.4)
    assert section.mounting.backing.nominal == "2x8"
    assert section.mounting.engineering.status == "required"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw["vanity"]["cabinet"].update(type="floor_supported"),
         "requires.*floating"),
        (lambda raw: raw["vanity"]["cabinet"]["front"].update(doors=3),
         "exactly two"),
        (lambda raw: raw["vanity"]["mounting"]["backing"].update(
            type="drywall_anchor"), "blocking_2x8"),
        (lambda raw: raw["vanity"]["mounting"]["fastener"].update(
            product="generic lag"), "known wall anchors"),
        (lambda raw: raw["vanity"]["mounting"]["engineering"].update(
            status="assumed"), "engineering.status"),
    ],
)
def test_vanity_schema_rejects_unsupported_or_ambiguous_authoring(
    mutation, message
):
    raw = _raw()
    mutation(raw)

    with pytest.raises(ProjectSchemaError, match=message):
        _parse(raw)


def test_plumbing_keepout_must_stay_inside_vanity_span():
    raw = _raw()
    raw["vanity"]["plumbing"]["keepout"]["width"] = 30

    with pytest.raises(ProjectSchemaError, match="plumbing keepout.*width"):
        _parse(raw)


def test_model_contains_wall_hung_load_path_and_no_floor_base(tmp_path):
    project = _compile(_raw(), tmp_path)
    roles = {part.role for part in project.model.parts}

    assert {
        "left_end", "right_end", "bottom", "front_stretcher",
        "rear_mounting_rail", "lower_back_left", "lower_back_right",
        "door_left", "door_right",
    } <= roles
    assert not {"toe_front", "toe_rear", "toe_left", "toe_right"} & roles
    assert {"wall_anchor_stud_32", "wall_anchor_stud_48"} <= roles
    assert any(role.startswith("backing_") for role in roles)
    assert project.lowered_doc.type == "vanity_frameless_floating"


def test_lowering_connects_anchors_through_rail_to_existing_structure(tmp_path):
    project = _compile(_raw(), tmp_path)
    overlaps = {
        (item.a, item.b) for item in project.lowered_doc.validation.expected_overlaps
    }

    for stud_id in ("stud_32", "stud_48"):
        screw = f"vanity.V36.wall_anchor_{stud_id}"
        assert (screw, "vanity.V36.rear_mounting_rail") in overlaps
        assert (screw, f"site.north_wall.{stud_id}") in overlaps
    assert [
        stage.name for stage in project.lowered_doc.sequence.stages
    ] == ["assemble_wall_hung_case", "anchor_case_to_wall"]


def test_backing_is_a_real_anchor_target_not_dead_context_geometry(tmp_path):
    project = _compile(_raw(), tmp_path)
    overlaps = {
        (item.a, item.b) for item in project.lowered_doc.validation.expected_overlaps
    }
    backing_ids = {
        part.part_id for part in project.model.parts
        if part.role.startswith("backing_")
    }
    anchor_ids = {
        part.part_id for part in project.model.parts
        if part.role.startswith("wall_anchor_")
    }

    assert backing_ids
    assert any(
        anchor in anchor_ids and target in backing_ids
        for anchor, target in overlaps
    )


def test_unreviewed_custom_mount_is_required_unknown_and_blocks_release(tmp_path):
    project = _compile(_raw(), tmp_path)
    finding = project.report.by_rule("vanity.mount.engineering")

    assert finding.verdict == "UNKNOWN"
    assert finding.severity == "required"
    with pytest.raises(ProjectReleaseError, match="mount.engineering"):
        project.require_release()


def test_verified_referenced_mount_review_can_cross_pack_and_base_gates(tmp_path):
    raw = _raw()
    raw["vanity"]["mode"] = "release"
    raw["vanity"]["mounting"]["engineering"] = {
        "status": "verified",
        "reference": "illustrative signed project-specific review S-001",
    }

    project = _compile(raw, tmp_path)
    project.require_release()

    assert project.release_ready
    assert project.base_report.ok
    coverage = {
        row["family"]: row["verdict"]
        for row in project.manifest()["base_coverage"]
    }
    assert coverage["Load-path representation"] == "PASS"
    assert coverage["Structural capacity"] == "UNKNOWN — NOT ANALYZED"
    assert project.report.by_rule(
        "vanity.mount.load_path_representation"
    ).verdict == "PASS"
    assert "certified" not in project.manifest_json().lower()


def test_external_review_cannot_repair_a_missing_modeled_load_path(tmp_path):
    from dataclasses import replace

    from detailgen.packs.cabinetry.vanity import validate_vanity_model

    raw = _raw()
    raw["vanity"]["mounting"]["engineering"] = {
        "status": "verified",
        "reference": "illustrative signed project-specific review S-001",
    }
    project = _compile(raw, tmp_path)
    broken = replace(project.model, anchor_targets=())

    report = validate_vanity_model(broken)

    assert report.by_rule("vanity.mount.engineering").verdict == "PASS"
    assert report.by_rule(
        "vanity.mount.load_path_representation"
    ).verdict == "FAIL"

    bad_target = replace(
        project.model.anchor_targets[0],
        target_part_id="site.north_wall.nonexistent_backing",
    )
    broken_target = replace(
        project.model,
        anchor_targets=(bad_target,),
    )
    assert validate_vanity_model(broken_target).by_rule(
        "vanity.mount.load_path_representation"
    ).verdict == "FAIL"


def test_backing_and_stud_survey_are_required_release_evidence(tmp_path):
    raw = _raw()
    raw["vanity"]["mounting"]["backing"]["verified"] = False
    raw["site"]["wall"]["studs"][1]["verified"] = False
    project = _compile(raw, tmp_path)

    assert project.report.by_rule("vanity.mount.backing").verdict == "UNKNOWN"
    assert project.report.by_rule("vanity.mount.targets").verdict == "UNKNOWN"


def test_anchor_inside_plumbing_keepout_fails(tmp_path):
    raw = _raw()
    raw["vanity"]["plumbing"]["keepout"].update({
        "from_cabinet_left": 6,
        "width": 20,
        "bottom_elevation": 24,
        "height": 8,
    })
    project = _compile(raw, tmp_path)

    finding = project.report.by_rule("vanity.plumbing.anchor_clearance")
    assert finding.verdict == "FAIL"
    assert "stud_32" in finding.message or "stud_48" in finding.message


def test_installation_artifact_covers_support_anchors_and_plumbing(tmp_path):
    project = _compile(_raw(), tmp_path)
    by_id = {step.step_id: step for step in project.artifacts.installation_steps}

    assert {
        "install.release_gate", "install.verify_backing_and_services",
        "install.temporary_support", "install.set_and_align",
        "install.structural_anchors", "install.inspect_load_path",
        "install.top_sink_and_plumbing", "install.leak_test",
        "install.commission",
    } <= by_id.keys()
    assert "two installers" in by_id["install.temporary_support"].instruction
    assert "each end" in by_id["install.structural_anchors"].instruction
    assert "remove" in by_id["install.inspect_load_path"].instruction
    assert "local" in by_id["install.top_sink_and_plumbing"].instruction


def test_all_vanity_artifact_steps_use_the_closed_evidence_vocabulary(tmp_path):
    from detailgen.packs.cabinetry.evidence import EVIDENCE_LEVELS

    project = _compile(_raw(), tmp_path)
    steps = (
        project.artifacts.fabrication_steps
        + project.artifacts.assembly_steps
        + project.artifacts.installation_steps
    )

    assert {step.evidence for step in steps} <= EVIDENCE_LEVELS
    assert {
        item.evidence for item in project.artifacts.hardware_schedule
    } <= EVIDENCE_LEVELS
    assert "certified" not in {
        step.evidence for step in steps
    }
    assert all(item.quantity_unit and item.procurement_note
               for item in project.artifacts.hardware_schedule)
    anchors = next(item for item in project.artifacts.hardware_schedule
                   if item.kind == "wall_hung_structural_anchor_system")
    assert anchors.quantity_unit == "screw"
    assert anchors.procurement_note == f"{anchors.quantity} individual screws"


def test_vanity_manifest_is_deterministic_and_names_pack(tmp_path):
    first = _compile(_raw(), tmp_path)
    second = _compile(_raw(), tmp_path)

    assert first.manifest_json() == second.manifest_json()
    assert first.manifest()["packs"] == {"vanity.frameless": "1.1.0"}
    assert first.artifacts.schema == "detailgen/vanity-artifacts/v2"
