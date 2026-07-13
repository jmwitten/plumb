"""Runtime/graph acceptance probes for the STEPDOC +process increment.

These fixtures stay synthetic and small: they pin the typed cure fact, the
two process-order edges, runtime capability defense, fragment isolation, and
the axis-3 falsifiability direction without depending on the caddy authoring
or reader surfaces (Task 3).
"""

from __future__ import annotations

import pytest

from detailgen.core import IN
from detailgen.assemblies import (
    Connection, ConnectionType, DetailAssembly, compile_connections,
    connection_types,
)
from detailgen.assemblies import event_graph as eg
from detailgen.assemblies.connection import Glued
from detailgen.assemblies.installation import straight_screw_group
from detailgen.components import Lumber, StructuralScrew
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text


def _boards(name="process"):
    assembly = DetailAssembly(name)
    lower = assembly.add(Lumber("2x4", 12 * IN, name="lower"))
    upper = assembly.add(
        Lumber("2x4", 12 * IN, name="upper"), at=(0, 0, 88.9))
    return assembly, lower, upper


def _glue(assembly=None, *, label="glue", process=()):
    if assembly is None:
        assembly, lower, upper = _boards()
    else:
        lower, upper = assembly.parts[:2]
    return assembly, Connection(
        kind=Glued(), parts=[lower, upper], label=label,
        assumptions=["Long-grain mating faces; capacity not analyzed."],
        process=process,
    )


def _cure_ref(source="glue"):
    return eg.ResolvedProcessRef(kind="cure", connection=source)


def _after(target="target", source="glue", *, chain="",
           why="Preserve the registration datum while driving screws."):
    return eg.ResolvedAfter(
        connection=target, after=(_cure_ref(source),), why=why, chain=chain)


def test_runtime_process_fact_is_a_typed_open_kind_value():
    fact = eg.ProcessFact(
        kind="cure", instructions=("Follow the selected label.",),
        completion="selected_label_full_cure", why="Adhesive bond.",
        provenance="authored_process_fact",
    )
    assert fact.kind == "cure"
    assert fact.instructions == ("Follow the selected label.",)
    assert fact.completion == "selected_label_full_cure"
    assert fact.provenance == "authored_process_fact"


def test_connection_type_default_has_no_process_capability_or_events():
    assembly, lower, upper = _boards()
    conn = Connection(
        kind=ConnectionType(), parts=[lower, upper], label="plain")
    assert conn.kind.supported_process_kinds() == frozenset()
    assert conn.kind.process_events(conn) == ()


def test_glued_default_cure_fact_is_safe_label_driven_and_duration_free():
    _assembly, conn = _glue()
    assert conn.kind.supported_process_kinds() == frozenset({"cure"})
    (fact,) = conn.kind.process_events(conn)
    assert fact.kind == "cure"
    assert fact.provenance == "connectiontype_default"
    assert fact.completion == "selected_label_full_cure"
    rendered = " ".join((*fact.instructions, fact.why)).lower()
    assert "selected adhesive label" in rendered
    assert "actual shop conditions" in rendered
    assert "full-cure/full-strength" in rendered
    assert not any(token in rendered for token in
                   ("24 hour", "24-hour", "30 minute", "60 minute"))


_AUTHORED_GLUE = """
name: authored process
units: in
components:
  - {id: lower, type: lumber, params: {nominal: 2x4, length: 12}}
  - id: upper
    type: lumber
    params: {nominal: 2x4, length: 12}
    place: {raw: {at: [0, 0, 3.5]}}
connections:
  - type: glued
    label: glue
    parts: [lower, upper]
    process:
      cure:
        instructions:
          - Spread the selected adhesive on both prepared mating faces.
          - Maintain the label-required fixture state.
        completion: selected_label_full_cure
        why: This project selects an adhesive bond for the mating plane.
"""


def test_compiler_hands_authored_process_fact_to_runtime_connection():
    detail = compile_spec(load_spec_text(_AUTHORED_GLUE))
    (conn,) = detail.connections()
    assert len(conn.process) == 1
    fact = conn.process[0]
    assert isinstance(fact, eg.ProcessFact)
    assert fact.provenance == "authored_process_fact"
    assert fact.instructions[0].startswith("Spread the selected adhesive")
    assert conn.kind.process_events(conn) == (fact,)


def test_detail_validation_threads_resolved_after_into_the_graph():
    raw = _AUTHORED_GLUE + """
sequence:
  after:
    - connection: glue
      after: [{cure: glue}]
      why: Deliberate self-contradiction proves the lifecycle consumed this.
"""
    detail = compile_spec(load_spec_text(raw))
    with pytest.raises(eg.EventOrderCycleError, match="process point constraint"):
        detail.validate()


def test_semantics_asks_registered_capability_not_the_glued_display_key(
        monkeypatch):
    class _CurableTest(ConnectionType):
        label = "not_glued_by_name"

        @classmethod
        def supported_process_kinds(cls):
            return frozenset({"cure"})

        def process_events(self, conn):
            return tuple(conn.process)

        def install_contract(self, conn):
            return ()

    monkeypatch.setitem(
        connection_types._entries, "curable_test", _CurableTest)
    raw = _AUTHORED_GLUE.replace("type: glued", "type: curable_test")
    detail = compile_spec(load_spec_text(raw))
    (conn,) = detail.connections()
    assert conn.kind.process_events(conn)[0].kind == "cure"


def test_glued_process_event_and_derived_bond_before_cure_fact():
    assembly, conn = _glue()
    checks = compile_connections(assembly, [conn])
    graph = checks.event_graph
    bond = eg.Event("drive", "glue", "")
    cure = eg.Event("process", "glue", "cure")

    assert graph.processes_of == {"glue": (cure,)}
    assert graph.process_facts[cure].provenance == "connectiontype_default"
    assert cure in graph.events
    assert graph.describe(cure) == "process(glue, cure)"
    assert graph.frame_of[bond] == graph.frame_of[cure] == "root"
    edge = next(e for e in graph.edges if e.a == bond and e.b == cure)
    assert edge.family == eg.FAMILY_NECESSITY
    assert "bond precedes its own cure" in edge.source
    assert graph.precedes(bond, cure)

    fact = next(f for f in checks.derived
                if f.rule == "Glued.process_events")
    assert "drive(glue, install)" in fact.fact
    assert "process(glue, cure)" in fact.fact
    assert fact.confidence == "inferred"
    assert fact.source_type == "verified_heuristic"


class _TwoRoleTarget(ConnectionType):
    label = "two_role_target"

    def install_contract(self, conn):
        return (
            straight_screw_group(
                "left_screws", [conn.hardware[0]], conn.parts[0].id),
            straight_screw_group(
                "right_screws", [conn.hardware[1]], conn.parts[0].id),
        )


def _glue_and_target():
    assembly, lower, upper = _boards("point-constraint")
    plate = assembly.add(
        Lumber("2x4", 12 * IN, name="target plate"), at=(0, 300, 0))
    mate = assembly.add(
        Lumber("2x4", 12 * IN, name="target mate"), at=(0, 400, 0))
    screws = [
        assembly.add(
            StructuralScrew(0.19 * IN, 1.5 * IN, name=f"screw {i}"),
            at=(40 + i * 40, 300, 88.9))
        for i in range(2)
    ]
    glue = Connection(
        kind=Glued(), parts=[lower, upper], label="glue",
        assumptions=["Long-grain mating faces; capacity not analyzed."])
    target = Connection(
        kind=_TwoRoleTarget(), parts=[plate, mate], hardware=screws,
        label="target")
    return assembly, glue, target


def test_authored_cure_constraint_gates_every_target_role_group_with_why():
    assembly, glue, target = _glue_and_target()
    claim = _after(why="Keep the datum fixed until both screw groups drive.")
    checks = compile_connections(
        assembly, [glue, target], after=(claim,))
    graph = checks.event_graph
    cure = eg.Event("process", "glue", "cure")
    target_drives = graph.drives_of["target"]

    assert checks.after == (claim,)
    assert graph.constraints == (claim,)
    assert len(target_drives) == 2
    authored = [e for e in graph.edges
                if e.family == eg.FAMILY_AUTHORED and e.a == cure]
    assert [(e.a, e.b) for e in authored] == [
        (cure, target_drives[0]), (cure, target_drives[1])]
    assert all("Keep the datum fixed" in e.source for e in authored)

    facts = [f for f in checks.derived if f.rule == "sequence.after"]
    assert len(facts) == 2
    assert all(f.confidence == "official" for f in facts)
    assert all(f.source_type == "authoritative" for f in facts)
    assert all(f.assumptions == (claim.why,) for f in facts)


def test_process_constraint_cycle_names_both_events_and_provenance_families():
    assembly, glue = _glue()
    with pytest.raises(eg.EventOrderCycleError) as err:
        compile_connections(
            assembly, [glue], after=(_after(target="glue"),))
    message = str(err.value)
    assert "drive(glue, install)" in message
    assert "process(glue, cure)" in message
    assert eg.FAMILY_NECESSITY in message
    assert eg.FAMILY_AUTHORED in message
    assert "Preserve the registration datum" in message
    assert "point constraint" in message


def test_runtime_rejects_unknown_target_and_source_without_display_guessing():
    assembly, glue, target = _glue_and_target()
    with pytest.raises(ValueError, match="target.*missing.*no compiled"):
        compile_connections(
            assembly, [glue, target],
            after=(_after(target="missing"),))
    with pytest.raises(ValueError, match="cure.*target.*does not produce"):
        compile_connections(
            assembly, [glue, target],
            after=(_after(source="target"),))


def test_runtime_confirms_actual_event_not_only_claimed_capability():
    class _CapabilityWithoutFact(ConnectionType):
        @classmethod
        def supported_process_kinds(cls):
            return frozenset({"cure"})

        def install_contract(self, conn):
            return ()

    assembly, glue, target = _glue_and_target()
    lying_source = Connection(
        kind=_CapabilityWithoutFact(), parts=glue.parts,
        label="claimed capability")
    with pytest.raises(ValueError, match="supports.*cure.*produced no"):
        compile_connections(
            assembly, [lying_source, target],
            after=(_after(source="claimed capability"),))


def test_runtime_rejects_authored_fact_the_type_cannot_produce():
    assembly, lower, upper = _boards()
    fact = eg.ProcessFact(
        kind="cure", instructions=("wait",),
        completion="selected_label_full_cure", why="test",
        provenance="authored_process_fact")
    conn = Connection(
        kind=ConnectionType(), parts=[lower, upper], label="plain",
        process=(fact,))
    with pytest.raises(ValueError, match="plain.*authored.*cure.*not supported"):
        compile_connections(assembly, [conn])


def test_runtime_rejects_forged_process_provenance():
    assembly, lower, upper = _boards()
    forged = eg.ProcessFact(
        kind="cure", instructions=("wait",),
        completion="selected_label_full_cure", why="test",
        provenance="pretend_authoritative")
    conn = Connection(
        kind=Glued(), parts=[lower, upper], label="forged glue",
        process=(forged,))
    with pytest.raises(ValueError, match="forged glue.*process provenance"):
        compile_connections(assembly, [conn])


def test_runtime_rejects_connection_type_rewriting_authored_process_fact():
    class _RewritesAuthored(ConnectionType):
        @classmethod
        def supported_process_kinds(cls):
            return frozenset({"cure"})

        def process_events(self, conn):
            return (eg.ProcessFact(
                kind="cure", instructions=("silently changed",),
                completion="selected_label_full_cure", why="changed why",
                provenance="authored_process_fact"),)

        def install_contract(self, conn):
            return ()

    assembly, lower, upper = _boards()
    authored = eg.ProcessFact(
        kind="cure", instructions=("author instruction",),
        completion="selected_label_full_cure", why="author why",
        provenance="authored_process_fact")
    conn = Connection(
        kind=_RewritesAuthored(), parts=[lower, upper], label="rewriter",
        process=(authored,))
    with pytest.raises(ValueError, match="rewriter.*changed authored.*cure"):
        compile_connections(assembly, [conn])


def test_process_constraints_cannot_cross_their_composed_fragment_chain():
    assembly, glue, target = _glue_and_target()
    fragments = {"glue": "left", "target": "right"}
    with pytest.raises(ValueError, match="chain 'right'.*glue.*left"):
        compile_connections(
            assembly, [glue, target], fragments=fragments,
            after=(_after(chain="right"),))
    with pytest.raises(ValueError, match="target.*right.*chain 'left'"):
        compile_connections(
            assembly, [glue, target], fragments=fragments,
            after=(_after(chain="left"),))

    local_fragments = {"glue": "left", "target": "left"}
    checks = compile_connections(
        assembly, [glue, target], fragments=local_fragments,
        after=(_after(chain="left"),))
    authored = [edge for edge in checks.event_graph.edges
                if edge.family == eg.FAMILY_AUTHORED]
    assert authored
    assert all(edge.a.subject == "glue" and edge.b.subject == "target"
               for edge in authored)


def test_process_linearization_is_connection_order_then_process_kind():
    assembly = DetailAssembly("process-order")
    boards = [
        assembly.add(
            Lumber("2x4", 12 * IN, name=f"board {i}"), at=(0, i * 100, 0))
        for i in range(4)
    ]
    first = Connection(
        kind=Glued(), parts=boards[:2], label="first glue")
    second = Connection(
        kind=Glued(), parts=boards[2:], label="second glue")
    graph = compile_connections(
        assembly, [first, second]).event_graph
    order = eg.linearize(graph)
    assert order == eg.linearize(graph)
    assert order.index(eg.Event("process", "first glue", "cure")) < \
        order.index(eg.Event("process", "second glue", "cure"))
