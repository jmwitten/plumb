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
    FAMILY_AUTHORED, FAMILY_NECESSITY, FAMILY_TECHNIQUE, Event,
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
