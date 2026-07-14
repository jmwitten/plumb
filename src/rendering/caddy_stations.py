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
    top_id = _single_reader_id(detail, "Top board")
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
        datum="top-board end faces and width centerline",
        p0=(bb.xmin, center[1], z),
        p1=(center[0], center[1], z),
    )


def _bond_stations(detail, panel, by_id, labels, graph):
    top_id = _single_reader_id(detail, "Top board")
    top_bb = _bbox(by_id[top_id])
    length = top_bb.xmax - top_bb.xmin
    result = []
    for connection in panel.connections:
        members = graph.members_of.get(connection, ())
        rails = [pid for pid in members
                 if labels[pid].reader_name == "Registration rail"]
        if len(rails) != 1 or top_id not in members:
            raise InstructionPresentationError(
                f"panel {panel.index} bond {connection!r} does not resolve "
                "to one registration rail and the top board")
        rail_id = rails[0]
        rail_bb = _bbox(by_id[rail_id])
        rail_center = _center(rail_bb)
        if rail_center[0] >= 0:
            end_x, station_x = top_bb.xmax, rail_bb.xmax
            near, far = end_x - station_x, station_x - top_bb.xmin
        else:
            end_x, station_x = top_bb.xmin, rail_bb.xmin
            near, far = station_x - end_x, top_bb.xmax - station_x
        front_flush = abs(rail_bb.ymin - top_bb.ymin) <= _RECONCILE_TOL_MM
        back_flush = abs(rail_bb.ymax - top_bb.ymax) <= _RECONCILE_TOL_MM
        underside_flush = abs(rail_bb.zmax - top_bb.zmin) <= _RECONCILE_TOL_MM
        if not (front_flush and back_flush and underside_flush):
            raise InstructionPresentationError(
                f"panel {panel.index} registration rail {rail_id!r} is "
                "missing the compiled front/back/top-underside flush datums")
        result.append(PlacementStation(
            feature="registration rail placement",
            label=(f"Set {labels[rail_id].display_name} {_fmt_mm(near)} in "
                   "from its top-board end, with front/back edges flush and "
                   "its top edge flush to the top underside."),
            reference_part_id=top_id,
            near_mm=near,
            far_mm=far,
            reference_length_mm=length,
            datum="top-board end, front/back edges, and underside",
            p0=(end_x, rail_center[1], top_bb.zmin),
            p1=(station_x, rail_center[1], top_bb.zmin),
        ))
    return tuple(result)


def _fastener_stations(detail, panel, by_id, labels, graph, checks):
    top_id = _single_reader_id(detail, "Top board")
    top_bb = _bbox(by_id[top_id])
    installs = {install.connection: install for install in checks.installs}
    result = []
    for connection in panel.connections:
        install = installs.get(connection)
        if install is None:
            raise InstructionPresentationError(
                f"panel {panel.index} fasten connection {connection!r} "
                "has no resolved installation")
        rail_id = install.contract.entry_face.part
        if (rail_id not in graph.members_of.get(connection, ())
                or labels[rail_id].reader_name != "Registration rail"):
            raise InstructionPresentationError(
                f"panel {panel.index} fasten connection {connection!r} "
                "entry face is not its registration rail")
        rail_bb = _bbox(by_id[rail_id])
        length = rail_bb.ymax - rail_bb.ymin
        for fastener_id in install.fasteners:
            if fastener_id not in by_id:
                raise InstructionPresentationError(
                    f"panel {panel.index} fastener {fastener_id!r} is absent")
            center = by_id[fastener_id].world_frame.origin
            near = center[1] - rail_bb.ymin
            far = rail_bb.ymax - center[1]
            drop = top_bb.zmin - center[2]
            result.append(PlacementStation(
                feature="rail-to-side screw center",
                label=(f"{labels[fastener_id].display_name}: {_fmt_mm(near)} "
                       "from the front rail end, "
                       f"{_fmt_mm(far)} from the back rail end, and "
                       f"{_fmt_mm(drop)} below the top underside."),
                reference_part_id=rail_id,
                near_mm=near,
                far_mm=far,
                reference_length_mm=length,
                datum="registration-rail front/back ends and top underside",
                p0=(center[0], rail_bb.ymin, center[2]),
                p1=center,
                secondary_mm=drop,
                secondary_datum="top underside",
                q0=(center[0], center[1], top_bb.zmin),
                q1=center,
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
        elif panel.action == "fasten":
            stations = _fastener_stations(
                detail, panel, by_id, labels, graph, checks)
        else:
            stations = ()
        panels.append(_with_reconciled(panel, stations))

    for action in ("prepare", "bond", "fasten"):
        panel = next((value for value in panels if value.action == action), None)
        if panel is None or not panel.stations:
            raise InstructionPresentationError(
                f"armchair caddy {action!r} panel is not station-complete")
    return replace(manual, panels=tuple(panels))
