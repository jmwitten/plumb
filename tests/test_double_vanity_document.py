"""Self-contained DV72 coordination study projected from the analytic pack."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys
from dataclasses import replace

from detailgen.packs import compile_project_file


ROOT = Path(__file__).parents[1]
FIXTURE = (
    ROOT / "tests/fixtures/cabinetry"
    / "floating_double_sink_four_drawer.project.yaml"
)


def _html():
    from detailgen.packs.cabinetry.double_vanity_document import (
        build_double_vanity_study_html,
    )

    return build_double_vanity_study_html(compile_project_file(FIXTURE))


def test_study_is_explicitly_non_released_and_contains_all_coordination_surfaces():
    html = _html()

    assert "DV72 floating double-sink four-drawer vanity study" in html
    assert "DESIGN STUDY — NOT A BUILD DOCUMENT" in html
    assert "Do not purchase, cut, drill, fabricate, or install" in html
    assert "Reference photograph controls visual intent only" in html
    assert "Installation/use release" not in html or "PASS" not in html
    for diagram in (
        "overall-elevation", "overall-plan", "bay-section",
        "left-bay-interaction", "right-bay-interaction", "wall-load-path",
    ):
        assert f'data-diagram="{diagram}"' in html
    for state in ("closed", "full-extension", "removal", "service"):
        assert f'data-motion-state="{state}"' in html


def test_study_projects_fixture_plumbing_drawer_and_code_facts_from_model():
    project = compile_project_file(FIXTURE)
    html = _html()

    for value in (
        "1828.8 mm", "558.8 mm", "533.4 mm", "38.1 mm",
        "514.0 × 398.0 × 186.0 mm", "448.0 × 334.0 × 135.0 mm",
        "44.0 mm", "31.75 mm", "1281904-7", "229.0 mm",
        "1219.2 mm", "609.6 mm", "381.0 mm", "762.0 mm", "533.4 mm",
    ):
        assert value in html
    assert html.count('data-plumbing-path="') == 2
    assert html.count('data-drawer-study="') == 4
    assert "upper U-shaped service drawer" in html
    assert "shortened lower drawer" in html
    assert "two independent P-traps" in html
    assert "Licensed Master Plumber" in html
    assert "space-saving drain systems can eliminate a conventional trap cutout" in html
    assert "Geberit ONE" in html
    assert "not interchangeable with the selected Kohler basin" in html
    assert "MOVENTO 763.4570S applies only to the upper U drawers" in html
    assert "MOVENTO 763.3050S applies to the lower shortened drawers" in html
    assert "457.0 mm drawer length" in html
    assert "lower runner family itself remains unselected" not in html
    assert "2022PC_Chapter4_FixturesWBwm.pdf" in html
    assert "2022PC_Chapter10_TrapsWBwm.pdf" in html
    for bay in project.model.sink_bays:
        assert f"{bay.sink_center_x_mm:.1f} mm" in html
    assert "Moving wings and runner travel clear" not in html
    assert "Lift/release path clears" not in html
    assert "Modeled study margin/opening" not in html
    assert "unverified until the runner SKU" not in html
    assert "Fabrication dimensions remain suppressed" not in html
    assert "cut depth and runner SKU remain suppressed" not in html
    assert "provisional U topology · cut dimensions held" not in html
    for drawer in project.model.drawers:
        assert f"U void {drawer.u_void_width_mm:.1f} mm" not in html


def test_every_release_gate_and_external_asset_boundary_is_visible():
    project = compile_project_file(FIXTURE)
    html = _html()

    for finding in project.report.findings:
        if finding.rule.startswith("double_vanity.release."):
            assert f'data-release-rule="{finding.rule}"' in html
            assert finding.message in html
    assert html.count('data-release-rule="double_vanity.release.') == 9
    assert "external CAD cache is optional" in html
    assert "visual/reference only" in html
    assert "cannot control cut lists, machining, plumbing, structure, or code" in html
    assert "redistribution: prohibited" in html
    assert "local_path" not in html


def test_wall_mount_and_installation_workflow_are_comparative_and_gate_bound():
    html = _html()

    assert "Reference installation patterns—not a DV72 prescription" in html
    assert "2x6 backing" in html
    assert "temporary support" in html
    assert "level and plumb" in html
    assert "all studs behind the rail" in html
    assert "https://techcomm.kohler.com/techcomm/pdf/1216526-2.pdf" in html
    assert "https://resources.kohler.com/webassets/kpna/catalog/pdf/en/1527256-2.pdf" in html
    assert "Release-dependent coordination workflow" in html
    assert "Leak-test both independent plumbing paths before drawers return" in html
    assert "does not authorize field work" in html


def test_part_names_are_canonical_on_visible_and_hover_surfaces():
    project = compile_project_file(FIXTURE)
    html = _html()
    named_roles = (
        "left_end", "center_divider", "right_end",
        "drawer_front_left_upper", "drawer_front_left_lower",
        "drawer_front_right_upper", "drawer_front_right_lower",
        "rear_mounting_rail",
    )
    for role in named_roles:
        part = project.model.part(role)
        assert f'data-part-id="{part.part_id}"' in html
        assert f"<title>{part.name}</title>" in html
        assert part.name in html


def test_diagram_anchor_marks_and_sink_datums_are_projected_from_model():
    project = compile_project_file(FIXTURE)
    html = _html()

    assert html.count('data-anchor-stud="') == len(project.model.anchor_stud_ids)
    for stud_id in project.model.anchor_stud_ids:
        assert f'data-anchor-stud="{stud_id}"' in html
    assert "vanity-left datum" in html
    assert "site-wall x" in html
    assert "vanity-local x = 457.2 mm" in html
    assert "vanity-local x = 1371.6 mm" in html


def test_fixture_adapter_mutation_moves_the_projected_plan_geometry(monkeypatch):
    import detailgen.packs.cabinetry.double_vanity as dv

    baseline = _html()
    monkeypatch.setattr(
        dv, "K20000",
        replace(dv.K20000, overall_width_mm=650.0, overall_depth_mm=450.0),
    )
    changed = _html()

    pattern = re.compile(
        r'data-fixture-envelope="left" x="[^"]+" y="[^"]+" '
        r'width="[^"]+" height="[^"]+"'
    )
    assert pattern.search(baseline)
    assert pattern.search(changed)
    assert pattern.search(baseline).group() != pattern.search(changed).group()


def test_ipc_profile_document_never_labels_its_value_as_nyc(tmp_path):
    from detailgen.packs.cabinetry.double_vanity_document import (
        build_double_vanity_study_html,
    )

    ipc_fixture = tmp_path / "ipc.project.yaml"
    ipc_fixture.write_text(
        FIXTURE.read_text().replace("jurisdiction: nyc_2022", "jurisdiction: ipc_2024")
    )
    html = build_double_vanity_study_html(compile_project_file(ipc_fixture))

    assert "International model code — 2024 IPC" in html
    assert "IPC 2024 609.6 mm" in html
    assert "NYC 609.6 mm" not in html


def test_generator_writes_deterministic_self_contained_html(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        import double_vanity_study as generator
    finally:
        sys.path.remove(str(scripts))

    first = generator.generate_double_vanity_study(
        FIXTURE, tmp_path / "first.html"
    )
    second = generator.generate_double_vanity_study(
        FIXTURE, tmp_path / "second.html"
    )
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()

    assert first_bytes == second_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()
    text = first_bytes.decode()
    assert "file://" not in text
    assert "<svg" in text
    assert "data:image" not in text
