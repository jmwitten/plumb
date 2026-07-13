"""The derived Build Sequence reader surface (task CPGCORE, STEPDOC design
§5.1/§5.2 minus views — the ONE v1-core reader surface, owner amendment 1).

The owner's directive ("with complex installations we should break it up
into steps") is a Presentation-Graph demand backed by a process IR: the
section rendered here is a projection of the merged event graph — the SAME
derived + declared order facts the axis-3 installability verdicts are judged
on — never hand-typed prose (design §6.5: a hand-authored sequence is
exactly the kind of load-bearing construction fact that rots).

Vocabulary (owner amendment 5, BINDING): the numbered units below are reader
STEPS (:class:`~detailgen.assemblies.event_graph.ReaderStep`, presentation
units); an authored ``sequence:`` grouping is a STAGE — a step that presents
a stage carries the stage's claim and its why inline, so a reader can
distinguish "this order is what the joints require" from "this order is
what the author chose" (declared order is visible, never ambient).

Reaches BOTH per-detail reader surfaces the install disclosures reach:
``validation_report.md`` (lifecycle level, ``Detail._write_build_sequence``)
and the HTML build document (``scripts/single_detail_report.py``).
"""

from __future__ import annotations

from ..assemblies.event_graph import derive_reader_steps, unordered_parts

#: The standing intro every rendered build sequence carries — the section's
#: epistemic contract in three sentences (derived, one-of-many valid
#: linearizations, accretion + P1 stated).
SEQUENCE_INTRO = (
    "Derived from the construction process graph — the same derived and "
    "declared order facts the installability verdicts are judged on; no "
    "step title, order, or sentence here is hand-typed. The printed order "
    "is ONE valid linearization, chosen deterministically for "
    "presentation: every verdict holds for EVERY build order that respects "
    "the order facts, so a builder who deviates from this printout but "
    "respects them is still covered. A step that rests on an authored "
    "claim prints the claim and its why. Parts are assumed to accrete at "
    "their final pose; insertion travel is not analyzed at any rung (P1)."
)


def _fab_note(component) -> str:
    """The part's carpenter-readable fabrication note from the ONE source
    the cut plan reads (``ProcessRecord.fab_note()`` — the viewer-tooltip
    precedent). Empty for a part with no fabrication record."""
    fn = getattr(component, "fabrication_record", None)
    record = fn() if fn is not None else None
    return record.fab_note() if record is not None else ""


def derive_build_sequence(detail):
    """The reader steps + trailing unordered-part ids for ``detail``'s last
    validation, or ``(None, ())`` when the detail carries no event graph
    (no connections and no authored sequence — there is no order content
    to derive, and fabricating a section would be fake coverage)."""
    checks = getattr(detail, "_connection_checks", None)
    graph = getattr(checks, "event_graph", None) if checks is not None else None
    if graph is None or (not graph.conn_labels and not graph.stages
                         and not graph.units):
        return None, ()
    return derive_reader_steps(graph), unordered_parts(graph)


def build_sequence_model(detail):
    """The fully-derived content model BOTH renderers (markdown report,
    HTML build document) print — one derivation, two views, so the two
    surfaces can never disagree. ``None`` when no event graph exists.

    Returns ``(steps, loose_names)`` where each step is a dict:
    ``title`` (the reader-step title), ``why`` (the authored stage/unit why,
    or ``None`` for a per-connection install unit), ``claim`` (``stage``,
    ``staging``, or ``None``), ``places`` (name, BOM
    label, fab note triples), ``drives`` (resolved-contract one-liners,
    per-field provenance included — the disclosure content scoped to the
    step), ``units`` (contract-less install-unit labels: bonds,
    connectors)."""
    steps, loose = derive_build_sequence(detail)
    if steps is None:
        return None
    checks = detail._connection_checks
    graph = checks.event_graph
    by_id = {p.id: p for p in detail.assembly.parts}
    installs_of: dict[str, list] = {}
    for ri in checks.installs:
        installs_of.setdefault(ri.connection, []).append(ri)

    out = []
    for step in steps:
        places = []
        for pid in step.parts_placed:
            p = by_id.get(pid)
            if p is None:
                continue
            places.append((p.name, p.component.bom_label(),
                           _fab_note(p.component)))
        drives, units = [], []
        for label in step.connections:
            ris = installs_of.get(label, [])
            if not ris:
                units.append(label)
            drives.extend(ri.describe() for ri in ris)
        out.append({
            "title": step.title,
            "why": (step.stage.why if step.stage is not None else
                    step.unit.why if step.unit is not None else None),
            "claim": ("stage" if step.stage is not None else
                      "staging" if step.unit is not None else None),
            "places": places, "drives": drives, "units": units,
            "joins": step.joins,
        })
    loose_names = tuple(graph.part_names.get(pid, pid) for pid in loose)
    return out, loose_names


#: The trailing honesty line for parts with no order fact at all.
def unordered_note(names) -> str:
    return (
        f"No order fact exists for: {', '.join(names)} — consumed by no "
        f"connection and claimed by no authored stage, so a printed "
        f"position would be an invention, not a derivation (a context "
        f"body's presence at any step is likewise underdetermined until a "
        f"staging declaration is authored).")


def render_build_sequence_md(detail) -> str:
    """The markdown Build Sequence section for the per-detail report
    surface. Deterministic and fully derived: step grouping and order from
    the event graph's canonical linearization, part lines from the
    assembly's own names/BOM labels/fab notes, fastener lines from the
    resolved installation contracts."""
    model = build_sequence_model(detail)
    if model is None:
        return ""
    steps, loose_names = model
    lines = ["## Build sequence (derived)", "", SEQUENCE_INTRO, ""]
    for i, step in enumerate(steps, start=1):
        if step["claim"] == "stage":
            lines.append(
                f"{i}. **{step['title']}** — authored build strategy, "
                f"declared and checked, never derived (why: {step['why']})")
        elif step["claim"] == "staging":
            lines.append(
                f"{i}. **{step['title']}** — authored staging claim, "
                f"declared and checked (why: {step['why']})")
        else:
            lines.append(f"{i}. **{step['title']}**")
        for name, bom, fab in step["places"]:
            fab_txt = f" — fab: {fab}" if fab else ""
            lines.append(f"   - place {name} ({bom}){fab_txt}")
        for label in step["units"]:
            lines.append(
                f"   - install {label} — no fastener contract (a bond or "
                f"connector install unit; its process facts live on the "
                f"connection's own assumptions)")
        for unit in step["joins"]:
            lines.append(
                f"   - set {unit} in place — join the completed bench unit "
                f"into the root assembly")
        for d in step["drives"]:
            lines.append(f"   - drive: {d}")
    if loose_names:
        lines.append("")
        lines.append(unordered_note(loose_names))
    lines.append("")
    return "\n".join(lines)
