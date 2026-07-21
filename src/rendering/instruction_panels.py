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
from .fastener_layouts import FastenerLayout, derive_fastener_layouts
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
class ProcedureLink:
    """Typed manufacturer link; references are not mislabeled as procedures."""

    label: str
    href: str
    source_ref: str
    kind: str = "product_reference"


@dataclass(frozen=True)
class RelatedDocumentLink:
    """One relative link to another document in the delivered set."""

    label: str
    href: str


@dataclass(frozen=True)
class JoinPresentation:
    """Project-authored reader copy for a typed root-join event."""

    title: str
    instructions: tuple[str, ...]
    honesty: tuple[str, ...] = ()
    tools: tuple[DisplayRow, ...] = ()


@dataclass(frozen=True)
class StopNotice:
    """An unavoidable action gate rendered before a panel's resources."""

    heading: str
    body: str


@dataclass(frozen=True)
class RecordField:
    """One printable closeout field attached to an instruction panel."""

    label: str
    guidance: str = ""


@dataclass(frozen=True)
class DiagramPrimitive:
    """One allow-listed vector mark in a reader-facing operation diagram.

    ``coords`` are normalized SVG coordinates.  ``model_point_mm`` retains the
    compiled coordinate behind a plotted station so tests and downstream
    readers can prove the illustration did not become a second source of truth.
    """

    kind: str
    coords: tuple[float, ...]
    role: str = "work"
    label: str = ""
    model_point_mm: tuple[float, ...] = ()
    fact_ref: str = ""
    rotation: float = 0.0  # text only; degrees about the anchor point


@dataclass(frozen=True)
class OperationDiagram:
    """Typed, model-derived 2D operation view rendered without raw SVG input.

    ``view_height`` crops the drawing's vertical extent: a wide plan whose
    marks stop at y=45 declares 45 so renderers scale it to full width
    instead of letterboxing it inside the default square canvas.
    """

    diagram_id: str
    title: str
    caption: str
    primitives: tuple[DiagramPrimitive, ...]
    source_refs: tuple[str, ...]
    view_height: float = 100.0


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
    mirror_p0: tuple[float, float, float] | None = None
    mirror_p1: tuple[float, float, float] | None = None


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
    procedure_links: tuple[ProcedureLink, ...] = ()
    diagrams: tuple[OperationDiagram, ...] = ()
    stations: tuple[PlacementStation, ...] = ()
    fastener_layouts: tuple[FastenerLayout, ...] = ()
    stop_notice: StopNotice | None = None
    record_title: str = ""
    record_fields: tuple[RecordField, ...] = ()
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
    lede: str
    excluded_part_ids: tuple[str, ...] = ()
    related_documents: tuple[RelatedDocumentLink, ...] = ()


_CADDY_MANUAL_LEDE = (
    "This is one machine-checked build order from the validated construction "
    "process graph. A blocking modeled failure blocks release. Its phase "
    "boundary includes {declared_constraints} authored process-order "
    "constraints; their declared reasons are printed where they apply. "
    "Deterministic tie-breaks between otherwise independent events are a "
    "readable build choice, not proof that no other valid order exists. "
    "Colored parts are current work, pale gray parts are already present, and "
    "blue marks share the compiled measurements used by the placement text. "
    "Prototype only: structural capacity, stability, sliding resistance, "
    "insertion travel, and hot-drink use remain unproved; do not treat it as "
    "load-bearing or use it for hot liquids until a representative build is "
    "validated."
)


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
    "seated": "head seated snug against the surface",
    "flush_countersunk": "head seated flush in its countersink",
}
_HEAD_ACTION = {
    "seated": "seat each head snug against the surface",
    "proud": "leave each head proud",
    "flush_countersunk": "seat each head flush in its countersink",
    "recessed_in_pocket": "seat each head in its pocket",
    "nut_and_washer": "complete each nut-and-washer stack",
}

def _relative_html_basename(value: str, field: str) -> str:
    if (not isinstance(value, str) or not value
            or Path(value).name != value
            or "/" in value or "\\" in value
            or ":" in value
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


def _fabrication_instructions(component, display_name: str) -> tuple[str, ...]:
    """Translate the component's typed fabrication record into shop language."""
    record_fn = getattr(component, "fabrication_record", None)
    record = record_fn() if record_fn is not None else None
    if record is None:
        return ()

    instructions = []
    for step in record.steps:
        if step.kind == "crosscut":
            instructions.append(
                f"Crosscut {display_name} to {component.describe()}.")
        elif step.kind == "ease":
            radius = fmt_frac_in(step.param("radius") / 25.4)
            instructions.append(
                f"Ease the long edges of {display_name} to a {radius} radius.")
        elif step.kind == "bore":
            parameters = step.params_dict()
            radius = parameters["radius"]
            diameter_text = fmt_frac_in(2 * radius / 25.4)
            radius_text = fmt_frac_in(radius / 25.4)
            feature = parameters.get("feature", "bore")
            instructions.append(
                f"Bore the {feature} in {display_name} at the placement station "
                f"shown: {diameter_text} diameter ({radius_text} radius), clean "
                "through the stock. The cutter type is not represented; select "
                "a clamped setup suitable for this stock and cut.")

    fab = record.fab_note()
    if fab and not any(step.kind == "bore" for step in record.steps):
        instructions.append(f"Machine {display_name}: {fab}.")
    return tuple(instructions)


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


def _service_panel_group(connections, semantics):
    """Return one homogeneous service-panel operation for a panel cohort."""
    rows = tuple(semantics.get(label) for label in connections)
    if not rows or any(row is None for row in rows):
        return None
    modes = {row[0] for row in rows}
    panel_ids = {row[1] for row in rows}
    if len(modes) != 1 or len(panel_ids) != 1:
        return None
    return next(iter(modes)), next(iter(panel_ids))


def _service_panel_semantics(detail) -> dict[str, tuple[str, str]]:
    """Map typed pivot/latch connections to their moving service panel."""
    result = {}
    for connection in detail.connections():
        mode = getattr(connection.kind, "mode", None)
        if mode in {"pivot", "latch"} and len(connection.parts) >= 2:
            result[connection.label] = (mode, connection.parts[1].id)
    return result


def _panel_title(
    detail, action, graph, steps, cohort, labels, service_semantics,
) -> str:
    stages = tuple(dict.fromkeys(
        steps[index].stage for index in cohort
        if steps[index].stage is not None
    ))
    if len(stages) == 1 and action in {"bond", "fasten"}:
        name = stages[0].name.strip()
        return name[:1].upper() + name[1:]
    if action == "prepare":
        ids = tuple(pid for index in cohort
                    for pid in steps[index].parts_placed)
        return f"Prepare {_counted_names(labels, ids)}"
    if action in {"bond", "fasten"}:
        connections = tuple(label for index in cohort
                            for label in steps[index].connections)
        service = _service_panel_group(connections, service_semantics)
        if action == "fasten" and service is not None:
            mode, service_panel_id = service
            service_panel = _display(labels, service_panel_id)
            if mode == "pivot":
                return f"Install {service_panel} pivot screws"
            return f"Close and latch {service_panel}"
        ids = _members_for(graph, connections)
        verb = "Bond" if action == "bond" else "Fasten"
        return f"{verb} {_counted_names(labels, ids)}"
    if action == "cure":
        count = len(cohort)
        noun = "bond" if count == 1 else "bonds"
        return f"Hold {count} adhesive {noun} to full cure"
    if action == "join":
        joins = tuple(unit for index in cohort
                      for unit in steps[index].joins)
        if joins != ("whole detail",):
            completion = graph.units[joins[0]].completion
            if completion is not None:
                return completion.title
            return f"Complete {joins[0]} subassembly"
        context = tuple(graph.context_parts)
        if context:
            return (
                f"Fit completed {detail.name} to "
                f"{_counted_names(labels, context)}"
            )
        return f"Complete {detail.name} bench assembly"
    return action.title()


def reader_dimensions(component) -> str:
    """Use construction fractions for headed fasteners on every manual surface."""
    catalog_size = getattr(component, "catalog_size", "")
    if catalog_size:
        return str(catalog_size)
    if (hasattr(component, "diameter") and hasattr(component, "length")
            and hasattr(component, "head_height")):
        diameter = fmt_frac_in(component.diameter / 25.4)
        length = fmt_frac_in(component.length / 25.4)
        return f"{diameter} dia × {length}"
    return component.describe()


def _hardware_rows(detail, installs) -> tuple[DisplayRow, ...]:
    by_id = {p.id: p for p in detail.assembly.parts}
    labels = part_labels(detail.assembly.parts)
    grouped = {}
    for install in installs:
        head_key = install.contract.head
        head = _HEAD_TEXT.get(head_key, head_key.replace("_", " "))
        for part_id in install.fasteners:
            component = by_id[part_id].component
            capabilities = component.capability_tags()
            family = (
                "Screw"
                if "wood_screw" in capabilities
                else labels[part_id].item
            )
            size = reader_dimensions(component)
            if "wood_screw" in capabilities:
                size = f"{fmt_frac_in(component.length / 25.4)} long"
            key = (
                family,
                size,
                head,
                component.bom_group(),
            )
            grouped.setdefault(key, []).append(part_id)
    if not grouped:
        return ()
    return tuple(
        DisplayRow(
            "screw",
            f"{item} ×{len(ids)} — {size}; select the exterior screw and "
            "its maker-specified drilling requirements before work begins",
            count=len(ids),
            source_part_ids=tuple(ids),
        )
        for (item, size, head, _bom_group), ids in grouped.items()
    )


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


def _actual_finished_dimensions(component) -> str | None:
    record_fn = getattr(component, "fabrication_record", None)
    record = record_fn() if record_fn is not None else None
    if record is None or record.stock.form != "linear_stick":
        return None
    box = component.bounding_box()
    dimensions = sorted((box.xlen, box.ylen, box.zlen))
    return " × ".join(fmt_frac_in(value / 25.4) for value in dimensions)


def _inventory(detail, labels) -> tuple[DisplayRow, ...]:
    grouped = {}
    for part in detail.assembly.parts:
        if part.component.bom_label().endswith("(existing)"):
            continue
        reader_name = labels[part.id].reader_name
        if "installation_fastener" in part.component.capability_tags():
            reader_name = labels[part.id].item
        key = (reader_name, labels[part.id].item,
               reader_dimensions(part.component),
               _actual_finished_dimensions(part.component))
        grouped.setdefault(key, []).append(part)
    rows = []
    for (reader_name, item, dimensions, actual), parts in grouped.items():
        actual_text = f"; actual {actual}" if actual is not None else ""
        rows.append(DisplayRow(
            "part",
            f"{len(parts)} × {reader_name} — {item}; {dimensions}{actual_text}",
            count=len(parts),
            source_part_ids=tuple(part.id for part in parts)))
    return tuple(rows)


def _consumable_inventory(graph) -> tuple[DisplayRow, ...]:
    if any(event.group == "cure" for event in graph.process_facts):
        return (DisplayRow(
            "adhesive",
            "Required consumable — selected wood adhesive; product selection "
            "required before work begins"),)
    return ()


def _panel_content(detail, graph, steps, cohort, action, labels,
                   installs_by_connection, join_presentation,
                   service_semantics):
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
    fastener_layouts = ()
    stages = tuple(dict.fromkeys(
        steps[index].stage for index in cohort
        if steps[index].stage is not None
    ))
    setups = tuple(stage.setup for stage in stages if stage.setup)
    checks = tuple(stage.check for stage in stages if stage.check)

    if action == "prepare":
        prepared_ids = tuple(pid for i in cohort for pid in steps[i].parts_placed)
        for part_id in prepared_ids:
            part = by_id[part_id]
            actual = _actual_finished_dimensions(part.component)
            actual_text = f"; actual {actual}" if actual is not None else ""
            line = (f"Prepare {_display(labels, part_id)} — "
                    f"{labels[part_id].item}; purchase profile and cut length "
                    f"{part.component.describe()}{actual_text}.")
            instructions.append(line)
            instructions.extend(_fabrication_instructions(
                part.component, _display(labels, part_id)))
        tools = list(_fabrication_tools(by_id[part_id] for part_id in prepared_ids))

    elif action == "bond":
        for connection in connections:
            members = _human_members(graph, labels, connection)
            fact = _process_fact_for_connection(graph, connection, "cure")
            scope = " and ".join(members)
            instructions.extend(
                f"For {scope}: {line}" for line in fact.instructions)
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
            subject = (" and ".join(_display(labels, pid) for pid in rail_ids)
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
        fastener_layouts = derive_fastener_layouts(
            detail, graph, labels, connections, installs_by_connection)
        instructions.extend(setups)
        service = _service_panel_group(connections, service_semantics)
        if service is not None:
            mode, service_panel_id = service
            service_panel = _display(labels, service_panel_id)
            entry_ids = tuple(dict.fromkeys(
                install.contract.entry_face.part for install in installs
            ))
            entry_names = " and ".join(
                _display(labels, pid) for pid in entry_ids
            )
            count = sum(len(install.fasteners) for install in installs)
            if mode == "pivot":
                instructions.append(
                    f"At the marked centers, drill clearance holes through "
                    f"{entry_names} and pilot holes into {service_panel}; "
                    f"install {count} aligned pivot screws with their heads "
                    "proud enough for the panel to swing freely."
                )
                if not checks:
                    instructions.append(
                        f"Swing {service_panel} open and closed to confirm "
                        "free movement before installing the lower latch."
                    )
            else:
                instructions.append(
                    f"At the marked center, drill a clearance hole through "
                    f"{entry_names} and a pilot hole into {service_panel}; "
                    "install the removable latch screw with its head proud. "
                    "Do not glue it."
                )
                if not checks:
                    instructions.append(
                        f"Open, close, and re-latch {service_panel} to confirm "
                        "service access."
                    )
        else:
            for connection in connections:
                resolved = installs_by_connection.get(connection, ())
                entry_ids = tuple(dict.fromkeys(
                    install.contract.entry_face.part for install in resolved
                ))
                member_ids = graph.members_of[connection]
                receiving_ids = tuple(
                    pid for pid in member_ids if pid not in entry_ids
                )
                receiving_names = " and ".join(
                    _display(labels, pid) for pid in receiving_ids)
                entry_names = " and ".join(
                    _display(labels, pid) for pid in entry_ids)
                count = sum(len(install.fasteners) for install in resolved)
                fastener_noun = "screw" if count == 1 else "screws"
                head = _HEAD_ACTION.get(
                    resolved[0].contract.head,
                    f"finish each head as {resolved[0].contract.head.replace('_', ' ')}")
                instructions.append(
                    f"At the marked centers, prepare the holes required by "
                    f"the selected screw maker, then drive {count} "
                    f"{fastener_noun} through {entry_names} into "
                    f"{receiving_names}; {head}.")
        instructions.extend(checks)
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
        authored_completion = (
            graph.units[joins[0]].completion
            if joins != ("whole detail",) else None
        )
        if join_presentation is None and authored_completion is not None:
            unit = graph.units[joins[0]]
            modeled_fasteners = tuple(
                part_id for part_id in unit.parts
                if "installation_fastener" in
                by_id[part_id].component.capability_tags()
            )
            if modeled_fasteners:
                noun = "screw" if len(modeled_fasteners) == 1 else "screws"
                instructions.append(
                    f"Confirm all {len(modeled_fasteners)} modeled {noun} "
                    f"assigned to the {unit.name} are installed."
                )
            instructions.extend(authored_completion.instructions)
            honesty.extend(authored_completion.honesty)
        elif join_presentation is None:
            if joins != ("whole detail",):
                instructions.append(
                    f"Complete the {joins[0]} as one subassembly."
                )
            else:
                context = tuple(graph.context_parts)
                context_names = _counted_names(labels, context)
            if joins == ("whole detail",) and context:
                instructions.extend((
                    f"Bring the completed {detail.name} to {context_names}.",
                    "Complete its declared final placement during fitting; the "
                    "model does not represent that position as a critical "
                    "placement station.",
                ))
                honesty.append(
                    f"DECLARED TRUST — {context_names} is connection-free "
                    "context. final placement and insertion travel are not "
                    "analyzed; fit, stability, sliding resistance, structural "
                    "capacity, and intended-use safety are not proved.")
                tools = [DisplayRow(
                    "fit",
                    f"Actual {context_names} for the declared fit placement",
                )]
            elif joins == ("whole detail",):
                instructions.append(
                    f"Complete the {detail.name} as one bench assembly."
                )
        else:
            instructions.extend(join_presentation.instructions)
            honesty.extend(join_presentation.honesty)
            tools = list(join_presentation.tools)
        if graph.staging is not None and graph.staging.why:
            rationales.append(graph.staging.why)

    return {
        "title": (
            join_presentation.title
            if action == "join" and join_presentation is not None
            else _panel_title(
                detail, action, graph, steps, cohort, labels,
                service_semantics,
            )
        ),
        "connections": connections,
        "joins": joins,
        "process_kind": process_kind,
        "process_facts": process_facts,
        "instructions": tuple(instructions),
        "rationales": tuple(rationales),
        "honesty": tuple(honesty),
        "hardware": hardware,
        "tools": tuple(tools),
        "fastener_layouts": fastener_layouts,
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
    *,
    title: str = "Armchair Coffee Caddy — Illustrated Assembly Manual",
    basename: str = "armchair_caddy_assembly_manual.html",
    lede: str = _CADDY_MANUAL_LEDE,
    related_documents: tuple[RelatedDocumentLink, ...] = (),
    excluded_part_ids: tuple[str, ...] = (),
    join_presentation: JoinPresentation | None = None,
) -> InstructionManual:
    """Build the pure instruction-manual model for a validated detail."""
    technical_href = _relative_html_basename(technical_href, "technical_href")
    basename = _relative_html_basename(basename, "basename")
    related_documents = tuple(
        replace(
            link,
            href=_relative_html_basename(
                link.href, f"related_documents[{index}].href"
            ),
        )
        for index, link in enumerate(related_documents)
    )
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be non-empty")
    if not isinstance(lede, str) or not lede.strip():
        raise ValueError("lede must be non-empty")
    graph = detail.construction_event_graph
    if graph is None:
        raise InstructionPresentationError(
            "instruction manual requires a validated event graph")

    steps = derive_reader_steps(graph)
    installs_by_connection = {}
    for install in detail.resolved_installations:
        installs_by_connection.setdefault(install.connection, []).append(install)
    installs_by_connection = {
        label: tuple(values) for label, values in installs_by_connection.items()}
    actions = tuple(_step_action(step, installs_by_connection) for step in steps)
    step_edges = _reader_step_edges(graph, steps)
    cohorts = _panel_cohorts(steps, actions)
    labels = part_labels(detail.assembly.parts)
    service_semantics = _service_panel_semantics(detail)

    by_id = {part.id: part for part in detail.assembly.parts}
    excluded = tuple(dict.fromkeys(excluded_part_ids))
    unknown_excluded = sorted(set(excluded) - set(by_id))
    if unknown_excluded:
        raise InstructionPresentationError(
            f"manual excludes unknown part ids: {unknown_excluded!r}")
    roles = detail.roles()
    invalid_excluded = sorted(
        part_id for part_id in excluded
        if roles.get(by_id[part_id].name) != "existing"
    )
    if invalid_excluded:
        raise InstructionPresentationError(
            "manual may exclude only parts declared with the existing role; "
            f"invalid exclusions: {invalid_excluded!r}")

    event_to_step = _step_event_map(graph, steps)
    cohort_of_step = {
        step_index: panel_index
        for panel_index, cohort in enumerate(cohorts, start=1)
        for step_index in cohort
    }
    schedule = {}
    for part in detail.assembly.parts:
        if part.id in excluded:
            continue
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
            installs_by_connection, join_presentation, service_semantics)
        arrivals = tuple(part.id for part in detail.assembly.parts
                         if part.id in schedule
                         and schedule[part.id] == panel_index)
        visible = tuple(part.id for part in detail.assembly.parts
                        if part.id in schedule
                        and schedule[part.id] <= panel_index)
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
        title=title,
        basename=basename,
        technical_href=technical_href,
        panels=tuple(panels),
        step_edges=step_edges,
        part_schedule=tuple((p.id, schedule[p.id])
                            for p in detail.assembly.parts
                            if p.id not in excluded),
        inventory=(*_inventory(detail, labels), *_consumable_inventory(graph)),
        lede=lede,
        related_documents=related_documents,
        excluded_part_ids=excluded,
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
