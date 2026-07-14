"""Runtime/graph acceptance probes for the STEPDOC +process increment.

These fixtures stay synthetic and small: they pin the typed cure fact, the
two process-order edges, runtime capability defense, fragment isolation,
axis-3 falsifiability, and the Task-3 reader-process boundary independently
from the shipped caddy authoring.
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
from detailgen.spec.semantics import SemanticError


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


def test_unknown_type_with_authored_process_keeps_registry_teaching_error():
    raw = _AUTHORED_GLUE.replace("type: glued", "type: gluud")
    with pytest.raises(SemanticError) as err:
        compile_spec(load_spec_text(raw))
    message = str(err.value)
    assert "unknown connection type 'gluud'" in message
    assert "known connection types" in message
    assert "glued" in message
    assert "does not support" not in message


def test_unknown_after_source_type_keeps_registry_teaching_error():
    raw = """
name: unknown process source
units: in
components:
  - {id: a, type: lumber, params: {nominal: 2x4, length: 12}}
  - {id: b, type: lumber, params: {nominal: 2x4, length: 12}}
  - {id: c, type: lumber, params: {nominal: 2x4, length: 12}}
connections:
  - {type: gluud, label: mystery source, parts: [a, b]}
  - {type: glued, label: target, parts: [b, c]}
sequence:
  after:
    - connection: target
      after: [{cure: mystery source}]
      why: The source process must finish before the target starts.
"""
    with pytest.raises(SemanticError) as err:
        compile_spec(load_spec_text(raw))
    message = str(err.value)
    assert "unknown connection type 'gluud'" in message
    assert "known connection types" in message
    assert "glued" in message
    assert "does not support" not in message


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


def test_runtime_rejects_type_forging_an_unauthored_process_fact():
    class _ForgesAuthored(ConnectionType):
        @classmethod
        def supported_process_kinds(cls):
            return frozenset({"cure"})

        def process_events(self, conn):
            return (eg.ProcessFact(
                kind="cure", instructions=("wait",),
                completion="selected_label_full_cure", why="forged why",
                provenance="authored_process_fact"),)

        def install_contract(self, conn):
            return ()

    assembly, lower, upper = _boards()
    conn = Connection(
        kind=_ForgesAuthored(), parts=[lower, upper], label="forger")
    with pytest.raises(
            ValueError, match="forger.*connectiontype_default"):
        compile_connections(assembly, [conn])


def test_runtime_rejects_duplicate_after_targets_and_names_both_whys():
    assembly, glue, target = _glue_and_target()
    first = _after(why="First authored rationale.")
    second = _after(why="Second conflicting rationale.")
    with pytest.raises(ValueError) as err:
        compile_connections(assembly, [glue, target], after=(first, second))
    message = str(err.value)
    assert "duplicate" in message
    assert "target" in message
    assert "First authored rationale." in message
    assert "Second conflicting rationale." in message


def test_runtime_rejects_duplicate_process_refs_in_one_after_claim():
    assembly, glue, target = _glue_and_target()
    duplicate = eg.ResolvedAfter(
        connection="target",
        after=(_cure_ref("glue"), _cure_ref("glue")),
        why="One prerequisite must be declared once.",
    )
    with pytest.raises(
            ValueError, match="duplicate.*cure.*glue.*target"):
        compile_connections(assembly, [glue, target], after=(duplicate,))


@pytest.mark.parametrize("bad_why", ["", " \t", 42])
def test_runtime_rejects_blank_or_non_string_after_why(bad_why):
    assembly, glue, target = _glue_and_target()
    claim = eg.ResolvedAfter(
        connection="target", after=(_cure_ref("glue"),), why=bad_why)

    with pytest.raises(ValueError) as err:
        compile_connections(assembly, [glue, target], after=(claim,))

    message = str(err.value)
    assert "sequence.after" in message
    assert "target" in message
    assert "why" in message
    assert "non-blank string" in message


def test_runtime_rejects_after_claim_without_a_process_prerequisite():
    assembly, glue, target = _glue_and_target()
    claim = eg.ResolvedAfter(
        connection="target", after=(), why="A rationale cannot add an edge.")

    with pytest.raises(ValueError) as err:
        compile_connections(assembly, [glue, target], after=(claim,))

    message = str(err.value)
    assert "sequence.after" in message
    assert "target" in message
    assert "after" in message
    assert "at least one" in message


def test_runtime_rejects_blank_after_target_connection():
    assembly, glue, target = _glue_and_target()
    claim = eg.ResolvedAfter(
        connection=" \t", after=(_cure_ref("glue"),),
        why="A blank target cannot receive the process edge.")

    with pytest.raises(ValueError) as err:
        compile_connections(assembly, [glue, target], after=(claim,))

    message = str(err.value)
    assert "sequence.after" in message
    assert "target connection" in message
    assert "non-blank string" in message


@pytest.mark.parametrize(
    ("ref", "field"),
    [
        (eg.ResolvedProcessRef(kind=" ", connection="glue"), "kind"),
        (eg.ResolvedProcessRef(kind="cure", connection=" \t"),
         "source connection"),
    ],
)
def test_runtime_rejects_blank_process_reference_fields(ref, field):
    assembly, glue, target = _glue_and_target()
    claim = eg.ResolvedAfter(
        connection="target", after=(ref,),
        why="Only a named typed source can gate the target.")

    with pytest.raises(ValueError) as err:
        compile_connections(assembly, [glue, target], after=(claim,))

    message = str(err.value)
    assert "sequence.after" in message
    assert "target" in message
    assert field in message
    assert "non-blank string" in message


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


def test_reader_cure_is_its_own_typed_step_and_splits_bond_from_target():
    """CAT-K's presentation boundary: a process event is never swallowed by
    a connection, authored stage, or bench-unit bucket.  The ReaderStep owns
    the exact event/fact emitted by the graph, so renderers cannot rediscover
    process truth from connection assumptions."""
    assembly, glue, target = _glue_and_target()
    authored = eg.ProcessFact(
        kind="cure",
        instructions=(
            "Spread the selected adhesive on both prepared mating faces.",
            "Clamp the joint in the label-required fixture state.",
        ),
        completion="selected_label_full_cure",
        why="The selected adhesive creates this bond.",
        provenance="authored_process_fact",
    )
    glue = Connection(
        kind=glue.kind, parts=glue.parts, label=glue.label,
        assumptions=glue.assumptions, process=(authored,))
    claim = _after(why="Keep the registration datum fixed while screws drive.")
    checks = compile_connections(assembly, [glue, target], after=(claim,))

    steps = eg.derive_reader_steps(checks.event_graph)

    assert [step.title for step in steps] == [
        "install glue", "cure glue", "install target"]
    cure_step = steps[1]
    assert cure_step.process_event == eg.Event("process", "glue", "cure")
    assert cure_step.process_fact is authored
    assert cure_step.connections == ()
    assert all(step.process_event is None for step in (steps[0], steps[2]))


def test_reader_cure_hard_break_survives_bench_and_stage_grouping():
    """A presentation grouping cannot swallow a real process barrier.  This
    is the adversarial same-stage + same-bench case that would otherwise turn
    bond -> cure -> target into a bucket-level cycle."""
    assembly, glue, target = _glue_and_target()
    claim = _after()
    members = tuple(
        part.id for conn in (glue, target)
        for part in (*conn.parts, *conn.hardware))
    staging = eg.ResolvedStaging(
        mode="subassemblies",
        units=(eg.ResolvedUnit("case", "assemble the case on the bench",
                               members),))
    stage = eg.ResolvedStage(
        name="join case", why="One authored shop operation.",
        connections=("glue", "target"))
    checks = compile_connections(
        assembly, [glue, target], sequence=(stage,), after=(claim,),
        staging=staging)

    steps = eg.derive_reader_steps(checks.event_graph)
    titles = [step.title for step in steps]

    assert titles == [
        "bench case",
        "bench case: stage 'join case' (declared order): install glue",
        "cure glue",
        "bench case: stage 'join case' (declared order): install target",
        "set case in place",
    ]
    assert steps[2].process_fact is checks.event_graph.process_facts[
        eg.Event("process", "glue", "cure")]
    assert steps[1].stage is stage and steps[3].stage is stage


def test_build_sequence_refuses_a_nonempty_graph_with_zero_reader_steps(
    monkeypatch,
):
    """A projection regression must stop document generation instead of
    silently rendering an empty derived build sequence."""
    from types import SimpleNamespace

    from detailgen.validation import build_sequence as sequence_module

    assembly, first, second = _glue_and_target()
    checks = compile_connections(assembly, [first, second])
    detail = SimpleNamespace(assembly=assembly, _connection_checks=checks)
    monkeypatch.setattr(sequence_module, "derive_reader_steps", lambda _graph: ())

    with pytest.raises(ValueError, match="zero reader steps"):
        sequence_module.derive_build_sequence(detail)


def test_build_sequence_model_renders_typed_process_and_both_constraint_ends():
    from types import SimpleNamespace

    from detailgen.validation.build_sequence import (
        build_sequence_model, render_build_sequence_md)

    assembly, glue, target = _glue_and_target()
    authored = eg.ProcessFact(
        kind="cure",
        instructions=(
            "Spread adhesive on both prepared faces.",
            "Maintain the selected label's fixture state.",
        ),
        completion="selected_label_full_cure",
        why="This joint uses the selected adhesive bond.",
        provenance="authored_process_fact",
    )
    glue = Connection(
        kind=glue.kind, parts=glue.parts, label=glue.label,
        assumptions=glue.assumptions, process=(authored,))
    claim = _after(why="Preserve the registration datum while screws drive.")
    checks = compile_connections(assembly, [glue, target], after=(claim,))
    detail = SimpleNamespace(assembly=assembly, _connection_checks=checks)

    model = build_sequence_model(detail)
    assert model is not None
    steps, _loose = model
    process = next(step for step in steps if step["process"] is not None)
    target_step = next(step for step in steps
                       if "target" in step["connections"])

    assert process["process"] == {
        "event": eg.Event("process", "glue", "cure"),
        "fact": authored,
    }
    assert process["order_claims"] == ({
        "role": "source", "process_kind": "cure", "source": "glue",
        "target": "target", "why": claim.why,
        "provenance": eg.FAMILY_AUTHORED,
    },)
    assert target_step["order_claims"] == ({
        "role": "target", "process_kind": "cure", "source": "glue",
        "target": "target", "why": claim.why,
        "provenance": eg.FAMILY_AUTHORED,
    },)

    md = render_build_sequence_md(detail)
    assert "Spread adhesive on both prepared faces." in md
    assert "Maintain the selected label's fixture state." in md
    assert "selected adhesive label's full-cure/full-strength condition" in md
    assert "under the actual shop conditions" in md
    assert "No generic duration is represented" in md
    assert "authored_process_fact" in md
    assert ("do not install target until this cure completes — "
            "authored_sequence" in md)
    assert ("complete cure for glue before installing target — "
            "authored_sequence" in md)
    assert md.count(claim.why) == 2


def test_epistemic_contract_uses_actual_process_edges_and_point_constraint():
    from detailgen.validation.install import epistemic_contract_rows

    assembly, glue, target = _glue_and_target()
    claim = _after(why="Preserve this fixture's registration datum.")
    checks = compile_connections(assembly, [glue, target], after=(claim,))

    rendered = "\n".join(" | ".join(row)
                           for row in epistemic_contract_rows(checks))

    assert "Bond/install before process cure" in rendered
    assert "DERIVED" in rendered
    assert "drive(glue, install)" in rendered
    assert "process(glue, cure)" in rendered
    assert "Glued.process_events" in rendered
    assert "Authored process point constraints" in rendered
    assert "DECLARED" in rendered
    assert "glue" in rendered and "target" in rendered
    assert claim.why in rendered
