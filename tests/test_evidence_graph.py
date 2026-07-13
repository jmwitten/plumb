"""Task EVIDENCE — the Evidence Graph, its completeness invariants (the
honesty core), the knowledge-source dimension + its non-blocking guarantee,
and the Inspector-oriented query API.

The invariant tests are written mutation-style: each asserts BOTH that the
real rock-anchor graph satisfies the invariant AND that a deliberately
corrupted graph is REJECTED with a hard diagnostic — a passing assertion on
clean data alone would not prove the guard has teeth (the permits-vs-requires
lesson applied to the evidence layer itself)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

import baseline_lib as bl
from detailgen.assemblies.connection import DerivedFact
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation.coverage import PROVENANCE_ONLY_KINDS, family_of
from detailgen.validation.evidence import (
    EvidenceGraph,
    EvidenceGraphError,
    SOURCE_TYPES,
    assert_llm_nonblocking,
)

_DETAILS = Path(__file__).resolve().parents[1] / "details"


# Factory keeping the ``RockAnchor()`` call syntax the tests use; compiles the
# detail's spec.yaml (the imperative mirror is retired).
def RockAnchor():
    return compile_spec_file(_DETAILS / "rock_anchor.spec.yaml")


@pytest.fixture(scope="module")
def rock_graph():
    detail = RockAnchor()
    detail.validate()
    return detail.evidence_graph


# -- adjacency index (task CLEANUP item 7): O(degree) queries, same results --


def test_adjacency_index_matches_a_full_edge_scan(rock_graph):
    """edges_from / edges_into read the incremental adjacency index; they must
    return exactly the full-scan filter, in the same (insertion) order, for
    every node — otherwise the O(degree) speedup would change query results."""
    for nid in rock_graph.nodes:
        assert (rock_graph.edges_from(nid)
                == [e for e in rock_graph.edges if e.src == nid])
        assert (rock_graph.edges_into(nid)
                == [e for e in rock_graph.edges if e.dst == nid])
    # a node with no edges yields empty, not KeyError
    assert rock_graph.edges_from("no:such:node") == []
    assert rock_graph.edges_into("no:such:node") == []


def test_adjacency_index_survives_serialization_round_trip(rock_graph):
    """from_dict rebuilds via add_edge, so a deserialized graph's index is
    populated and self-consistent (its edges_from/into match its own full scan).
    Intra-bucket order may differ from the original — to_dict emits edges sorted
    by key — but that is a serialization detail; the freshly-built graph the
    Inspector queries keeps insertion order, and both are deterministic."""
    clone = EvidenceGraph.from_dict(rock_graph.to_dict())
    for nid in clone.nodes:
        assert clone.edges_from(nid) == [e for e in clone.edges if e.src == nid]
        assert clone.edges_into(nid) == [e for e in clone.edges if e.dst == nid]
    # and the edge SETS are identical to the original (only order can differ)
    assert {e._key() for e in clone.edges} == {e._key() for e in rock_graph.edges}


# -- req 5a: no orphan facts -------------------------------------------------


def test_every_derived_fact_reaches_a_declaration(rock_graph):
    facts = rock_graph.nodes_of_kind("derived_fact")
    assert facts, "rock anchor must derive facts"
    for f in facts:
        decls = [e for e in rock_graph.edges_from(f.id) if e.kind == "derived_from"]
        assert decls, f"orphan derived fact with no declaration: {f.id}"


def test_orphan_fact_is_a_hard_diagnostic():
    """A derived fact whose connection resolves to no declaration must make
    graph construction RAISE — never silently drop or silently keep it."""
    detail = RockAnchor()
    detail.validate()
    cc = detail._connection_checks
    cc.derived.append(DerivedFact(
        fact="ghost fact", connection="no-such-connection",
        rule="ghost.rule", confidence="inferred",
    ))
    with pytest.raises(EvidenceGraphError, match="orphan"):
        EvidenceGraph.build(
            assembly=detail.assembly, connections=detail.connections(),
            connection_checks=cc, report=detail.report,
        )


# -- req 5b: every generated check traces to its fact/connection -------------


def test_every_finding_traces_to_a_declaration_or_fact(rock_graph):
    findings = rock_graph.nodes_of_kind("finding")
    assert findings
    for f in findings:
        gen = [e for e in rock_graph.edges_into(f.id) if e.kind == "generated"]
        assert gen, f"orphan finding with no generator: {f.id} ({f.label})"


def test_connection_findings_trace_to_a_derived_fact(rock_graph):
    """A connection-generated check (bearing / hardware presence) must trace
    to the derived fact that produced it, not merely to an imperative node."""
    for f in rock_graph.nodes_of_kind("finding"):
        if f.attrs["check"] in ("bearing", "connection_hardware"):
            gens = [rock_graph.node(e.src)
                    for e in rock_graph.edges_into(f.id) if e.kind == "generated"]
            assert any(g.kind == "derived_fact" for g in gens), \
                f"connection finding {f.id} does not trace to a derived fact"


# -- req 5c: family verdicts match the coverage matrix provenance ------------


def test_family_verdicts_match_coverage_matrix(rock_graph):
    detail = RockAnchor()
    report = detail.validate()
    matrix = {row.family: row for row in report.coverage_matrix()}
    for fam_node in rock_graph.nodes_of_kind("family_verdict"):
        family = fam_node.attrs["family"]
        row = matrix[family]
        substantiators = [e for e in rock_graph.edges_into(fam_node.id)
                          if e.kind == "substantiates"]
        assert len(substantiators) == row.checks_run, (
            f"{family}: {len(substantiators)} substantiating findings vs "
            f"coverage checks_run={row.checks_run}")
        kinds = Counter(rock_graph.node(e.src).attrs["check"] for e in substantiators)
        assert tuple(sorted(kinds.items())) == row.ran_kinds
        assert fam_node.attrs["verdict"] == row.verdict


def test_provenance_only_findings_never_substantiate_a_family(rock_graph):
    for f in rock_graph.nodes_of_kind("finding"):
        if f.attrs["check"] in PROVENANCE_ONLY_KINDS:
            subs = [e for e in rock_graph.edges_from(f.id)
                    if e.kind == "substantiates"]
            assert not subs, f"provenance marker {f.id} wrongly substantiates a family"


# -- req 5d: serialization round-trips ---------------------------------------


def test_graph_round_trips(rock_graph):
    payload = rock_graph.to_dict()
    import json
    revived = EvidenceGraph.from_dict(json.loads(json.dumps(payload)))
    assert revived == rock_graph
    assert revived.to_dict() == payload


# -- req 2: knowledge-source dimension + non-blocking by construction --------


def test_every_fact_and_declaration_carries_a_known_source_type(rock_graph):
    for kind in ("derived_fact", "declaration"):
        for n in rock_graph.nodes_of_kind(kind):
            assert n.attrs["source_type"] in SOURCE_TYPES, n


def test_source_type_is_orthogonal_to_confidence(rock_graph):
    """The two axes are recorded independently: a fact may be authoritative or
    verified_heuristic at either confidence — neither field is a function of
    the other's stored value on the node."""
    facts = rock_graph.nodes_of_kind("derived_fact")
    # rock anchor exercises authoritative+official (declared hardware) and
    # verified_heuristic+inferred (rule-derived bearings) — both present.
    seen = {(n.attrs["source_type"], n.attrs["confidence"]) for n in facts}
    assert ("authoritative", "official") in seen
    assert ("verified_heuristic", "inferred") in seen


def test_llm_hypotheses_are_non_blocking(rock_graph):
    # nothing in the codebase is an llm_hypothesis today
    assert not [n for n in rock_graph.nodes_of_kind("derived_fact")
                if n.attrs["source_type"] == "llm_hypothesis"]
    # ... and the clean graph passes the guard
    assert_llm_nonblocking(rock_graph) is None


def test_llm_hypothesis_that_generates_a_failing_check_is_rejected(rock_graph):
    """The guarantee is enforced, not merely observed absent: an llm_hypothesis
    fact wired to a FAILING check must be caught by a hard diagnostic."""
    g = rock_graph.copy()
    g.add_node("derived_fact", "fact:llm-bug", "hypothetical llm rule",
               source_type="llm_hypothesis", confidence="inferred")
    g.add_node("finding", "finding:llm-bug", "a failing check",
               check="bearing", passed=False)
    g.add_edge("fact:llm-bug", "finding:llm-bug", "generated")
    with pytest.raises(EvidenceGraphError, match="llm_hypothesis"):
        assert_llm_nonblocking(g)


# -- req 4: Inspector query API on real rock-anchor geometry ------------------


def test_what_is_returns_a_descriptor(rock_graph):
    d = rock_graph.what_is("leg")
    assert d["name"] == "leg"
    assert d["component_type"] == "Lumber"
    assert "material" in d and "descriptor" in d and "params" in d


def test_why_here_separates_authored_from_derived(rock_graph):
    d = rock_graph.why_here("leg")
    assert d["authored"], "the leg participates in declared connections"
    assert d["derived"], "the leg has facts derived about it"
    for row in d["authored"]:
        assert row["source_type"] in SOURCE_TYPES
    # the leg is a declared participant of a rod-epoxy anchor connection
    assert any("rod" in r["label"] for r in d["authored"])


def test_how_verified_is_never_a_bare_verdict(rock_graph):
    d = rock_graph.how_verified("leg")
    assert d["findings"], "the leg is covered by findings"
    assert d["family_verdicts"]
    assert d["evidence_chain"], "verdicts must be explained with a chain"
    # every reported family verdict carries its explanation note
    for fam in d["family_verdicts"]:
        assert fam["verdict"] and fam["note"]


def test_what_depends_on_lists_graph_neighbors_and_invalidations(rock_graph):
    d = rock_graph.what_depends_on("leg")
    assert d["construction_neighbors"], "the leg bears/fastens to neighbors"
    kinds = {n["edge"] for n in d["construction_neighbors"]}
    assert kinds & {"bears_on", "fastened_by", "transfers_load_to", "installed_before"}
    assert d["invalidated_if_changed"], "facts/checks depend on the leg"


# -- graph size sanity (documents the rock-anchor graph for the report) ------


def test_rock_anchor_graph_is_well_formed(rock_graph):
    kinds = Counter(n.kind for n in rock_graph.nodes.values())
    _ra = bl.load_baseline("detail_counts")["rock_anchor"]
    assert kinds["part"] == _ra["parts"]
    assert kinds["family_verdict"] == 9  # graph-shape constant (9 families since task INSTALL)
    assert kinds["derived_fact"] == _ra["derivation_log"]
    # every edge endpoint resolves to a real node
    for e in rock_graph.edges:
        assert e.src in rock_graph.nodes and e.dst in rock_graph.nodes
