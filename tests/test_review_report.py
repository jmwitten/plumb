"""Reconciliation (staleness + never-reviewed) and the visual-review status
block. The block must read as a smell test and never claim to carry a verdict."""

from __future__ import annotations

from detailgen.review.finding import RenderRef, Resolution, VisualReviewFinding
from detailgen.review.manifest import RenderEntry, ReviewManifest
from detailgen.review.report import (
    CURRENT,
    RENDER_MISSING,
    STALE,
    UNVERIFIED,
    STANDING_NOTE,
    reconcile,
    render_visual_review_block_html,
    render_visual_review_block_md,
)
from detailgen.review.store import FindingStore


def _finding(fid, refs, **over):
    base = dict(
        id=fid, subject="s", suspected_issue="i", severity="LOW",
        visual_evidence="v", invariant_family="UNKNOWN",
        recommended_action="a", renders=tuple(refs),
    )
    base.update(over)
    return VisualReviewFinding(**base)


def _store(*findings):
    return FindingStore(version=1, findings=tuple(findings))


def _manifest(*pairs):
    return ReviewManifest(renders=tuple(
        RenderEntry(path=p, content_hash=h, detail="d", view="v") for p, h in pairs))


def test_ref_states_current_stale_missing_unverified():
    store = _store(
        _finding("A", [RenderRef("r/current.png", content_hash="h1")]),
        _finding("B", [RenderRef("r/stale.png", content_hash="OLD")]),
        _finding("C", [RenderRef("r/gone.png", content_hash="h3")]),
        _finding("D", [RenderRef("r/nohash.png")]),  # no captured hash
    )
    man = _manifest(
        ("r/current.png", "h1"),
        ("r/stale.png", "NEW"),
        ("r/nohash.png", "h4"),
        ("r/never.png", "h5"),   # in the build, referenced by no finding
    )
    rec = reconcile(store, man)
    states = {r.finding_id: r.state for r in rec.ref_states}
    assert states["A"] == CURRENT
    assert states["B"] == STALE
    assert states["C"] == RENDER_MISSING
    assert states["D"] == UNVERIFIED
    assert [e.path for e in rec.never_reviewed] == ["r/never.png"]


def test_no_manifest_means_unverified_not_all_clear():
    store = _store(_finding("A", [RenderRef("r/x.png", content_hash="h1")]))
    rec = reconcile(store, None)
    assert not rec.has_manifest
    assert rec.ref_states[0].state == UNVERIFIED
    assert rec.never_reviewed == ()


def test_md_block_carries_smell_test_wording_and_unresolved_count():
    store = _store(
        _finding("A", [RenderRef("r/x.png")], severity="CRITICAL"),
        _finding("B", [RenderRef("r/y.png")],
                 resolution=Resolution("covered-by-existing-invariant",
                                       note="the interference check flags it")),
    )
    md = render_visual_review_block_md(store)
    assert STANDING_NOTE in md
    assert "1 unresolved" in md            # A is open, B is resolved
    assert "suspicion" in md.lower() or "smell test" in md.lower()
    assert "CRITICAL" in md
    # never substitutes for the invariant verdict — says so explicitly
    assert "coverage matrix" in md.lower()


def test_html_block_marks_open_vs_resolved_and_severity():
    store = _store(
        _finding("A", [RenderRef("r/x.png")], severity="CRITICAL"),
        _finding("B", [RenderRef("r/y.png")],
                 resolution=Resolution("dismissed-false-positive",
                                       note="measured clearance is intended")),
    )
    html = render_visual_review_block_html(store)
    assert "vr-open" in html and "vr-resolved" in html
    assert "vr-crit" in html
    assert STANDING_NOTE in html


def test_fixed_by_revision_renders_distinctly_from_a_plain_resolved_state():
    # a fixed-by-revision finding must READ as fixed, not as a mere accepted
    # assumption: the HTML cell gets its own class (vr-fixed, not vr-resolved) and
    # both surfaces print the state name.
    store = _store(
        _finding("A", [RenderRef("r/a.png")],
                 resolution=Resolution("fixed-by-revision",
                                       note="fixed by the cleat revision — show-face screws deleted")),
        _finding("B", [RenderRef("r/b.png")],
                 resolution=Resolution("documented-assumption-or-unknown",
                                       note="accepted as intended")),
    )
    html = render_visual_review_block_html(store)
    assert "vr-fixed" in html                       # the fixed row is styled distinctly
    assert "fixed-by-revision" in html
    md = render_visual_review_block_md(store)
    assert "fixed-by-revision: 1" in md             # counted in the resolution rollup
    assert "0 unresolved" in md                     # both are resolved


def test_freshness_section_reports_manifest_rollups():
    store = _store(_finding("A", [RenderRef("r/x.png", content_hash="OLD")]))
    man = _manifest(("r/x.png", "NEW"), ("r/never.png", "h"))
    md = render_visual_review_block_md(store, man)
    assert "1 render(s) never reviewed" in md
    assert "STALE" in md
