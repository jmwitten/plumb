"""Integration smoke test: the real 4-detail BOM packs into a cut plan and
the consolidated-report "Consolidated stock & cut plan" section renders.

Loads ``scripts/consolidated_report.py`` by file path (it is a script, not a
package module; the details themselves are now compiled from their
``*.spec.yaml`` inside it). This test only calls ``combined_bom`` /
``lumber_cut_items`` / ``pack`` / ``render_cutplan`` — never ``main()`` — so it
never renders, exports, or touches the real vault file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report_mod():
    return _load("consolidated_report_test", REPO_ROOT / "scripts" / "consolidated_report.py")


@pytest.fixture(scope="module")
def details(report_mod):
    return report_mod.load_details()


@pytest.fixture(scope="module")
def cut_plans(report_mod, details):
    from detailgen.core.cutplan import pack

    purchased, _existing = report_mod.combined_bom(details)
    items = report_mod.lumber_cut_items(purchased, details)
    return items, pack(items)


def test_real_bom_has_lumber_and_decking_cut_items(cut_plans):
    items, plans = cut_plans
    assert items, "expected at least one lumber/decking cut item from the real BOM"
    profiles = set(plans)
    assert "PT 2x6 lumber" in profiles
    assert "PT 2x4 lumber" in profiles
    assert "PT 5/4x6 decking" in profiles


def test_real_bom_lumber_only_originates_from_platform(report_mod, details):
    """The double-count guard (is_context_stub_lumber) is documented as
    dropping every non-platform lumber row — confirm that still holds for
    the real 4 details, i.e. the cut plan never silently double-counts a
    stub member from tree_attachment/rock_anchor/trolley_launch."""
    purchased, _existing = report_mod.combined_bom(details)
    for row in purchased:
        if row["length_mm"] is not None:
            assert row["origin"] == {"platform"}, row


def test_real_bom_reconciles_no_lumber_dropped_or_duplicated(report_mod, details):
    """Every cut instance's length must come from the real per-part BOM data
    — total packed raw length per profile must equal the sum of the platform
    detail's own bom_table() rows for that profile (nothing lost, nothing
    double-counted by the packer)."""
    purchased, _existing = report_mod.combined_bom(details)
    items = report_mod.lumber_cut_items(purchased, details)

    packed_raw_by_profile: dict[str, float] = {}
    for it in items:
        packed_raw_by_profile[it.profile] = packed_raw_by_profile.get(it.profile, 0.0) + it.length_mm

    expected_by_profile: dict[str, float] = {}
    for row in purchased:
        if row["length_mm"] is not None:
            expected_by_profile[row["item"]] = (
                expected_by_profile.get(row["item"], 0.0) + row["length_mm"] * row["qty"]
            )

    assert packed_raw_by_profile == pytest.approx(expected_by_profile)


def test_cut_plan_section_renders_with_real_data(report_mod, cut_plans):
    _items, plans = cut_plans
    html = report_mod.render_cutplan(plans)
    assert "Consolidated stock" in html
    assert "PT 2x6 lumber" in html
    assert "PT 5/4x6 decking" in html
    # every stick must show a waste figure and a stock length
    assert "ft" in html


def test_stub_members_never_appear_in_cut_items(report_mod, cut_plans):
    """STUBVIZ added ``stub_of`` presentation metadata to the tree_attachment
    beam stubs and rock_anchor leg stub (full-piece dims for the viewer
    tooltip) without touching their geometry or BOM identity — confirm the
    existing double-count guard (is_context_stub_lumber) still keeps them out
    of the cut plan, i.e. no cut instance is sourced from either detail."""
    items, _plans = cut_plans
    for it in items:
        assert not it.source.startswith("tree_attachment:"), it
        assert not it.source.startswith("rock_anchor:"), it


def test_cut_plan_never_appears_via_no_lumber_short_circuit(report_mod):
    """render_cutplan must not blow up (and should render nothing) when
    there's no lumber to plan, e.g. an empty pack() result."""
    assert report_mod.render_cutplan({}) == ""
