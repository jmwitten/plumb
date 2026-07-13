"""Findings-store loader: strict, teaching errors, and load/dump/load round-trip."""

from __future__ import annotations

import pytest

from detailgen.review.store import (
    STORE_VERSION,
    dump_findings_text,
    load_findings_text,
)
from detailgen.review.finding import ReviewSchemaError

_ONE = """
version: 1
findings:
  - id: F1
    subject: platform support at grade
    suspected_issue: the tree end has no leg to grade
    severity: CRITICAL
    visual_evidence: platform_front.png shows open air under the tree end
    renders:
      - path: outputs/consolidated/renders/platform/platform_front.png
    invariant_family: Load-path representation
    recommended_action: confirm the support invariant flags this
    resolution:
      status: unresolved
"""


def test_loads_a_valid_store():
    s = load_findings_text(_ONE)
    assert s.version == STORE_VERSION
    assert len(s.findings) == 1
    assert s.findings[0].id == "F1"


def test_empty_findings_list_is_legal():
    s = load_findings_text("version: 1\nfindings: []\n")
    assert s.findings == ()


def test_unknown_top_level_key_teaching_error():
    with pytest.raises(ReviewSchemaError) as e:
        load_findings_text("version: 1\nfindings: []\nfinding: []\n")
    assert "did you mean" in str(e.value).lower()


def test_unknown_finding_key_teaching_error():
    bad = _ONE.replace("    subject:", "    subjekt:\n    subject:", 1)
    with pytest.raises(ReviewSchemaError) as e:
        load_findings_text(bad)
    assert "subjekt" in str(e.value)
    assert "did you mean" in str(e.value).lower()


def test_missing_required_finding_key_names_the_field():
    bad = _ONE.replace("    severity: CRITICAL\n", "")
    with pytest.raises(ReviewSchemaError) as e:
        load_findings_text(bad)
    assert "severity" in str(e.value)


def test_wrong_version_is_rejected_not_best_effort():
    with pytest.raises(ReviewSchemaError) as e:
        load_findings_text("version: 2\nfindings: []\n")
    assert "version" in str(e.value).lower()


def test_duplicate_ids_rejected():
    two = _ONE + _ONE.split("findings:")[1]  # duplicate the same F1 block
    with pytest.raises(ReviewSchemaError) as e:
        load_findings_text(two)
    assert "duplicate" in str(e.value).lower()


def test_empty_document_teaching_error():
    with pytest.raises(ReviewSchemaError):
        load_findings_text("")


def test_render_ref_missing_path_is_teaching_error():
    bad = _ONE.replace("      - path: outputs/consolidated/renders/platform/platform_front.png",
                       "      - content_hash: abc123")
    with pytest.raises(ReviewSchemaError) as e:
        load_findings_text(bad)
    assert "path" in str(e.value)


def test_dismissed_without_evidence_rejected_at_load():
    bad = _ONE.replace("      status: unresolved",
                       "      status: dismissed-false-positive")
    with pytest.raises(ReviewSchemaError) as e:
        load_findings_text(bad)
    assert "evidence" in str(e.value).lower()


def test_fixed_by_revision_status_loads_and_round_trips():
    # the design-change resolution state loads through the strict loader like any
    # other resolved state (it carries the required note) and survives dump->load.
    text = _ONE.replace(
        "      status: unresolved",
        "      status: fixed-by-revision\n"
        "      note: fixed by the cleat revision (sdd/cleat) — show-face screws deleted")
    s = load_findings_text(text)
    assert s.findings[0].resolution.status == "fixed-by-revision"
    assert not s.findings[0].is_open
    assert load_findings_text(dump_findings_text(s)).findings == s.findings


def test_round_trip_load_dump_load():
    s = load_findings_text(_ONE)
    s2 = load_findings_text(dump_findings_text(s))
    assert s.findings == s2.findings
    assert s.version == s2.version


def test_dump_preserves_content_hash_when_present():
    with_hash = _ONE.replace(
        "      - path: outputs/consolidated/renders/platform/platform_front.png",
        "      - path: outputs/consolidated/renders/platform/platform_front.png\n"
        "        content_hash: deadbeef")
    s = load_findings_text(with_hash)
    assert s.findings[0].renders[0].content_hash == "deadbeef"
    s2 = load_findings_text(dump_findings_text(s))
    assert s2.findings[0].renders[0].content_hash == "deadbeef"
