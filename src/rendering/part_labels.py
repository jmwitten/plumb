"""Shared reader-facing labels for placed assembly parts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class PartLabel:
    machine_name: str
    reader_name: str
    item: str
    index: int
    count: int


def part_labels(parts) -> dict[str, PartLabel]:
    """Project placed parts to immutable display labels keyed by part id."""
    parts = tuple(parts)
    names = tuple((p.reader_name or p.name) for p in parts)
    totals = Counter(names)
    seen = Counter()
    result = {}
    for placed, name in zip(parts, names):
        seen[name] += 1
        result[placed.id] = PartLabel(
            placed.name,
            name,
            placed.component.bom_label(),
            seen[name],
            totals[name],
        )
    return result
