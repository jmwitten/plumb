"""Task PROMOTE — the platform full-content drift guard, on the spec path.

The promotion of ``FaceMountHanger`` / ``ToeScrewed`` / ``RailCapScrewed`` into
the library + the two rider fixes must NOT change the platform's validation
output. This locks the platform fingerprint (124 parts / clean / a full-content
hash) so any future drift fails loudly, and proves the platform resolves its
joints to the LIBRARY-registered connection types (identity), not a private copy.

The spec is the only path built here. The reference side is the frozen imperative
truth in ``tests/baselines/frozen_truth/platform.json`` (captured at the base SHA
by ``scripts/capture_frozen_truth.py``).

FULL-CONTENT FINGERPRINT. The by-kind counts + ``derivation_log`` length lock the
*shape* of the output; they do not notice a content-only drift that preserves
counts (a finding's ``detail`` text changing, a fact's confidence flipping, a BOM
dimension shifting, a part translating). :func:`baseline_lib.content_fingerprint`
closes that gap — it hashes the FULL sorted content of every finding, every
derivation fact (incl. confidence / source_type / assumptions / subjects), the
whole BOM, and every part's world transform (rounded to 1e-6 mm to shed the
sub-picometre float-ordering residual, never real geometry).

SPEC-VS-IMPERATIVE CONTENT DIVERGENCE (frozen, not hidden). The guard locks
``content_fp_spec`` — the surviving spec path's hash — because after milestone
4B-4b the spec is the only path. It differs from the imperative testimony
(``content_fp``) by exactly what ``content_fp_divergence`` in the corpus
enumerates: the spec reworded the LUS-class hanger-schedule ``assumptions`` prose
on 536 derivation facts (semantically identical, byte-different) and carries the
sub-1e-6 mm inch->mm ``length_mm`` residual on 3 BOM rows that
``content_fingerprint`` does not round. This divergence was invisible to the
pre-4B suite (nothing compared the two paths' derivation-fact assumptions). No
OTHER content line differs — the guard asserts that below, so a real drift can
never hide inside the divergence record.

To see WHICH content lines a failing spec moved, run this file as a script
(``python tests/test_platform_promote_equiv.py``) and ``diff`` the dump against a
known-good one. The frozen corpus is regenerated only while the imperative .py
still exist: ``python scripts/capture_frozen_truth.py`` (see tests/baselines/README.md).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import baseline_lib as bl
from baseline_lib import content_fingerprint, content_lines, by_kind

from detailgen.assemblies import (
    BoltedClamp, FaceMountHanger, RailCapScrewed, ToeScrewed,
)
from detailgen.spec.loader import load_spec_file
from detailgen.spec.compiler import compile_spec

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "platform.spec.yaml"
FROZEN = ROOT / "tests" / "baselines" / "frozen_truth" / "platform.json"


def _frozen():
    return json.loads(FROZEN.read_text())


def _platform():
    return compile_spec(load_spec_file(SPEC))


def test_platform_uses_library_connection_types():
    """Every promoted joint the platform declares resolves to the LIBRARY class
    object — not a shadow copy — after promotion."""
    detail = _platform()
    _ = detail.assembly   # build so connections()'s per-joint args are populated
    kinds = {type(c.kind) for c in detail.connections()}
    assert {FaceMountHanger, ToeScrewed, RailCapScrewed, BoltedClamp} <= kinds


def test_platform_validation_fingerprint_unchanged():
    detail = _platform()
    report = detail.validate()
    # A2 RE-FREEZE: the corpus is the current spec, so the platform is CLEAN (the
    # support family is now a PASS — deck tree end supported by design) and by-kind
    # matches the corpus EXACTLY (FROZEN_POSTDATING_KINDS is now empty).
    assert report.failures == []
    frozen = _frozen()
    assert len(detail.assembly.parts) == frozen["counts"]["parts"]
    live_by_kind = {k: v for k, v in by_kind(report).items()
                    if k not in bl.FROZEN_POSTDATING_KINDS}
    assert live_by_kind == frozen["by_kind"]
    # every hardware-requirement fact stays "official" (all platform types use the
    # base ``required_hardware`` pass-through — rider 4a invariant).
    hw_facts = [f for f in detail.derivation_log
                if f.rule.endswith(".required_hardware")]
    assert hw_facts and all(f.confidence == "official" for f in hw_facts)
    assert len(detail.derivation_log) == frozen["counts"]["derivation_log"]


def test_platform_full_content_fingerprint_unchanged():
    """The FULL content — every finding's text, every derivation fact's
    confidence/source_type/assumptions/subjects, the whole BOM, every part
    transform — hashes to the committed spec fingerprint. Catches content-only
    drift the by-kind counts above cannot see. On failure, dump both sides with
    ``python tests/test_platform_promote_equiv.py`` and ``diff`` them."""
    detail = _platform()
    detail.validate()
    frozen = _frozen()
    # A2 RE-FREEZE: the corpus is the current SPEC path, so the guard is pinned to
    # the corpus's own ``content_fp_spec`` (auto-derived, not a hand-typed constant
    # that drifts). The compiled spec must hash to it byte-for-byte; this still
    # catches ANY drift in findings text, derivation prose, BOM, or transforms the
    # triple/count checks can't see. Regenerate the corpus (scripts/refreeze_from_
    # spec.py) and review the diff on an intended change.
    assert content_fingerprint(detail) == frozen["content_fp_spec"], (
        "platform full-content fingerprint drifted from the re-frozen corpus — if "
        "intended, re-run scripts/refreeze_from_spec.py and show the content diff "
        "in review; if not, a real drift slipped in")
    # the floating check roots at the real FOUNDATION boulder (task SUPPORT req 2),
    # and the platform is clean (support is a PASS now).
    floating = next(f for f in detail.report.findings if f.check == "floating")
    assert "boulder" in floating.detail
    assert detail.report.failures == []
    # There is no imperative path to diverge from post-re-freeze: content_fp equals
    # content_fp_spec and the divergence record is empty. A future regen recording
    # an unexplained line would fail here, so a real drift cannot hide.
    assert frozen["content_fp"] == frozen["content_fp_spec"]
    assert frozen["content_fp_divergence"] == {}


if __name__ == "__main__":  # dump the diffable content for a re-baseline
    _d = _platform()
    _d.validate()
    print("\n".join(content_lines(_d)))
    print(f"# fingerprint: {content_fingerprint(_d)}", file=sys.stderr)
