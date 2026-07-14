"""Self-contained cabinetry build-document rendering from PackedProject data."""

from __future__ import annotations

from dataclasses import replace
from html import unescape
from pathlib import Path
import re
import sys

import pytest

from detailgen.packs import compile_project_file
from detailgen.packs.cabinetry.validation import validate_model
from detailgen.rendering.web_viewer import build_viewer_payload


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cabinetry_project_report as CPR  # noqa: E402


DB40 = ROOT / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"
B30 = ROOT / "tests/fixtures/cabinetry/frameless_base_cabinet.project.yaml"
PIXEL = "data:image/png;base64,iVBORw0KGgo="
DB40_UNKNOWN_VERDICTS = (
    ("cabinetry.performance.anchor_capacity", "UNKNOWN"),
    ("cabinetry.performance.physical_tests", "UNKNOWN"),
    ("cabinetry.performance.whole_cabinet_capacity", "UNKNOWN"),
)
DB40_STATUS_MATRIX = (
    ("Model/shop-data gate", "PASS"),
    ("Purchasing/cutting preflight", "OPEN"),
    ("Whole-cabinet structural capacity", "UNKNOWN"),
    ("Installation/use release", "HOLD"),
)
REVIEW_VIEWS = ("front", "installation-plan", "anchor-section")
SHOP_VIEWS = ("front", "exploded", "drawer-detail")
VIEWER_MARKERS = ('id="detail-data-', 'id="detail-glb-', "THREE.GLTFLoader")


def _visible_text(document: str) -> str:
    without_embedded_data = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1\s*>",
        " ",
        document,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_embedded_data)
    return " ".join(unescape(without_tags).split())


def _headings(document: str) -> tuple[str, ...]:
    return tuple(
        _visible_text(body)
        for body in re.findall(
            r"<h[1-6]\b[^>]*>(.*?)</h[1-6]\s*>",
            document,
            flags=re.IGNORECASE | re.DOTALL,
        )
    )


def _images() -> dict[str, str]:
    return {view: PIXEL for view in CPR.REQUIRED_VIEWS}


def _review_html(project):
    project.require_fabrication_release()
    return CPR.build_cabinetry_review_html(
        project,
        images=_images(),
        viewer_payload=build_viewer_payload(project.detail),
        glb_b64="H4sIAAAAAAACAwMAAAAAAAAAAAA=",
    )


def _fabrication_html(project):
    project.require_fabrication_release()
    return CPR.build_cabinetry_fabrication_html(project, images=_images())


def _audit_html(project):
    project.require_fabrication_release()
    return CPR.build_cabinetry_audit_html(project)


def test_db40_primary_sheet_owns_review_and_installation_within_reader_budget():
    project = compile_project_file(DB40)
    assert tuple(
        (finding.rule, finding.verdict)
        for finding in project.report.findings
        if finding.verdict == "UNKNOWN"
    ) == DB40_UNKNOWN_VERDICTS

    html = _review_html(project)
    visible = _visible_text(html)
    budgets = {
        "visible_words": (len(re.findall(r"\b[\w'’-]+\b", visible)), 2_500),
        "table_rows": (len(re.findall(r"<tr\b", html, re.IGNORECASE)), 80),
        "tables": (len(re.findall(r"<table\b", html, re.IGNORECASE)), 8),
    }
    over_budget = {
        name: {"actual": actual, "limit": limit}
        for name, (actual, limit) in budgets.items()
        if actual > limit
    }
    required_content = (
        "1016.00 mm",
        "876.30 mm",
        "590.55 mm",
        "158.75 mm",
        "254.00 mm",
        "354.95 mm",
        "1.50 mm",
        "2.00 mm",
        "Field-verify stud centers",
        "wall flatness",
        "highest floor point",
        "signed, project-specific acceptance",
        *(step.step_id for step in project.artifacts.installation_steps),
    )
    missing_content = tuple(item for item in required_content if item not in visible)
    missing_status_pairs = tuple(
        (component, status)
        for component, status in DB40_STATUS_MATRIX
        if f"{component}: {status}" not in visible
    )
    missing_unknown_rows = tuple(
        (rule, verdict)
        for rule, verdict in DB40_UNKNOWN_VERDICTS
        if re.search(
            rf"{re.escape(rule)}\s+{re.escape(verdict)}\b", visible,
        ) is None
    )
    forbidden_headings = {
        "Cut list",
        "Edge banding",
        "Hardware schedule",
        "Machining schedule",
        "Fabrication",
        "Assembly & shipping",
        "Validation findings",
        "Evidence register",
        "Source map",
    }
    owned_elsewhere = tuple(sorted(forbidden_headings.intersection(
        _headings(html)
    )))
    missing_views = tuple(
        view for view in REVIEW_VIEWS if f'data-view="{view}"' not in html
    )
    raw_views = tuple(
        view for view in ("side", "plan", "exploded", "drawer-detail")
        if f'data-view="{view}"' in html
    )

    assert not (
        over_budget or missing_content or missing_status_pairs
        or missing_unknown_rows or owned_elsewhere or missing_views or raw_views
    ), {
        "over_budget": over_budget,
        "missing_content": missing_content,
        "missing_status_pairs": missing_status_pairs,
        "missing_unknown_rows": missing_unknown_rows,
        "headings_owned_by_companions": owned_elsewhere,
        "missing_review_views": missing_views,
        "raw_views_owned_elsewhere": raw_views,
    }


def test_build_cabinetry_html_wraps_the_focused_review_composer():
    project = compile_project_file(DB40)
    project.require_fabrication_release()
    images = {view: PIXEL for view in CPR.REQUIRED_VIEWS}
    kwargs = {
        "images": images,
        "viewer_payload": build_viewer_payload(project.detail),
        "glb_b64": "H4sIAAAAAAACAwMAAAAAAAAAAAA=",
    }

    focused = CPR.build_cabinetry_review_html(project, **kwargs)

    assert focused == CPR.build_cabinetry_html(project, **kwargs)


def test_fabrication_composer_owns_complete_shop_and_assembly_ledgers():
    project = compile_project_file(DB40)
    html = _fabrication_html(project)

    for complete_renderer_output in (
        CPR._render_cut_list(project),
        CPR._render_edge_banding(project),
        CPR._render_hardware(project),
        CPR._render_machining(project),
        CPR._render_steps("Fabrication", project.artifacts.fabrication_steps),
        CPR._render_steps("Assembly & shipping", project.artifacts.assembly_steps),
    ):
        assert complete_renderer_output in html
    assert all(f'data-view="{view}"' in html for view in SHOP_VIEWS)

    forbidden_headings = {
        "Installation & commissioning",
        "Validation findings",
        "Evidence register",
        "Source map",
    }
    assert forbidden_headings.isdisjoint(_headings(html))
    for step in project.artifacts.installation_steps:
        assert step.step_id not in html
    for finding in project.report.findings:
        assert finding.rule not in html
    for evidence in project.report.evidence:
        assert evidence.evidence_id not in html
    for marker in VIEWER_MARKERS:
        assert marker not in html


def test_audit_composer_owns_complete_findings_evidence_and_source_map():
    project = compile_project_file(DB40)
    html = _audit_html(project)

    assert CPR._render_findings(project) in html
    assert CPR._render_source_map(project) in html
    forbidden_headings = {
        "Cut list",
        "Edge banding",
        "Hardware schedule",
        "Machining schedule",
        "Fabrication",
        "Assembly & shipping",
        "Installation & commissioning",
        "Drawings",
        "Interactive assembly",
        "Part key",
        "Dimensions",
    }
    assert forbidden_headings.isdisjoint(_headings(html))
    for step in (
        *project.artifacts.fabrication_steps,
        *project.artifacts.assembly_steps,
        *project.artifacts.installation_steps,
    ):
        assert step.step_id not in html
    for marker in VIEWER_MARKERS:
        assert marker not in html


def test_review_requires_base_validation_and_projects_typed_release_state():
    unvalidated = compile_project_file(DB40)
    with pytest.raises(ValueError, match="fabrication-released"):
        CPR.build_cabinetry_review_html(
            unvalidated,
            images=_images(),
            viewer_payload=build_viewer_payload(unvalidated.detail),
            glb_b64="H4sIAAAAAAACAwMAAAAAAAAAAAA=",
        )

    db40 = _review_html(compile_project_file(DB40))
    assert "Model/shop-data gate: PASS" in db40
    assert "Purchasing/cutting preflight: OPEN" in db40
    assert "Fabrication/model gate" not in db40
    assert "Installation/use release: HOLD" in db40

    b30 = _review_html(compile_project_file(B30))
    assert "Model/shop-data gate: PASS" in b30
    assert "Purchasing/cutting preflight: OPEN" in b30
    assert "Fabrication/model gate" not in b30
    assert "Installation/use release: PASS" in b30
    assert "Installation/use release: HOLD" not in b30


def test_future_db40_capacity_clearance_flips_typed_banner_without_html_edit():
    project = compile_project_file(DB40)
    cleared_rules = {
        "cabinetry.performance.anchor_capacity",
        "cabinetry.performance.whole_cabinet_capacity",
    }
    project.report = replace(
        project.report,
        findings=tuple(
            replace(finding, verdict="PASS", evidence_level="calculated")
            if finding.rule in cleared_rules else finding
            for finding in project.report.findings
        ),
    )
    project.require_release()

    html = CPR.build_cabinetry_review_html(
        project,
        images=_images(),
        viewer_payload=build_viewer_payload(project.detail),
        glb_b64="H4sIAAAAAAACAwMAAAAAAAAAAAA=",
    )
    assert "Installation/use release: PASS" in html
    assert "Installation/use release: HOLD" not in html
    release_gate = next(
        step.instruction for step in project.artifacts.installation_steps
        if step.step_id == "install.release_gate"
    )
    assert "Installation/use release: PASS" in release_gate
    assert "INSTALLATION/USE HOLD" not in release_gate

    from detailgen.packs.cabinetry.instruction_manual import (
        build_cabinetry_instruction_manual,
    )
    manual = build_cabinetry_instruction_manual(
        project,
        technical_href="db40_build.html",
        basename="db40_manual.html",
    )
    assert "INSTALLATION/USE HOLD" not in manual.lede
    assert all(
        "INSTALLATION/USE HOLD" not in item
        for item in manual.panels[5].honesty
    )
    assert "Installation/use release: PASS" in manual.lede


def test_db40_review_contains_release_boundary_views_and_exact_dimensions():
    project = compile_project_file(DB40)
    html = _review_html(project)

    assert "Model/shop-data gate: PASS" in html
    assert "Purchasing/cutting preflight: OPEN" in html
    assert "Fabrication/model gate" not in html
    assert "Installation/use release: HOLD" in html
    assert "Do not load, commission, or put the cabinet into service" in html
    assert "qualified cabinet or structural design professional" in html
    assert "serious or fatal crushing injury" in html
    assert "CPSC Anchor It! general guidance" in html
    assert "16 CFR part 1261 applies" in html
    assert "Whole-cabinet structural capacity: UNKNOWN" in _visible_text(html)
    for view in REVIEW_VIEWS:
        assert f'data-view="{view}"' in html
    for value in (
        "1016.00 mm", "876.30 mm", "590.55 mm", "977.90 mm",
        "1013.00 mm", "158.75 mm", "254.00 mm", "354.95 mm",
        "967.90 mm", "935.90 mm", "533.00 mm", "1.50 mm", "2.00 mm",
    ):
        assert value in html


def test_fabrication_projects_shop_sources_and_owned_process_phases():
    project = compile_project_file(DB40)
    html = _fabrication_html(project)

    for heading in (
        "Cut list", "Edge banding", "Hardware schedule", "Machining schedule",
        "Fabrication", "Assembly & shipping",
    ):
        assert heading in _headings(html)
    assert "Target id" in html
    assert "runner and lateral-stabilizer preparation" in html
    assert "Full-height surveyed wall studs are omitted" in html
    for product in (
        "blum_movento_763_5330s@2026.1",
        "blum_t51_7601_pair@2026.1",
        "blum_606n_no6x5_8@2026.1",
        "blum_zs7m686mu@2026.1",
        "hafele_vogue_155_01_613@2026.1",
        "hafele_handle_screw_m4x26_022_35_261@2026.1",
    ):
        assert product in html
    for source in project.model.catalog_source_manifest().values():
        assert f'href="{source}"' in html
    for step_id in (
        "fab.stabilizer_preparation", "shop.adjust_drawers",
        "ship.remove_drawers", "ship.empty_carcass",
    ):
        assert step_id in html


def test_review_reuses_interactive_viewer_payload_and_is_self_contained():
    project = compile_project_file(DB40)
    html = _review_html(project)
    slug = build_viewer_payload(project.detail)["slug"]

    assert f'data-detail="{slug}"' in html
    assert f'id="detail-data-{slug}"' in html
    assert f'id="detail-glb-{slug}"' in html
    assert "Explore in 3D" in html
    assert "THREE.GLTFLoader" in html
    assert "https://cdn" not in html
    assert 'src="http' not in html


def test_fabrication_uses_one_reader_vocabulary_for_hover_and_visible_part_key():
    project = compile_project_file(DB40)
    html = _fabrication_html(project)
    assembly = CPR.product_view_assembly(project)
    payload = CPR.product_viewer_payload(project, assembly)
    expected = {
        "DB40 left end": ("cabinetry.DB40.left_end", "Left cabinet side"),
        "DB40 right end": ("cabinetry.DB40.right_end", "Right cabinet side"),
        "DB40 drawer top side left": (
            "cabinetry.DB40.drawer_top_side_left",
            "Top drawer box — left side",
        ),
        "DB40 drawer front middle": (
            "cabinetry.DB40.drawer_front_middle", "Middle drawer front",
        ),
        "DB40 toe front": ("cabinetry.DB40.toe_front", "Toe-kick front"),
    }
    assert {
        machine_name: payload["parts"][machine_name]["reader_name"]
        for machine_name in expected
    } == {
        machine_name: reader_name
        for machine_name, (_part_id, reader_name) in expected.items()
    }
    assert "<h2>Part key</h2>" in html
    for part_id, reader_name in expected.values():
        assert part_id in html
        assert reader_name in html
    assert CPR.front_annotation_labels(project) == {
        "left_side": "Left cabinet side",
        "right_side": "Right cabinet side",
        "cabinet_bottom": "Cabinet bottom",
        "toe_front": "Toe-kick front",
        "drawer_top": "Top drawer front",
        "drawer_middle": "Middle drawer front",
        "drawer_bottom": "Bottom drawer front",
    }


def test_product_hover_metadata_matches_the_per_part_cut_record():
    project = compile_project_file(DB40)
    assembly = CPR.product_view_assembly(project)
    payload = CPR.product_viewer_payload(project, assembly)
    machine_name_by_part_id = {
        part.part_id: part.name for part in project.model.parts
    }

    for cut in project.artifacts.cut_list:
        hover = payload["parts"][machine_name_by_part_id[cut.part_id]]
        assert hover["qty"] == cut.quantity == 1
        assert hover["material"] == cut.material


def test_fabrication_starts_with_builder_readiness_and_machining_contract():
    project = compile_project_file(DB40)
    html = _fabrication_html(project)

    for phrase in (
        "Before you start",
        "Required tools and jigs",
        "Material and inclusion boundary",
        "Calculated moving load (not a rating)",
        "Machining datum rules",
        "Receiving part",
        "Pitch axis",
        "Physical qty",
        "Procurement meaning",
        "2 handed pieces = 1 left/right pair",
        "T65.1600.01",
        "5 mm pilot / 7 mm shank / 10 mm countersink",
        "No generic numeric tolerance is invented",
        "guided stepped drill and depth stop",
        "measured-stock offcut trial",
    ):
        assert phrase in html
    assert "Moving rated load" not in html
    assert "rated_moving_load_lb" not in html
    assert "Pre-band cut size" in html
    assert "0.5 mm declared finished thickness" in html
    assert "Bore locations are centers" in html
    assert "groove/notch locations are lower-left feature origins" in html
    assert sum(item.count for item in project.artifacts.machining_schedule
               if item.kind == "confirmat_step_drill") == 26


def test_base_cabinet_before_start_has_real_tool_requirements():
    project = compile_project_file(B30)
    html = _fabrication_html(project)

    for phrase in (
        "Layout and checking", "Sheet breakdown", "Confirmat joinery",
        "Doors and shelf", "System-32 boring jig", "Installation",
        "PZ3", "001.22.485", "Safety and dust control",
        "Safety glasses", "respiratory protection",
    ):
        assert phrase in html
    assert 'href="https://files.hafele.co.uk/catalogfiles/www/105-61.pdf"' in html


def test_report_does_not_authorize_declared_clothing_load_without_capacity():
    project = compile_project_file(DB40)
    html = _review_html(project)
    install = "\n".join(
        step.instruction for step in project.artifacts.installation_steps
    )

    assert "repeat operation with the declared" not in install
    assert "Do not load or use the cabinet" in install
    assert "40 lb" not in install
    assert "whole-cabinet structural capacity" in html.lower()


def test_multi_source_evidence_renders_as_separate_valid_links():
    project = compile_project_file(DB40)
    html = _audit_html(project)
    finding = project.report.by_rule("cabinetry.drawer.moving_hardware_mass")
    evidence = next(item for item in project.report.evidence
                    if item.evidence_id in finding.evidence_ids)
    sources = evidence.source.split(" | ")

    assert len(sources) >= 3
    for source in sources:
        assert f'href="{source}"' in html
    assert f'href="{evidence.source}"' not in html


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


def test_drawer_detail_geometry_uses_bottom_blank_and_selected_hardware_facts():
    project = compile_project_file(DB40)
    model = project.model
    facts = CPR.drawer_detail_geometry(model)
    bottom = model.part("drawer_top_bottom")

    assert facts["bottom_front_origin_mm"] == 10.0
    assert facts["bottom_side_origin_mm"] == 10.0
    assert facts["bottom_blank_width_mm"] == bottom.length_mm
    assert facts["bottom_blank_depth_mm"] == bottom.width_mm
    assert facts["runner_physical_length_mm"] == \
        model.drawer_bank.runner.physical_length_mm
    assert facts["pull_hole_spacing_mm"] == \
        model.drawer_bank.pull_product.hole_spacing_mm
    assert facts["locking_skus"] == (
        model.drawer_bank.locking_device.left_sku,
        model.drawer_bank.locking_device.right_sku,
    )
    assert facts["rear_notch_mm"] == (50.0, 13.0)
    assert facts["rear_hook_centers_mm"] == (
        (7.0, 24.0),
        (model.drawer_bank.inside_box_width_mm - 7.0, 24.0),
    )


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


def test_focused_review_and_fabrication_surfaces_accept_existing_door_base():
    project = compile_project_file(B30)
    review = _review_html(project)
    fabrication = _fabrication_html(project)

    assert "B30 frameless base cabinet" in review
    assert "Explore in 3D" in review
    assert "door_left" in fabrication
    assert "Cut list" in _headings(fabrication)
