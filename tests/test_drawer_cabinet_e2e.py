"""Real DB40 project, release gates, manifest protocol, and determinism."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from detailgen.core.registry import components, materials
from detailgen.packs import (
    ProjectReleaseError,
    compile_project,
    compile_project_file,
)


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"
EXAMPLE = ROOT / "details/frameless_three_drawer_40.project.yaml"


def test_real_db40_passes_fabrication_gate_but_holds_installation_and_use():
    project = compile_project_file(FIXTURE)
    assert project.report.fabrication_ready
    assert not project.report.installation_use_ready
    assert not project.report.release_ready
    assert not project.release_ready
    assert not project.artifacts.release_ready
    assert project.manifest()["release_contract"] == "split"
    assert project.manifest()["release_scope"] == "none"
    assert project.manifest()["artifacts"]["release_contract"] == "split"
    assert project.manifest()["artifacts"]["release_scope"] == "none"

    assembly = project.build()
    base_report = project.validate()

    assert base_report.ok, "\n".join(str(item) for item in base_report.blocking)
    assert project.fabrication_ready
    assert not project.release_ready
    assert project.artifacts.fabrication_ready
    assert not project.artifacts.installation_use_ready
    assert not project.artifacts.release_ready
    assert len(assembly.parts) == len(project.model.parts)
    assert project.require_fabrication_release() is project
    with pytest.raises(ProjectReleaseError, match="installation/use release blocked"):
        project.require_release()


def test_installation_policy_rejects_unknown_blocker_rule_references():
    project = compile_project_file(FIXTURE)
    bad_policy = replace(
        project.report.installation_use_policy,
        blocking_rules=("cabinetry.performance.typo",),
    )
    with pytest.raises(ValueError, match="unknown blocking rules"):
        replace(project.report, installation_use_policy=bad_policy)


def test_failed_base_validation_keeps_nested_and_top_level_scope_at_none(
    monkeypatch,
):
    from detailgen.validation.checks import Finding

    project = compile_project_file(FIXTURE)
    failed = project.detail.validate()
    failed.add(Finding(
        check="interference",
        subject="DB40",
        passed=False,
        detail="test-only base failure",
    ))
    monkeypatch.setattr(project.detail, "validate", lambda: failed)
    project.validate()

    payload = project.manifest()
    assert not project.fabrication_ready
    assert payload["release_scope"] == "none"
    assert payload["artifacts"]["release_scope"] == "none"


def test_manifest_uses_model_catalog_protocol_and_records_policy():
    project = compile_project_file(FIXTURE)
    project.require_fabrication_release()
    payload = project.manifest()

    assert payload["catalogs"] == {
        "front_fastener": "grk_low_profile_cabinet_8x1_1_4_114069@2026.1",
        "drawer_box_joinery_fastener": (
            "hafele_confirmat_7x50_264_42_190@2026.1"
        ),
        "lateral_stabilizer": "blum_zs7m686mu@2026.1",
        "locking_device": "blum_t51_7601_pair@2026.1",
        "locking_device_screw": "blum_606n_no6x5_8@2026.1",
        "pull": "hafele_vogue_155_01_613@2026.1",
        "pull_mounting_screw": (
            "hafele_handle_screw_m4x26_022_35_261@2026.1"
        ),
        "runner": "blum_movento_763_5330s@2026.1",
        "runner_installation_screw": "blum_606n_no6x5_8@2026.1",
        "wall_anchor": "grk_low_profile_cabinet_8x3_1_8@2026.1",
    }
    assert payload["catalog_sources"] == {
        "drawer_box_joinery_fastener": (
            project.model.drawer_bank.joinery_fastener.source_url
        ),
        "front_fastener": project.model.front_fastener.source_url,
        "lateral_stabilizer": project.model.drawer_bank.stabilizer.source_url,
        "locking_device": project.model.drawer_bank.locking_device.source_url,
        "locking_device_screw": project.model.drawer_bank.locking_device.source_url,
        "pull": project.model.drawer_bank.pull_product.source_url,
        "pull_mounting_screw": (
            project.model.drawer_bank.pull_product.mounting_screw_source_url
        ),
        "runner": project.model.drawer_bank.runner.source_url,
        "runner_installation_screw": project.model.drawer_bank.runner.source_url,
        "wall_anchor": project.model.wall_anchor.source_url,
    }
    assert payload["archetypes"] == ["drawer_base_three@1"]
    assert payload["sizing_policies"] == ["progressive_clothing_3@1"]
    assert payload["derived_facts"]["drawer_cells"]["top"]["moving_hardware_mass_kg"] > 0
    assert "cabinetry.DB40.top.runner_installation_screws" in payload["source_map"]
    assert payload["source_map"]["cabinetry.DB40.top.runner_installation_screws"]["source_url"]
    assert payload["release_ready"] is False
    assert payload["fabrication_ready"] is True
    assert payload["installation_use_ready"] is False
    assert payload["release_contract"] == "split"
    assert payload["release_scope"] == "fabrication_only"
    assert payload["artifacts"]["release_contract"] == "split"
    assert payload["artifacts"]["release_scope"] == "fabrication_only"
    assert payload["physical_tests"] == "not_performed"
    assert "certified" not in project.manifest_json().lower()
    assert json.loads(project.manifest_json()) == payload


def test_three_drawers_are_physical_boxes_not_front_only():
    project = compile_project_file(FIXTURE)
    assembly = project.build()
    names = {part.name for part in assembly.parts}

    for cell in ("top", "middle", "bottom"):
        assert {
            f"DB40 drawer {cell} side left",
            f"DB40 drawer {cell} side right",
            f"DB40 drawer {cell} front",
            f"DB40 drawer {cell} back",
            f"DB40 drawer {cell} bottom",
            f"DB40 drawer front {cell}",
        } <= names


def test_expanded_replay_and_checked_in_example_are_deterministic():
    assert EXAMPLE.read_text() == FIXTURE.read_text()
    compact = compile_project_file(FIXTURE)
    replay = compile_project(compact.expanded_project_doc)

    assert replay.model == compact.model
    assert replay.lowered_doc == compact.lowered_doc
    assert replay.manifest_json() == compact.manifest_json()
    assert compile_project_file(EXAMPLE).manifest_json() == compact.manifest_json()


def test_db40_compile_does_not_mutate_global_registries():
    before_components = tuple(components.names())
    before_materials = tuple(materials.names())

    compile_project_file(FIXTURE).build()

    assert tuple(components.names()) == before_components
    assert tuple(materials.names()) == before_materials


def test_manifest_is_deterministic_across_fresh_processes():
    code = (
        "from detailgen.packs import compile_project_file; "
        f"print(compile_project_file({str(FIXTURE)!r}).manifest_json())"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / ".shim")
    outputs = [
        subprocess.check_output(
            [sys.executable, "-c", code], cwd=ROOT, env=env, text=True
        ).strip()
        for _ in range(2)
    ]

    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["project"] == "DB40 three-drawer clothing cabinet"
