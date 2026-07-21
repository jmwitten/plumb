"""Model-derived, transferable fastener coordinates for reader manuals."""

from __future__ import annotations

from dataclasses import dataclass

from ..details.base import fmt_frac_in


@dataclass(frozen=True)
class FastenerLayout:
    """One edge-datum schedule derived from a modeled screw group."""

    connection: str
    label: str
    entry_part_id: str
    receiving_part_ids: tuple[str, ...]
    fastener_part_ids: tuple[str, ...]
    head_points_mm: tuple[tuple[float, float, float], ...]
    drive_direction: str


_AXIS_EDGE_TEXT = {
    0: ("left edge", "right edge", "each side edge"),
    1: ("front edge", "back edge", "the front and back edges"),
    2: ("bottom", "top", "the bottom and top"),
}


def _display(labels, part_id: str) -> str:
    return labels[part_id].display_name


def _human_list(values: tuple[str, ...]) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return " and ".join(values)
    return ", ".join(values[:-1]) + ", and " + values[-1]


def _axis_index(vector: tuple[float, float, float]) -> int | None:
    magnitudes = tuple(abs(value) for value in vector)
    axis = max(range(3), key=magnitudes.__getitem__)
    if magnitudes[axis] < 1 - 1e-6:
        return None
    if any(value > 1e-6 for index, value in enumerate(magnitudes)
           if index != axis):
        return None
    return axis


def _rounded_unique(values: tuple[float, ...]) -> tuple[float, ...]:
    result = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > 0.25:
            result.append(value)
    return tuple(result)


def _station_dimension(value_mm: float) -> str:
    """Reader dimensions use conventional sixteenths, never exotic fractions."""
    sixteenths = round(value_mm / 25.4 * 16)
    return fmt_frac_in(sixteenths / 16)


def _offset_phrase(
    values: tuple[float, ...],
    low: float,
    high: float,
    semantic_axis: int,
    semantic_sign: float,
) -> str:
    """Compact modeled coordinates against one stable final-orientation datum."""
    from_low = tuple(value - low for value in values)
    from_high = tuple(high - value for value in values)
    if semantic_sign < 0:
        from_low, from_high = from_high, from_low
    low_name, _high_name, symmetric_name = _AXIS_EDGE_TEXT[semantic_axis]
    if semantic_axis != 2:
        low_set = _rounded_unique(from_low)
        high_set = _rounded_unique(from_high)
        if (len(values) > 1 and len(low_set) == len(high_set)
                and all(abs(a - b) <= 0.25
                        for a, b in zip(low_set, high_set))):
            edge_offsets = _rounded_unique(tuple(
                min(a, b) for a, b in zip(from_low, from_high)))
            amounts = _human_list(tuple(
                _station_dimension(value) for value in edge_offsets))
            return f"{amounts} from {symmetric_name}"
    amounts = _human_list(tuple(
        _station_dimension(value) for value in _rounded_unique(from_low)))
    if semantic_axis == 2:
        return f"{amounts} above the {low_name}"
    return f"{amounts} from the {low_name}"


def _point_offset_phrase(
    value: float,
    low: float,
    high: float,
    semantic_axis: int,
    semantic_sign: float,
) -> str:
    """Locate one center from the nearest reader-visible edge."""
    from_low = value - low
    from_high = high - value
    if semantic_sign < 0:
        from_low, from_high = from_high, from_low
    low_name, high_name, _symmetric_name = _AXIS_EDGE_TEXT[semantic_axis]
    if semantic_axis == 2:
        return f"{_station_dimension(from_low)} above the {low_name}"
    if from_low <= from_high:
        return f"{_station_dimension(from_low)} from the {low_name}"
    return f"{_station_dimension(from_high)} from the {high_name}"


def _entry_surface_axis(
    points: tuple[tuple[float, float, float], ...],
    lows: tuple[float, float, float],
    highs: tuple[float, float, float],
) -> int | None:
    """Return the local bbox axis whose min/max face owns every screw head."""
    candidates = []
    for axis in range(3):
        residual = min(
            max(abs(point[axis] - lows[axis]) for point in points),
            max(abs(point[axis] - highs[axis]) for point in points),
        )
        candidates.append((residual, axis))
    residual, axis = min(candidates)
    return axis if residual <= 0.5 else None


def derive_fastener_layouts(
    detail,
    graph,
    labels,
    connections: tuple[str, ...],
    installs_by_connection: dict[str, tuple],
) -> tuple[FastenerLayout, ...]:
    """Derive one concise, transferable screw schedule per connection."""
    by_id = {part.id: part for part in detail.assembly.parts}
    result = []
    for connection in connections:
        for install in installs_by_connection.get(connection, ()):
            entry_face = install.contract.entry_face
            if entry_face is None or not install.fasteners:
                continue
            entry = by_id[entry_face.part]
            heads = tuple(tuple(by_id[part_id].datum_world(
                "head_bearing").origin) for part_id in install.fasteners)
            inverse = entry.world_frame.inverse()
            local_heads = tuple(inverse.transform_point(point)
                                for point in heads)
            axes = tuple(tuple(by_id[part_id].datum_world("axis").z_axis)
                         for part_id in install.fasteners)
            local_bb = entry.component.solid.val().BoundingBox()
            lows = (local_bb.xmin, local_bb.ymin, local_bb.zmin)
            highs = (local_bb.xmax, local_bb.ymax, local_bb.zmax)
            surface_axis = _entry_surface_axis(local_heads, lows, highs)
            if surface_axis is None:
                label = (
                    f"{_display(labels, entry.id)}: modeled screw centers are "
                    "shown, but no common entry-face edge schedule is derivable."
                )
            else:
                phrases = []
                tangent_axes = []
                for local_axis in range(3):
                    if local_axis == surface_axis:
                        continue
                    direction = entry.world_frame.transform_direction(tuple(
                        1.0 if axis == local_axis else 0.0
                        for axis in range(3)))
                    semantic_axis = max(
                        range(3), key=lambda axis: abs(direction[axis]))
                    values = tuple(
                        point[local_axis] for point in local_heads)
                    tangent_axes.append((
                        local_axis,
                        semantic_axis,
                        direction[semantic_axis],
                        values,
                    ))
                    phrases.append(_offset_phrase(
                        values,
                        lows[local_axis], highs[local_axis],
                        semantic_axis, direction[semantic_axis],
                    ))
                receivers = tuple(
                    part_id for part_id in graph.members_of[connection]
                    if part_id != entry.id)
                receiver_text = " and ".join(
                    _display(labels, part_id) for part_id in receivers)
                if (len(local_heads) > 1 and all(
                        len(_rounded_unique(axis[3])) > 1
                        for axis in tangent_axes)):
                    paired_centers = tuple(
                        "(" + _human_list(tuple(
                            _point_offset_phrase(
                                point[local_axis],
                                lows[local_axis],
                                highs[local_axis],
                                semantic_axis,
                                semantic_sign,
                            )
                            for (local_axis, semantic_axis, semantic_sign,
                                 _values) in tangent_axes
                        )) + ")"
                        for point in local_heads
                    )
                    label = (
                        f"{_display(labels, entry.id)} → {receiver_text}: "
                        f"paired centers {_human_list(paired_centers)}."
                    )
                else:
                    label = (
                        f"{_display(labels, entry.id)} → {receiver_text}: "
                        f"screw centers {_human_list(tuple(phrases))}."
                    )
            drive_axis = _axis_index(axes[0])
            if drive_axis is None:
                drive_direction = "modeled direction"
            else:
                direction_names = (("left", "right"),
                                   ("front", "back"),
                                   ("down", "up"))[drive_axis]
                drive_direction = (
                    direction_names[0] if axes[0][drive_axis] < 0
                    else direction_names[1]
                )
            receivers = tuple(
                part_id for part_id in graph.members_of[connection]
                if part_id != entry.id)
            result.append(FastenerLayout(
                connection=connection,
                label=label,
                entry_part_id=entry.id,
                receiving_part_ids=receivers,
                fastener_part_ids=tuple(install.fasteners),
                head_points_mm=heads,
                drive_direction=drive_direction,
            ))
    return tuple(result)
