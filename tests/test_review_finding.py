"""VisualReviewFinding model: always-valid construction + the resolution-workflow
enforcement (the four outcomes, the legal persistent `unresolved`, and the
dismissed-false-positive-requires-evidence teaching error)."""

from __future__ import annotations

import pytest

from detailgen.review.finding import (
    FIXED_BY_REVISION,
    RESOLUTION_STATES,
    SEVERITIES,
    UNKNOWN_FAMILY,
    UNRESOLVED,
    RenderRef,
    Resolution,
    ReviewSchemaError,
    VisualReviewFinding,
    known_invariant_families,
)


def _finding(**over):
    base = dict(
        id="F1",
        subject="platform support at grade",
        suspected_issue="the tree end has no leg to grade",
        severity="CRITICAL",
        visual_evidence="platform_front.png shows open air under the tree end",
        renders=(RenderRef("outputs/consolidated/renders/platform/platform_front.png"),),
        invariant_family="Load-path representation",
        recommended_action="confirm the support invariant flags this",
    )
    base.update(over)
    return VisualReviewFinding(**base)


def test_minimal_valid_finding_is_open_by_default():
    f = _finding()
    assert f.is_open
    assert f.resolution.status == UNRESOLVED


def test_family_validated_against_live_validation_families():
    # every known family is accepted...
    for fam in known_invariant_families():
        _finding(invariant_family=fam)
    # ...and the explicit UNKNOWN sentinel (the discovery case) is legal.
    assert _finding(invariant_family=UNKNOWN_FAMILY).invariant_family == UNKNOWN_FAMILY


def test_unknown_family_is_a_teaching_error_with_did_you_mean():
    with pytest.raises(ReviewSchemaError) as e:
        _finding(invariant_family="Load path representation")  # spaces, not hyphen-exact
    msg = str(e.value)
    assert "Load-path representation" in msg  # did-you-mean names the real family
    assert UNKNOWN_FAMILY in msg              # and points at the honest escape hatch


def test_unknown_severity_rejected():
    with pytest.raises(ReviewSchemaError) as e:
        _finding(severity="SEVERE")
    assert "CRITICAL" in str(e.value)


def test_required_text_fields_must_be_nonempty():
    for empty in ("", "   "):
        with pytest.raises(ReviewSchemaError):
            _finding(subject=empty)
        with pytest.raises(ReviewSchemaError):
            _finding(suspected_issue=empty)


def test_at_least_one_render_required():
    with pytest.raises(ReviewSchemaError):
        _finding(renders=())


@pytest.mark.parametrize("status", [s for s in RESOLUTION_STATES if s != UNRESOLVED])
def test_every_resolved_state_requires_a_note(status):
    with pytest.raises(ReviewSchemaError):
        Resolution(status=status, note="")


def test_dismissed_false_positive_without_evidence_is_the_sharpest_error():
    with pytest.raises(ReviewSchemaError) as e:
        Resolution(status="dismissed-false-positive", note="")
    msg = str(e.value)
    assert "evidence" in msg.lower()
    # the message must teach that assertion alone is not enough
    assert "assertion" in msg.lower() or "not a real issue" in msg.lower()


def test_dismissed_false_positive_with_evidence_is_accepted():
    r = Resolution(status="dismissed-false-positive",
                   note="dimension check proves the beam bears; the gap is the intended growth gap")
    assert not r.is_open


def test_unknown_resolution_status_teaching_error():
    with pytest.raises(ReviewSchemaError) as e:
        Resolution(status="wontfix")
    assert UNRESOLVED in str(e.value)


def test_fixed_by_revision_is_a_legal_resolved_state():
    # the design-change outcome: a REAL defect removed by a spec revision. It is a
    # resolved (not-open) state in the vocabulary, and — like every resolved state —
    # its note is required (here: cite the revision that fixed it).
    assert FIXED_BY_REVISION in RESOLUTION_STATES
    r = Resolution(status=FIXED_BY_REVISION,
                   note="fixed by the cleat revision (sdd/cleat) — cleat_screwed hides the fasteners")
    assert not r.is_open
    f = _finding().resolved_as(FIXED_BY_REVISION,
                               note="fixed by the cleat revision — show-face screws deleted")
    assert not f.is_open and f.resolution.status == FIXED_BY_REVISION
    # it is NOT the dismissal state — no special evidence rule, just the standard
    # note requirement (an empty note is the plain resolved-state teaching error).
    with pytest.raises(ReviewSchemaError):
        Resolution(status=FIXED_BY_REVISION, note="")


def test_resolved_as_returns_new_immutable_finding():
    f = _finding()
    g = f.resolved_as("new-formal-invariant", note="the SUPPORT invariant now flags it")
    assert f.is_open and not g.is_open
    assert g.resolution.status == "new-formal-invariant"
    assert f is not g


def test_render_ref_rejects_empty_path_and_blank_hash():
    with pytest.raises(ReviewSchemaError):
        RenderRef("")
    with pytest.raises(ReviewSchemaError):
        RenderRef("a/b.png", content_hash="   ")
    # omitted hash is legal (unverifiable staleness, reported honestly)
    assert RenderRef("a/b.png").content_hash is None


def test_notes_are_context_not_resolution():
    # a KNOWN/in-fix note does NOT close the finding — it stays open work.
    f = _finding(notes="KNOWN — in-fix on sdd/struct")
    assert f.is_open
