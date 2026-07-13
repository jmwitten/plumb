"""View-coverage guards for the consolidated build document (view-coverage-directive).

The directive requires each doc build to give every high-install-complexity,
low-visibility area its own zoomed view. This build's decision table added two
views that the prior build lacked, and these guards pin them so a later edit
can't silently drop the coverage:

  1. the platform panel carries a ``top`` (plan) view — the only view that shows
     the six deck-board trunk notches, the flagship fabrication feature; and
  2. Panel E zooms the three precast-pier foundations and is the plain-language
     home of the site's blocking ``foundation_capacity`` UNKNOWNs — so it must read
     "Structural capacity: UNKNOWN — UNRESOLVED" loudly and DERIVE the finding count
     from the live site report, never hardcode it.

Fast + render-free: the pier section is exercised with stubbed images (the section
prose/verdict is what these guard), and the view-assembly selection is checked
against the compiled platform parts without exporting a PNG.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import consolidated_report as cr  # noqa: E402
from detailgen.spec.compiler import compile_spec_file  # noqa: E402


class _FakeReport:
    """A site report with a controllable blocking-finding count, so the section's
    count is proven DERIVED from the report rather than a literal."""

    def __init__(self, n_blocking: int):
        self.blocking = list(range(n_blocking))


def test_platform_panel_carries_the_top_deck_notch_view():
    """The deck-notch plan view is the only view that shows the six notched boards;
    it must stay in the platform panel's view set with a notch-naming caption."""
    views = cr.PANELS["platform"]["views"]
    assert "top" in views, (
        "platform panel dropped the 'top' plan view — the only view that shows the "
        "six deck-board trunk notches (view-coverage-directive)")
    cap = cr.PANELS["platform"]["captions"]["top"].lower()
    assert "notch" in cap and "deck" in cap, \
        "the platform top-view caption must point the carpenter at the deck notch"


def test_pier_foundation_view_selects_the_three_real_foundation_parts():
    """The zoom is a scoped view of REAL compiled platform parts — leg base, precast
    block and standoff post base — not a synthetic drawing."""
    platform = compile_spec_file(ROOT / "details" / "platform.spec.yaml")
    view = cr._pier_foundation_view_assembly(platform)
    names = {p.name for p in view.parts}
    assert names == set(cr._PIER_FOUNDATION_PARTS)
    # one leg + one pier block + one standoff post base = a legible foundation zoom.
    assert any(n.startswith("leg") for n in names)
    assert any(n.startswith("pier") for n in names)
    assert any("post base" in n for n in names)


def test_pier_foundation_section_reads_blocked_and_derives_the_count():
    """Panel E leads with the loud, honest blocked-capacity verdict and takes its
    finding count from the site report (not a literal), so the number can never
    drift from the model."""
    details = {"platform": None}  # not touched on the stubbed-image path

    for n in (1, 3, 5):
        html = cr.render_pier_foundation_section(details, _FakeReport(n), images=None)
        assert "Structural capacity: UNKNOWN &mdash; UNRESOLVED" in html
        assert "E &middot; Pier Foundations" in html
        # count is derived from len(report.blocking)
        assert f"{n} findings that block" in html, \
            f"section did not derive the finding count {n} from the report"
    # the standoff install and the boulder-anchor cross-reference are both present
    html = cr.render_pier_foundation_section(details, _FakeReport(3), images=None)
    assert "standoff post base" in html.lower()
    assert "boulder" in html.lower() and "Panel C" in html


def test_pier_section_uses_supplied_render_and_falls_back_to_stub():
    """With rendered images it embeds them; without, it uses the strip-safe stub so
    the prose/golden guards stay render-free."""
    details = {"platform": None}
    supplied = {"iso": "data:image/png;base64,REALISO",
                "front": "data:image/png;base64,REALFRONT"}
    html = cr.render_pier_foundation_section(details, _FakeReport(3), images=supplied)
    assert "REALISO" in html and "REALFRONT" in html

    stubbed = cr.render_pier_foundation_section(details, _FakeReport(3), images=None)
    assert cr._STUB_PNG in stubbed
