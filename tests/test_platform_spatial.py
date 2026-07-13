"""Task SPATIAL — coverage-matrix activation on the real details.

The platform declares spatial invariants, so its Spatial-intent coverage row is
the FIRST family to flip from UNKNOWN to PASS. The rock anchor declares none, so
its Spatial-intent row MUST stay UNKNOWN — merely having the feature available
fabricates no coverage (the permits-vs-requires honesty rule). Both are asserted
here, plus that the platform's declared invariants are real, passing findings.

Both details are compiled from their ``.spec.yaml`` via ``compile_spec_file``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file
from detailgen.validation.coverage import PASS, UNKNOWN, coverage_matrix

ROOT = Path(__file__).resolve().parents[1]


def _detail(spec_name):
    return compile_spec_file(ROOT / "details" / spec_name)


def _row(report, family):
    return next(r for r in coverage_matrix(report) if r.family == family)


@pytest.fixture(scope="module")
def platform_report():
    return _detail("platform.spec.yaml").validate()


def test_platform_declares_symmetric_about_for_every_mirror_pair(platform_report):
    sym = [f for f in platform_report.findings if f.check == "symmetric_about"]
    # the +Y/-Y selector generalizes the mutation-proven 20-pair RAILFIX audit;
    # the model has grown well past 20 mirrored pairs since.
    assert len(sym) > 20
    assert all(f.passed for f in sym), [f for f in sym if not f.passed]
    assert all("XZ" in f.subject for f in sym)


def test_platform_declares_ladder_faces_away_from_deck_interior(platform_report):
    faces = [f for f in platform_report.findings if f.check == "faces_away"]
    assert len(faces) == 1
    assert faces[0].passed and "rung 0" in faces[0].subject


def test_platform_spatial_family_flips_to_pass(platform_report):
    row = _row(platform_report, "Spatial intent")
    assert row.verdict == PASS, row
    # provenance names the kinds that ran (P1/P4).
    kinds = dict(row.ran_kinds)
    assert kinds.get("symmetric_about", 0) > 20
    assert kinds.get("faces_away", 0) == 1


def test_rock_anchor_spatial_family_stays_unknown():
    report = _detail("rock_anchor.spec.yaml").validate()
    row = _row(report, "Spatial intent")
    assert row.verdict == UNKNOWN, row
    assert row.checks_run == 0
    # no spatial finding kind appears anywhere in the rock anchor's report.
    assert not [f for f in report.findings
                if f.check in ("symmetric_about", "faces_toward", "faces_away")]
