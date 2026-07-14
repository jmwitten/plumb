"""Pure model for IKEA-shaped instruction panels.

This module is deliberately free of HTML, VTK, and file I/O. It projects the
validated Construction Process Graph into a deterministic panel schedule and
composes builder-facing content from typed process/install facts. Presentation
selects one valid topological order; it never adds an order fact or changes a
verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ..assemblies.event_graph import derive_reader_steps
from ..details.base import fmt_frac_in
from .part_labels import part_labels


class InstructionPresentationError(ValueError):
    """The semantic model cannot be projected into an honest manual."""


@dataclass(frozen=True)
class DisplayRow:
    icon: str
    label: str


@dataclass(frozen=True)
class PlacementStation:
    """One geometry-derived placement instruction shared by text and image."""

    feature: str
    label: str
    reference_part_id: str
    near_mm: float
    far_mm: float
    reference_length_mm: float
    datum: str
    p0: tuple[float, float, float]
    p1: tuple[float, float, float]


@dataclass(frozen=True)
class InstructionPanel:
    index: int
    action: str
    title: str
    reader_step_indexes: tuple[int, ...]
    connections: tuple[str, ...] = ()
    joins: tuple[str, ...] = ()
    process_kind: str | None = None
    process_facts: tuple = ()
    visible_part_ids: tuple[str, ...] = ()
    arrival_part_ids: tuple[str, ...] = ()
    focus_part_ids: tuple[str, ...] = ()
    instructions: tuple[str, ...] = ()
    rationales: tuple[str, ...] = ()
    honesty: tuple[str, ...] = ()
    hardware: tuple[DisplayRow, ...] = ()
    tools: tuple[DisplayRow, ...] = ()
    stations: tuple[PlacementStation, ...] = ()
    content_key: str = ""


@dataclass(frozen=True)
class InstructionManual:
    title: str
    basename: str
    technical_href: str
    panels: tuple[InstructionPanel, ...]
    step_edges: tuple[tuple[int, int], ...]
    part_schedule: tuple[tuple[str, int], ...]
    inventory: tuple[DisplayRow, ...]


_ACTION_PRIORITY = {
    "prepare": 0,
    "bond": 1,
    "cure": 2,
    "fasten": 3,
    "join": 4,
    "unordered": 5,
}


def _relative_html_basename(value: str, field: str) -> str:
    if (not isinstance(value, str) or not value
            or Path(value).name != value
            or "/" in value or "\\" in value
            or not value.endswith(".html")):
        raise ValueError(
            f"{field} must be a relative HTML basename; got {value!r}")
    return value


def _step_action(step, installs_by_connection: dict[str, tuple]) -> str:
    if step.process_event is not None:
        return step.process_event.group
    if step.joins:
        return "join"
    if step.connections:
        if any(installs_by_connection.get(label)
               for label in step.connections):
            return "fasten"
        return "bond"
    if step.parts_placed:
        return "prepare"
    raise InstructionPresentationError(
        f"reader step {step.title!r} has no place, connection, process, or join content")


def _step_event_map(graph, steps) -> dict:
    event_to_step = {}
    for index, step in enumerate(steps):
        for part_id in step.parts_placed:
            event = graph.event_of.get(part_id)
            if event is not None:
                event_to_step[event] = index
        for label in step.connections:
            for event in graph.drives_of.get(label, ()):
                event_to_step[event] = index
        if step.process_event is not None:
            event_to_step[step.process_event] = index
        for unit in step.joins:
            event_to_step[graph.join_of[unit]] = index
    return event_to_step


def _reader_step_edges(graph, steps) -> tuple[tuple[int, int], ...]:
    event_to_step = _step_event_map(graph, steps)
    pairs = set()
    for edge in graph.edges:
        a = event_to_step.get(edge.a)
        b = event_to_step.get(edge.b)
        if a is None or b is None or a == b:
            continue
        pairs.add((a, b))
    return tuple(sorted(pairs))


def _cohort_key(step, action: str) -> tuple:
    unit = step.unit.name if step.unit is not None else ""
    stage = step.stage.name if step.stage is not None else ""
    return action, unit, stage


def _panel_cohorts(steps, step_edges, actions) -> tuple[tuple[int, ...], ...]:
    successors = {i: set() for i in range(len(steps))}
    indegree = {i: 0 for i in range(len(steps))}
    for a, b in step_edges:
        if b not in successors[a]:
            successors[a].add(b)
            indegree[b] += 1

    remaining = set(range(len(steps)))
    cohorts = []
    while remaining:
        ready = sorted(i for i in remaining if indegree[i] == 0)
        if not ready:
            raise InstructionPresentationError(
                "reader-step projection contains a cycle")
        first = min(
            ready,
            key=lambda i: (_ACTION_PRIORITY.get(actions[i], 99), i))
        key = _cohort_key(steps[first], actions[first])
        cohort = tuple(i for i in ready
                       if _cohort_key(steps[i], actions[i]) == key)
        cohorts.append(cohort)
        for i in cohort:
            remaining.remove(i)
            for nxt in successors[i]:
                indegree[nxt] -= 1
    return tuple(cohorts)


def _display(labels, part_id: str) -> str:
    return labels[part_id].display_name


def _fab_note(component) -> str:
    fn = getattr(component, "fabrication_record", None)
    record = fn() if fn is not None else None
    return record.fab_note() if record is not None else ""


def _members_for(graph, connections) -> tuple[str, ...]:
    seen = []
    for label in connections:
        for part_id in graph.members_of.get(label, ()):
            if part_id not in seen:
                seen.append(part_id)
    return tuple(seen)


def _human_members(graph, labels, connection: str) -> tuple[str, ...]:
    return tuple(_display(labels, pid)
                 for pid in graph.members_of.get(connection, ()))


def _process_fact_for_connection(graph, connection: str, kind: str):
    for event in graph.processes_of.get(connection, ()):
        if event.group == kind:
            return graph.process_facts[event]
    raise InstructionPresentationError(
        f"connection {connection!r} has no typed process fact {kind!r}")


def _title(action: str, count: int) -> str:
    return {
        "prepare": "Prepare and dry-fit the five wood parts",
        "bond": "Glue both registration rails to the top underside",
        "cure": "Keep both rail bonds clamped until full cure",
        "fasten": "Fasten both side boards to the registration rails",
        "join": "Set the completed caddy over the actual sofa arm",
    }.get(action, f"{action.title()} ({count} steps)")


def _hardware_rows(detail, installs) -> tuple[DisplayRow, ...]:
    by_id = {p.id: p for p in detail.assembly.parts}
    ids = [pid for install in installs for pid in install.fasteners]
    if not ids:
        return ()
    first = by_id[ids[0]].component
    length = getattr(first, "length", None)
    length_text = f", {fmt_frac_in(length / 25.4)}" if length is not None else ""
    head = installs[0].contract.head.replace("_", "-")
    return (DisplayRow(
        "screw",
        f"{len(ids)} × Rail-to-side screw — #10-class{length_text} "
        f"flat-head, {head}"),)


def _inventory(detail, labels) -> tuple[DisplayRow, ...]:
    grouped = {}
    for part in detail.assembly.parts:
        if part.component.bom_label().endswith("(existing)"):
            continue
        grouped.setdefault(labels[part.id].reader_name, []).append(part)
    return tuple(
        DisplayRow("part", f"{len(parts)} × {reader_name} — "
                   f"{labels[parts[0].id].item}")
        for reader_name, parts in grouped.items())


def _panel_content(detail, graph, steps, cohort, action, labels,
                   installs_by_connection):
    by_id = {p.id: p for p in detail.assembly.parts}
    connections = tuple(label for i in cohort for label in steps[i].connections)
    joins = tuple(unit for i in cohort for unit in steps[i].joins)
    process_facts = tuple(
        steps[i].process_fact for i in cohort
        if steps[i].process_fact is not None)
    process_kind = (steps[cohort[0]].process_event.group
                    if action not in ("prepare", "bond", "fasten", "join")
                    else None)
    instructions, rationales, honesty, tools = [], [], [], []
    hardware = ()

    if action == "prepare":
        for part_id in (pid for i in cohort for pid in steps[i].parts_placed):
            part = by_id[part_id]
            fab = _fab_note(part.component)
            line = f"Prepare {_display(labels, part_id)} — {labels[part_id].item}"
            if fab:
                line += f": {fab}."
            instructions.append(line)
        instructions.append(
            "Dry-fit the cut wood parts on the actual sofa arm before any glue is applied.")
        tools = [DisplayRow("measure", "Tape measure, square, and pencil"),
                 DisplayRow("saw", "Saw and sanding/edge-easing tools"),
                 DisplayRow("drill", "Clamped drill setup for the modeled cup bore")]

    elif action == "bond":
        for connection in connections:
            members = _human_members(graph, labels, connection)
            fact = _process_fact_for_connection(graph, connection, "cure")
            rail = next((name for name in members
                         if name.startswith("Registration rail")), members[0])
            instructions.extend(f"{rail}: {line}" for line in fact.instructions)
            if fact.why not in rationales:
                rationales.append(fact.why)
        tools = [DisplayRow("adhesive", "Selected stock-compatible wood adhesive"),
                 DisplayRow("clamp", "Clamps and square; clamp count is product/setup specific")]

    elif action == "cure":
        for i in cohort:
            event, fact = steps[i].process_event, steps[i].process_fact
            members = _human_members(graph, labels, event.subject)
            rail = next((name for name in members
                         if name.startswith("Registration rail")), members[0])
            instructions.append(
                f"Keep {rail} clamped until the selected adhesive label's "
                "full-cure/full-strength condition is met under the actual shop conditions.")
            if fact.why not in rationales:
                rationales.append(fact.why)
        instructions.append("No generic duration is represented.")
        rationales.append(
            "Waiting preserves each cured registration rail as the datum while "
            "its matching side board is positioned and screwed. This is an "
            "authored caddy assembly strategy, not a universal glue-before-screws rule.")
        tools = [DisplayRow("hold", "Hard stop: keep the selected label's fixture state")]

    elif action == "fasten":
        installs = tuple(inst for connection in connections
                         for inst in installs_by_connection.get(connection, ()))
        hardware = _hardware_rows(detail, installs)
        for connection in connections:
            members = _human_members(graph, labels, connection)
            rail = next(name for name in members
                        if name.startswith("Registration rail"))
            side = next(name for name in members if name.startswith("Side board"))
            count = sum(len(inst.fasteners)
                        for inst in installs_by_connection.get(connection, ()))
            instructions.append(
                f"Fasten {side} to {rail}; drive all {count} modeled screws "
                "through the rail and into the side-board face grain, seating each head flush.")
        rationales.append(
            "Each side waits for its matching cured rail so the rail remains the "
            "registration datum; this is not a universal glue-before-screws rule.")
        tools = [DisplayRow("driver", "Drill/driver"),
                 DisplayRow("bit", "Pilot/countersink bit selected from the screw manufacturer's chart")]

    elif action == "join":
        instructions.extend((
            "Lift the completed five-piece caddy and set it over the actual sofa arm.",
            "With the caddy empty, confirm square bearing, cushion clearance, cup fit, and movement in both directions before use.",
        ))
        if graph.staging is not None and graph.staging.why:
            rationales.append(graph.staging.why)
        honesty.append(
            "DECLARED TRUST — the sofa arm is connection-free context. "
            "insertion travel is not analyzed; stability, sliding resistance, "
            "structural capacity, and hot-drink use are not proved.")
        tools = [DisplayRow("fit", "Actual sofa arm and intended cup for the final fit gate")]

    return {
        "title": _title(action, len(cohort)),
        "connections": connections,
        "joins": joins,
        "process_kind": process_kind,
        "process_facts": process_facts,
        "instructions": tuple(instructions),
        "rationales": tuple(rationales),
        "honesty": tuple(honesty),
        "hardware": hardware,
        "tools": tuple(tools),
    }


def build_instruction_manual(
    detail,
    technical_href: str = "armchair_caddy_build_document.html",
) -> InstructionManual:
    """Build the pure instruction-manual model for a validated detail."""
    technical_href = _relative_html_basename(technical_href, "technical_href")
    checks = getattr(detail, "_connection_checks", None)
    graph = getattr(checks, "event_graph", None)
    if graph is None:
        raise InstructionPresentationError(
            "instruction manual requires a validated event graph")

    steps = derive_reader_steps(graph)
    installs_by_connection = {}
    for install in checks.installs:
        installs_by_connection.setdefault(install.connection, []).append(install)
    installs_by_connection = {
        label: tuple(values) for label, values in installs_by_connection.items()}
    actions = tuple(_step_action(step, installs_by_connection) for step in steps)
    step_edges = _reader_step_edges(graph, steps)
    cohorts = _panel_cohorts(steps, step_edges, actions)
    labels = part_labels(detail.assembly.parts)

    event_to_step = _step_event_map(graph, steps)
    cohort_of_step = {
        step_index: panel_index
        for panel_index, cohort in enumerate(cohorts, start=1)
        for step_index in cohort
    }
    schedule = {}
    for part in detail.assembly.parts:
        if part.id in graph.context_parts:
            join_panel = next(
                (i for i, cohort in enumerate(cohorts, start=1)
                 if any(steps[s].joins for s in cohort)), None)
            if join_panel is None:
                raise InstructionPresentationError(
                    f"context part {part.id!r} has no join panel")
            schedule[part.id] = join_panel
            continue
        event = graph.event_of.get(part.id)
        step_index = event_to_step.get(event)
        if step_index is None:
            raise InstructionPresentationError(
                f"part {part.id!r} has no reader-step presentation event")
        schedule[part.id] = cohort_of_step[step_index]

    panels = []
    for panel_index, cohort in enumerate(cohorts, start=1):
        action = actions[cohort[0]]
        content = _panel_content(
            detail, graph, steps, cohort, action, labels,
            installs_by_connection)
        arrivals = tuple(part.id for part in detail.assembly.parts
                         if schedule[part.id] == panel_index)
        visible = tuple(part.id for part in detail.assembly.parts
                        if schedule[part.id] <= panel_index)
        if action == "prepare":
            focus = arrivals
        elif action == "cure":
            focus = _members_for(
                graph, tuple(steps[i].process_event.subject for i in cohort))
        elif action in ("bond", "fasten"):
            focus = _members_for(graph, content["connections"])
            if action == "fasten":
                focus = tuple(dict.fromkeys((*focus, *arrivals)))
        else:
            focus = tuple(dict.fromkeys((*visible, *arrivals)))
        if not focus:
            raise InstructionPresentationError(
                f"panel {panel_index} ({action}) has no focus region")
        panels.append(InstructionPanel(
            index=panel_index, action=action,
            reader_step_indexes=cohort,
            visible_part_ids=visible,
            arrival_part_ids=arrivals,
            focus_part_ids=focus,
            **content,
        ))

    if detail.name == "armchair caddy":
        expected = ("prepare", "bond", "cure", "fasten", "join")
        got = tuple(panel.action for panel in panels)
        if got != expected:
            raise InstructionPresentationError(
                f"armchair caddy panel contract changed: {got!r}, expected {expected!r}")

    return InstructionManual(
        title="Armchair Coffee Caddy — Illustrated Assembly Manual",
        basename="armchair_caddy_assembly_manual.html",
        technical_href=technical_href,
        panels=tuple(panels),
        step_edges=step_edges,
        part_schedule=tuple((p.id, schedule[p.id])
                            for p in detail.assembly.parts),
        inventory=_inventory(detail, labels),
    )


def panel_part_schedule(manual: InstructionManual) -> dict[str, int]:
    """Return the first-visible panel per built part id."""
    return dict(manual.part_schedule)


def with_panel_stations(
    panel: InstructionPanel,
    stations: tuple[PlacementStation, ...],
) -> InstructionPanel:
    """Pure helper used by a detail-specific geometry station adapter."""
    return replace(panel, stations=stations)
