"""Event-graph probes for the CPG v1-core assembly slice (task CPGCORE,
stepdoc-cpg-design.md §2–§5) — the adversarial review's LIVE constructions
pinned as tests, so the two lift rules (F-5 same-event drop, R-2 multi-stack
mapping), the structural-necessity exception, the merged cycle check's
teaching error, and the stage/step vocabulary boundary cannot silently
regress. Synthetic minimal assemblies throughout (the CAT lineage), so each
mechanism is exercised in isolation from any shipped spec.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from detailgen.core import IN
from detailgen.assemblies import (
    BoltedClamp, Connection, ConnectionType, DetailAssembly, FaceMountHanger,
    compile_connections, connection_types,
)
from detailgen.assemblies.connection import Edge
from detailgen.assemblies.event_graph import (
    FAMILY_AUTHORED, FAMILY_NECESSITY, FAMILY_STAGING, FAMILY_TECHNIQUE, Event,
    EventOrderCycleError, ResolvedStage, ResolvedStaging, ResolvedUnit,
    build_event_graph,
    derive_reader_steps, linearize, unordered_parts,
)
from detailgen.assemblies.installation import straight_screw_group
from detailgen.components import (
    HexBolt, HexNut, JoistHanger, Lumber, StructuralScrew, Washer,
)


def _graph(assembly, conns, stages=(), staging=None):
    checks = compile_connections(
        assembly, list(conns), sequence=stages, staging=staging)
    return checks.event_graph


# -- lift rule (a): same-event edges drop (review F-5) -------------------------


def _bolted_clamp():
    a = DetailAssembly("f5")
    p1 = a.add(Lumber("2x4", 4 * IN, name="head plate"))
    p2 = a.add(Lumber("2x4", 4 * IN, name="nut plate"), at=(0, 38.1, 0))
    bolt = a.add(HexBolt(0.375 * IN, 3.5 * IN, name="clamp bolt"),
                 at=(50.0, 0.0, 44.0), rotate=[("X", 90)])
    hw = a.add(Washer(0.4 * IN, name="head washer"), at=(50.0, -2.0, 44.0))
    nw = a.add(Washer(0.4 * IN, name="nut washer"), at=(50.0, 78.0, 44.0))
    nut = a.add(HexNut(0.375 * IN, name="clamp nut"), at=(50.0, 80.0, 44.0))
    conn = Connection(kind=BoltedClamp(axis="Y", hardware_area=1,
                                       end_plate_area=1),
                      parts=[p1, p2], hardware=[bolt, hw, nw, nut],
                      label="clamp")
    return a, conn, (p1, p2, bolt, hw, nw, nut)


def test_f5_intra_stack_edges_are_order_vacuous_and_drop():
    """The reviewer's live F-5 construction in miniature: a BoltedClamp's
    bolt→washer→washer→nut chain (the platform carries 40 such edges) maps
    every stack piece to the ONE ``drive(clamp, bolt_stack)`` event, so the
    intra-stack edges are self-loops and must DROP as order-vacuous —
    without the drop rule every bolted detail fails at load, day one, on
    self-loop "cycles". The graph must load cycle-free with exactly the
    place→drive lifts remaining."""
    a, conn, (p1, p2, bolt, hw, nw, nut) = _bolted_clamp()
    g = _graph(a, [conn])   # loads — no self-loop cycle
    drive = Event("drive", "clamp", "bolt_stack")
    for part in (bolt, hw, nw, nut):
        assert g.event_of[part.id] == drive
    assert all(e.a != e.b for e in g.edges)
    lifted = [e for e in g.edges if e.family == FAMILY_TECHNIQUE]
    assert {(e.a, e.b) for e in lifted} == {
        (Event("place", p1.id), drive), (Event("place", p2.id), drive)}


# -- lift rule (b): multi-stack hardware mapping (review R-2) ------------------


def _hanger_joint():
    a = DetailAssembly("r2")
    header = a.add(Lumber("2x6", 10 * IN, name="header"))
    hung = a.add(Lumber("2x6", 10 * IN, name="hung"), at=(0, 60, 0))
    hanger = a.add(JoistHanger(1.5 * IN, 5.5 * IN, name="hanger"),
                   at=(0, 30, 0))
    screws = [a.add(StructuralScrew(0.157 * IN, 1.5 * IN, name=f"s{i}"),
                    at=(10 * i, 30, 0)) for i in range(2)]
    kind = FaceMountHanger(seat_axis="Z", seat_area=60,
                           n_header_screws=1, n_hung_screws=1)
    conn = Connection(kind=kind, parts=[header, hung],
                      hardware=[hanger, *screws], label="hang")
    return a, conn, (header, hung, hanger, screws[0], screws[1])


def test_r2_multi_stack_hanger_maps_to_the_header_side_drive():
    """R-2 pinned with the reviewer's construction: the hanger piece rides
    BOTH screw groups' stacks; its own ``hanger → header screws`` type edge
    places it at-or-before the HEADER-side drive, so it maps there and the
    whole collapse is consistent — ``hanger → header screws`` becomes a
    self-loop and drops (F-5), ``hanger → hung`` lands as a duplicate of
    the header-screws-before-hung technique edge, ``header → hanger``
    becomes place-before-drive. The graph loads cycle-free."""
    a, conn, (header, hung, hanger, hs, us) = _hanger_joint()
    g = _graph(a, [conn])
    hdr_drive = Event("drive", "hang", "header_screws")
    hung_drive = Event("drive", "hang", "hung_screws")
    assert g.event_of[hanger.id] == hdr_drive
    pairs = {(e.a, e.b) for e in g.edges if e.family == FAMILY_TECHNIQUE}
    assert (Event("place", header.id), hdr_drive) in pairs
    assert (hdr_drive, Event("place", hung.id)) in pairs
    assert (Event("place", hung.id), hung_drive) in pairs
    assert all(e.a != e.b for e in g.edges)


def test_r2_counterexample_the_hung_side_mapping_would_cycle():
    """The reviewer's pinned counterexample, encoded as this test's
    rationale: had the lift mapped the hanger to the HUNG-side drive, its
    ``hanger → hung`` edge would lift to ``drive(hung-side) → place(hung)``
    while the type's own ``hung → hung screws`` edge (and structural
    necessity) gives ``place(hung) → drive(hung-side)`` — a direct 2-cycle
    that would fail every hanger-bearing detail (the platform first) at
    load. Proven here by performing the WRONG lift by hand on the type's
    own raw edges and exhibiting both directions of the cycle."""
    a, conn, (header, hung, hanger, hs, us) = _hanger_joint()
    raw = [e for e in conn.kind.edges(conn) if e.kind == "installed_before"]
    hung_drive = Event("drive", "hang", "hung_screws")
    wrong_map = {hanger.id: hung_drive, hs.id: Event("drive", "hang",
                                                     "header_screws"),
                 us.id: hung_drive,
                 header.id: Event("place", header.id),
                 hung.id: Event("place", hung.id)}
    lifted = {(wrong_map[e.a], wrong_map[e.b]) for e in raw
              if wrong_map[e.a] != wrong_map[e.b]}
    assert (hung_drive, Event("place", hung.id)) in lifted
    assert (Event("place", hung.id), hung_drive) in lifted   # the 2-cycle


def test_structural_necessity_yields_to_a_declared_opposite_path():
    """§3.1 family 2's exception, on the live hanger: the type DECLARES the
    header screws precede the hung member (drive → place), so the default
    ``place(hung) → drive(header_screws)`` necessity edge must NOT be
    emitted — emitting it would cycle the technique's own truth. The hung
    member's necessity edge into its OWN screws' drive stays."""
    a, conn, (header, hung, hanger, hs, us) = _hanger_joint()
    g = _graph(a, [conn])
    hdr_drive = Event("drive", "hang", "header_screws")
    hung_drive = Event("drive", "hang", "hung_screws")
    necessity = {(e.a, e.b) for e in g.edges if e.family == FAMILY_NECESSITY}
    assert (Event("place", hung.id), hdr_drive) not in necessity
    assert (Event("place", header.id), hdr_drive) in necessity \
        or g.precedes(Event("place", header.id), hdr_drive)
    # the hung member still provably precedes its own screws' drive
    assert g.precedes(Event("place", hung.id), hung_drive)


def test_mid_event_member_interleave_drops_both_directions_rock_anchor():
    """The THIRD lift rule, pinned on the live construction that forced it
    (found in this task — same defect class as F-5/R-2): the shipped
    ThreadedRodEpoxyAnchor threads its hardware chain THROUGH a member
    (``... lo_washer -> bracket -> up_washer ...``), so the lift produces
    both ``drive -> place(bracket)`` and ``place(bracket) -> drive`` for
    the one anchor_rod drive event — a 2-cycle the part-level chain never
    had. Both directions are the member's MID-EVENT arrival and drop;
    structural necessity keeps the conservative ``place(bracket) -> drive``
    (present at the event, never quietly later). The shipped rock anchor
    must load cycle-free with exactly that surviving direction."""
    from detailgen.spec.compiler import compile_spec_file

    root = Path(__file__).resolve().parents[1]
    d = compile_spec_file(root / "details" / "rock_anchor.spec.yaml")
    d.validate()
    g = d._connection_checks.event_graph
    # find an anchor_rod drive and its bracket member
    anchor_drives = [ev for ev in g.events
                     if ev.kind == "drive" and ev.group == "anchor_rod"]
    assert anchor_drives
    for dev in anchor_drives:
        members = g.members_of[dev.subject]
        bracket = next(m for m in members
                       if "angle" in g.part_names[m])
        place = Event("place", bracket)
        tech_pairs = {(e.a, e.b) for e in g.edges
                      if e.family == FAMILY_TECHNIQUE}
        assert (dev, place) not in tech_pairs      # dropped: mid-event
        assert (place, dev) not in tech_pairs      # dropped: mid-event
        necessity = {(e.a, e.b) for e in g.edges
                     if e.family == FAMILY_NECESSITY}
        assert (place, dev) in necessity           # the surviving direction


def test_multi_stack_hardware_without_a_disambiguating_edge_is_loud():
    """R-2's ambiguity half: hardware riding two stacks whose own type
    edges place it at-or-before NEITHER drive has no honest mapping — a
    loud teaching error naming the rule, never a guess."""

    class _TwoStackType(ConnectionType):
        label = "test_two_stack"

        def install_contract(self, conn):
            shared = conn.hardware[2]
            return (
                straight_screw_group("g_a", [conn.hardware[0]],
                                     conn.parts[0].id,
                                     stack=(shared.id,)),
                straight_screw_group("g_b", [conn.hardware[1]],
                                     conn.parts[0].id,
                                     stack=(shared.id,)),
            )

    a = DetailAssembly("ambig")
    p1 = a.add(Lumber("2x4", 4 * IN, name="plate"))
    p2 = a.add(Lumber("2x4", 4 * IN, name="other"), at=(0, 60, 0))
    s1 = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="sA"), at=(10, 0, 0))
    s2 = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="sB"), at=(20, 0, 0))
    shared = a.add(JoistHanger(1.5 * IN, 5.5 * IN, name="shared bracket"),
                   at=(0, 30, 0))
    conn = Connection(kind=_TwoStackType(), parts=[p1, p2],
                      hardware=[s1, s2, shared], label="ambiguous")
    with pytest.raises(ValueError, match="rides 2 role groups' stacks"):
        compile_connections(a, [conn])


# -- authored_sequence: stage edges, chains, and the merged cycle check --------


def _two_screwed_plates():
    a = DetailAssembly("stages")
    p1 = a.add(Lumber("2x4", 4 * IN, name="plate one"))
    m1 = a.add(Lumber("2x4", 4 * IN, name="member one"), at=(0, 60, 0))
    p2 = a.add(Lumber("2x4", 4 * IN, name="plate two"), at=(0, 200, 0))
    m2 = a.add(Lumber("2x4", 4 * IN, name="member two"), at=(0, 260, 0))
    s1 = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="screw one"),
               at=(50, 19, 88.9))
    s2 = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="screw two"),
               at=(50, 219, 88.9))
    cleat = connection_types.get("cleat_screwed")
    c1 = Connection(kind=cleat(n_screws=1), parts=[p1, m1], hardware=[s1],
                    label="joint one")
    c2 = Connection(kind=cleat(n_screws=1), parts=[p2, m2], hardware=[s2],
                    label="joint two")
    return a, c1, c2


def test_authored_stage_orders_drive_events_with_the_why_on_the_edge():
    a, c1, c2 = _two_screwed_plates()
    stages = (
        ResolvedStage(name="first", why="fixture order", connections=("joint one",)),
        ResolvedStage(name="second", why="after first", connections=("joint two",)),
    )
    g = _graph(a, [c1, c2], stages)
    d1 = Event("drive", "joint one", "cleat_screws")
    d2 = Event("drive", "joint two", "cleat_screws")
    assert g.precedes(d1, d2)
    authored = [e for e in g.edges if e.family == FAMILY_AUTHORED]
    assert [(e.a, e.b) for e in authored] == [(d1, d2)]
    assert "stage 'first' precedes stage 'second'" in authored[0].source
    assert "why: fixture order" in authored[0].source


def test_stages_in_different_chains_never_cross_order():
    """§3.2's honesty at the mechanism level: a site replays each fragment's
    stages under the fragment's own chain — stages of DIFFERENT chains must
    produce NO authored edge between them (cross-fragment order does not
    exist in v1; inventing it here would be a silent unsoundness)."""
    a, c1, c2 = _two_screwed_plates()
    stages = (
        ResolvedStage(name="first", why="w", chain="frag1",
                      connections=("joint one",)),
        ResolvedStage(name="second", why="w", chain="frag2",
                      connections=("joint two",)),
    )
    g = _graph(a, [c1, c2], stages)
    assert not [e for e in g.edges if e.family == FAMILY_AUTHORED]
    d1 = Event("drive", "joint one", "cleat_screws")
    d2 = Event("drive", "joint two", "cleat_screws")
    assert not g.precedes(d1, d2) and not g.precedes(d2, d1)


def test_cat_i_load_half_stage_contradicting_technique_is_a_cycle_error():
    """CAT-I's load-time half: an authored stage that places the hung
    member BEFORE the hanger's drives contradicts the type's own
    header-screws-before-hung technique edge — a loud
    :class:`EventOrderCycleError` naming BOTH claims and BOTH provenance
    families, so the author knows which claim to fix."""
    a, conn, (header, hung, hanger, hs, us) = _hanger_joint()
    stages = (
        ResolvedStage(name="member first", why="wrongly authored",
                      parts=(hung.id,)),
        ResolvedStage(name="then the hanger", why="contradicts the type",
                      connections=("hang",)),
    )
    with pytest.raises(EventOrderCycleError) as err:
        _graph(a, [conn], stages)
    msg = str(err.value)
    assert FAMILY_AUTHORED in msg and FAMILY_TECHNIQUE in msg
    assert "stage 'member first' precedes stage 'then the hanger'" in msg
    assert "installed_before" in msg
    assert "Fix the claim that is wrong" in msg


def test_f1_stage_cannot_silence_structural_necessity_member_after_drive():
    """Review-cpgcore F-1 (BLOCKING), pinned: the structural-necessity
    exception is scoped to TECHNIQUE edges only — an authored stage that
    orders a MEMBER's place event after its own connection's drive event
    must NOT suppress the derived presence edge (that would be a declared
    order silencing a derived check, §6 rule 1's forbidden waiver channel).
    Both edges stay in the merged graph and the load errors loudly, naming
    BOTH claims and BOTH provenance families."""
    a, c1, _c2 = _two_screwed_plates()
    member = c1.parts[1]
    stages = (
        ResolvedStage(name="drive first", why="wrongly authored",
                      connections=("joint one",)),
        ResolvedStage(name="member later", why="silencing attempt",
                      parts=(member.id,)),
    )
    with pytest.raises(EventOrderCycleError) as err:
        _graph(a, [c1], stages)
    msg = str(err.value)
    assert FAMILY_AUTHORED in msg and FAMILY_NECESSITY in msg
    assert "stage 'drive first' precedes stage 'member later'" in msg
    assert "must exist before its" in msg   # the necessity claim, on paper


def test_f1_interleave_variant_stage_vs_necessity_still_cycles():
    """Review-cpgcore F-1, construction 2: on a connection whose OWN chain
    threads through a member (``f1 -> member -> f2``, one role group — the
    rock anchor's shape), the third lift rule drops both technique
    directions (mid-event arrival), so structural necessity is the ONLY
    fact holding the member present at the drive. An authored stage
    ordering the member after the drive contradicts the type's own shipped
    chain knowledge — with the technique edges gone, the necessity edge is
    what must catch it: loud cycle error, both families named, never a
    quiet provably-later flip."""

    class _ChainThroughMember(ConnectionType):
        label = "test_chain_through_member"

        def edges(self, conn):
            s1, s2 = conn.hardware
            member = conn.parts[1]
            return [
                Edge(s1.id, member.id, "installed_before", conn.label),
                Edge(member.id, s2.id, "installed_before", conn.label),
            ]

        def install_contract(self, conn):
            return (straight_screw_group(
                "chain_screws", list(conn.hardware), conn.parts[0].id),)

    a = DetailAssembly("interleave-f1")
    base = a.add(Lumber("2x4", 4 * IN, name="base plate"))
    member = a.add(Lumber("2x4", 4 * IN, name="threaded member"),
                   at=(0, 60, 0))
    s1 = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="chain screw 1"),
               at=(10, 0, 0))
    s2 = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="chain screw 2"),
               at=(20, 0, 0))
    conn = Connection(kind=_ChainThroughMember(), parts=[base, member],
                      hardware=[s1, s2], label="chain joint")
    # sanity: without stages the interleave drop leaves exactly the
    # conservative necessity direction and loads cycle-free
    g = _graph(a, [conn])
    drive = Event("drive", "chain joint", "chain_screws")
    tech = {(e.a, e.b) for e in g.edges if e.family == FAMILY_TECHNIQUE}
    assert (drive, Event("place", member.id)) not in tech
    assert (Event("place", member.id), drive) not in tech
    assert (Event("place", member.id), drive) in {
        (e.a, e.b) for e in g.edges if e.family == FAMILY_NECESSITY}
    # the authored silencing attempt must cycle loudly
    stages = (
        ResolvedStage(name="drive first", why="wrongly authored",
                      connections=("chain joint",)),
        ResolvedStage(name="member later", why="contradicts the chain",
                      parts=(member.id,)),
    )
    with pytest.raises(EventOrderCycleError) as err:
        _graph(a, [conn], stages)
    msg = str(err.value)
    assert FAMILY_AUTHORED in msg and FAMILY_NECESSITY in msg


def test_stage_naming_unknown_connection_or_part_is_loud():
    a, c1, _c2 = _two_screwed_plates()
    with pytest.raises(ValueError, match="names no compiled connection"):
        _graph(a, [c1], (ResolvedStage(name="s", why="w",
                                       connections=("nope",)),))
    with pytest.raises(ValueError, match="names no built part"):
        _graph(a, [c1], (ResolvedStage(name="s", why="w",
                                       parts=("ghost-part",)),))


# -- +staging compiled surface ------------------------------------------------


def _compile_staging(text: str):
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_text

    return compile_spec(load_spec_text(text))


def test_specdetail_resolves_explicit_units_and_existing_context_to_built_ids():
    detail = _compile_staging("""
name: resolved staging
units: in
components:
  - {id: leg, type: lumber, params: {nominal: 2x4, length: 4}}
  - {id: rail, type: lumber, params: {nominal: 2x4, length: 4}}
  - {id: room, type: boulder, params: {width: 12, length: 12, depth: 4}}
roles:
  room: {role: existing, grounded_by: site}
sequence:
  subassemblies:
    - name: side
      parts: [leg, rail]
      why: Screw the side flat on the bench.
""")
    resolved = detail.resolved_staging()
    assert isinstance(resolved, ResolvedStaging)
    assert resolved.mode == "subassemblies"
    assert resolved.why == ""
    assert len(resolved.units) == 1
    assert isinstance(resolved.units[0], ResolvedUnit)
    by_name = {p.name: p.id for p in detail.build().parts}
    assert resolved.units[0].parts == (by_name["leg"], by_name["rail"])
    assert resolved.context_parts == frozenset({by_name["room"]})


def test_bench_then_set_resolves_to_one_unit_of_every_non_context_part():
    detail = _compile_staging("""
name: bench sugar
units: in
components:
  - {id: board, type: lumber, params: {nominal: 2x4, length: 4}}
  - {id: screw, type: structural_screw, params: {diameter: 0.16, length: 1.5}}
  - {id: sofa, type: boulder, params: {width: 12, length: 12, depth: 4}}
roles:
  sofa: {role: existing, grounded_by: site}
sequence:
  assembly:
    mode: bench_then_set
    why: Build the whole product away from the sofa.
""")
    resolved = detail.resolved_staging()
    by_name = {p.name: p.id for p in detail.build().parts}
    assert resolved.mode == "bench_then_set"
    assert resolved.why == "Build the whole product away from the sofa."
    assert len(resolved.units) == 1
    assert resolved.units[0].name == "whole detail"
    assert resolved.units[0].parts == (by_name["board"], by_name["screw"])
    assert resolved.context_parts == frozenset({by_name["sofa"]})


def test_repeat_template_unit_membership_expands_to_every_built_instance():
    detail = _compile_staging("""
name: repeat staging
units: in
components:
  - repeat: {var: i, count: 2}
    body:
      - id: 'leg_{i}'
        type: lumber
        params: {nominal: 2x4, length: 4}
sequence:
  subassemblies:
    - name: pair
      parts: ['leg_{i}']
      why: Both repeated legs form one bench unit.
""")
    resolved = detail.resolved_staging()
    assert resolved.units[0].parts == tuple(p.id for p in detail.build().parts)


def test_zero_instance_unit_member_is_a_loud_compile_error():
    detail = _compile_staging("""
name: zero staging
units: in
components:
  - repeat: {var: i, count: 0}
    body:
      - id: 'leg_{i}'
        type: lumber
        params: {nominal: 2x4, length: 4}
sequence:
  subassemblies:
    - name: empty after expansion
      parts: ['leg_{i}']
      why: Probe the zero-instance diagnostic.
""")
    with pytest.raises(ValueError, match="built no instance"):
        detail.resolved_staging()


def test_event_graph_defends_against_multi_membership_if_loader_is_bypassed():
    a, c1, _c2 = _two_screwed_plates()
    repeated = c1.parts[0].id
    staging = ResolvedStaging(
        mode="subassemblies", why="", context_parts=frozenset(),
        units=(
            ResolvedUnit("side a", "first claim", (repeated,)),
            ResolvedUnit("side b", "second claim", (repeated,)),
        ))
    with pytest.raises(ValueError, match="at most one subassembly") as err:
        _graph(a, [c1], staging=staging)
    assert "side a" in str(err.value) and "side b" in str(err.value)


def test_event_graph_defends_against_reserved_root_unit_if_loader_is_bypassed():
    a, c1, _c2 = _two_screwed_plates()
    staging = ResolvedStaging(
        mode="subassemblies", context_parts=frozenset(),
        units=(ResolvedUnit("root", "collides with frame sentinel",
                            tuple(p.id for p in c1.parts)),))
    with pytest.raises(ValueError, match="reserved.*root frame"):
        _graph(a, [c1], staging=staging)


def test_event_graph_defends_against_duplicate_unit_names_if_loader_is_bypassed():
    a, c1, c2 = _two_screwed_plates()
    staging = ResolvedStaging(
        mode="subassemblies", context_parts=frozenset(),
        units=(
            ResolvedUnit("side", "first", tuple(p.id for p in c1.parts)),
            ResolvedUnit("side", "second", tuple(p.id for p in c2.parts)),
        ))
    with pytest.raises(ValueError, match="duplicated.*unique"):
        _graph(a, [c1, c2], staging=staging)


def _two_bench_units_with_root_joint():
    a, c1, c2 = _two_screwed_plates()
    bridge_screw = a.add(
        StructuralScrew(0.19 * IN, 1.5 * IN, name="bridge screw"),
        at=(50, 100, 88.9))
    bridge = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=1),
        parts=[c1.parts[0], c2.parts[0]], hardware=[bridge_screw],
        label="root bridge")
    staging = ResolvedStaging(
        mode="subassemblies", context_parts=frozenset(),
        units=(
            ResolvedUnit("side a", "bench side A flat",
                         tuple(p.id for p in c1.parts)),
            ResolvedUnit("side b", "bench side B flat",
                         tuple(p.id for p in c2.parts)),
        ))
    return a, c1, c2, bridge, staging


def test_connections_scope_to_bench_only_when_all_members_share_one_unit():
    a, c1, c2, bridge, staging = _two_bench_units_with_root_joint()
    g = _graph(a, [c1, c2, bridge], staging=staging)
    d1 = Event("drive", "joint one", "cleat_screws")
    d2 = Event("drive", "joint two", "cleat_screws")
    root_drive = Event("drive", "root bridge", "cleat_screws")
    assert g.frame_of[d1] == "side a"
    assert g.frame_of[d2] == "side b"
    assert g.frame_of[root_drive] == "root"
    for pid in staging.units[0].parts:
        ev = g.event_of[pid]
        if ev.kind == "place":
            assert g.frame_of[ev] == "side a"


def test_r1_every_bench_event_precedes_its_join_without_ordering_other_units():
    a, c1, c2, bridge, staging = _two_bench_units_with_root_joint()
    g = _graph(a, [c1, c2, bridge], staging=staging)
    d1 = Event("drive", "joint one", "cleat_screws")
    d2 = Event("drive", "joint two", "cleat_screws")
    j1, j2 = Event("join", "side a"), Event("join", "side b")
    assert j1 in g.events and j2 in g.events
    assert g.precedes(d1, j1) and g.precedes(d2, j2)
    assert all(g.precedes(ev, j1) for ev in g.events
               if g.frame_of[ev] == "side a")
    assert all(g.precedes(ev, j2) for ev in g.events
               if g.frame_of[ev] == "side b")
    # Frame semantics do not invent a construction order between independent
    # bench units; declaration order is a presentation tie-breaker only.
    assert not g.precedes(d1, d2) and not g.precedes(d2, d1)
    r1 = [e for e in g.edges if e.family == FAMILY_STAGING and e.b == j1]
    assert r1 and all("bench events precede join" in e.source for e in r1)


def test_root_connection_uses_joins_as_member_presence_events():
    a, c1, c2, bridge, staging = _two_bench_units_with_root_joint()
    g = _graph(a, [c1, c2, bridge], staging=staging)
    root_drive = Event("drive", "root bridge", "cleat_screws")
    for unit in staging.units:
        join = Event("join", unit.name)
        assert g.precedes(join, root_drive)
        assert (join, root_drive) in {
            (e.a, e.b) for e in g.edges if e.family == FAMILY_NECESSITY}


def test_bench_frame_presence_excludes_every_nonmember_without_cross_order():
    a, c1, c2, bridge, staging = _two_bench_units_with_root_joint()
    g = _graph(a, [c1, c2, bridge], staging=staging)
    d1 = Event("drive", "joint one", "cleat_screws")
    opposite = c2.parts[0]
    decision = g.presence_at(d1, opposite.id)
    assert decision.state == "absent"
    assert decision.event == Event("join", "side b")
    assert decision.facts and decision.facts[0].family == FAMILY_STAGING
    assert "bench side A flat" in decision.facts[0].source
    assert not decision.declared_trust


def test_same_bench_hardware_uses_reachability_instead_of_false_absence():
    """Hardware inherits its connection drive's frame even when an explicit
    subassembly lists only structural members. Another same-unit fastener is
    therefore internal work, not an absent nonmember that staging may clear."""
    a, c1, c2 = _two_screwed_plates()
    staging = ResolvedStaging(
        mode="subassemblies",
        units=(ResolvedUnit(
            "case", "assemble both joints on one bench",
            tuple(p.id for c in (c1, c2) for p in c.parts)),))
    g = _graph(a, [c1, c2], staging=staging)
    drive = Event("drive", "joint one", "cleat_screws")
    other_hardware = c2.hardware[0]
    own_event = g.event_of[other_hardware.id]
    assert g.frame_of[drive] == g.frame_of[own_event] == "case"
    assert other_hardware.id not in g.unit_of
    decision = g.presence_at(drive, other_hardware.id)
    assert decision.state == "unordered"
    assert not decision.facts


def test_hardware_cannot_be_authored_into_a_unit_other_than_its_drive_frame():
    a, c1, c2 = _two_screwed_plates()
    misplaced = c2.hardware[0]
    staging = ResolvedStaging(
        mode="subassemblies",
        units=(
            ResolvedUnit(
                "side a", "first unit",
                tuple(p.id for p in c1.parts) + (misplaced.id,)),
            ResolvedUnit(
                "side b", "the hardware's actual connection unit",
                tuple(p.id for p in c2.parts)),
        ))
    with pytest.raises(ValueError, match="hardware.*side a.*side b") as err:
        _graph(a, [c1, c2], staging=staging)
    assert misplaced.name in str(err.value)
    assert "drive frame" in str(err.value)


def test_bench_then_set_context_absence_is_explicit_declared_trust():
    a, c1, _c2 = _two_screwed_plates()
    context = a.add(Lumber("2x4", 4 * IN, name="sofa context"),
                    at=(0, 500, 0))
    unit_parts = tuple(p.id for p in a.parts if p.id != context.id)
    staging = ResolvedStaging(
        mode="bench_then_set", why="build away from the sofa",
        context_parts=frozenset({context.id}),
        units=(ResolvedUnit("whole detail", "build away from the sofa",
                            unit_parts),))
    g = _graph(a, [c1], staging=staging)
    drive = Event("drive", "joint one", "cleat_screws")
    decision = g.presence_at(drive, context.id)
    assert decision.state == "absent" and decision.declared_trust
    assert "DECLARED TRUST" in decision.facts[0].source
    assert "build away from the sofa" in decision.facts[0].source


def test_bench_then_set_context_is_present_for_root_work_after_whole_unit_join():
    """A stage may not re-author a context body's ordinary place event after
    root work and thereby turn context into a false later-arrival clear. Under
    bench_then_set, the whole-detail join governs context presence at root."""
    a, bench, _unused = _two_screwed_plates()
    anchor = a.add(Lumber("2x4", 4 * IN, name="anchored context"),
                   at=(0, 500, 0))
    free_context = a.add(Lumber("2x4", 4 * IN, name="free context blocker"),
                         at=(0, 700, 0))
    root_screw = a.add(
        StructuralScrew(0.19 * IN, 1.5 * IN, name="root screw"),
        at=(50, 500, 88.9))
    root_conn = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=1),
        parts=[bench.parts[0], anchor], hardware=[root_screw],
        label="root work")
    unit_parts = tuple(
        p.id for p in a.parts if p not in (anchor, free_context))
    staging = ResolvedStaging(
        mode="bench_then_set", why="set the completed unit onto its context",
        context_parts=frozenset({anchor.id, free_context.id}),
        units=(ResolvedUnit("whole detail", "assemble away from context",
                            unit_parts),))
    stages = (
        ResolvedStage(name="root connection", why="real root work",
                      connections=("root work",)),
        ResolvedStage(name="fictional late context", why="must not win",
                      parts=(free_context.id,)),
    )
    g = _graph(a, [bench, root_conn], stages=stages, staging=staging)
    drive = Event("drive", "root work", "cleat_screws")
    assert g.precedes(g.join_of["whole detail"], drive)
    assert g.precedes(drive, g.event_of[free_context.id])
    decision = g.presence_at(drive, free_context.id)
    assert decision.state == "present"
    assert decision.facts and decision.facts[0].family == FAMILY_STAGING
    assert "whole-detail join" in decision.facts[0].source


def test_bench_then_set_root_hardware_keeps_its_drive_presence_event():
    """The whole-detail sugar lists every non-context component, but hardware
    for post-join root work arrives at its own root drive, not at the unit join.
    Mapping it to the join would make later hardware falsely present early."""
    a, bench, _unused = _two_screwed_plates()
    context_one = a.add(
        Lumber("2x4", 4 * IN, name="context one"), at=(0, 500, 0))
    context_two = a.add(
        Lumber("2x4", 4 * IN, name="context two"), at=(0, 700, 0))
    screw_one = a.add(
        StructuralScrew(0.19 * IN, 1.5 * IN, name="root screw one"),
        at=(50, 500, 88.9))
    screw_two = a.add(
        StructuralScrew(0.19 * IN, 1.5 * IN, name="root screw two"),
        at=(50, 700, 88.9))
    root_one = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=1),
        parts=[bench.parts[0], context_one], hardware=[screw_one],
        label="root one")
    root_two = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=1),
        parts=[bench.parts[0], context_two], hardware=[screw_two],
        label="root two")
    contexts = frozenset({context_one.id, context_two.id})
    staging = ResolvedStaging(
        mode="bench_then_set", why="set before root work",
        context_parts=contexts,
        units=(ResolvedUnit(
            "whole detail", "synthetic all-non-context unit",
            tuple(p.id for p in a.parts if p.id not in contexts)),))
    stages = (
        ResolvedStage(name="first root drive", why="declared first",
                      connections=("root one",)),
        ResolvedStage(name="second root drive", why="declared second",
                      connections=("root two",)),
    )
    g = _graph(
        a, [bench, root_one, root_two], stages=stages, staging=staging)
    drive_one = Event("drive", "root one", "cleat_screws")
    drive_two = Event("drive", "root two", "cleat_screws")
    assert g.frame_of[drive_one] == g.frame_of[drive_two] == "root"
    assert g.event_of[screw_two.id] == drive_two
    decision = g.presence_at(drive_one, screw_two.id)
    assert decision.state == "absent"
    assert decision.event == drive_two
    assert decision.facts and decision.facts[0].family == FAMILY_AUTHORED


def test_explicit_in_situ_context_is_present_and_undeclared_is_unordered():
    a, c1, _c2 = _two_screwed_plates()
    context = a.add(Lumber("2x4", 4 * IN, name="context"), at=(0, 500, 0))
    drive = Event("drive", "joint one", "cleat_screws")
    in_situ = ResolvedStaging(
        mode="in_situ", why="build on the context",
        context_parts=frozenset({context.id}))
    declared_graph = _graph(a, [c1], staging=in_situ)
    decision = declared_graph.presence_at(drive, context.id)
    assert decision.state == "present"
    assert decision.facts[0].family == FAMILY_STAGING
    assert "build on the context" in decision.facts[0].source

    undeclared_graph = _graph(a, [c1])
    assert undeclared_graph.presence_at(drive, context.id).state == "unordered"


# -- canonical linearization + reader steps (§5.1; amendment 5 vocabulary) -----


def test_linearization_is_deterministic_and_respects_the_partial_order():
    a, c1, c2 = _two_screwed_plates()
    stages = (
        ResolvedStage(name="first", why="w", connections=("joint two",)),
        ResolvedStage(name="second", why="w", connections=("joint one",)),
    )
    g = _graph(a, [c1, c2], stages)
    order = linearize(g)
    assert order == linearize(g)   # byte-stable
    pos = {ev: i for i, ev in enumerate(order)}
    for e in g.edges:
        assert pos[e.a] < pos[e.b]
    # the authored stage order decides the tie between the two drives
    assert pos[Event("drive", "joint two", "cleat_screws")] < \
        pos[Event("drive", "joint one", "cleat_screws")]


def test_reader_steps_group_by_stage_else_per_connection_unit():
    """§5.1's grouping, pinned: a staged connection presents inside its
    STAGE's step (the authored claim + why visible on the step), an
    unstaged connection is its own per-connection install unit, and a
    member's place folds into the first connection that consumes it. A
    ReaderStep is a presentation unit — never an authored stage; the two
    are distinct types by construction (owner amendment 5)."""
    a, c1, c2 = _two_screwed_plates()
    stages = (ResolvedStage(name="lead", why="declared build strategy",
                            connections=("joint one",)),)
    g = _graph(a, [c1, c2], stages)
    steps = derive_reader_steps(g)
    assert [s.title for s in steps] == [
        "stage 'lead' (declared order)", "install joint two"]
    staged, unstaged = steps
    assert staged.stage is not None and staged.stage.why == \
        "declared build strategy"
    assert staged.connections == ("joint one",)
    # plate one / member one fold into their first (only) consumer's step
    p_ids = set(staged.parts_placed)
    assert {g.part_names[p] for p in p_ids} == {"plate one", "member one"}
    assert unstaged.stage is None
    assert {g.part_names[p] for p in unstaged.parts_placed} == \
        {"plate two", "member two"}


def test_unordered_parts_are_reported_not_positioned():
    a, c1, _c2 = _two_screwed_plates()
    ctx = a.add(Lumber("2x4", 4 * IN, name="context body"), at=(0, 500, 0))
    g = _graph(a, [c1])
    assert ctx.id in unordered_parts(g)
    steps = derive_reader_steps(g)
    for s in steps:
        assert ctx.id not in s.parts_placed


def test_build_sequence_model_projects_reader_names_for_placed_and_loose_parts():
    from detailgen.validation.build_sequence import build_sequence_model

    detail = _compile_staging("""
name: reader sequence projection
units: in
components:
  - id: staged
    type: lumber
    name: staged rail +X
    reader_name: Staged rail
    params: {nominal: 2x4, length: 4}
  - id: loose
    type: lumber
    name: loose panel -X
    reader_name: Loose panel
    params: {nominal: 2x4, length: 4}
sequence:
  stages:
    - name: prepare staged rail
      parts: [staged]
      why: Prepare the staged rail first.
""")
    detail.validate()

    steps, loose = build_sequence_model(detail)
    assert [name for step in steps for name, _bom, _fab in step["places"]] == [
        "Staged rail"
    ]
    assert loose == ("Loose panel",)

    graph = detail._connection_checks.event_graph
    by_id = {part.id: part.name for part in detail.assembly.parts}
    assert graph.part_names == by_id


def test_build_sequence_model_reuses_projection_ordinals_for_duplicate_names():
    from detailgen.validation.build_sequence import build_sequence_model

    detail = _compile_staging("""
name: reader sequence ordinal projection
units: in
components:
  - id: first
    type: lumber
    name: staged rail +X
    reader_name: Registration rail
    params: {nominal: 2x4, length: 4}
  - id: second
    type: lumber
    name: staged rail -X
    reader_name: Registration rail
    params: {nominal: 2x4, length: 4}
sequence:
  stages:
    - name: prepare rails
      parts: [first, second]
      why: Prepare both rails first.
""")
    detail.validate()

    steps, loose = build_sequence_model(detail)

    assert [name for step in steps for name, _bom, _fab in step["places"]] == [
        "Registration rail (1 of 2)",
        "Registration rail (2 of 2)",
    ]
    assert loose == ()


def test_reader_steps_group_bench_units_then_visible_joins_without_graph_edges():
    """Presentation may choose declaration order for independent units, but
    the graph must remain partially ordered: two bench steps, then two visible
    joins, with no invented cross-unit event edge."""
    a, c1, c2 = _two_screwed_plates()
    staging = ResolvedStaging(
        mode="subassemblies",
        units=(
            ResolvedUnit("side one", "clamp side one square",
                         tuple(p.id for p in c1.parts)),
            ResolvedUnit("side two", "clamp side two square",
                         tuple(p.id for p in c2.parts)),
        ))
    g = _graph(a, [c1, c2], staging=staging)
    steps = derive_reader_steps(g)
    assert [s.title for s in steps] == [
        "bench side one", "bench side two",
        "set side one in place", "set side two in place"]
    assert [s.unit.name if s.unit else None for s in steps] == [
        "side one", "side two", "side one", "side two"]
    assert [s.joins for s in steps] == [(), (), ("side one",), ("side two",)]
    assert steps[0].connections == ("joint one",)
    assert steps[1].connections == ("joint two",)
    assert not g.precedes(g.join_of["side one"],
                          next(iter(g.drives_of["joint two"])))
    assert not g.precedes(g.join_of["side two"],
                          next(iter(g.drives_of["joint one"])))


def test_reader_steps_preserve_authored_stage_order_inside_a_bench_unit():
    """A bench frame is a presence boundary, not permission to erase finer
    authored order. Stage buckets inside the unit must retain the graph order,
    the declared rationale, and the connection each stage owns."""
    a, c1, c2 = _two_screwed_plates()
    staging = ResolvedStaging(
        mode="subassemblies",
        units=(ResolvedUnit(
            "case", "assemble both joints on the bench",
            tuple(p.id for c in (c1, c2) for p in c.parts)),))
    stages = (
        ResolvedStage(name="joint two first", why="declared first",
                      connections=("joint two",),
                      parts=(c2.parts[0].id,)),
        ResolvedStage(name="joint one second", why="declared second",
                      connections=("joint one",)),
    )
    g = _graph(a, [c1, c2], stages=stages, staging=staging)
    assert g.precedes(Event("drive", "joint two", "cleat_screws"),
                      Event("drive", "joint one", "cleat_screws"))
    steps = derive_reader_steps(g)
    assert [s.title for s in steps] == [
        "bench case",
        "bench case: stage 'joint two first' (declared order)",
        "bench case: stage 'joint one second' (declared order)",
        "set case in place",
    ]
    assert [s.connections for s in steps] == [
        (), ("joint two",), ("joint one",), ()]
    assert c2.parts[0].id not in steps[0].parts_placed
    assert c2.parts[0].id in steps[1].parts_placed
    assert [s.stage.why for s in steps[1:3]] == [
        "declared first", "declared second"]


def test_reader_steps_keep_a_part_only_stage_inside_a_bench_unit():
    a, c1, _c2 = _two_screwed_plates()
    staging = ResolvedStaging(
        mode="subassemblies",
        units=(ResolvedUnit(
            "case", "assemble the joint on the bench",
            tuple(p.id for p in c1.parts)),))
    prepared = c1.parts[0].id
    stages = (ResolvedStage(
        name="prepare plate", why="mark the plate before assembly",
        parts=(prepared,)),)
    g = _graph(a, [c1], stages=stages, staging=staging)
    steps = derive_reader_steps(g)
    stage_steps = [s for s in steps if s.stage is not None]
    assert len(stage_steps) == 1
    assert stage_steps[0].title == \
        "bench case: stage 'prepare plate' (declared order)"
    assert stage_steps[0].stage.why == "mark the plate before assembly"
    assert stage_steps[0].parts_placed == (prepared,)
    assert prepared not in next(
        s for s in steps if s.title == "bench case").parts_placed


# -- §4.3 rung guard: SEQUENCE-PROVEN is claimed NOWHERE -----------------------


def test_sequence_proven_is_claimed_nowhere_in_source_strings():
    """Grep-enforceable rung ceiling (design §4.3, owner amendment 1): no
    emitted string in ``src/`` may claim the SEQUENCE-PROVEN rung. The
    token may appear in docstrings/comments (describing the ladder) and in
    strings that explicitly RESERVE the rung or negate the claim — nothing
    else. AST-walked so a new emitter cannot slip a claim past a plain
    grep's docstring noise."""
    src = Path(__file__).resolve().parents[1] / "src"
    offenders: list[str] = []
    for py in sorted(src.rglob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                body = getattr(node, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(
                        body[0].value, ast.Constant) and isinstance(
                        body[0].value.value, str):
                    docstrings.add(id(body[0].value))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)):
                continue
            if id(node) in docstrings:
                continue
            if "SEQUENCE-PROVEN" not in node.value:
                continue
            if "RESERVED" in node.value or "claims it nowhere" in node.value:
                continue  # describing/reserving the rung, not claiming it
            offenders.append(f"{py.relative_to(src)}:{node.lineno}: "
                             f"{node.value[:80]!r}")
    assert not offenders, (
        "SEQUENCE-PROVEN may not be claimed by any emitted string in v1 "
        "(design §4.3) — describe the rung as RESERVED or negate the "
        "claim:\n" + "\n".join(offenders))
