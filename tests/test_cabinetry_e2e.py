"""Real packed-project compile through the existing DetailSpec/CadQuery path."""

from __future__ import annotations

import json
from pathlib import Path

from detailgen.core.registry import components, materials
from detailgen.packs import compile_project_file

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/cabinetry/frameless_base_cabinet.project.yaml"
EXAMPLE = ROOT / "details/frameless_base_cabinet.project.yaml"


def test_real_project_compiles_builds_and_passes_both_release_gates():
    project = compile_project_file(FIXTURE)
    assert not project.release_ready  # base geometry has not run yet
    assembly = project.build()
    base_report = project.validate()

    assert project.report.release_ready
    assert base_report.ok, "\n".join(str(finding) for finding in base_report.blocking)
    assert project.release_ready
    assert len(assembly.parts) == len(project.lowered_doc.components)
    assert len(assembly.parts) == len(project.model.parts)
    assert project.require_release() is project


def test_packed_project_exposes_existing_detail_behavior_and_pack_artifacts():
    project = compile_project_file(FIXTURE)

    assert project.detail.name == "B30 frameless base cabinet"
    assert project.bom_table() == project.detail.bom_table()
    assert not project.artifacts.release_ready
    project.require_release()
    assert project.artifacts.release_ready
    assert len(project.artifacts.cut_list) == 14
    assert len(project.artifacts.installation_steps) == 10


def test_manifest_records_versions_evidence_and_no_conformity_claim():
    project = compile_project_file(FIXTURE)
    project.require_release()
    payload = project.manifest()

    assert payload["schema"] == "detailgen/packed-project/v1"
    assert payload["packs"] == {"cabinetry.frameless": "1.1.0"}
    assert payload["profile"] == "frameless_plywood_shop_v1@1.0.0"
    assert payload["catalogs"] == {
        "hinge": "blum_clip_top_blumotion_110_h002@2025.1",
        "wall_anchor": "grk_low_profile_cabinet_8x3_1_8@2026.1",
    }
    assert payload["release_ready"] is True
    assert payload["physical_tests"] == "not_performed"
    assert "certified" not in project.manifest_json().lower()
    assert json.loads(project.manifest_json()) == payload


def test_pack_compile_does_not_mutate_base_registries_or_base_compile():
    from detailgen.spec import compile_spec, load_spec_text

    base_spec = """
name: compatibility panel
units: in
components:
  - id: panel
    type: plywood_panel
    params: {length: 12 in, width: 8 in, thickness: 0.75 in}
"""
    before_components = tuple(components.names())
    before_materials = tuple(materials.names())
    before = compile_spec(load_spec_text(base_spec))
    before_transform = before.build().parts[0].world_frame

    compile_project_file(FIXTURE)

    after = compile_spec(load_spec_text(base_spec))
    assert tuple(components.names()) == before_components
    assert tuple(materials.names()) == before_materials
    assert after.doc == before.doc
    after_transform = after.build().parts[0].world_frame
    assert (
        after_transform.origin,
        after_transform.x_axis,
        after_transform.y_axis,
        after_transform.z_axis,
    ) == (
        before_transform.origin,
        before_transform.x_axis,
        before_transform.y_axis,
        before_transform.z_axis,
    )


def test_checked_in_example_is_the_verified_vertical_slice():
    assert EXAMPLE.exists()
    assert EXAMPLE.read_text() == FIXTURE.read_text()
    project = compile_project_file(EXAMPLE)
    assert project.manifest_json() == compile_project_file(FIXTURE).manifest_json()


def test_manifest_and_stable_source_map_are_deterministic():
    a = compile_project_file(FIXTURE)
    b = compile_project_file(FIXTURE)

    assert a.manifest_json() == b.manifest_json()
    assert a.model.source_map == b.model.source_map
    assert a.lowered_doc == b.lowered_doc
