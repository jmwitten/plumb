"""Focused linked reader surfaces for the DV72 vanity."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import re
import sys
from pathlib import Path

import pytest

from detailgen.packs import compile_project_file


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT / "tests/fixtures/cabinetry"
    / "floating_double_sink_four_drawer.project.yaml"
)


def _documents():
    from detailgen.packs.cabinetry.double_vanity_documents import (
        build_double_vanity_document_set,
    )

    return build_double_vanity_document_set(compile_project_file(FIXTURE))


def test_four_concise_linked_reader_surfaces_have_distinct_jobs():
    documents = _documents()

    assert tuple(documents) == (
        "dv72_review_installation.html",
        "dv72_assembly_service.html",
        "dv72_fabrication_coordination.html",
        "dv72_validation_sources.html",
    )
    expected_titles = (
        "Review & installation",
        "Assembly & service",
        "Fabrication coordination",
        "Validation & sources",
    )
    for name, title in zip(documents, expected_titles):
        html = documents[name]
        assert f"<h1>{title}</h1>" in html
        assert "file://" not in html
        for other in documents:
            assert f'href="{other}"' in html


def test_documents_distinguish_all_authorities():
    docs = _documents()

    assert "CONDITIONAL FABRICATION RELEASE" in (
        docs["dv72_fabrication_coordination.html"]
    )
    assert "INSTALLATION HOLD — FIELD VERIFY" in (
        docs["dv72_review_installation.html"]
    )
    assert "owner_assumed" in docs["dv72_review_installation.html"]
    assert "not field verified" in docs["dv72_review_installation.html"]
    assert "TRADE HOLD" in docs["dv72_validation_sources.html"]
    assert 'data-release-status="CONDITIONAL_FABRICATION_RELEASE"' in (
        docs["dv72_fabrication_coordination.html"]
    )
    assert 'data-release-status="HOLD_FIELD_VERIFY"' in (
        docs["dv72_review_installation.html"]
    )
    assert 'data-release-status="HOLD_RESPONSIBLE_TRADE_APPROVAL"' in (
        docs["dv72_validation_sources.html"]
    )


def test_fabrication_names_both_runners_and_withholds_stone():
    html = _documents()["dv72_fabrication_coordination.html"]

    assert "763.4570S" in html
    assert "763.3050S" in html
    assert "Released cabinet and drawer inventory" in html
    assert "Stone cutting remains fabricator-controlled" in html


def test_review_projects_owner_assumptions_and_field_comparison_checklist():
    html = _documents()["dv72_review_installation.html"]

    assert "Owner-assumed site and rough-in schedule" in html
    assert "left_waste" in html
    assert "right_cold" in html
    assert "Field comparison checklist" in html
    assert "Do not install" in html
    assert "Install the" not in html


def test_assembly_projects_exact_drawer_and_runner_facts_without_install_steps():
    html = _documents()["dv72_assembly_service.html"]

    assert "763.4570S" in html
    assert "763.3050S" in html
    assert "873.8 mm × 457.0 mm" in html
    assert "873.8 mm × 305.0 mm" in html
    assert "Exact owner-assumed rough-ins" in html
    assert "left_waste" in html
    assert "1066.8 mm" in html
    assert "not field verified" in html
    assert "Runner machining remains withheld" in html
    assert "Install the" not in html


def test_fabrication_scopes_release_and_held_work():
    html = _documents()["dv72_fabrication_coordination.html"]

    assert 'data-cut-list-row="' in html
    assert "42 released parts" in html
    assert "30.0 mm quartz structural slab" in html
    assert "38.0 mm visual edge" in html
    assert "Selected material, joinery, finish, and tolerance schedule" in html
    assert "Wall drilling" in html
    assert "loading" in html
    assert "installation" in html


def test_fabrication_publishes_complete_owner_assumed_shop_basis():
    html = _documents()["dv72_fabrication_coordination.html"]

    for fact in (
        "19.0 mm veneer-core plywood case and slab fronts",
        "15.0 mm veneer-core plywood drawer sides, fronts, and backs",
        "9.0 mm plywood drawer bottoms",
        "continuous figured-walnut grain sequence across the four slab fronts",
        "1.0 mm matching walnut veneer edge band",
        "clear low-sheen conversion-varnish finish",
        "glued doweled butt joints",
        "#8 × 38 mm flat-head cabinet screws",
        "finished net part sizes after trimming and edge banding",
        "±0.5 mm part-size tolerance",
    ):
        assert fact in html
    assert html.count("owner_assumed; not field verified") >= 10
    assert "remain fabricator-controlled coordination items" not in html


def test_fabrication_publishes_controlling_top_and_model_derived_sink_zones():
    html = _documents()["dv72_fabrication_coordination.html"]

    assert "30.0 mm quartz structural slab" in html
    assert "38.0 mm visual edge" in html
    assert "controlling owner_assumed case-height and load inputs" in html
    assert "200.2 mm left gross side zone" in html
    assert "400.4 mm gross inter-sink web" in html
    assert "200.2 mm right gross side zone" in html
    assert "105.4 mm gross front zone" in html
    assert "30.0 mm gross rear zone" in html
    assert "not cutout dimensions" in html
    assert "final stone authority remains with the countertop fabricator" in html


def test_static_cut_release_is_not_revoked_by_runner_or_dynamic_gates():
    docs = _documents()
    joined = "\n".join(docs.values())
    validation = docs["dv72_validation_sources.html"]

    assert (
        "Static drawer-box cuts remain conditionally released; prove runner "
        "drilling/templates, locking-device shop setup, and dynamic/service access"
    ) in validation
    assert "Dynamic access does not revoke the conditionally released static cuts" in validation
    for contradiction in (
        "Derive buildable U voids",
        "re-derive both U-shaped upper boxes",
        "drawer joinery remains held",
        "joinery remains withheld",
    ):
        assert contradiction not in joined


def test_review_exposes_axes_site_assumptions_faucet_target_and_all_loads():
    html = _documents()["dv72_review_installation.html"]
    project = compile_project_file(FIXTURE)

    assert "x increases right along the wall" in html
    assert "y = 0 at the project datum" in html
    assert "y increases toward the wall" in html
    assert "z increases above the floor datum" in html
    assert "straight, flat, and plumb wall" in html
    assert "4.50 in above the finished counter" in html
    assert "21.00 in clear room depth in front" in html
    for name, value in project.model.load_case.component_weights_lb().items():
        assert name.replace("_", " ") in html
        assert f"{value:.1f} lb" in html
    assert f"{project.model.load_case.unfactored_total_lb:.1f} lb" in html
    assert f"{project.model.load_case.factored_total_lb:.1f} lb" in html


def test_mount_diagram_uses_supports_as_primary_gravity_path():
    html = _documents()["dv72_review_installation.html"]

    assert "study-declared/owner_assumed framing" in html
    assert "Rakks supports are the primary gravity path" in html
    assert "continuous rail is positioning/lateral only with zero gravity credit" in html
    assert 'data-load-path="primary-support"' in html
    assert 'data-load-path="top-to-rail"' not in html
    assert "surveyed framing" not in html
    assert "top/fixtures/contents → case → continuous rail" not in html


def test_validation_assigns_owner_and_blocking_phase_to_every_finding():
    project = compile_project_file(FIXTURE)
    html = _documents()["dv72_validation_sources.html"]

    assert html.count('data-finding-rule="') == len(project.report.findings)
    assert html.count('data-responsible-party="') == len(project.report.findings)
    assert html.count('data-blocking-phase="') == len(project.report.findings)


def test_document_set_rejects_stale_pre_release_contradictions():
    joined = "\n".join(_documents().values())

    for contradiction in (
        "Fabrication dimensions remain suppressed",
        "cut depth and runner SKU remain suppressed",
        "lower runner family itself remains unselected",
        "unverified until the runner SKU",
        "No cut authorization is issued",
        "dimensions remain coordination targets",
        "must re-derive the drawer voids before fabrication",
    ):
        assert contradiction not in joined


def test_product_geometry_hold_never_leaks_visible_fabrication_release():
    from detailgen.packs.cabinetry.double_vanity_documents import (
        build_double_vanity_document_set,
    )

    project = compile_project_file(FIXTURE)
    held_release = replace(
        project.model.release,
        fabrication_status="HOLD_PRODUCT_GEOMETRY",
    )
    held_project = replace(
        project,
        model=replace(project.model, release=held_release),
    )
    docs = build_double_vanity_document_set(held_project)
    fabrication = docs["dv72_fabrication_coordination.html"]
    joined = "\n".join(docs.values())

    assert 'data-release-status="HOLD_PRODUCT_GEOMETRY"' in fabrication
    assert "FABRICATION HOLD — PRODUCT GEOMETRY" in fabrication
    assert "Released cabinet and drawer inventory" not in joined
    assert "released parts" not in joined
    assert "CONDITIONAL FABRICATION RELEASE" not in joined
    assert 'data-cut-list-row="' not in fabrication
    joined_lower = joined.lower()
    for leak in (
        "conditional fabrication release",
        "conditionally released",
        "released cabinet and drawer cuts",
        "released cabinet and drawer inventory",
        "released box",
        "released u void",
        "released parts",
    ):
        assert leak not in joined_lower


def test_fabrication_labels_every_assumption_as_unverified_owner_input():
    project = compile_project_file(FIXTURE)
    html = _documents()["dv72_fabrication_coordination.html"]
    inventory_rows = re.findall(r'<tr data-cut-list-row=".*?</tr>', html)

    assert len(inventory_rows) == len(project.artifacts.cut_list)
    for row in inventory_rows:
        assert "owner_assumed" in row
        assert "not field verified" in row
    assumptions = html[html.index("Selected material, joinery, finish, and tolerance schedule"):]
    assert "owner_assumed" in assumptions
    assert "not field verified" in assumptions


def test_package_has_no_unlabelled_assumption_claims():
    for html in _documents().values():
        paragraphs = re.findall(r"<p(?: [^>]*)?>.*?</p>", html, flags=re.S)
        for paragraph in paragraphs:
            if re.search(r"\bassumption\b", paragraph, flags=re.I):
                assert "owner_assumed" in paragraph
                assert "not field verified" in paragraph
    assert "by assumption" not in "\n".join(_documents().values()).lower()


def test_validation_routes_evidence_without_claiming_approval_authority():
    html = _documents()["dv72_validation_sources.html"]
    lower = html.lower()

    assert "routes evidence requests only" in lower
    assert "coordination routing only" in lower
    assert "approval and release authority is established outside this renderer" in lower
    assert "responsible for closing" not in lower
    assert "authority remains with the named responsible parties" not in lower


def test_validation_gate_language_preserves_conditional_cabinet_cut_authority():
    html = _documents()["dv72_validation_sources.html"]

    assert "do not revoke the conditionally released cabinet and drawer cuts" in html
    assert "Close all eight before purchase, fabrication" not in html
    assert "installation, stone, runner machining, trade work, and use" in html


def test_finding_routing_is_exhaustive_and_exact():
    from detailgen.packs.cabinetry.double_vanity_documents import _finding_routing

    expected = {
        "double_vanity.code.fixture_spacing": ("Design coordinator", "design validation"),
        "double_vanity.drawer.runner_applicability": ("Cabinet fabricator", "runner machining and assembly"),
        "double_vanity.geometry.fixture_plumbing_drawer": ("Design coordinator", "design validation"),
        "double_vanity.geometry.service_openings": ("Cabinet fabricator", "runner machining and assembly"),
        "double_vanity.geometry.two_bays": ("Design coordinator", "design validation"),
        "double_vanity.mount.layout": ("Structural reviewer", "wall drilling and loading"),
        "double_vanity.mount.representation": ("Structural reviewer", "wall drilling and loading"),
        "double_vanity.plumbing.independent_traps": ("Licensed Master Plumber", "trade coordination"),
        "double_vanity.release.commissioning": ("General contractor and responsible trades", "commissioning"),
        "double_vanity.release.countertop_fabricator": ("Countertop fabricator", "stone fabrication"),
        "double_vanity.release.drawer_derivation": ("Cabinet fabricator", "runner machining and assembly"),
        "double_vanity.release.dynamic_access": ("Cabinet fabricator", "runner machining and assembly"),
        "double_vanity.release.faucet": ("Licensed Master Plumber", "trade coordination"),
        "double_vanity.release.fixture_template": ("Countertop fabricator", "stone fabrication"),
        "double_vanity.release.plumbing_approval": ("Licensed Master Plumber", "trade coordination"),
        "double_vanity.release.site_survey": ("Field surveyor", "field verification"),
        "double_vanity.release.wall_mount": ("Structural reviewer", "wall drilling and loading"),
    }
    project = compile_project_file(FIXTURE)

    assert {finding.rule for finding in project.report.findings} == set(expected)
    assert {
        finding.rule: _finding_routing(finding.rule)
        for finding in project.report.findings
    } == expected
    with pytest.raises(ValueError, match="unmapped DV72 finding rule"):
        _finding_routing("double_vanity.future.unreviewed")


def test_visible_collection_counts_derive_from_model_collections():
    project = compile_project_file(FIXTURE)
    docs = _documents()
    review = docs["dv72_review_installation.html"]
    validation = docs["dv72_validation_sources.html"]
    rough_ins = project.model.assumed_site.wastes + project.model.assumed_site.supplies
    preinstall = [
        finding for finding in project.report.findings
        if finding.rule.startswith("double_vanity.release.")
        and finding.rule != "double_vanity.release.commissioning"
    ]

    assert f"{len(project.model.support_layout.supports)} provisional support envelopes" in review
    assert f"{len(rough_ins)} owner-assumed coordinates" in review
    assert f"{len(preinstall)} pre-install release gates" in validation


def test_review_owns_the_useful_sink_plumbing_drawer_mount_section():
    review = _documents()["dv72_review_installation.html"]

    assert "Sink, plumbing, drawers, counter, and wall mount" in review
    assert 'data-section-system="fixture"' in review
    assert 'data-section-system="p-trap"' in review
    assert 'data-section-system="upper-drawer"' in review
    assert 'data-section-system="lower-drawer"' in review
    assert 'data-section-system="rear-rail"' in review
    assert 'data-section-system="wall"' in review
    assert "Held service sequence" in review
    assert "IMG_7670.HEIC" in review
    assert "warm figured wood" in review
    assert "visual intent only" in review


def test_validation_owns_all_release_rows_without_omnibus_duplication():
    project = compile_project_file(FIXTURE)
    documents = _documents()
    validation = documents["dv72_validation_sources.html"]
    release_findings = tuple(
        finding for finding in project.report.findings
        if finding.rule.startswith("double_vanity.release.")
    )

    assert len(release_findings) == 9
    assert validation.count('data-release-rule="double_vanity.release.') == 8
    for finding in release_findings:
        assert finding.rule in validation
        assert finding.message in validation
    for name, html in documents.items():
        if name != "dv72_validation_sources.html":
            assert 'data-release-rule="' not in html


def test_validation_names_pinned_plumbing_runner_and_comparative_mount_authority():
    html = _documents()["dv72_validation_sources.html"]

    assert "K-7124-A" in html
    assert "1-1/4 in overflow drain" in html
    assert "K-8998" in html
    assert "298.0 × 111.0 mm" in html
    assert "763.4570S" in html
    assert "Rakks EH-1818-LV" in html
    assert "450 lb evenly distributed static load" in html
    assert "comparative reference only" in html
    assert "does not establish DV72 capacity" in html


def test_handyman_review_findings_are_resolved_without_overclaiming_access():
    documents = _documents()
    joined = "\n".join(documents.values())
    review = documents["dv72_review_installation.html"]
    assembly = documents["dv72_assembly_service.html"]
    validation = documents["dv72_validation_sources.html"]

    assert "independent independent" not in joined
    assert "remain reachable" not in joined
    assert "proposed service-access concept" in review
    assert "Released drawer geometry and held assembly authority" in assembly
    assert "Build and square" not in assembly
    assert "34.50 in" in review
    assert "11.00 in" in review
    assert "site-wall zero datum" in review
    assert "Issue date" in joined
    assert validation.count('data-release-rule="double_vanity.release.') == 8
    assert 'data-commissioning-rule="double_vanity.release.commissioning"' in validation
    assert "Post-install commissioning hold" in validation
    assert "Sequence concept only—installation and service remain held" in assembly
    assert "surveyed wall studs" not in validation
    assert "study-declared stud axes" in validation


def test_generator_compiles_once_and_writes_deterministic_inventory(tmp_path):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        import double_vanity_documents as generator
    finally:
        sys.path.remove(str(scripts))

    first = generator.generate_double_vanity_documents(FIXTURE, tmp_path / "one")
    second = generator.generate_double_vanity_documents(FIXTURE, tmp_path / "two")

    assert tuple(first["files"]) == tuple(_documents())
    assert first["sha256"] == second["sha256"]
    for name, digest in first["sha256"].items():
        data = (tmp_path / "one" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        assert not re.search(rb'href="(?:/|[A-Za-z]:)', data)
