"""Focused linked reader surfaces for the DV72 vanity."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import re
import inspect
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

    assert "FABRICATION HOLD — FABRICATOR ACCEPTANCE PENDING" in (
        docs["dv72_fabrication_coordination.html"]
    )
    assert "INSTALLATION HOLD — FIELD VERIFY" in (
        docs["dv72_review_installation.html"]
    )
    assert "owner_assumed" in docs["dv72_review_installation.html"]
    assert "not field verified" in docs["dv72_review_installation.html"]
    assert "TRADE HOLD" in docs["dv72_validation_sources.html"]
    assert 'data-release-status="HOLD_FABRICATOR_ACCEPTANCE"' in (
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
    assert "Prepared cabinet and drawer inventory — non-production" in html
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
    assert "42 prepared parts" in html
    assert "30.0 mm engineered quartz selected by countertop fabricator structural slab" in html
    assert "38.0 mm visual edge" in html
    assert "Selected material, joinery, finish, and tolerance schedule" in html
    assert "Wall drilling" in html
    assert "loading" in html
    assert "installation" in html


def test_fabrication_publishes_complete_owner_assumed_shop_basis():
    html = _documents()["dv72_fabrication_coordination.html"]

    for fact in (
        "19.05 mm veneer-core plywood",
        "15.0 mm veneer-core plywood",
        "9.0 mm plywood",
        "continuous grain sequence across four slab fronts",
        "1.0 mm matching walnut veneer edge band",
        "clear low-sheen conversion-varnish finish",
        "glued doweled butt joints",
        "#8 x 38 mm flat-head cabinet screws",
        "finished net part sizes after trimming and edge banding",
        "±0.5 mm part-size tolerance",
    ):
        assert fact in html
    assert html.count("owner_assumed; not field verified") >= 10
    assert "remain fabricator-controlled coordination items" not in html


def test_fabrication_publishes_controlling_top_and_model_derived_sink_zones():
    html = _documents()["dv72_fabrication_coordination.html"]

    assert "30.0 mm engineered quartz selected by countertop fabricator structural slab" in html
    assert "38.0 mm visual edge" in html
    assert "controlling owner_assumed case-height and load inputs" in html
    assert "200.2 mm/400.4 mm/200.2 mm/105.4 mm/30.0 mm" in html
    assert "not cutout, clamp, reinforcement, or structural authority" in html
    assert "final stone authority remains with the countertop fabricator" in html


def test_prepared_static_cuts_remain_nonproduction_and_dynamic_gates_are_separate():
    docs = _documents()
    joined = "\n".join(docs.values())
    validation = docs["dv72_validation_sources.html"]

    assert (
        "Static drawer-box cuts are prepared for review only; signed "
        "fabricator acceptance of the exact basis digest is required before production"
    ) in validation
    assert "dynamic/service access remain separately held" in validation
    for contradiction in (
        "Derive buildable U voids",
        "re-derive both U-shaped upper boxes",
        "drawer joinery remains held",
        "joinery remains withheld",
    ):
        assert contradiction not in joined

    for sentence in re.split(r"(?<=[.!?])\s+", joined):
        if re.search(r"\bjoinery\b", sentence, flags=re.I) and re.search(
            r"\b(?:held|withheld)\b", sentence, flags=re.I
        ):
            assert "prepared for review" in sentence and "non-production" in sentence


def test_review_exposes_axes_site_assumptions_faucet_target_and_all_loads():
    html = _documents()["dv72_review_installation.html"]
    project = compile_project_file(FIXTURE)

    assert "x = 0 at the finished left end of the assumed 144.00 in wall" in html
    assert "y = 0 at the project datum plane" in html
    assert "1.00 in in front of the modeled finished vanity-front plane" in html
    assert "y increases toward the wall" in html
    assert "z = 0 at the assumed finished-floor datum" in html
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


def test_production_cut_authority_requires_written_fabricator_acceptance():
    html = _documents()["dv72_fabrication_coordination.html"]

    assert "FABRICATION HOLD — FABRICATOR ACCEPTANCE PENDING" in html
    assert "Prepared schedule only — non-production" in html
    assert "not authorized for production cutting" in html
    assert "accepted replacements require regeneration of affected cut authority" in html


def test_review_distinguishes_selected_veneer_from_unresolved_pulls():
    review = _documents()["dv72_review_installation.html"]

    assert "Half-moon pulls and veneer sequencing remain unresolved" not in review
    assert (
        "Veneer sequence is conditionally selected owner_assumed pending written "
        "cabinet-fabricator acceptance"
    ) in review
    assert (
        "Veneer sequencing is conditionally selected owner_assumed pending written "
        "cabinet-fabricator acceptance; half-moon pulls remain unresolved"
    ) in review
    assert "Half-moon brass pulls remain unresolved" in review


def test_nominal_profile_panels_map_to_selected_19mm_material_basis():
    project = compile_project_file(FIXTURE)
    html = _documents()["dv72_fabrication_coordination.html"]
    rows = re.findall(r'<tr data-cut-list-row=".*?</tr>', html)
    nominal_roles = {
        item.role for item in project.artifacts.cut_list
        if item.thickness_mm == pytest.approx(project.model.profile.carcass_thickness_mm)
        or item.thickness_mm == pytest.approx(project.model.profile.door_thickness_mm)
    }

    assert project.model.profile.carcass_thickness_mm == pytest.approx(19.05)
    assert nominal_roles
    for role in nominal_roles:
        row = next(row for row in rows if f".{role}</code>" in row)
        assert "veneer-core plywood" in row
        assert "thickness-specific material basis requires" not in row


def test_renderer_projects_typed_fabrication_basis_without_shop_literals():
    import detailgen.packs.cabinetry.double_vanity_documents as documents

    source = inspect.getsource(documents._fabrication_boundaries)
    for literal in (
        "continuous figured-walnut grain sequence",
        "glued doweled butt joints at the released finished extents",
        "#8 × 38 mm",
        "±0.5 mm part-size tolerance",
        "quartz structural slab",
    ):
        assert literal not in source

    project = compile_project_file(FIXTURE)
    html = _documents()["dv72_fabrication_coordination.html"]
    for row in project.model.fabrication_basis.shop_schedule():
        assert row in html


def test_documents_reject_forged_or_stale_authority_state():
    from dataclasses import replace
    from detailgen.packs.cabinetry.double_vanity_documents import (
        build_double_vanity_document_set,
    )

    pending = compile_project_file(FIXTURE)
    forged = replace(
        pending,
        model=replace(
            pending.model,
            release=replace(
                pending.model.release,
                fabrication_status="CONDITIONAL_FABRICATION_RELEASE",
            ),
        ),
    )
    with pytest.raises(ValueError, match="authority state is inconsistent"):
        build_double_vanity_document_set(forged)

    from detailgen.packs.cabinetry.double_vanity import (
        FabricationAcceptance,
        accept_double_vanity_project,
    )
    acceptance = FabricationAcceptance(
        status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
        accepted_on="2026-07-15",
        basis_digest=pending.model.fabrication_basis.digest(),
        evidence_revision="signed-shop-basis-r1",
    )
    accepted = accept_double_vanity_project(pending, acceptance)
    stale = replace(
        accepted,
        artifacts=replace(accepted.artifacts, fabrication_ready=False),
    )
    with pytest.raises(ValueError, match="authority state is inconsistent"):
        build_double_vanity_document_set(stale)


def test_accepted_documents_record_exact_acceptance_evidence_without_hold_leakage():
    from detailgen.packs.cabinetry.double_vanity import (
        FabricationAcceptance,
        accept_double_vanity_project,
    )
    from detailgen.packs.cabinetry.double_vanity_documents import (
        build_double_vanity_document_set,
    )

    pending = compile_project_file(FIXTURE)
    acceptance = FabricationAcceptance(
        status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
        accepted_on="2026-07-15",
        basis_digest=pending.model.fabrication_basis.digest(),
        evidence_revision="signed-shop-basis-r1",
    )
    accepted = accept_double_vanity_project(pending, acceptance)
    accepted.validate()
    docs = build_double_vanity_document_set(accepted)
    fabrication = docs["dv72_fabrication_coordination.html"]
    assert "FABRICATOR ACCEPTANCE RECORDED" in fabrication
    for value in (
        acceptance.accepted_by, acceptance.accepted_on,
        acceptance.evidence_revision, acceptance.basis_digest,
    ):
        assert value in fabrication
    assert "FABRICATOR ACCEPTANCE PENDING" not in fabrication
    assert "Prepared schedule only — non-production" not in fabrication
    assert "production inventory" in fabrication


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


def test_forged_product_geometry_hold_fails_authority_coherence():
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
    with pytest.raises(ValueError, match="authority state is inconsistent"):
        build_double_vanity_document_set(held_project)


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


def test_validation_gate_language_preserves_prepared_nonproduction_schedule():
    html = _documents()["dv72_validation_sources.html"]

    assert "prepared for review only" in html
    assert "acceptance of the exact basis digest is required before production" in html
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
        if finding.rule != "double_vanity.release.drawer_derivation":
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
    assert "Prepared drawer geometry and held assembly authority" in assembly
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
