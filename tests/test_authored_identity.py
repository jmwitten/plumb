"""INCR-1 — the authored-id bridge (src/spec/identity.py).

The bridge maps ``authored id <-> Placed <-> evidence-graph part node`` keyed on
the insertion-stable authored id, so a built part is addressable by an identity
that survives editing (incr-design.md §2 Finding 2). These tests prove:

- every platform part (and every part of the other 3 details + the composed site)
  round-trips ``authored id -> Placed -> graph node -> authored id``, and the
  bridge's node ids are EXACTLY the evidence graph's ``part`` nodes;
- the Finding-1 renumbering counterexample: inserting a part earlier in build
  order shifts ``Placed.id`` but leaves the authored id (and the round-trip)
  stable;
- a ``bind:``/``dedup:``-merged single-node member resolves to ONE canonical
  authored identity — the real member, not the retired stub/context copy;
- ambiguity is a loud teaching error and an undeclared part gets an explicit
  "no authored id", never a guess (P1).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from detailgen.spec.compiler import compile_spec, compile_spec_file
from detailgen.spec.identity import (
    AuthoredIdentity,
    NoAuthoredId,
    SpecIdentityError,
    authored_identity,
    graph_part_nid,
)
from detailgen.spec.loader import load_spec_text
from detailgen.spec.site import compile_site_file

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"
DETAIL_NAMES = ["platform", "rock_anchor", "tree_attachment", "trolley_launch"]


def _detail(name):
    return compile_spec_file(str(DETAILS / f"{name}.spec.yaml"))


def _site():
    return compile_site_file(str(DETAILS / "site.spec.yaml"))


# --- round-trip: id -> Placed -> graph node -> id on every real model ---------

@pytest.mark.parametrize("name", DETAIL_NAMES)
def test_every_part_round_trips_id_placed_node_id(name):
    d = _detail(name)
    ai = AuthoredIdentity(d)
    ids = ai.authored_ids()
    assert ids, f"{name} has no authored parts"
    for aid in ids:
        placed = ai.placed_of(aid)
        assert ai.authored_id_of(placed) == aid          # Placed -> id
        nid = ai.graph_nid_of(aid)                        # id -> graph node
        assert nid == graph_part_nid(placed.id)
        assert ai.authored_id_of_graph_nid(nid) == aid    # node -> id (full loop)


def test_site_every_part_round_trips():
    ai = AuthoredIdentity(_site())
    ids = ai.authored_ids()
    assert len(ids) == 180  # FAB-3: +3 post bases (one canonical id each: platform/pier_*_base)
    for aid in ids:
        nid = ai.graph_nid_of(aid)
        assert ai.authored_id_of_graph_nid(nid) == aid


@pytest.mark.parametrize("name", DETAIL_NAMES)
def test_bridge_nodes_are_exactly_the_evidence_graph_part_nodes(name):
    """The bridge addresses precisely the graph's ``part`` nodes — no synthesized
    node the graph lacks, and every real part node resolves back to a canonical
    authored id. (The load-bearing "round-trips to its graph node" guarantee.)"""
    d = _detail(name)
    d.validate()
    ai = AuthoredIdentity(d)
    graph_part_nodes = {n.id for n in d.evidence_graph.nodes.values()
                        if n.kind == "part"}
    bridge_nodes = {ai.graph_nid_of(a) for a in ai.authored_ids()}
    assert bridge_nodes == graph_part_nodes
    for pn in graph_part_nodes:                            # each resolves back
        assert ai.authored_id_of_graph_nid(pn) in ai.authored_ids()


def test_site_bridge_nodes_match_evidence_graph():
    s = _site()
    s.validate()
    ai = AuthoredIdentity(s)
    graph_part_nodes = {n.id for n in s.evidence_graph.nodes.values()
                        if n.kind == "part"}
    assert {ai.graph_nid_of(a) for a in ai.authored_ids()} == graph_part_nodes


def test_reverse_by_id_accessor_is_bijection_on_a_plain_detail():
    d = _detail("platform")
    rev = d.reverse_by_id()                                # accessor beside _by_id
    fwd = d._by_id
    assert len(rev) == len(fwd) == len(d.assembly.parts)
    for cid, placed in fwd.items():
        assert rev[placed] == cid                          # exact inverse
    assert AuthoredIdentity(d).parts_without_authored_id() == []


# --- Finding 1: the renumbering counterexample (regression) ------------------

def _demo_spec(insert_shim: bool) -> str:
    shim = ("""
  - id: shim
    type: lumber
    name: "shim"
    params: {nominal: "2x4", length: 6.0, treated: false, ease_radius: "0.125 in"}
    place: {raw: {at: [0, -20, 0]}}
""" if insert_shim else "")
    return f"""
name: rt demo
type: demo
units: in
components:{shim}
  - id: alpha
    type: lumber
    name: "alpha"
    params: {{nominal: "2x6", length: 12.0, treated: true, ease_radius: "0.125 in"}}
    place: {{raw: {{at: [0, 0, 0]}}}}
  - id: bravo
    type: lumber
    name: "bravo"
    params: {{nominal: "2x6", length: 12.0, treated: true, ease_radius: "0.125 in"}}
    place: {{raw: {{at: [0, 10, 0]}}}}
"""


def test_insertion_shifts_placed_id_but_authored_id_stays_stable():
    base = AuthoredIdentity(compile_spec(load_spec_text(_demo_spec(False))))
    var = AuthoredIdentity(compile_spec(load_spec_text(_demo_spec(True))))

    # The positional Placed.id renumbers on the earlier insertion (Finding 1)...
    assert base.placed_of("alpha").id == "lumber-0"
    assert var.placed_of("alpha").id == "lumber-1"
    assert base.graph_nid_of("alpha") != var.graph_nid_of("alpha")

    # ...but the authored id is insertion-stable, and the bridge resolves it in
    # BOTH revisions — an inserted part does not report every later member as
    # replaced (which keying on Placed.id would).
    for br in (base, var):
        assert br.authored_id_of_graph_nid(br.graph_nid_of("alpha")) == "alpha"
        assert br.authored_id_of_graph_nid(br.graph_nid_of("bravo")) == "bravo"
    assert var.placed_of("shim").id == "lumber-0"          # shim took the ordinal


# --- site single-node identity: the real member wins -------------------------

# Each pair is (retired alias qid, canonical real-member qid) for a bind:/dedup:
# merged node in the composed site.
SITE_MERGES = [
    ("rock_anchor/leg", "platform/leg_pY"),      # stub bind
    ("trolley/far_post", "platform/leg_pY"),     # second alias on the same node
    ("trolley/launch_post", "platform/leg_mY"),
    ("tree/beam_pY", "platform/beam_pY"),
    ("tree/beam_mY", "platform/beam_mY"),
    ("trolley/deck_rim", "platform/end_joist"),
    ("platform/boulder", "rock_anchor/boulder"),  # dedup context body
    ("platform/trunk", "tree/trunk"),
]


@pytest.mark.parametrize("alias,real", SITE_MERGES)
def test_bind_merged_node_resolves_to_the_real_member(alias, real):
    ai = AuthoredIdentity(_site())
    # The alias addresses the SAME built node as the real member (single node)...
    assert ai.placed_of(alias) is ai.placed_of(real)
    assert ai.graph_nid_of(alias) == ai.graph_nid_of(real)
    # ...and that node's ONE canonical identity is the real member, never the
    # retired stub/context copy.
    assert ai.authored_id_of_graph_nid(ai.graph_nid_of(alias)) == real
    assert ai.authored_id_of(ai.placed_of(alias)) == real
    # The alias is recorded, canonical-first, so the merge is queryable not lost.
    aliases = ai.aliases_of(real)
    assert aliases[0] == real and alias in aliases


def test_three_ids_on_one_node_pick_the_single_real_member():
    ai = AuthoredIdentity(_site())
    node = ai.graph_nid_of("platform/leg_pY")
    on_node = [a for a in ai._forward if ai.graph_nid_of(a) == node]
    assert set(on_node) == {"platform/leg_pY", "rock_anchor/leg", "trolley/far_post"}
    assert ai.authored_id_of_graph_nid(node) == "platform/leg_pY"


# --- P1: ambiguity is loud, an undeclared part is explicit -------------------

class _P:
    """A minimal Placed stand-in — the bridge only reads ``.id`` and hashes by
    identity (Placed is ``eq=False``)."""

    def __init__(self, pid):
        self.id = pid


def _fake(by_id, retired=(), extra_parts=()):
    parts = list(dict.fromkeys(list(by_id.values()) + list(extra_parts)))
    return SimpleNamespace(
        _by_id=dict(by_id),
        _retired_ids=lambda: frozenset(retired),
        build=lambda: None,
        assembly=SimpleNamespace(parts=parts),
    )


def test_two_live_declarations_on_one_node_is_a_loud_error():
    shared = _P("lumber-0")
    detail = _fake({"a": shared, "b": shared})   # two live ids, no retirement
    with pytest.raises(SpecIdentityError) as e:
        AuthoredIdentity(detail)
    assert "'a'" in str(e.value) and "'b'" in str(e.value)
    assert "bind:" in str(e.value)               # names the fix, not a bare raise


def test_a_declared_retirement_disambiguates_the_same_shared_node():
    shared = _P("lumber-0")
    detail = _fake({"real": shared, "alias": shared}, retired=["alias"])
    ai = AuthoredIdentity(detail)
    assert ai.authored_id_of(shared) == "real"
    assert ai.aliases_of("real") == ("real", "alias")


def test_node_addressed_only_by_retired_ids_is_a_loud_error():
    shared = _P("lumber-0")
    detail = _fake({"aliasA": shared, "aliasB": shared},
                   retired=["aliasA", "aliasB"])
    with pytest.raises(SpecIdentityError) as e:
        AuthoredIdentity(detail)
    assert "no canonical" in str(e.value)


def test_undeclared_part_is_an_explicit_no_authored_id():
    named = _P("lumber-0")
    orphan = _P("lumber-9")
    detail = _fake({"named": named}, extra_parts=[orphan])
    ai = AuthoredIdentity(detail)
    assert ai.parts_without_authored_id() == [orphan]
    assert ai.try_authored_id_of(orphan) is None
    with pytest.raises(NoAuthoredId) as e:
        ai.authored_id_of(orphan)
    assert "lumber-9" in str(e.value)            # reports the build-order handle
    assert "no authored id" in str(e.value)


def test_unknown_authored_id_and_unknown_graph_node_raise_with_hints():
    ai = AuthoredIdentity(_detail("platform"))
    with pytest.raises(SpecIdentityError):
        ai.placed_of("not_a_real_id")
    with pytest.raises(SpecIdentityError):
        ai.authored_id_of_graph_nid("part:no-such-node")
    with pytest.raises(SpecIdentityError):
        ai.authored_id_of_graph_nid("beam_pY")   # authored id is NOT a node id


def test_graph_part_nid_is_idempotent_and_matches_evidence_key():
    from detailgen.validation.evidence import _part_nid
    for pid in ["lumber-0", "boulder-3", "part:already"]:
        assert graph_part_nid(pid) == _part_nid(pid)
        assert graph_part_nid(graph_part_nid(pid)) == graph_part_nid(pid)


def test_authored_identity_convenience_entry_point():
    assert isinstance(authored_identity(_detail("rock_anchor")), AuthoredIdentity)
