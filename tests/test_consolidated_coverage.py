"""Coverage matrix on the consolidated_report code path (task W31, req 5).

Loads ``scripts/consolidated_report.py`` by file path (same pattern as
``test_site_overview.py``) and exercises ``render_coverage_section`` directly —
no ``main()``, so nothing renders/exports or touches the vault.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from detailgen.validation.coverage import INVARIANT_FAMILIES, STANDING_NOTE

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class _CoverageContext:
    details: dict
    detail_reports: dict
    site: object
    site_report: object


def _build_coverage_context(report_mod):
    details = report_mod.load_details()
    detail_reports = {name: detail.validate() for name, detail in details.items()}
    site = report_mod.load_site()
    return _CoverageContext(
        details=details,
        detail_reports=detail_reports,
        site=site,
        site_report=site.validate(),
    )


def test_coverage_context_loads_and_validates_each_accepted_model_once():
    calls = {"details": 0, "site": 0, "validations": []}

    class _Model:
        def __init__(self, name):
            self.name = name

        def validate(self):
            calls["validations"].append(self.name)
            return f"report:{self.name}"

    class _ReportModule:
        @staticmethod
        def load_details():
            calls["details"] += 1
            return {"a": _Model("a"), "b": _Model("b")}

        @staticmethod
        def load_site():
            calls["site"] += 1
            return _Model("site")

    context = _build_coverage_context(_ReportModule)

    assert calls == {
        "details": 1,
        "site": 1,
        "validations": ["a", "b", "site"],
    }
    assert context.detail_reports == {"a": "report:a", "b": "report:b"}
    assert context.site_report == "report:site"


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
def coverage_context(report_mod, tmp_path_factory):
    cache_dir = tmp_path_factory.mktemp("consolidated_coverage_cache")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(cache_dir))
        monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)
        yield _build_coverage_context(report_mod)


@pytest.fixture(scope="module")
def coverage_html(report_mod, coverage_context):
    # The caller validates ONCE from exact geometry before the lossy web-GLB
    # export, and each matrix renders that verdict instead of re-validating.
    return report_mod.render_coverage_section(
        coverage_context.details,
        coverage_context.detail_reports,
    )


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


def test_verdict_headline_leads_with_the_per_family_breakdown(
    report_mod, coverage_context
):
    """The title-block verdict must LEAD with the per-family breakdown and demote
    "CLEAN" to an internal note (owner directive §3). HEADLINE replaced the
    prose ``_derive_status_sentence`` with ``_render_verdict_headline``, which
    DERIVES the headline from the coverage matrices rolled up across all reports
    (never a hardcoded literal), so this asserts the derived breakdown.

    Uses real reports (the composed site + the four details) so the aggregate is
    the true document-level roll-up, not a stub."""
    from detailgen.validation.coverage import INVARIANT_FAMILIES

    status = report_mod._render_verdict_headline(
        coverage_context.detail_reports,
        coverage_context.site_report,
    )

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
