"""Binding CAT-L: presentation regrouping cannot move validation truth."""

from __future__ import annotations

from pathlib import Path

from detailgen.assemblies.event_graph import (
    FAMILY_AUTHORED,
    derive_reader_steps,
)
from detailgen.core.buildinfo import build_manifest
from detailgen.rendering.instruction_panels import InstructionPanel
from detailgen.rendering.instruction_render import panel_content_key
from detailgen.spec.compiler import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
STOOL_SPEC = ROOT / "details" / "step_stool.spec.yaml"
STAGES = """
sequence:
  stages:
    - name: fasten both upper-tread cap joints
      connections:
        - "upper tread -> +X panel top (screwed down)"
        - "upper tread -> -X panel top (screwed down)"
      why: Fasten both upper-tread cap joints as one declared shop stage.
    - name: fasten both lower-tread cleats
      connections:
        - "cleat +X -> +X panel inner face (screwed, face grain)"
        - "cleat -X -> -X panel inner face (screwed, face grain)"
      why: Fasten both cleats after the cap-joint stage.
"""


def _compile(path: Path):
    detail = compile_spec_file(path)
    report = detail.validate()
    return detail, report


def _finding_signature(report):
    return tuple(
        (finding.verdict, finding.check, finding.subject, finding.detail,
         finding.declared_order, finding.declared_trust)
        for finding in report.findings
    )


def _step_signature(steps):
    return tuple(
        (step.title, step.stage.name if step.stage else None,
         step.connections, step.parts_placed, step.joins,
         step.process_event, step.process_fact)
        for step in steps
    )


def _edge_signature(graph):
    return tuple(
        (edge.a, edge.b, edge.family, edge.source)
        for edge in graph.edges
    )


def _source_events(graph, step):
    events = []
    for part_id in step.parts_placed:
        event = graph.event_of.get(part_id)
        if event is not None and event not in events:
            events.append(event)
    for connection in step.connections:
        for event in graph.drives_of[connection]:
            if event not in events:
                events.append(event)
    if step.process_event is not None and step.process_event not in events:
        events.append(step.process_event)
    for unit in step.joins:
        event = graph.join_of[unit]
        if event not in events:
            events.append(event)
    return tuple(events)


def _step_panel(detail, step, index):
    graph = detail._connection_checks.event_graph
    events = _source_events(graph, step)
    event_set = set(events)
    arrival = tuple(
        part.id for part in detail.assembly.parts
        if graph.event_of.get(part.id) in event_set)
    focus = tuple(dict.fromkeys((
        *arrival,
        *(part_id for connection in step.connections
          for part_id in graph.members_of[connection]),
    )))
    return InstructionPanel(
        index=index + 1,
        action="fasten",
        title=step.title,
        reader_step_indexes=(index,),
        source_events=tuple(
            (event.kind, event.subject, event.group) for event in events),
        connections=step.connections,
        visible_part_ids=focus,
        arrival_part_ids=arrival,
        focus_part_ids=focus,
    )


def _step_keys(detail, steps):
    return tuple(
        panel_content_key(detail, _step_panel(detail, step, index))
        for index, step in enumerate(steps)
    )


def test_cat_l_stool_stages_regroup_reader_steps_without_moving_truth(tmp_path):
    staged_path = tmp_path / "staged.spec.yaml"
    staged_path.write_text(STOOL_SPEC.read_text() + STAGES)

    unstaged, unstaged_report = _compile(STOOL_SPEC)
    staged, staged_report = _compile(staged_path)
    reverted, reverted_report = _compile(STOOL_SPEC)
    unstaged_graph = unstaged._connection_checks.event_graph
    staged_graph = staged._connection_checks.event_graph
    reverted_graph = reverted._connection_checks.event_graph
    unstaged_steps = derive_reader_steps(unstaged_graph)
    staged_steps = derive_reader_steps(staged_graph)
    reverted_steps = derive_reader_steps(reverted_graph)

    assert len(unstaged_steps) == 3
    assert len(staged_steps) == 2
    assert tuple(step.stage.name for step in staged_steps) == (
        "fasten both upper-tread cap joints",
        "fasten both lower-tread cleats",
    )
    assert _step_signature(reverted_steps) == _step_signature(unstaged_steps)
    assert _edge_signature(reverted_graph) == _edge_signature(unstaged_graph)
    assert _finding_signature(staged_report) == _finding_signature(
        unstaged_report)
    assert _finding_signature(reverted_report) == _finding_signature(
        unstaged_report)

    unstaged_edges = set(_edge_signature(unstaged_graph))
    staged_edges = set(_edge_signature(staged_graph))
    added = staged_edges - unstaged_edges
    assert not unstaged_edges - staged_edges
    assert len(added) == 4
    assert {edge[2] for edge in added} == {FAMILY_AUTHORED}

    assert build_manifest(staged.assembly)["assembly_hash"] == \
        build_manifest(unstaged.assembly)["assembly_hash"]
    unstaged_keys = _step_keys(unstaged, unstaged_steps)
    staged_keys = _step_keys(staged, staged_steps)
    assert staged_keys[0] == unstaged_keys[0]
    assert staged_keys[1] not in unstaged_keys[1:]
    assert _step_keys(reverted, reverted_steps) == unstaged_keys


def test_cat_l_unrelated_spec_comment_does_not_rekey_reader_renders(tmp_path):
    variant_path = tmp_path / "comment-only.spec.yaml"
    variant_path.write_text(
        "# Comment-only CAT-L key probe.\n" + STOOL_SPEC.read_text())

    original, _report = _compile(STOOL_SPEC)
    variant, _variant_report = _compile(variant_path)
    original_steps = derive_reader_steps(
        original._connection_checks.event_graph)
    variant_steps = derive_reader_steps(variant._connection_checks.event_graph)

    assert _step_signature(variant_steps) == _step_signature(original_steps)
    assert _step_keys(variant, variant_steps) == _step_keys(
        original, original_steps)
