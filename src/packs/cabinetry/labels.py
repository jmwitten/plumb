"""Closed reader-facing vocabulary for cabinetry parts.

Machine ids and component names remain stable implementation identities. This
module owns the human name projected into documents, drawings, and hover.
"""

from __future__ import annotations

import re


_COMMON = {
    "left_end": "Left cabinet side",
    "right_end": "Right cabinet side",
    "bottom": "Cabinet bottom",
    "captured_back": "Captured back panel",
    "front_stretcher": "Front stretcher",
    "rear_stretcher": "Rear stretcher",
    "anchor_strip": "Wall anchor strip",
    "adjustable_shelf": "Adjustable shelf",
    "door_left": "Left cabinet door",
    "door_right": "Right cabinet door",
    "toe_front": "Toe-kick front",
    "toe_rear": "Toe-kick rear",
    "toe_left": "Toe-kick left return",
    "toe_right": "Toe-kick right return",
}
_DRAWER_BOX = re.compile(
    r"^drawer_(?P<cell>top|middle|bottom)_"
    r"(?P<member>side_left|side_right|front|back|bottom)$"
)
_DRAWER_FRONT = re.compile(r"^drawer_front_(?P<cell>top|middle|bottom)$")
_WALL_STUD = re.compile(r"^wall_stud_(?P<stud>.+)$")
_WALL_ANCHOR = re.compile(r"^wall_anchor_(?P<stud>.+)$")
_MEMBER_NAMES = {
    "side_left": "left side",
    "side_right": "right side",
    "front": "front",
    "back": "back",
    "bottom": "bottom",
}


def reader_name_for_role(role: str) -> str:
    """Return one canonical builder label, or fail on unowned vocabulary."""

    if role in _COMMON:
        return _COMMON[role]
    match = _DRAWER_BOX.fullmatch(role)
    if match:
        return (
            f"{match.group('cell').title()} drawer box — "
            f"{_MEMBER_NAMES[match.group('member')]}"
        )
    match = _DRAWER_FRONT.fullmatch(role)
    if match:
        return f"{match.group('cell').title()} drawer front"
    match = _WALL_STUD.fullmatch(role)
    if match:
        return f"Wall stud ({match.group('stud').replace('_', ' ')})"
    match = _WALL_ANCHOR.fullmatch(role)
    if match:
        return f"Wall anchor ({match.group('stud').replace('_', ' ')})"
    raise ValueError(
        f"cabinetry role {role!r} has no reader-facing label; add it to the "
        "closed cabinetry vocabulary before generating documents"
    )


def reader_name_for_part(part) -> str:
    """Project a cabinetry ``PartModel`` through the closed role vocabulary."""

    return reader_name_for_role(part.role)
