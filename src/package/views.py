"""Render deterministic standard camera views from an existing assembly."""

from __future__ import annotations

from pathlib import Path

from ..rendering.export import VIEWS, export_png


def render_standard_views(detail, out_dir, names) -> tuple[Path, ...]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    unknown = sorted(set(names) - set(VIEWS))
    if unknown:
        raise ValueError(
            f"unknown standard view(s) {unknown}; valid: {sorted(VIEWS)}"
        )
    return tuple(
        export_png(detail.assembly, out_dir / f"{name}.png", view=name)
        for name in names
    )
