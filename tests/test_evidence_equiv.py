"""Task EVIDENCE — the validation-outcome drift guard, on the spec path.

The Evidence Graph (the matured derivation log with ``source_type`` / ``subjects``
on every ``DerivedFact``, and the lifecycle capture of the compiled
``ConnectionChecks``) must not move a single validation OUTCOME. This locks that
in with a byte-level fingerprint over the full findings set (check / subject /
passed / detail) on BOTH shipped Connection-bearing details, built from their
compiled specs.

It also proves the graph is a pure READER: building/querying the Evidence Graph
produces an identical report to never building it (no shared mutable state leaks
back into validation).

The reference side is the frozen imperative truth in
``tests/baselines/frozen_truth/{rock_anchor,platform}.json`` — captured at the
base SHA by ``scripts/capture_frozen_truth.py``. The rock anchor's ``load_path``
family (task ONTOLOGY) and the platform's ``symmetric_about`` / ``faces_away``
families (task SPATIAL) are outcome additions already baked into that frozen
truth; the drift guard still has full teeth for every other family.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

import baseline_lib as bl
from detailgen.spec.loader import load_spec_file
from detailgen.spec.compiler import compile_spec

ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = ROOT / "tests" / "baselines" / "frozen_truth"

#: slug -> compiled spec file. The frozen corpus is keyed by the same slug.
_SPECS = {
    "rock_anchor": ROOT / "details" / "rock_anchor.spec.yaml",
    "platform": ROOT / "details" / "platform.spec.yaml",
}


def _frozen(slug):
    return json.loads((FROZEN_DIR / f"{slug}.json").read_text())


def _build(slug):
    return compile_spec(load_spec_file(_SPECS[slug]))


@pytest.mark.parametrize("slug", list(_SPECS))
def test_validation_outcome_byte_identical_to_frozen(slug):
    detail = _build(slug)
    report = detail.validate()
    frozen = _frozen(slug)
    # A2 RE-FREEZE: the corpus is the CURRENT spec path (FROZEN_POSTDATING_KINDS is
    # empty), so the validation OUTCOME matches it EXACTLY — every (check, subject,
    # passed) triple, by-kind, and count. Each evolved detail validates CLEAN.
    assert report.failures == []
    assert len(detail.assembly.parts) == frozen["counts"]["parts"]
    by_kind = {k: v for k, v in Counter(f.check for f in report.findings).items()
               if k not in bl.FROZEN_POSTDATING_KINDS}
    assert by_kind == frozen["by_kind"]
    assert len(detail.derivation_log) == frozen["counts"]["derivation_log"]
    live_triples = Counter((f.check, f.subject, bool(f.passed))
                           for f in report.findings
                           if f.check not in bl.FROZEN_POSTDATING_KINDS)
    assert live_triples == Counter(tuple(t) for t in frozen["findings"]), (
        f"{detail.name}: validation OUTCOME diverged from the re-frozen corpus — "
        f"the compiled details/{slug}.spec.yaml no longer reproduces the baseline")
    # the platform's floating check roots at the real FOUNDATION boulder (SUPPORT
    # req 2), and the support family is a PASS (deck tree end supported by design).
    if slug == "platform":
        assert [f.check for f in report.failures] == []
        floating = next(f for f in report.findings if f.check == "floating")
        assert "boulder" in floating.detail
        assert any(f.check == "support" and f.passed for f in report.findings)


@pytest.mark.parametrize("slug", list(_SPECS))
def test_building_the_graph_does_not_perturb_validation(slug):
    """Building + querying the Evidence Graph is side-effect-free on the
    report — the graph is a reader, not a mutator — and the outcome stays equal
    to the frozen truth throughout."""
    frozen_triples = Counter(tuple(t) for t in _frozen(slug)["findings"])

    plain = _build(slug)
    plain_report = plain.validate()
    # frozen predates task SUPPORT (support family + the req-2 floating-root fix);
    # hold its (check,subject,passed) triple surface equal to frozen, minus support.
    live_triples = Counter((f.check, f.subject, bool(f.passed))
                           for f in plain_report.findings
                           if f.check not in bl.FROZEN_POSTDATING_KINDS)
    assert live_triples == frozen_triples
    # the "graph doesn't perturb" invariant runs on the FULL live surface (incl.
    # support + the detail text), so a perturbation of ANY finding is still caught.
    plain_fp = bl.findings_fingerprint(plain_report)

    withgraph = _build(slug)
    report = withgraph.validate()
    g = withgraph.evidence_graph          # build it
    # exercise the query surface (a query must not mutate the report either)
    part_name = withgraph.assembly.parts[0].name
    g.what_is(part_name)
    g.why_here(part_name)
    g.how_verified(part_name)
    g.what_depends_on(part_name)
    assert bl.findings_fingerprint(report) == plain_fp
    assert bl.findings_fingerprint(withgraph.validate()) == plain_fp  # stable
