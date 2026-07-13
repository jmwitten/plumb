"""Coverage matrix on the consolidated_report code path (task W31, req 5).

Loads ``scripts/consolidated_report.py`` by file path (same pattern as
``test_site_overview.py``) and exercises ``render_coverage_section`` directly —
no ``main()``, so nothing renders/exports or touches the vault.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from detailgen.validation.coverage import INVARIANT_FAMILIES, STANDING_NOTE

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report_mod():
    return _load("consolidated_report_test_cov", REPO_ROOT / "scripts" / "consolidated_report.py")


@pytest.fixture(scope="module")
def coverage_html(report_mod):
    details = report_mod.load_details()
    # render_coverage_section now takes the per-detail verdicts as a second arg
    # (docrebuild): the caller validates ONCE from exact geometry before the lossy
    # web-GLB export, and each matrix renders that verdict instead of re-validating
    # possibly-mutated solids. Here the details are freshly compiled and never
    # exported, so validate() is the clean verdict.
    reports = {name: d.validate() for name, d in details.items()}
    return report_mod.render_coverage_section(details, reports)


def test_section_names_every_family_for_every_detail(coverage_html):
    # four tables (one caption per detail)
    for title in ("Zipline platform", "Rock anchor", "Tree-end attachment", "Trolley launch"):
        assert title in coverage_html
    for fam in INVARIANT_FAMILIES:
        assert fam in coverage_html


def test_section_marks_unanalyzed_families_not_analyzed(coverage_html):
    assert "NOT ANALYZED" in coverage_html
    assert STANDING_NOTE in coverage_html
    # Functional / Structural capacity / Code compliance are UNKNOWN for all
    # four details (4x3); Spatial is analyzed only on the platform and
    # Load-path only on the rock anchor, leaving 3 UNKNOWN cells each.
    assert coverage_html.count("UNKNOWN") >= 4 * 3 + 3 + 3


def test_section_never_claims_safety(coverage_html):
    lowered = coverage_html.lower()
    assert "is safe" not in lowered
    # the honest wording is present instead
    assert "REPRESENTED" in coverage_html


def test_verdict_headline_leads_with_the_per_family_breakdown(report_mod):
    """The title-block verdict must LEAD with the per-family breakdown and demote
    "CLEAN" to an internal note (owner directive §3). HEADLINE replaced the
    prose ``_derive_status_sentence`` with ``_render_verdict_headline``, which
    DERIVES the headline from the coverage matrices rolled up across all reports
    (never a hardcoded literal), so this asserts the derived breakdown.

    Uses real reports (the composed site + the four details) so the aggregate is
    the true document-level roll-up, not a stub."""
    from detailgen.validation.coverage import INVARIANT_FAMILIES

    details = report_mod.load_details()
    detail_reports = {n: d.validate() for n, d in details.items()}
    site = report_mod.load_site()
    status = report_mod._render_verdict_headline(detail_reports, site.validate())

    # PRIMARY: the per-family breakdown — every invariant family named, in a
    # verdict-tagged headline list, with the honest NOT-ANALYZED families present.
    assert 'class="verdict-headline"' in status
    for fam in INVARIANT_FAMILIES:
        assert fam in status, fam
    assert "NOT ANALYZED" in status
    # the never-checked families read NOT ANALYZED, not a silent pass
    for fam in ("Structural capacity", "Code compliance"):
        assert f">{fam}</span>" in status

    # SECONDARY: the ladder rung + adequacy disclaimer stay in plain language.
    assert "support-REPRESENTED (rung 3)" in status
    assert "not proven safe" in status.lower()

    # FAB-3 (retire R29): the document is NO LONGER clean — the platform holds
    # the blocking foundation-capacity UNKNOWNs and the composed site's render
    # gate is closed by them. The internal verdict reads NOT CLEAN, demoted below
    # the per-family breakdown (never an unqualified top-line either way).
    assert "Internal export verdict: NOT CLEAN" in status
    assert "block the render gate" in status
