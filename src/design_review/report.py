"""Deterministic developer-facing design-selection HTML."""

from __future__ import annotations

from html import escape

from .gate import DesignGovernance, governance_for_review
from .schema import CRITERIA, DesignReviewDoc
from .validation import DesignReviewResult


def _e(value) -> str:
    return escape(str(value), quote=True)


def _status(ready: bool) -> str:
    return "READY" if ready else "BLOCKED"


def render_design_review_html(
    doc: DesignReviewDoc,
    result: DesignReviewResult,
    governance: DesignGovernance | None = None,
) -> str:
    if governance is None:
        governance = governance_for_review(
            doc, selected_concept=doc.decision.selected_concept
        )
    concepts = {concept.id: concept for concept in doc.concepts}
    cells = {(cell.concept, cell.criterion): cell for cell in doc.comparison}
    lines = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{_e(doc.title)} — design selection</title>",
        "<style>",
        "body{font:15px/1.45 system-ui,sans-serif;max-width:1180px;margin:0 auto;padding:28px;color:#202124}",
        "h1,h2,h3{line-height:1.15} table{border-collapse:collapse;width:100%;margin:12px 0 28px}",
        "th,td{border:1px solid #ccd0d5;padding:8px;vertical-align:top;text-align:left}",
        ".ready{color:#176b36;font-weight:700}.blocked{color:#a1261d;font-weight:700}",
        ".unknown{background:#fff4ce}.mono{font-family:ui-monospace,monospace;word-break:break-all}",
        "</style></head><body>",
        f"<h1>{_e(doc.title)}</h1>",
        f"<p>Project <code>{_e(doc.project_id)}</code> · record status <strong>{_e(doc.status)}</strong></p>",
        "<h2>Lifecycle gates</h2>",
        f'<p class="{"ready" if governance.modeling_ready else "blocked"}">Production promotion: {_status(governance.modeling_ready)}</p>',
        f'<p class="{"ready" if governance.delivery_ready else "blocked"}">Delivery: {_status(governance.delivery_ready)}</p>',
        f'<p class="mono">Selection fingerprint: {_e(governance.selection_digest)}</p>',
    ]
    if governance.model_digest is not None:
        lines.append(
            f'<p class="mono">Model fingerprint: {_e(governance.model_digest)}</p>'
        )
    lines.extend(["<h2>Blocking findings</h2>", "<ul>"])
    if result.blocking:
        lines.extend(
            f"<li><code>{_e(finding.code)}</code> at "
            f"<code>{_e(finding.path)}</code>: {_e(finding.message)}</li>"
            for finding in result.blocking
        )
    else:
        lines.append("<li>None — the structured draft is complete; approval is a separate gate.</li>")
    lines.extend([
        "</ul>",
        "<h2>Design brief</h2>",
        "<dl>",
        f"<dt>Use</dt><dd>{_e(doc.brief.use)}</dd>",
        f"<dt>Loads</dt><dd>{_e(doc.brief.loads)}</dd>",
        f"<dt>Fit range</dt><dd>{_e(doc.brief.fit_range)}</dd>",
        f"<dt>Appearance</dt><dd>{_e(doc.brief.appearance)}</dd>",
        f"<dt>Builder skill</dt><dd>{_e(doc.brief.builder_skill)}</dd>",
        f"<dt>Tools</dt><dd>{_e(', '.join(doc.brief.tools))}</dd>",
        "</dl>",
        "<h3>Required features</h3><ul>",
    ])
    lines.extend(
        f"<li><code>{_e(item.id)}</code> — {_e(item.text)}</li>"
        for item in doc.brief.required_features
    )
    lines.append("</ul><h3>Prioritized constraints</h3><ol>")
    lines.extend(
        f"<li value=\"{item.priority}\"><code>{_e(item.id)}</code> — {_e(item.text)}</li>"
        for item in sorted(doc.brief.constraints, key=lambda item: item.priority)
    )
    lines.append("</ol><h2>Precedent provenance</h2><table><thead><tr><th>Id</th><th>Kind / source</th><th>Observed construction</th><th>Lessons</th></tr></thead><tbody>")
    for source in doc.precedents:
        lessons = "<ul>" + "".join(
            f"<li>{_e(lesson)}</li>" for lesson in source.lessons
        ) + "</ul>"
        lines.append(
            f"<tr><td><code>{_e(source.id)}</code></td>"
            f"<td>{_e(source.kind)}<br><a href=\"{_e(source.url)}\">"
            f"{_e(source.title)}</a><br>{_e(source.publisher)} · accessed "
            f"{_e(source.accessed_on)}</td>"
            f"<td>{_e(source.construction_pattern)}</td><td>{lessons}</td></tr>"
        )
    lines.append("</tbody></table><h2>Concepts</h2>")
    for concept in doc.concepts:
        lines.extend([
            f"<h3><code>{_e(concept.id)}</code> — {_e(concept.title)}</h3>",
            f"<p>{_e(concept.summary)}</p>",
            "<table><tbody>",
        ])
        for name, value in concept.signature.__dict__.items():
            lines.append(f"<tr><th>{_e(name)}</th><td>{_e(value)}</td></tr>")
        lines.append("</tbody></table><h4>Feature inventory</h4><ul>")
        lines.extend(
            f"<li><code>{_e(concept.id)}.{_e(feature.id)}</code> — "
            f"{_e(feature.description)}; precedents: "
            f"{_e(', '.join(feature.precedent_refs) or 'none')}</li>"
            for feature in concept.features
        )
        lines.append("</ul><h4>Simplification review</h4><ul>")
        lines.extend(
            f"<li><strong>{_e(part.part_family)}</strong>: {_e(part.purpose)} "
            f"Joinery review: {_e(part.joinery_replacement)}</li>"
            for part in concept.parts
        )
        lines.append("</ul>")
    lines.append("<h2>Comparison matrix</h2><table><thead><tr><th>Criterion</th>")
    lines.extend(f"<th>{_e(concept.id)}</th>" for concept in doc.concepts)
    lines.append("</tr></thead><tbody>")
    for criterion in CRITERIA:
        lines.append(f"<tr><th>{_e(criterion)}</th>")
        for concept in doc.concepts:
            cell = cells.get((concept.id, criterion))
            if cell is None:
                lines.append('<td class="blocked">MISSING</td>')
                continue
            css = "unknown" if cell.assessment == "unknown" else ""
            lines.append(
                f'<td class="{css}"><strong>{_e(cell.assessment)}</strong><br>'
                f"{_e(cell.explanation)}<br><small>Evidence: "
                f"{_e(', '.join(cell.evidence_refs))}</small></td>"
            )
        lines.append("</tr>")
    lines.append("</tbody></table><h2>Novelty and deviations</h2><ul>")
    if not doc.deviations:
        lines.append("<li>No unsupported feature deviations are recorded.</li>")
    for deviation in doc.deviations:
        if deviation.forcing_requirement:
            basis = f"forced by {_e(deviation.forcing_requirement)}"
        elif deviation.exception is not None:
            basis = (
                f"exception approved by {_e(deviation.exception.approved_by)} "
                f"on {_e(deviation.exception.approved_on)}: "
                f"{_e(deviation.exception.rationale)}; cost/risk: "
                f"{_e(deviation.exception.cost_or_risk)}"
            )
        else:
            basis = '<span class="blocked">UNSUPPORTED</span>'
        lines.append(
            f"<li><code>{_e(deviation.feature_ref)}</code> — {basis}</li>"
        )
    selected = concepts.get(doc.decision.selected_concept)
    lines.extend([
        "</ul><h2>Decision</h2>",
        f"<p>Selected concept: <strong>{_e(doc.decision.selected_concept)}</strong>"
        + (f" — {_e(selected.title)}" if selected else "") + "</p>",
        f"<p>Application: <strong>{_e(doc.decision.application)}</strong></p>",
        f"<p>{_e(doc.decision.rationale)}</p>",
        f"<p>Decisive cells: {_e(', '.join(doc.decision.decisive_cells))}</p>",
        "<h3>Accepted tradeoffs</h3><ul>",
    ])
    lines.extend(f"<li>{_e(item)}</li>" for item in doc.decision.tradeoffs)
    lines.append("</ul></body></html>\n")
    return "\n".join(lines)
