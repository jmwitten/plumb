"""Focused regressions for generic reader-step process projection."""

from detailgen.assemblies import Connection, DetailAssembly, compile_connections
from detailgen.assemblies.connection import ConnectionType, Glued
from detailgen.assemblies.event_graph import (
    ResolvedStage,
    ResolvedStaging,
    ResolvedUnit,
    derive_reader_steps,
    linearize,
)
from detailgen.components import Lumber
from detailgen.core import IN


def test_late_stage_bonds_precede_their_cures_and_share_stage_identity():
    assembly = DetailAssembly("late-stage bonds")
    left = assembly.add(Lumber("2x4", 4 * IN, name="left end"))
    right = assembly.add(
        Lumber("2x4", 4 * IN, name="right end"), at=(0, 100, 0)
    )
    handle = assembly.add(
        Lumber("2x4", 4 * IN, name="handle"), at=(0, 200, 0)
    )
    connections = (
        Connection(kind=Glued(), parts=(left, handle), label="left bond"),
        Connection(kind=Glued(), parts=(right, handle), label="right bond"),
    )
    bond_stage = ResolvedStage(
        name="bond both handle ends",
        why="Clamp both handle bonds in one setup before either cure completes.",
        connections=("left bond", "right bond"),
        parts=(handle.id,),
    )
    stages = (
        ResolvedStage(
            name="prepare left end", why="Prepare the first support.",
            parts=(left.id,),
        ),
        ResolvedStage(
            name="prepare right end", why="Prepare the second support.",
            parts=(right.id,),
        ),
        bond_stage,
    )
    staging = ResolvedStaging(
        mode="subassemblies",
        units=(ResolvedUnit(
            "handle unit", "Build the complete unit on the bench.",
            (left.id, right.id, handle.id),
        ),),
    )
    graph = compile_connections(
        assembly, connections, sequence=stages, staging=staging,
    ).event_graph

    steps = derive_reader_steps(graph)
    process_steps = tuple(
        step for step in steps
        if step.connections or step.process_event is not None
    )

    assert [
        (
            step.connections,
            (
                (step.process_event.subject, step.process_event.group)
                if step.process_event else None
            ),
            step.stage,
        )
        for step in process_steps
    ] == [
        (("left bond",), None, bond_stage),
        (("right bond",), None, bond_stage),
        ((), ("left bond", "cure"), bond_stage),
        ((), ("right bond", "cure"), bond_stage),
    ]


def test_root_stage_bonds_precede_their_cures_and_share_stage_identity():
    assembly = DetailAssembly("root-stage bonds")
    left = assembly.add(Lumber("2x4", 4 * IN, name="left end"))
    right = assembly.add(
        Lumber("2x4", 4 * IN, name="right end"), at=(0, 100, 0)
    )
    handle = assembly.add(
        Lumber("2x4", 4 * IN, name="handle"), at=(0, 200, 0)
    )
    connections = (
        Connection(kind=Glued(), parts=(left, handle), label="left bond"),
        Connection(kind=Glued(), parts=(right, handle), label="right bond"),
    )
    bond_stage = ResolvedStage(
        name="bond both handle ends",
        why="Clamp both handle bonds in one setup before either cure completes.",
        connections=("left bond", "right bond"),
        parts=(handle.id,),
    )
    graph = compile_connections(
        assembly, connections, sequence=(bond_stage,),
    ).event_graph
    left_drive = graph.drives_of["left bond"][0]
    right_drive = graph.drives_of["right bond"][0]
    left_cure = graph.processes_of["left bond"][0]
    right_cure = graph.processes_of["right bond"][0]

    assert not graph.precedes(left_drive, right_drive)
    assert not graph.precedes(right_drive, left_drive)
    assert not graph.precedes(left_cure, right_drive)
    assert not graph.precedes(right_cure, left_drive)

    steps = derive_reader_steps(graph)
    process_steps = tuple(
        step for step in steps
        if step.connections or step.process_event is not None
    )

    assert [
        (
            step.connections,
            (
                (step.process_event.subject, step.process_event.group)
                if step.process_event else None
            ),
            step.stage,
        )
        for step in process_steps
    ] == [
        (("left bond",), None, bond_stage),
        (("right bond",), None, bond_stage),
        ((), ("left bond", "cure"), bond_stage),
        ((), ("right bond", "cure"), bond_stage),
    ]


def test_mixed_root_stage_and_unstaged_connection_have_total_stable_order():
    class PlainJoint(ConnectionType):
        label = "plain_joint"

        def install_contract(self, conn):
            return ()

    assembly = DetailAssembly("mixed root work")
    left = assembly.add(Lumber("2x4", 4 * IN, name="left end"))
    right = assembly.add(
        Lumber("2x4", 4 * IN, name="right end"), at=(0, 100, 0)
    )
    handle = assembly.add(
        Lumber("2x4", 4 * IN, name="handle"), at=(0, 200, 0)
    )
    loose_a = assembly.add(
        Lumber("2x4", 4 * IN, name="loose member A"), at=(0, 300, 0)
    )
    loose_b = assembly.add(
        Lumber("2x4", 4 * IN, name="loose member B"), at=(0, 400, 0)
    )
    connections = (
        Connection(kind=Glued(), parts=(left, handle), label="left bond"),
        Connection(
            kind=PlainJoint(), parts=(loose_a, loose_b), label="plain joint",
        ),
        Connection(kind=Glued(), parts=(right, handle), label="right bond"),
    )
    bond_stage = ResolvedStage(
        name="bond both handle ends",
        why="Keep both bonds in one authored operation.",
        connections=("left bond", "right bond"),
        parts=(handle.id,),
    )
    base_graph = compile_connections(
        assembly, connections, sequence=(bond_stage,),
    ).event_graph
    plain_position = linearize(base_graph).index(
        base_graph.drives_of["plain joint"][0]
    )
    padding = tuple(
        ResolvedStage(name=f"padding {index}", why="No event-bearing work.")
        for index in range(plain_position - 1)
    )
    graph = compile_connections(
        assembly, connections, sequence=(*padding, bond_stage),
    ).event_graph
    plain_drive = graph.drives_of["plain joint"][0]
    assert linearize(graph).index(plain_drive) == plain_position
    assert 1 + graph.stages.index(bond_stage) == plain_position
    assert all(
        not graph.precedes(event, plain_drive)
        and not graph.precedes(plain_drive, event)
        for label in ("left bond", "right bond")
        for event in (*graph.drives_of[label], *graph.processes_of[label])
    )

    steps = derive_reader_steps(graph)
    work = tuple(
        (step.connections, step.process_event.subject
         if step.process_event is not None else None)
        for step in steps
        if step.connections or step.process_event is not None
    )

    assert work == (
        (("left bond",), None),
        (("right bond",), None),
        ((), "left bond"),
        ((), "right bond"),
        (("plain joint",), None),
    )
