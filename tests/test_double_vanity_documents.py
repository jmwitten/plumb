"""Focused linked reader surfaces for the DV72 vanity."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

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
        assert "DESIGN HOLD" in html
        assert "file://" not in html
        for other in documents:
            assert f'href="{other}"' in html


def test_review_owns_the_useful_sink_plumbing_drawer_mount_section():
    review = _documents()["dv72_review_installation.html"]

    assert "Sink, plumbing, drawers, counter, and wall mount" in review
    assert 'data-section-system="fixture"' in review
    assert 'data-section-system="p-trap"' in review
    assert 'data-section-system="upper-drawer"' in review
    assert 'data-section-system="lower-drawer"' in review
    assert 'data-section-system="rear-rail"' in review
    assert 'data-section-system="wall"' in review
    assert "Drawer-removal service sequence" in review
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
    assert "Proposed shell assembly" in assembly
    assert "Build and square" not in assembly
    assert "34.50 in" in review
    assert "11.00 in" in review
    assert "site-wall zero datum" in review
    assert "Issue date" in joined
    assert validation.count('data-release-rule="double_vanity.release.') == 8
    assert 'data-commissioning-rule="double_vanity.release.commissioning"' in validation
    assert "Post-install commissioning hold" in validation
    assert "Proposed sequence—conditional" in assembly
    assert "If runner validation proves" in assembly
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
