"""The DetailSpec **report renderer** — turns a compiled ``doc:`` block into the
same ``validation_report.md`` the imperative details hand-write (task 4B-2).

A report is an ORDERED list of sections. Authored PROSE (title, architect notes,
assumptions, field-verify text) is carried verbatim except for ``{token}``
interpolations, which resolve through the value language over the compiled
param+derived namespace (a cited param can't drift from the geometry) plus a
small REPORT-CONTEXT namespace (a finding count, the result verdict, a
cross-check value). The COMPUTED sections — findings loops, the sampled
derivation log, the sampled hardware-presence list, the BOM table — the renderer
fills from the live model, matching each detail's exact formatting.

Adjacent sections are joined by exactly one blank line (the uniform spacing every
imperative report already uses); every section renders WITHOUT a leading or
trailing blank, so the join reproduces the report byte-for-byte. The output
carries NO trailing newline (``"\\n".join(lines)``, exactly as the imperative
``_write_report`` writes it).
"""

from __future__ import annotations

from collections import Counter

from ..core import IN  # noqa: F401  (kept: value language yields authoring units)
from .schema import (
    BomTableSection,
    DerivationLogSection,
    FindingsSection,
    HardwarePresenceSection,
    ProseSection,
)
from .values import SpecValueError, evaluate


class ReportRenderError(ValueError):
    """A doc prose token could not be interpolated (an unknown name, a bad
    format spec). Names the offending token in the teaching style."""


def render_report(detail, doc) -> str:
    """Render ``detail``'s :class:`~detailgen.spec.schema.DocSpec` ``doc`` to the
    report markdown. ``detail`` is a validated :class:`SpecDetail` (its
    ``report`` / ``derivation_log`` / ``bom_table`` / ``cross_check`` are
    available — this is invoked only by the gated ``render``)."""
    namespace = detail.namespace
    context = _report_context(detail)
    out: list[str] = []
    for i, section in enumerate(doc.sections):
        if i:
            out.append("")  # exactly one blank line between sections
        out.extend(_render_section(section, detail, namespace, context))
    return "\n".join(out)


def _report_context(detail) -> dict:
    """The report-context namespace: values computed from the live model that a
    prose token may cite alongside params/derived. Findings-derived counts, the
    result verdict, and (when the detail has one) the cross-check summary."""
    report = detail.report
    findings = report.findings
    fails = report.failures
    by_kind = Counter(f.check for f in findings)
    # Owner directive (Joel, 2026-07-08 §3): the reader-facing result LEADS with
    # the per-family breakdown — what this detail actually established, derived
    # from its coverage matrix — rather than an unqualified "CLEAN" that overstates
    # confidence. "CLEAN"/require_clean survives as a demoted internal verdict. The
    # breakdown comes from the coverage machinery, so it can never diverge from the
    # matrix the base appends to this same report.
    from ..validation.coverage import coverage_matrix, render_headline_line

    internal = "CLEAN — all checks pass" if report.ok else f"{len(fails)} FAILURES"
    ctx: dict = {
        "result_verdict": (
            f"{render_headline_line(coverage_matrix(report))} "
            f"(internal verdict: {internal})"),
        "interference_checks": by_kind.get("interference", 0),
        "interference_failures": sum(1 for f in fails if f.check == "interference"),
    }
    cc = detail.cross_check()
    if cc:
        ctx["cc_solver"] = cc.get("solver")
        ctx["cc_max_radial_deviation_in"] = cc.get("max_radial_deviation_in")
        ctx["cc_note"] = cc.get("note", "")
    return ctx


def _render_section(section, detail, namespace, context) -> list[str]:
    if isinstance(section, ProseSection):
        return interpolate(section.text, namespace, context).rstrip("\n").split("\n")
    if isinstance(section, FindingsSection):
        return _render_findings(section, detail)
    if isinstance(section, DerivationLogSection):
        return _render_derivation_log(section, detail, namespace, context)
    if isinstance(section, HardwarePresenceSection):
        return _render_hardware_presence(section, detail)
    if isinstance(section, BomTableSection):
        return _render_bom_table(section, detail)
    raise ReportRenderError(f"unknown doc section {type(section).__name__}")


def _finding_line(f) -> str:
    return f"- {'PASS' if f.passed else 'FAIL'} {f.subject} — {f.detail}"


def _render_findings(section: FindingsSection, detail) -> list[str]:
    lines = [section.header]
    for f in detail.report.findings:
        if f.check == section.check:
            lines.append(_finding_line(f))
    return lines


def _render_derivation_log(section, detail, namespace, context) -> list[str]:
    lines = [section.header]
    if section.preamble:
        lines.extend(interpolate(section.preamble, namespace, context)
                     .rstrip("\n").split("\n"))
    log = detail.derivation_log
    n_conn = len(detail.connections())
    lines.append(f"- **{len(log)} facts derived** from "
                 f"**{n_conn} declared Connections**.")
    if section.mode == "per_connection":
        by_conn: dict = {}
        for fact in log:
            by_conn.setdefault(fact.connection, []).append(fact)
        for conn_label, facts in by_conn.items():
            for fact in facts[:section.cap]:
                lines.append(_fact_line(fact))
            if len(facts) > section.cap:
                lines.append(f"  - ...and {len(facts) - section.cap} more "
                             f"facts for {conn_label!r}.")
    else:  # first_n
        for fact in log[:section.cap]:
            lines.append(_fact_line(fact))
        if len(log) > section.cap:
            lines.append(f"  - ...and {len(log) - section.cap} more.")
    return lines


def _fact_line(fact) -> str:
    """One derivation-log line: confidence + fact + producing rule — plus
    the fact's assumption notes, which carry the WHY behind assumption-grade
    content (the half-length embedment rule, the toe-screw technique angle).
    Guardrail #7 asks that a reviewer see WHICH content is assumption-grade
    and why, so the notes are part of the doc disclosure, not internal
    metadata."""
    line = (f"  - [{fact.confidence}] {fact.fact} "
            f"(`{fact.rule}`, via {fact.connection})")
    for note in fact.assumptions:
        line += f"\n    - assumption: {note}"
    return line


def _render_hardware_presence(section, detail) -> list[str]:
    report = detail.report
    lines = [section.header]
    hw = [f for f in report.findings if f.check == "connection_hardware"]
    by_label: dict = {}
    for f in hw:
        by_label.setdefault(f.subject.split(":", 1)[0], []).append(f)
    word = "PASS" if report.ok else "see failures above"
    for label, group in by_label.items():
        for f in group[:section.cap]:
            lines.append(_finding_line(f))
        if len(group) > section.cap:
            lines.append(f"  - ...and {len(group) - section.cap} more for "
                         f"{label!r} (all {word}).")
    lines.append(f"- **{len(hw)} hardware-presence checks** across "
                 f"**{len(by_label)} declared Connections** (all {word}).")
    return lines


def _render_bom_table(section, detail) -> list[str]:
    lines = [
        section.header, "",
        "| Qty | Item | Material | Dimensions | Source | Assumptions |",
        "|----:|------|----------|------------|--------|-------------|",
    ]
    for r in detail.bom_table():
        lines.append(f"| {r['qty']} | {r['item']} | {r['material']} | "
                     f"{r['dimensions']} | {r['source']} | {r['assumptions']} |")
    return lines


# -- value interpolation ------------------------------------------------------


def interpolate(text: str, namespace: dict, context: dict) -> str:
    """Substitute ``{expr}`` / ``{expr:fmt}`` tokens in ``text``. ``expr`` is a
    report-context name or a value-language expression over ``namespace``
    (authoring-unit magnitudes); ``fmt`` is a Python format spec. ``{{`` / ``}}``
    are literal braces. A bare token with no format renders an integral number as
    an int (so a count reads ``3``, not ``3.0``); a formatted token uses
    ``format(value, fmt)`` exactly as the imperative f-string did."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "{":
            if i + 1 < n and text[i + 1] == "{":
                out.append("{")
                i += 2
                continue
            j = text.find("}", i + 1)
            if j == -1:
                raise ReportRenderError(
                    f"doc prose has an unbalanced '{{' near {text[i:i + 40]!r}")
            out.append(_resolve_token(text[i + 1:j], namespace, context))
            i = j + 1
        elif c == "}":
            if i + 1 < n and text[i + 1] == "}":
                out.append("}")
                i += 2
                continue
            out.append("}")
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _resolve_token(token: str, namespace: dict, context: dict) -> str:
    expr, fmt = (token.split(":", 1) + [None])[:2] if ":" in token else (token, None)
    key = expr.strip()
    if key in context:
        value = context[key]
    else:
        try:
            value = evaluate(key, namespace)
        except SpecValueError as e:
            raise ReportRenderError(
                f"doc prose interpolation {{{token}}}: {e}") from None
    if fmt:
        try:
            return format(value, fmt)
        except (ValueError, TypeError) as e:
            raise ReportRenderError(
                f"doc prose {{{token}}}: bad format {fmt!r} for value "
                f"{value!r}: {e}") from None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return str(value)
