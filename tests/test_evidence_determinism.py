"""Task CLEANUP item 1 — the Evidence Graph must serialize DETERMINISTICALLY.

The compiled ``ConnectionChecks.derived`` list arrives in a process-varying
order (its upstream connection hooks iterate sets), so before this guard the
index-based ``fact:i`` node ids — and every edge referencing them — differed
across processes: two fresh builds of the *same* platform produced graphs with
identical node/edge CONTENT but different ``to_dict()`` bytes. Only the sorted
report-findings fingerprint (``test_evidence_equiv.py``) was stable; the graph
the Inspector consumes was not.

``EvidenceGraph._add_derived_facts`` now assigns fact ids in a canonical
content order, so the serialized graph is invariant to the derived list's
order. This locks that in the strongest content-agnostic way: shuffling the
derived facts (the ONLY non-deterministic input) must not move a single byte of
``to_dict()``. A regression that drops the canonical sort fails here regardless
of what the graph's legitimate content happens to be that day."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file
from detailgen.validation.evidence import EvidenceGraph, _detail_roles

_DETAILS = Path(__file__).resolve().parents[1] / "details"


# Factories keeping the ``RockAnchor()`` / ``Platform()`` call syntax the tests
# below use: each compiles the detail's spec.yaml (the retired imperative
# mirrors were byte-identical by the frozen-truth oracles).
def RockAnchor():
    return compile_spec_file(_DETAILS / "rock_anchor.spec.yaml")


def Platform():
    return compile_spec_file(_DETAILS / "platform.spec.yaml")


def _graph_hash(graph: EvidenceGraph) -> str:
    return hashlib.sha256(
        json.dumps(graph.to_dict(), sort_keys=True).encode()).hexdigest()


def _rebuild(detail, derived_order) -> EvidenceGraph:
    """Build the detail's evidence graph from its captured lifecycle outputs,
    substituting a specific ``derived`` fact ordering — the one input whose
    order the platform does not control."""
    cc = detail._connection_checks
    cc = replace(cc, derived=derived_order)
    return EvidenceGraph.build(
        assembly=detail.assembly,
        connections=detail.connections(),
        connection_checks=cc,
        report=detail.report,
        roles=_detail_roles(detail),
    )


@pytest.mark.parametrize("cls", [RockAnchor, Platform])
def test_graph_serialization_is_order_invariant(cls):
    detail = cls()
    detail.validate()
    baseline = _rebuild(detail, list(detail._connection_checks.derived))
    # non-vacuous: there are derived facts whose order could have leaked in
    assert baseline.nodes_of_kind("derived_fact"), "no derived facts to shuffle"
    base_hash = _graph_hash(baseline)

    for seed in (0, 1, 7, 42):
        shuffled = list(detail._connection_checks.derived)
        random.Random(seed).shuffle(shuffled)
        rebuilt = _rebuild(detail, shuffled)
        assert _graph_hash(rebuilt) == base_hash, (
            f"{detail.name}: evidence graph serialization changed when the "
            f"derived-fact list was shuffled (seed {seed}) — the canonical "
            f"fact-id ordering regressed, graph is non-deterministic again")
