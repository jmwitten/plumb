"""Self-contained cabinetry build-document rendering from PackedProject data."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

from detailgen.packs import compile_project_file
from detailgen.packs.cabinetry.validation import validate_model
from detailgen.rendering.web_viewer import build_viewer_payload


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cabinetry_project_report as CPR  # noqa: E402


DB40 = ROOT / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"
B30 = ROOT / "tests/fixtures/cabinetry/frameless_base_cabinet.project.yaml"
PIXEL = "data:image/png;base64,iVBORw0KGgo="


def _html(project):
    project.require_release()
    images = {view: PIXEL for view in CPR.REQUIRED_VIEWS}
    return CPR.build_cabinetry_html(
        project,
        images=images,
        viewer_payload=build_viewer_payload(project.detail),
        glb_b64="H4sIAAAAAAACAwMAAAAAAAAAAAA=",
    )


def test_db40_report_contains_release_boundary_views_and_exact_dimensions():
    project = compile_project_file(DB40)
    html = _html(project)

    assert "Pack release: PASS" in html
    assert "Whole-cabinet structural capacity" in html
    assert "UNKNOWN — not qualified" in html
    for view in CPR.REQUIRED_VIEWS:
        assert f'data-view="{view}"' in html
    for value in (
        "1016.00 mm", "876.30 mm", "590.55 mm", "977.90 mm",
        "1013.00 mm", "158.75 mm", "254.00 mm", "354.95 mm",
        "967.90 mm", "935.90 mm", "533.00 mm", "1.50 mm", "2.00 mm",
    ):
        assert value in html
    assert "cabinetry.DB40.drawer_top_side_left" in html
    assert "cabinetry.DB40.drawer_middle_side_left" in html
    assert "cabinetry.DB40.drawer_bottom_side_left" in html


def test_report_projects_shop_evidence_sources_and_all_process_phases():
    project = compile_project_file(DB40)
    html = _html(project)

    for heading in (
        "Cut list", "Edge banding", "Hardware schedule", "Machining schedule",
        "Validation findings", "Evidence register", "Source map",
        "Fabrication", "Assembly & shipping", "Installation & commissioning",
    ):
        assert heading in html
    for product in (
        "blum_movento_763_5330s@2026.1",
        "blum_t51_7601_pair@2026.1",
        "blum_zs7m686mu@2026.1",
        "hafele_vogue_155_01_613@2026.1",
    ):
        assert product in html
    for source in project.model.catalog_source_manifest().values():
        assert f'href="{source}"' in html
    for step_id in (
        "fab.stabilizer_preparation", "shop.adjust_drawers",
        "ship.remove_drawers", "ship.empty_carcass",
        "install.reinstall_by_identity", "install.commission_drawers",
    ):
        assert step_id in html


def test_report_reuses_interactive_viewer_payload_and_is_self_contained():
    project = compile_project_file(DB40)
    html = _html(project)
    slug = build_viewer_payload(project.detail)["slug"]

    assert f'data-detail="{slug}"' in html
    assert f'id="detail-data-{slug}"' in html
    assert f'id="detail-glb-{slug}"' in html
    assert "Explore in 3D" in html
    assert "THREE.GLTFLoader" in html
    assert "https://cdn" not in html
    assert 'src="http' not in html


def test_report_scene_excludes_full_height_site_context_but_keeps_install_anchors():
    project = compile_project_file(DB40)

    assembly = CPR.product_view_assembly(project)
    payload = CPR.product_viewer_payload(project, assembly)
    names = {part.name for part in assembly.parts}

    assert "north_wall stud_32" not in names
    assert "north_wall stud_48" not in names
    assert "DB40 wall anchor at stud_32" in names
    assert "DB40 wall anchor at stud_48" in names
    assert set(payload["parts"]) == names


def test_dimension_projection_and_validation_share_the_mutated_model():
    project = compile_project_file(DB40)
    front = project.model.part("drawer_front_top")
    changed = replace(front, width_mm=front.width_mm + 1)
    parts = tuple(changed if part.part_id == front.part_id else part
                  for part in project.model.parts)
    bank_parts = tuple(changed if part.part_id == front.part_id else part
                       for part in project.model.drawer_bank.parts)
    model = replace(
        project.model,
        parts=parts,
        drawer_bank=replace(project.model.drawer_bank, parts=bank_parts),
    )

    table = CPR.render_dimension_tables(model)
    finding = validate_model(model).by_rule("cabinetry.drawer.front_allocation")

    assert "159.75 mm" in table
    assert finding.verdict == "FAIL"
    assert "768.70 mm" in finding.message


def test_same_report_surface_accepts_existing_door_base_project():
    project = compile_project_file(B30)
    html = _html(project)

    assert "B30 frameless base cabinet" in html
    assert "door_left" in html
    assert "Cut list" in html
    assert "Explore in 3D" in html
