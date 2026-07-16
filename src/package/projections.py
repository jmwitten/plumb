"""Capability-driven projections from one compiled and validated detail."""

from __future__ import annotations

from pathlib import Path


def fabrication_projection(detail) -> tuple[dict[str, object], ...]:
    """Project typed fabrication records without inspecting project identity."""
    rows = []
    for part in detail.assembly.parts:
        record = part.component.fabrication_record(part.id)
        if record is None:
            continue
        rows.append(
            {
                "part_id": part.id,
                "part_name": part.name,
                "stock_profile": record.stock.profile,
                "steps": tuple(
                    {"kind": step.kind, "params": step.params_dict()}
                    for step in record.steps
                ),
                "note": record.fab_note(),
            }
        )
    return tuple(rows)


def technical_projection(detail, view_paths: tuple[Path, ...]) -> dict[str, object]:
    """Project compiled facts and document-relative standard-view paths."""
    from ..validation.coverage import coverage_matrix, render_headline_line

    matrix = coverage_matrix(detail.report)
    return {
        "title": detail.name,
        "headline": render_headline_line(matrix),
        "views": tuple(Path(path).as_posix() for path in view_paths),
        "coverage": tuple(row.to_dict() for row in matrix),
        "bom": tuple(detail.bom_table()),
        "callouts": tuple(detail.rendered_callouts()),
    }


def installation_projection(detail) -> dict[str, object]:
    """Project typed installation and process facts without prose inference."""
    return {
        "installs": detail.resolved_installations,
        "event_graph": detail.construction_event_graph,
        "connection_edges": tuple(detail.connection_edges),
        "coverage": tuple(detail.coverage_matrix()),
    }
