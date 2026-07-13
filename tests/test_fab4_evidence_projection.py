"""FAB-4 — the read-only projection of the Construction Process Graph into the
Evidence graph: ``process_step`` nodes + ``produced_by`` edges.

The Construction Process Graph is GENERATIVE — per Placed part, a ``ProcessRecord``
of ``stock -> ordered steps -> installed geometry`` whose steps ARE the source of
truth the cut list / BOM / geometry derive from (fab-design.md §4). It cannot live
inside the Evidence graph, whose invariant is that it generates nothing. So the
Evidence graph gains a read-only PROJECTION of it — exactly as it already re-hosts
Construction edges verbatim.

Three acceptance bars:

* **CAT-3 (capability).** For any fabricated part, "how is this made from what I
  buy?" has a derived, walkable answer — ``stock -> ordered steps -> installed
  geometry`` — and each step is walkable back to the design intent that generated
  it (its FEATURE / ``holes`` entry / implicit crosscut). Asserted on the notched
  ``deck 3`` (notch -> clearance intent) and on a drilled ``Lumber`` leg
  (drill -> ``holes`` entry).
* **Read-only, additive.** Projecting the record moves NO validation outcome and
  NO existing-kind node/edge — the existing-kind subgraph is byte-identical to a
  build with the projection disabled, on all four details and the composed site.
* **Purchased-as-is.** A part that is bought, not made (a pier block) projects NO
  ``process_step`` nodes; the ABSENCE of ``produced_by`` edges on its part node is
  the honest "purchased, not fabricated" fact, and ``how_made`` reports it.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file
from detailgen.spec.site import compile_site_file
from detailgen.validation.evidence import (
    EvidenceGraph,
    _detail_roles,
    assert_llm_nonblocking,
)

_DETAILS = Path(__file__).resolve().parents[1] / "details"
_DETAIL_SLUGS = ("platform", "rock_anchor", "tree_attachment", "trolley_launch")


def _compile(slug):
    if slug == "site":
        return compile_site_file(_DETAILS / "site.spec.yaml")
    return compile_spec_file(_DETAILS / f"{slug}.spec.yaml")


def _build_graph(detail) -> EvidenceGraph:
    """Assemble the evidence graph from the detail's ALREADY-computed lifecycle
    outputs (no re-validate — the graph assembly is the cheap part). Mirrors
    ``test_evidence_determinism._rebuild``."""
    return EvidenceGraph.build(
        assembly=detail.assembly,
        connections=detail.connections(),
        connection_checks=detail._connection_checks,
        report=detail.report,
        roles=_detail_roles(detail),
    )


@pytest.fixture(scope="module")
def models():
    """Validate all four details + the composed site ONCE (validate is the
    expensive step); tests build graphs from the cached outputs."""
    out = {}
    for slug in (*_DETAIL_SLUGS, "site"):
        d = _compile(slug)
        d.validate()
        out[slug] = d
    return out


@pytest.fixture(scope="module")
def platform_graph(models):
    return _build_graph(models["platform"])


@pytest.fixture(scope="module")
def rock_graph(models):
    return _build_graph(models["rock_anchor"])


# --------------------------------------------------------------------------- #
# CAT-3 — the stock -> ordered steps -> installed chain is walkable, and every
# step is walkable back to the design intent that produced it.
# --------------------------------------------------------------------------- #
def test_cat3_deck_3_notch_walks_back_to_the_clearance_intent(platform_graph):
    """`deck 3` is a board the trunk crosses: its fabrication chain is crosscut ->
    ease -> notch, and the notch is walkable back to the clearance intent that
    generated it (the trunk cutout)."""
    g = platform_graph
    made = g.how_made("deck 3")

    assert made["purchased"] is False
    # "what I buy" is legible: the 5/4x6 PT stick.
    assert made["stock"]["profile"] == "5/4x6 PT"
    assert made["stock"]["form"] == "linear_stick"
    assert made["installed"] == "derived: fold(stock, steps)"

    # ordered steps: crosscut first (establishes the stick), then ease, then notch
    kinds = [s["kind"] for s in made["steps"]]
    assert kinds == ["crosscut", "ease", "notch"], kinds
    assert [s["order"] for s in made["steps"]] == [0, 1, 2]

    notch = made["steps"][-1]
    # walkback: the step names the AUTHORED design intent that generated it
    assert notch["intent"] == "clearance_cut:trunk"
    assert notch["params"]["feature"] == "trunk"

    # the same intent is carried on the produced_by EDGE (the INCR seam): a
    # changed clearance op is walkable from the installed part to the op and back
    # to the authored declaration (the part node — authoritative authored fact).
    pid = g._resolve_part("deck 3")
    notch_edges = [e for e in g.edges_from(pid)
                   if e.kind == "produced_by"
                   and g.nodes[e.dst].attrs["step_kind"] == "notch"]
    assert len(notch_edges) == 1
    e = notch_edges[0]
    assert e.src == pid and e.provenance == "clearance_cut:trunk"
    # walkable BACK: the step's only incoming edge reaches the authored part node
    back = [b for b in g.edges_into(e.dst) if b.kind == "produced_by"]
    assert [b.src for b in back] == [pid]
    assert g.nodes[pid].kind == "part"
    assert g.nodes[pid].attrs["source_type"] == "authoritative"


def test_cat3_drilled_leg_drill_walks_back_to_its_holes_entry(rock_graph):
    """A drilled `Lumber` leg: the chain is crosscut -> ease -> drill(s), and each
    drill is walkable back to the authored `holes` entry that generated it."""
    g = rock_graph
    # the rock anchor's one Lumber member carries authored holes -> drill steps
    leg_pids = [n.id for n in g.nodes_of_kind("part")
                if n.attrs["component_type"] == "Lumber"]
    assert leg_pids, "expected a Lumber leg to be present"
    pid = leg_pids[0]
    made = g.how_made(pid)

    assert made["purchased"] is False
    assert made["stock"]["form"] == "linear_stick"
    kinds = [s["kind"] for s in made["steps"]]
    assert kinds[0] == "crosscut", "the stick is established by a crosscut first"
    assert "drill" in kinds, "a drilled leg must project drill steps"

    drills = [s for s in made["steps"] if s["kind"] == "drill"]
    for d in drills:
        # walkback to the authored intent — the specific holes entry
        assert d["intent"].startswith("holes[("), d["intent"]
        # the drill keys on its authored (x, z); diameter is comparable content
        assert {"x", "z", "diameter"} <= set(d["params"])

    # every step carries a non-empty provenance and the endpoint is derived
    assert all(s["intent"] for s in made["steps"])
    assert made["installed"] == "derived: fold(stock, steps)"


def test_cat3_every_projected_step_is_walkable_to_an_authored_part(models):
    """Across all four details + site: every projected step is reachable, in
    order, from its installed part via `produced_by`, and every step carries a
    provenance intent — no orphan or intentless op."""
    for slug in (*_DETAIL_SLUGS, "site"):
        g = _build_graph(models[slug])
        steps = g.nodes_of_kind("process_step")
        if not steps:
            continue
        for n in steps:
            # exactly one incoming produced_by, from a real part node
            back = [e for e in g.edges_into(n.id) if e.kind == "produced_by"]
            assert len(back) == 1, (slug, n.id)
            assert g.nodes[back[0].src].kind == "part", (slug, n.id)
            assert n.attrs["provenance"], f"{slug}: {n.id} has no provenance"
            assert n.attrs["source_type"] == "authoritative"


# --------------------------------------------------------------------------- #
# Read-only, additive — projecting the record changes no validation outcome and
# no existing-kind node/edge, on all four details + the composed site.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("slug", (*_DETAIL_SLUGS, "site"))
def test_projection_is_additive_and_validation_outcome_is_unchanged(
        slug, models, monkeypatch):
    detail = models[slug]

    # (1) the projection does not perturb the validation outcome: the report's
    # (check, subject, passed, detail) surface is identical before and after the
    # graph is built + queried.
    before = Counter((f.check, f.subject, bool(f.passed), f.detail)
                     for f in detail.report.findings)
    full = _build_graph(detail)
    # exercise the projection query surface (a query must not mutate either)
    for n in full.nodes_of_kind("part")[:3]:
        full.how_made(n.id)
    after = Counter((f.check, f.subject, bool(f.passed), f.detail)
                    for f in detail.validate().findings)
    assert after == before, f"{slug}: building/querying the graph moved a finding"

    # (2) byte-identical existing-kind subgraph: build the SAME graph with the
    # projection disabled; dropping process_step nodes + produced_by edges from
    # the full graph must reproduce it exactly. So the projection touched no
    # existing node's attrs and added no existing-kind edge.
    monkeypatch.setattr(EvidenceGraph, "_add_process_steps",
                        lambda self, assembly: None)
    no_proj = _build_graph(detail)
    monkeypatch.undo()

    fd = full.to_dict()
    existing = {
        "nodes": [n for n in fd["nodes"] if n["kind"] != "process_step"],
        "edges": [e for e in fd["edges"] if e["kind"] != "produced_by"],
    }
    assert existing == no_proj.to_dict(), (
        f"{slug}: the fabrication projection perturbed the existing-kind subgraph "
        f"— it must be ADDITIVE ONLY")
    # and the disabled build genuinely projects nothing (guards the guard)
    assert not no_proj.nodes_of_kind("process_step")
    assert not no_proj.edges_of_kind("produced_by")
    # the full graph still passes the honesty guards with the projection present
    assert_llm_nonblocking(full)


def test_projection_serialization_is_deterministic(models):
    """Two builds of the same detail produce byte-identical process_step nodes +
    produced_by edges — the node ids key on content, not on a process-varying
    order, so the projected layer is reproducible."""
    detail = models["platform"]
    a = _build_graph(detail).to_dict()
    b = _build_graph(detail).to_dict()

    def _fab(d):
        return ([n for n in d["nodes"] if n["kind"] == "process_step"],
                [e for e in d["edges"] if e["kind"] == "produced_by"])

    assert _fab(a) == _fab(b)
    ps, pb = _fab(a)
    assert ps and pb, "platform must project a non-trivial fabrication layer"


# --------------------------------------------------------------------------- #
# Purchased-as-is — a bought part projects nothing; the absence is the fact.
# --------------------------------------------------------------------------- #
def test_purchased_pier_block_projects_no_steps(platform_graph):
    """The platform's pier block is a purchased item, not fabricated from stock:
    it projects NO process_step nodes, and the absence of produced_by edges on its
    part node IS the honest 'bought, not made' fact `how_made` reports."""
    g = platform_graph
    made = g.how_made("pier -Y")
    assert made["purchased"] is True
    assert made["steps"] == []
    assert made["stock"] is None
    assert made["installed"] is None

    pid = g._resolve_part("pier -Y")
    assert not [e for e in g.edges_from(pid) if e.kind == "produced_by"]
    # no process_step node claims this part
    assert not [n for n in g.nodes_of_kind("process_step")
                if n.attrs["part"] == pid]


def test_purchased_parts_project_nothing_across_all_models(models):
    """Every part with no fabrication record (base Component: bolts, hangers,
    mesh, trunk, boulder, pier blocks) projects zero process_step nodes — only
    Lumber / DeckBoard members do."""
    for slug in (*_DETAIL_SLUGS, "site"):
        detail = models[slug]
        g = _build_graph(detail)
        fabricated_pids = {
            n.attrs["part"] for n in g.nodes_of_kind("process_step")}
        for p in detail.assembly.parts:
            is_fab = type(p.component).__name__ in ("Lumber", "DeckBoard")
            from detailgen.validation.evidence import _part_nid
            has_steps = _part_nid(p.id) in fabricated_pids
            if not is_fab:
                assert not has_steps, f"{slug}: {p.id} ({type(p.component).__name__}) projected steps"
