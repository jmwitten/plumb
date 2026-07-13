"""The committed ZIPLINE store (reviews/visual/zipline-findings.yaml) loads
faithfully: the 6 interim smell-test findings, with the expected
severities/families. STRUCT task #19 RESOLVED all six (the resolution VISREV
deferred to STRUCT), each with its enforced 4-outcome status + evidence, so they
now load resolved, not open.

This golden pins the ZIPLINE's store SPECIFICALLY, resolved off the per-detail
enumeration surface by name (task VISREVSTORES) — so it bites the zipline's F1-F6
exactly while placing no constraint on any OTHER detail's store."""

from __future__ import annotations

from pathlib import Path

from detailgen.review import find_detail_store
from detailgen.review.store import dump_findings_text, load_findings_file, load_findings_text

ROOT = Path(__file__).resolve().parents[1]
SEED = find_detail_store(ROOT / "reviews" / "visual", "zipline", "visual")


def test_seed_loads_six_findings_all_resolved_by_struct():
    store = load_findings_file(SEED)
    assert [f.id for f in store.findings] == ["F1", "F2", "F3", "F4", "F5", "F6"]
    # STRUCT task #19 resolved every finding (the transition VISREV deferred to it),
    # so none remain open. Each carries a non-'unresolved' status with evidence,
    # which the strict loader enforces.
    assert len(store.open_findings()) == 0
    assert all(not f.is_open for f in store.findings)


def test_seed_severities_and_families():
    by_id = load_findings_file(SEED).by_id()
    assert by_id["F1"].severity == "CRITICAL"
    assert by_id["F1"].invariant_family == "Load-path representation"
    # the two illustrative/context findings are honest UNKNOWN (candidates for a
    # new family), not forced into an ill-fitting one.
    assert by_id["F3"].invariant_family == "UNKNOWN"
    assert by_id["F4"].invariant_family == "UNKNOWN"
    assert by_id["F6"].invariant_family == "Code compliance"


def test_seed_critical_is_resolved_by_struct_via_the_support_invariant():
    f1 = load_findings_file(SEED).by_id()["F1"]
    assert "struct" in f1.notes.lower()   # records the resolving context
    # F1 (missing rear support) is now CLOSED by an existing compiler invariant:
    # the SUPPORT check passes via the tree-end legs + declared cantilever.
    assert not f1.is_open
    assert f1.resolution.status == "covered-by-existing-invariant"


def test_seed_render_refs_have_no_captured_hash():
    # the interim run predated the manifest; staleness is honestly unverifiable
    # until a reviewer re-reviews against a live manifest.
    for f in load_findings_file(SEED).findings:
        for r in f.renders:
            assert r.content_hash is None


def test_seed_round_trips():
    store = load_findings_file(SEED)
    assert load_findings_text(dump_findings_text(store)).findings == store.findings
