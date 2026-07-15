"""Geometry-derived placement stations for the armchair caddy manual.

This adapter is deliberately narrow: it selects semantic caddy members from
the validated graph and shared reader labels, then measures their compiled
world geometry.  It does not copy dimension literals out of the source spec.
"""

from __future__ import annotations

from dataclasses import replace

from ..details.base import fmt_frac_in
from .instruction_panels import (
    InstructionManual,
    InstructionPanel,
    InstructionPresentationError,
    PlacementStation,
)
from .part_labels import part_labels


_RECONCILE_TOL_MM = 0.5


def _bbox(part):
    return part.world_solid().val().BoundingBox()


def _center(bb) -> tuple[float, float, float]:
    return (
        (bb.xmin + bb.xmax) / 2,
        (bb.ymin + bb.ymax) / 2,
        (bb.zmin + bb.zmax) / 2,
    )


def _fmt_mm(mm: float) -> str:
    inches = mm / 25.4
    sixteenths = round(inches * 16)
    if abs(inches - sixteenths / 16) < 1e-6:
        return fmt_frac_in(inches)
    return f'{inches:.2f}"'


def _reconcile(panel: InstructionPanel, station: PlacementStation) -> None:
    residual = abs(
        station.near_mm + station.far_mm - station.reference_length_mm)
    if residual > _RECONCILE_TOL_MM:
        raise InstructionPresentationError(
            f"panel {panel.index} ({panel.action}) station "
            f"{station.feature!r} on {station.reference_part_id!r} is "
            "inconsistent: "
            f"near={station.near_mm:.3f} mm, far={station.far_mm:.3f} mm, "
            f"reference={station.reference_length_mm:.3f} mm, "
            f"datum={station.datum!r}, residual={residual:.3f} mm")


def _with_reconciled(
    panel: InstructionPanel,
    stations: tuple[PlacementStation, ...],
) -> InstructionPanel:
    for station in stations:
        if not station.datum:
            raise InstructionPresentationError(
                f"panel {panel.index} ({panel.action}) station "
                f"{station.feature!r} on {station.reference_part_id!r} "
                "has no datum")
        _reconcile(panel, station)
    return replace(panel, stations=stations)


def _reader_ids(detail, reader_name: str) -> tuple[str, ...]:
    labels = part_labels(detail.assembly.parts)
    return tuple(part.id for part in detail.assembly.parts
                 if labels[part.id].reader_name == reader_name)


def _single_reader_id(detail, reader_name: str) -> str:
    ids = _reader_ids(detail, reader_name)
    if len(ids) != 1:
        raise InstructionPresentationError(
            f"armchair caddy station adapter requires exactly one "
            f"{reader_name!r}; found {ids!r}")
    return ids[0]


def _bore_station(detail, panel, by_id, labels) -> PlacementStation:
    top_id = _single_reader_id(detail, "Top panel")
    top = by_id[top_id]
    record_fn = getattr(top.component, "fabrication_record", None)
    record = record_fn() if record_fn is not None else None
    bores = [step for step in (record.steps if record is not None else ())
             if step.kind == "bore"]
    if len(bores) != 1:
        raise InstructionPresentationError(
            f"panel {panel.index} (prepare) requires one typed bore on "
            f"{labels[top_id].display_name}; found {len(bores)}")
    params = dict(bores[0].params)
    try:
        local_center = (float(params["cx"]), float(params["cy"]), 0.0)
    except (KeyError, TypeError, ValueError) as exc:
        raise InstructionPresentationError(
            f"panel {panel.index} (prepare) bore has no numeric cx/cy datum") from exc

    center = top.world_frame.transform_point(local_center)
    bb = _bbox(top)
    length = bb.xmax - bb.xmin
    near = center[0] - bb.xmin
    far = bb.xmax - center[0]
    z = bb.zmax + 8.0
    feature_name = str(params.get("feature", "bore"))
    return PlacementStation(
        feature=f"{feature_name} center",
        label=(f"Center the {feature_name} {_fmt_mm(near)} from either end "
               "and on the board width centerline."),
        reference_part_id=top_id,
        near_mm=near,
        far_mm=far,
        reference_length_mm=length,
        datum="top-panel end faces and width centerline",
        p0=(bb.xmin, center[1], z),
        p1=(center[0], center[1], z),
    )


def _bond_stations(detail, panel, by_id, labels, graph):
    top_id = _single_reader_id(detail, "Top panel")
    top_bb = _bbox(by_id[top_id])
    length = top_bb.ymax - top_bb.ymin
    result = []
    for connection in panel.connections:
        members = graph.members_of.get(connection, ())
        sides = [pid for pid in members
                 if labels[pid].reader_name == "Side panel"]
        dowels = list(dict.fromkeys(
            edge.b for edge in detail._connection_edges
            if edge.connection == connection
            and edge.kind == "installed_before"
            and labels[edge.b].reader_name == "Corner key"
        ))
        if len(sides) != 1 or len(dowels) != 2 or top_id not in members:
            raise InstructionPresentationError(
                f"panel {panel.index} bond {connection!r} does not resolve "
                "to the top panel, one side panel, and two corner keys")
        side_id = sides[0]
        side_bb = _bbox(by_id[side_id])
        if (abs(side_bb.ymin - top_bb.ymin) > _RECONCILE_TOL_MM
                or abs(side_bb.ymax - top_bb.ymax) > _RECONCILE_TOL_MM):
            raise InstructionPresentationError(
                f"panel {panel.index} side panel {side_id!r} is missing "
                "the compiled front/back flush datums")

        ordered = sorted(dowels, key=lambda pid: by_id[pid].world_frame.origin[1])
        front, back = (by_id[pid].world_frame.origin for pid in ordered)
        near = front[1] - top_bb.ymin
        far = top_bb.ymax - front[1]
        mirrored_near = top_bb.ymax - back[1]
        if abs(near - mirrored_near) > _RECONCILE_TOL_MM:
            raise InstructionPresentationError(
                f"panel {panel.index} corner keys for {connection!r} are "
                "not symmetric from the front/back edges")
        joint_x = (front[0] + back[0]) / 2
        result.append(PlacementStation(
            feature="symmetric corner-key pair",
            label=(f"At the {labels[side_id].display_name} corner, mark one "
                   f"Corner key center {_fmt_mm(near)} from each front/back "
                   "edge. Bring the panel edges flush and clamp until the "
                   "miter faces close without a gap."),
            reference_part_id=top_id,
            near_mm=near,
            far_mm=far,
            reference_length_mm=length,
            datum="top-panel front/back edges and the closed miter faces",
            p0=(joint_x, top_bb.ymin, front[2]),
            p1=front,
            mirror_p0=(joint_x, top_bb.ymax, back[2]),
            mirror_p1=back,
        ))
    return tuple(result)


def attach_caddy_stations(detail, manual: InstructionManual) -> InstructionManual:
    """Attach complete, geometry-measured caddy placement data to panels."""
    if detail.name != "armchair caddy":
        raise InstructionPresentationError(
            f"caddy station adapter cannot render {detail.name!r}")
    checks = getattr(detail, "_connection_checks", None)
    graph = getattr(checks, "event_graph", None)
    if graph is None:
        raise InstructionPresentationError(
            "caddy station adapter requires a validated event graph")

    by_id = {part.id: part for part in detail.assembly.parts}
    labels = part_labels(detail.assembly.parts)
    panels = []
    for panel in manual.panels:
        if panel.action == "prepare":
            stations = (_bore_station(detail, panel, by_id, labels),)
        elif panel.action == "bond":
            stations = _bond_stations(
                detail, panel, by_id, labels, graph)
        else:
            stations = ()
        panels.append(_with_reconciled(panel, stations))

    for action in ("prepare", "bond"):
        panel = next((value for value in panels if value.action == action), None)
        if panel is None or not panel.stations:
            raise InstructionPresentationError(
                f"armchair caddy {action!r} panel is not station-complete")
    return replace(manual, panels=tuple(panels))
