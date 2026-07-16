"""ARCH0 — the baseline mechanism guards itself.

These tests prove the committed baselines are (a) DETERMINISTIC and CURRENT — a
fresh regeneration reproduces them byte-for-byte, so the committed state really
is today's model truth — and (b) LOAD-BEARING — a tampered baseline is caught
loudly and named. Plus the annotation discipline: every pinned site-divergence
finding carries a real justification note (no ``TODO-JUSTIFY`` placeholder can be
committed).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import baseline_lib as bl

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import regen_baselines as regen  # noqa: E402

COMMITTED = sorted(p.name for p in bl.BASELINE_DIR.glob("*.json"))


def test_all_surfaces_are_committed():
    expected = sorted(f"{n}.json" for n in
                      list(bl.SIMPLE_SURFACES) + ["site_divergence"])
    assert COMMITTED == expected


@pytest.mark.platform_integration
def test_regen_round_trip_reproduces_committed_baselines(tmp_path):
    """Regenerating reproduces the committed baselines byte-for-byte. Proves
    determinism AND that the committed state is current (no baseline drifted from
    the live model). Notes are read from the committed dir, so the annotated
    surface round-trips too."""
    regen.regenerate(tmp_path, source_dir=bl.BASELINE_DIR)
    stale = regen.stale_baseline_names(tmp_path, bl.BASELINE_DIR)
    assert stale == (), (
        f"STALE baselines {list(stale)} — the live model diverged from the "
        f"committed baseline; {bl.REGEN_HINT}")


def test_missing_baseline_teaches_the_regen_command(tmp_path, monkeypatch):
    monkeypatch.setattr(bl, "BASELINE_DIR", tmp_path)  # empty dir
    with pytest.raises(AssertionError) as e:
        bl.load_baseline("detail_counts")
    assert "regen_baselines" in str(e.value)


def test_every_pinned_finding_carries_a_real_note():
    """The annotation channel is enforced: every pinned site-divergence finding
    has a non-empty justification and none is the regen placeholder — an
    un-annotated finding cannot be committed. STRUCT task #19 resolved the last
    pins BY DESIGN, so the set is currently EMPTY (the site validates clean); the
    guard holds vacuously today and re-arms the moment any finding is pinned."""
    findings = bl.load_baseline("site_divergence")["findings"]
    for f in findings:
        note = f.get("note", "")
        assert note and note != regen.TODO_NOTE, (
            f"pinned finding {f['check']}/{f['subject']} needs a justification note")
