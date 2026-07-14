"""Pure model for IKEA-shaped instruction panels.

This module is deliberately free of HTML, VTK, and file I/O. It projects the
validated Construction Process Graph into a deterministic panel schedule and
composes builder-facing content from typed process/install facts. Presentation
selects one valid topological order; it never adds an order fact or changes a
verdict.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from ..assemblies.event_graph import derive_reader_steps, reader_step_event_map
from ..details.base import fmt_frac_in
from .part_labels import part_labels


class InstructionPresentationError(ValueError):
    """The semantic model cannot be projected into an honest manual."""


@dataclass(frozen=True)
class DisplayRow:
    icon: str
    label: str
    count: int | None = None
    source_part_ids: tuple[str, ...] = ()


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
    secondary_mm: float | None = None
    secondary_datum: str = ""
    q0: tuple[float, float, float] | None = None
    q1: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class InstructionPanel:
    index: int
    action: str
    title: str
    reader_step_indexes: tuple[int, ...]
    source_events: tuple[tuple[str, str, str], ...] = ()
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


# Small reader-register vocabulary keyed only by typed model facts. Sentence
# structure and quantities are composed below from live parts/connections.
_FAB_TOOL_ROWS = {
    "crosscut": DisplayRow("saw", "Saw suitable for the modeled crosscuts"),
    "ease": DisplayRow("ease", "Sanding or edge-easing tool"),
    "bore": DisplayRow("drill", "Clamped drilling setup for the modeled bore"),
}
_COMPLETION_TEXT = {
    "selected_label_full_cure": (
        "the selected adhesive label's full-cure/full-strength condition is "
        "met under the actual shop conditions"),
}
_COMPLETION_GAP = {
    "selected_label_full_cure": "No generic duration is represented.",
}
_INSTALL_TOOL_ROWS = {
    "driven_straight": DisplayRow(
        "driver", "Drill/driver aligned with the modeled shank axis"),
}
_HEAD_TOOL_ROWS = {
    "flush_countersunk": DisplayRow(
        "countersink",
        "Pilot/countersink selected from the fastener maker's instructions"),
}
_HEAD_TEXT = {
    "flush_countersunk": "head seated flush in its countersink",
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
    return reader_step_event_map(graph, tuple(steps))


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


def _panel_cohorts(steps, actions) -> tuple[tuple[int, ...], ...]:
    if not steps:
        return ()
    cohorts = []
    current = [0]
    for index in range(1, len(steps)):
        prior = current[-1]
        if (_cohort_key(steps[index], actions[index])
                == _cohort_key(steps[prior], actions[prior])):
            current.append(index)
        else:
            cohorts.append(tuple(current))
            current = [index]
    cohorts.append(tuple(current))
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


def _counted_names(labels, part_ids) -> str:
    part_ids = tuple(dict.fromkeys(part_ids))
    counts = Counter(labels[part_id].reader_name for part_id in part_ids)
    names = list(counts)
    chunks = [
        (f"{counts[name]} × {name}" if counts[name] > 1 else name)
        for name in names
    ]
    if not chunks:
        return ""
    if len(chunks) == 1:
        return chunks[0]
    if len(chunks) == 2:
        return " and ".join(chunks)
    return ", ".join(chunks[:-1]) + ", and " + chunks[-1]


def _panel_title(detail, action, graph, steps, cohort, labels) -> str:
    if action == "prepare":
        ids = tuple(pid for index in cohort
                    for pid in steps[index].parts_placed)
        return f"Prepare {_counted_names(labels, ids)}"
    if action in {"bond", "fasten"}:
        connections = tuple(label for index in cohort
                            for label in steps[index].connections)
        ids = _members_for(graph, connections)
        verb = "Bond" if action == "bond" else "Fasten"
        return f"{verb} {_counted_names(labels, ids)}"
    if action == "cure":
        count = len(cohort)
        noun = "bond" if count == 1 else "bonds"
        return f"Hold {count} adhesive {noun} to full cure"
    if action == "join":
        context = tuple(graph.context_parts)
        suffix = (f" over {_counted_names(labels, context)}"
                  if context else " in the root assembly")
        return f"Set completed {detail.name}{suffix}"
    return action.title()


def _hardware_rows(detail, installs) -> tuple[DisplayRow, ...]:
    by_id = {p.id: p for p in detail.assembly.parts}
    ids = [pid for install in installs for pid in install.fasteners]
    if not ids:
        return ()
    first = by_id[ids[0]].component
    length = getattr(first, "length", None)
    diameter = getattr(first, "diameter", None)
    size = []
    if diameter is not None:
        size.append(f"{fmt_frac_in(diameter / 25.4)} dia")
    if length is not None:
        size.append(fmt_frac_in(length / 25.4))
    head_key = installs[0].contract.head
    head = _HEAD_TEXT.get(head_key, head_key.replace("_", " "))
    labels = part_labels(detail.assembly.parts)
    reader_name = labels[ids[0]].reader_name
    return (DisplayRow(
        "screw",
        f"{len(ids)} × {reader_name} — {' × '.join(size)}, {head}",
        count=len(ids), source_part_ids=tuple(ids)),)


def _fabrication_tools(parts) -> tuple[DisplayRow, ...]:
    kinds = []
    for part in parts:
        record_fn = getattr(part.component, "fabrication_record", None)
        record = record_fn() if record_fn is not None else None
        for step in (record.steps if record is not None else ()):
            if step.kind in _FAB_TOOL_ROWS and step.kind not in kinds:
                kinds.append(step.kind)
    return tuple(_FAB_TOOL_ROWS[kind] for kind in kinds)


def _constraint_whys(graph, *, connections=(), process_events=()) -> tuple[str, ...]:
    connections = set(connections)
    process_keys = {(event.group, event.subject) for event in process_events}
    result = []
    for claim in graph.constraints:
        applies = claim.connection in connections or any(
            (ref.kind, ref.connection) in process_keys for ref in claim.after)
        if applies and claim.why not in result:
            result.append(claim.why)
    return tuple(result)


def _inventory(detail, labels) -> tuple[DisplayRow, ...]:
    grouped = {}
    for part in detail.assembly.parts:
        if part.component.bom_label().endswith("(existing)"):
            continue
        grouped.setdefault(labels[part.id].reader_name, []).append(part)
    return tuple(
        DisplayRow("part", f"{len(parts)} × {reader_name} — "
                   f"{labels[parts[0].id].item}", count=len(parts),
                   source_part_ids=tuple(part.id for part in parts))
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
        prepared_ids = tuple(pid for i in cohort for pid in steps[i].parts_placed)
        for part_id in prepared_ids:
            part = by_id[part_id]
            fab = _fab_note(part.component)
            line = f"Prepare {_display(labels, part_id)} — {labels[part_id].item}"
            if fab:
                line += f": {fab}."
            instructions.append(line)
        tools = list(_fabrication_tools(by_id[part_id] for part_id in prepared_ids))

    elif action == "bond":
        for connection in connections:
            members = _human_members(graph, labels, connection)
            fact = _process_fact_for_connection(graph, connection, "cure")
            instructions.extend(f"{line}" for line in fact.instructions)
            if fact.why not in rationales:
                rationales.append(fact.why)
        hardware = (DisplayRow(
            "adhesive", "Selected wood adhesive — product selection required"),)
        tools = [DisplayRow(
            "clamp", "Clamps; count follows the product and setup")]

    elif action == "cure":
        process_events = tuple(steps[i].process_event for i in cohort)
        for i in cohort:
            event, fact = steps[i].process_event, steps[i].process_fact
            rail_ids = tuple(
                pid for pid in graph.members_of[event.subject]
                if any(pid == install.contract.entry_face.part
                       for values in installs_by_connection.values()
                       for install in values))
            subject = (_counted_names(labels, rail_ids)
                       if rail_ids else _counted_names(
                           labels, graph.members_of[event.subject]))
            completion = _COMPLETION_TEXT.get(
                fact.completion, fact.completion.replace("_", " "))
            instructions.append(
                f"Keep {subject} clamped until {completion}.")
            if fact.why not in rationales:
                rationales.append(fact.why)
            gap = _COMPLETION_GAP.get(fact.completion)
            if gap and gap not in instructions:
                instructions.append(gap)
        rationales.extend(why for why in _constraint_whys(
            graph, process_events=process_events) if why not in rationales)
        tools = [DisplayRow(
            "clamp", "Keep the bond clamps in the selected label's fixture state")]

    elif action == "fasten":
        installs = tuple(inst for connection in connections
                         for inst in installs_by_connection.get(connection, ()))
        hardware = _hardware_rows(detail, installs)
        for connection in connections:
            resolved = installs_by_connection.get(connection, ())
            rail_ids = tuple(install.contract.entry_face.part
                             for install in resolved)
            member_ids = graph.members_of[connection]
            side_ids = tuple(pid for pid in member_ids if pid not in rail_ids)
            count = sum(len(install.fasteners) for install in resolved)
            head = _HEAD_TEXT.get(
                resolved[0].contract.head,
                resolved[0].contract.head.replace("_", " "))
            instructions.append(
                f"Fasten {_counted_names(labels, side_ids)} to "
                f"{_counted_names(labels, rail_ids)}; drive all {count} modeled "
                f"fasteners through the rail into the other member, with each {head}.")
        rationales.extend(_constraint_whys(graph, connections=connections))
        method_keys = tuple(dict.fromkeys(
            install.contract.method for install in installs))
        head_keys = tuple(dict.fromkeys(
            install.contract.head for install in installs))
        tools = [*(_INSTALL_TOOL_ROWS[key] for key in method_keys
                   if key in _INSTALL_TOOL_ROWS),
                 *(_HEAD_TOOL_ROWS[key] for key in head_keys
                   if key in _HEAD_TOOL_ROWS)]

    elif action == "join":
        context = tuple(graph.context_parts)
        context_names = _counted_names(labels, context)
        instructions.extend((
            f"Set the completed {detail.name} over {context_names}.",
            "Choose its along-arm position during fitting; the model does not "
            "represent that direction as a critical placement station.",
        ))
        if graph.staging is not None and graph.staging.why:
            rationales.append(graph.staging.why)
        honesty.append(
            "DECLARED TRUST — the sofa arm is connection-free context. "
            "insertion travel is not analyzed; stability, sliding resistance, "
            "structural capacity, and hot-drink use are not proved.")
        tools = [DisplayRow("fit", f"Actual {context_names} for the declared fit placement")]

    return {
        "title": _panel_title(detail, action, graph, steps, cohort, labels),
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


def _source_events(graph, steps, cohort) -> tuple[tuple[str, str, str], ...]:
    """Return the event identities owned by a reader-step cohort."""
    events = []
    for index in cohort:
        step = steps[index]
        for part_id in step.parts_placed:
            event = graph.event_of.get(part_id)
            if event is not None and event not in events:
                events.append(event)
        for connection in step.connections:
            for event in graph.drives_of.get(connection, ()):
                if event not in events:
                    events.append(event)
        if step.process_event is not None and step.process_event not in events:
            events.append(step.process_event)
        for unit in step.joins:
            event = graph.join_of[unit]
            if event not in events:
                events.append(event)
    return tuple((event.kind, event.subject, event.group) for event in events)


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
    cohorts = _panel_cohorts(steps, actions)
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
            source_events=_source_events(graph, steps, cohort),
            visible_part_ids=visible,
            arrival_part_ids=arrivals,
            focus_part_ids=focus,
            **content,
        ))

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
