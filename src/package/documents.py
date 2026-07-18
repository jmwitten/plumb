"""Generic technical, fabrication, and installation renderers."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .html import page


def _text(value: object) -> str:
    return escape(str(value))


def _mapping_table(rows, *, empty: str, label: str) -> str:
    rows = tuple(rows)
    if not rows:
        return f"<p>{escape(empty)}</p>"
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    head = "".join(f"<th>{_text(key).replace('_', ' ')}</th>" for key in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{_text(row.get(key, ''))}</td>" for key in columns)
        + "</tr>"
        for row in rows
    )
    table = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    return (
        '<p class="table-scroll-cue" aria-hidden="true">'
        "Scroll sideways to see all columns.</p>"
        f'<div class="table-scroll" role="region" aria-label="{_text(label)}" '
        f'tabindex="0">{table}</div>'
    )


def render_technical_html(model: dict[str, object]) -> str:
    """Render standard views, coverage, callouts, and BOM."""
    title = str(model["title"])
    views = "".join(
        f'<figure><img src="{_text(name)}" alt="{_text(name)}"></figure>'
        for name in model.get("views", ())
    )
    body = (
        f"<h1>{_text(title)}</h1>"
        f'<p class="unknown">{_text(model.get("headline", ""))}</p>'
        f"<section><h2>Standard views</h2>{views}</section>"
        "<section><h2>Validation coverage</h2>"
        f"{_mapping_table(model.get('coverage', ()), empty='No coverage facts.', label='Validation coverage table')}"
        "</section>"
        "<section><h2>Dimensions and callouts</h2>"
        f"{_mapping_table(model.get('callouts', ()), empty='No callouts.', label='Dimensions and callouts table')}"
        "</section>"
        "<section><h2>Bill of materials</h2>"
        f"{_mapping_table(model.get('bom', ()), empty='No BOM rows.', label='Bill of materials table')}"
        "</section>"
    )
    return page(title, body)


def render_fabrication_html(rows) -> str:
    """Render one fabrication section per capability-projected part."""
    sections = []
    for row in rows:
        steps = "".join(
            "<li>"
            f"{_text(step['kind'])}: "
            + ", ".join(
                f"{_text(key)}={_text(value)}"
                for key, value in sorted(step.get("params", {}).items())
            )
            + "</li>"
            for step in row.get("steps", ())
        )
        step_html = f"<ol>{steps}</ol>" if steps else (
            "<p>No modeled fabrication steps.</p>"
        )
        sections.append(
            "<section>"
            f"<h2>{_text(row['part_name'])}</h2>"
            f"<p><strong>Part ID:</strong> {_text(row['part_id'])}<br>"
            f"<strong>Stock:</strong> {_text(row['stock_profile'])}</p>"
            f"{step_html}<p><strong>Note:</strong> {_text(row.get('note', ''))}</p>"
            "</section>"
        )
    body = "<h1>Fabrication</h1>" + (
        "".join(sections) if sections else "<p>No modeled fabrication records.</p>"
    )
    return page("Fabrication", body)


def render_installation_html(model: dict[str, object]) -> str:
    """Render resolved installation contracts and construction-order facts."""
    installs = tuple(model.get("installs", ()))
    if installs:
        contracts = "<ul>" + "".join(
            f"<li>{_text(install.describe())}</li>" for install in installs
        ) + "</ul>"
    else:
        contracts = (
            '<p class="unknown">No modeled installation contract is available; '
            "installation remains UNKNOWN — NOT ANALYZED.</p>"
        )

    graph = model.get("event_graph")
    if graph is None:
        sequence = "<p>No modeled construction event graph.</p>"
    else:
        sequence = "<ol>" + "".join(
            f"<li>{_text(graph.describe(edge.a))} → "
            f"{_text(graph.describe(edge.b))} [{_text(edge.family)}]: "
            f"{_text(edge.source)}</li>"
            for edge in graph.edges
        ) + "</ol>"

    part_edges = tuple(model.get("connection_edges", ()))
    connection_table = _mapping_table(
        (
            {
                "from": edge.a,
                "to": edge.b,
                "kind": edge.kind,
                "connection": edge.connection,
            }
            for edge in part_edges
        ),
        empty="No modeled connection edges.",
        label="Connection graph table",
    )
    body = (
        f"<h1>Installation</h1><section><h2>Installation contracts</h2>{contracts}</section>"
        f"<section><h2>Construction sequence facts</h2>{sequence}</section>"
        f"<section><h2>Connection graph</h2>{connection_table}</section>"
    )
    return page("Installation", body)


def write_package_documents(
    out_dir,
    *,
    technical: dict[str, object],
    fabrication,
    installation: dict[str, object] | None = None,
) -> dict[str, Path]:
    """Write default documents and an explicitly requested installation audit."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "technical": out_dir / "technical.html",
        "fabrication": out_dir / "fabrication.html",
    }
    paths["technical"].write_text(
        render_technical_html(technical), encoding="utf-8"
    )
    paths["fabrication"].write_text(
        render_fabrication_html(fabrication), encoding="utf-8"
    )
    if installation is not None:
        paths["installation"] = out_dir / "installation.html"
        paths["installation"].write_text(
            render_installation_html(installation), encoding="utf-8"
        )
    return paths
