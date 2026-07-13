"""SM2 — the consolidated report's site-overview section is driven by the ONE
compiled site model (replacing the _site_overview.py composition).

Loads ``scripts/consolidated_report.py`` by file path (same pattern as
``test_site_overview.py`` / ``test_consolidated_coverage.py``) and exercises
``render_site_model_section`` directly — no ``main()``, so nothing renders/
exports or touches the vault. STRUCT task #19 resolved the last pins by design,
so the site is now CLEAN: the section's PRIMARY tested path is the gate-OPEN
render note plus the findings-driven divergence table deriving its EMPTY state
(no hardcoded "resolved" caveat) — the flip of the former gate-blocked path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import baseline_lib as bl
from detailgen.validation.coverage import STANDING_NOTE

REPO = Path(__file__).resolve().parents[1]


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report_mod():
    return _load("consolidated_report_sm2", REPO / "scripts" / "consolidated_report.py")


@pytest.fixture(scope="module")
def site(report_mod):
    s = report_mod.load_site()
    s.validate()
    return s


@pytest.fixture(scope="module")
def section(report_mod, site):
    # The model-driven section. render_site_model_section now takes the site's
    # validation report as a second arg (docrebuild): the caller validates ONCE
    # from exact geometry before the lossy web-GLB export, and the section renders
    # that verdict instead of re-validating possibly-mutated solids. The fixture's
    # ``site.report`` is that clean pre-export verdict.
    return report_mod.render_site_model_section(site, site.report)


def test_section_is_driven_by_the_one_model(section):
    assert "ONE compiled site model" in section
    assert "details/site.spec.yaml" in section
    assert "one node" in section  # the shared-member single-node claim


def test_render_gate_is_closed_by_foundation_capacity(section):
    # FAB-3 (retire R29): the site is blocked by the three foundation-capacity
    # UNKNOWNs, so the composed render is GATED — the section shows the BLOCKED
    # note (SYSTEM-derived), not the gate-open "validates CLEAN" note. The gate
    # working is the point: an undesigned foundation cannot render clean.
    assert "Composed render BLOCKED" in section
    assert "validates CLEAN" not in section
    assert "site-level gate" in section


def test_blocked_section_lists_the_open_capacity_findings(section, site):
    import html

    # The site is NOT clean: no FAIL (every blocker is an honest UNKNOWN),
    # but four blocking findings the section must surface by name — the
    # three foundation-capacity UNKNOWNs (FAB-3) plus the ONE remaining
    # install UNKNOWN (rock-anchor rod 1 under the platform's lowest ladder
    # rung, a composed-only truth: cross-fragment order + insertion travel,
    # both named — the platform's two toe screws resolved on merit, task
    # CPGCORE).
    assert site.report.failures == []
    assert {f.check for f in site.report.blocking} == {
        "foundation_capacity", "install_access"}
    assert len(site.report.blocking) == 4
    assert "no open divergence" not in section
    for f in site.report.blocking:
        assert html.escape(f.subject) in section


def test_placement_table_from_site_facts(section):
    # placement/provenance table carries the declared confidences
    assert "Subsystem" in section and "Confidence" in section
    assert "EXACT" in section and "ASSUMED" in section
    assert "platform" in section and "rock_anchor" in section


def test_coverage_matrix_is_the_sites_own(section):
    assert "Whole site" in section
    assert STANDING_NOTE in section
    assert "NOT ANALYZED" in section


def test_divergence_section_is_findings_driven(section, site):
    assert "Divergence findings" in section
    assert "SYSTEM-derived" in section
    # The table is findings-driven, NOT a hand-written caveat: FAB-3's blocking
    # foundation-capacity UNKNOWNs derive real rows (never a hardcoded note),
    # each naming the foundation whose capacity is unresolved.
    assert site.report.failures == []
    assert "no open divergence" not in section
    assert "foundation_capacity" in section


def test_section_never_claims_safety(section):
    lowered = section.lower()
    assert "is safe" not in lowered
    # "proven safe" appears ONLY inside the standing note's negation
    # ("REPRESENTED, not proven safe") — never as an affirmative claim.
    assert "not proven safe" in lowered
    assert lowered.count("proven safe") == lowered.count("not proven safe")


def test_divergence_table_is_findings_driven_capacity_unknowns(report_mod, site):
    """The divergence/open-findings table is findings-driven (no hand-written
    caveat). STRUCT #19 resolved the LAST cross-subsystem divergences by design;
    FAB-3 then made the site block on the three foundation-capacity UNKNOWNs, so
    the table now DERIVES a row per capacity UNKNOWN (never a hardcoded note). The
    grab-bar divergence in particular is still GONE. render_site_model_section
    still takes no ``details`` argument."""
    section = report_mod.render_site_model_section(site, site.report)
    # no hand-written / pending caveat survives
    assert "hand-written, pending" not in section
    assert "pending tree" not in section
    # the resolved tree divergence no longer appears
    assert "beam inner face tangent at trunk radius" not in section
    # the table derives real rows from the blocking findings (site not clean)
    assert site.report.failures == []
    assert "no open divergence" not in section
    assert "foundation_capacity" in section
    # the details parameter is gone
    import inspect
    assert "details" not in inspect.signature(
        report_mod.render_site_model_section).parameters


def test_section_renders_the_passed_report_and_never_re_validates(report_mod, site):
    """Ordering guard (docrebuild): the section must render the verdict it is
    HANDED — the caller's exact-geometry report, taken before the lossy web-GLB
    export re-tessellates the shared solids — and must never re-derive it. Guarding
    the ordering, not just the signature: if the render path re-validated, a
    post-export bounding-box wobble (trunk 20.06" vs exact 20.00") would leak a
    spurious dimension finding into the shipped document.

    Two teeth:
    1. The render path contains no ``.validate()`` call, so it structurally CANNOT
       recompute the verdict — whatever it shows came from the passed report.
    2. Behaviourally, the section is a pure function of its ``report`` argument:
       handed a report whose finding carries a sentinel subject, it renders the
       sentinel; handed the clean report, it does not — proving it mirrors the
       argument, not a fresh ``site.validate()``."""
    import copy
    import inspect

    src = inspect.getsource(report_mod.render_site_model_section)
    assert ".validate()" not in src, (
        "render_site_model_section re-validates instead of rendering the passed "
        "(pre-export, exact-geometry) report — the ordering guarantee is broken")

    clean = site.report
    assert "sentinel-divergence" not in report_mod.render_site_model_section(site, clean)

    # A deep-copied report (isolated from the module-scoped site.report) with a
    # synthetic FAIL finding appended must render that sentinel — the section
    # reflects its ``report`` argument, never re-derives from ``site``. STRUCT: the
    # real site is clean, so the sentinel is ADDED (the old test mutated the
    # subject of a pinned failure that no longer exists) — same guarantee, and it
    # additionally proves the section renders a divergence when the report holds one.
    from detailgen.validation.checks import Finding
    doctored = copy.deepcopy(clean)
    doctored.add(Finding("bearing", "sentinel-divergence marker", False,
                         "synthetic finding for the render-not-revalidate guard"))
    section = report_mod.render_site_model_section(site, doctored)
    assert "sentinel-divergence marker" in section
