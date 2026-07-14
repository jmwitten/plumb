"""Data contract for the interactive build-document viewer.

``build_viewer_payload`` is pure data: no three.js, no HTML, no browser
concerns. It turns a built :class:`~detailgen.details.base.Detail` into the
JSON-serializable dict the (phase-C) inline viewer joins against a part's GLB
node by name (``Placed.name`` — unique per assembly, see
``DetailAssembly._append``). Everything here reads only *public* surface —
``bom_table()``, ``Placed.name``/``.id``/``.component``, and the public
``Component`` methods (``bom_label``, ``describe``, ``assumptions``,
``bom_group``, ``params``, ``.material``) — so it needs no new accessor on
``DetailAssembly``/``Detail``.

Each part row also carries ``fab`` — the part's carpenter-readable fabrication
note, read from the ONE source the cut plan reads (``ProcessRecord.fab_note``),
so the hover tooltip and the cut list can never describe different fabrication.
And ``explode`` — the part's pull-apart offset, either authored on the detail
or DERIVED from the model's declared contacts (see :mod:`.explode`) so a spec
with no ``explode:`` block still drives the viewer's explode slider.

``viewer_js`` / ``viewer_css`` load the interactive viewer's source text (the
vendored three.js viewer under this package), inlined into the build document
by the report scripts.
"""

from __future__ import annotations

from pathlib import Path

from ...details.base import fmt_frac_in
from ..part_labels import part_labels

_HERE = Path(__file__).parent


def _existing(component) -> bool:
    """A part is "existing — not purchased" under the same rule
    ``scripts/consolidated_report.py``'s ``is_existing`` applies to BOM rows:
    a non-default ``source`` (set by parts that model real pre-existing
    hardware, e.g. the live tree or the zipline cable/trolley), OR a
    ``bom_label()`` marked ``"(existing)"`` for a part with no distinguishing
    source metadata (the boulder — a natural feature, ``source`` stays the
    default ``"generated"``). Read from ``consolidated_report.py``, not
    imported — the two modules must not cross-import."""
    source = getattr(component, "source", "generated")
    return source != "generated" or "(existing)" in component.bom_label()


def _format_spec_value(value):
    """Render one ``Component.params()`` value for the specs table, or
    ``None`` to skip it (lists/dicts/None — not scalar, not display-ready)."""
    if isinstance(value, bool) or isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{fmt_frac_in(value / 25.4)} ({value:.1f} mm)"
    return None


def _fab_note(component) -> str:
    """The part's carpenter-readable fabrication note, read from the SINGLE
    source the cut plan reads — ``ProcessRecord.fab_note()`` off the component's
    own ``fabrication_record()`` — never a second derivation. Empty for a part
    with no fabrication record or no note-bearing step (a purchased or plain
    part, truthfully)."""
    fn = getattr(component, "fabrication_record", None)
    record = fn() if fn is not None else None
    return record.fab_note() if record is not None else ""


def _explode_for(detail, assembly) -> dict:
    """The explode dict the payload carries: a detail's own authored
    ``explode_vectors()`` when it declares them (rock anchor / tree / trolley —
    their goldens are unchanged), otherwise DERIVED from the model's declared
    contacts so a spec with no ``explode:`` block (the platform, the composed
    site) still drives the viewer's explode slider. See
    :mod:`detailgen.rendering.web_viewer.explode`."""
    from .explode import derive_explode_vectors

    authored = detail.explode_vectors()
    if authored:
        return authored
    contacts = None
    spec_fn = getattr(detail, "validation_spec", None)
    if spec_fn is not None:
        try:
            contacts = spec_fn()
        except Exception:
            contacts = None
    return derive_explode_vectors(assembly, contacts)


def _instruction_panel_payload(assembly, manual) -> tuple[dict[str, int], list[dict]]:
    """Validate and project a manual's part-id schedule into GLB node names."""
    rows = tuple(manual.part_schedule)
    scheduled_ids = [part_id for part_id, _panel in rows]
    duplicates = sorted({part_id for part_id in scheduled_ids
                         if scheduled_ids.count(part_id) > 1})
    if duplicates:
        raise ValueError(
            f"instruction panel schedule lists part ids more than once: {duplicates!r}")

    parts_by_id = {part.id: part for part in assembly.parts}
    known_ids = set(parts_by_id)
    actual_ids = set(scheduled_ids)
    unknown = sorted(actual_ids - known_ids)
    if unknown:
        raise ValueError(
            f"instruction panel schedule has unknown part ids: {unknown!r}")
    missing = sorted(known_ids - actual_ids)
    if missing:
        raise ValueError(
            f"instruction panel schedule omits part ids: {missing!r}")

    schedule = dict(rows)
    panel_count = len(manual.panels)
    invalid = sorted((part_id, panel) for part_id, panel in rows
                     if not isinstance(panel, int)
                     or panel < 1 or panel > panel_count)
    if invalid:
        raise ValueError(
            f"instruction panel schedule has invalid panel numbers: {invalid!r}")

    panels = []
    for panel in manual.panels:
        unknown_arrivals = sorted(set(panel.arrival_part_ids) - known_ids)
        if unknown_arrivals:
            raise ValueError(
                f"instruction panel {panel.index} has unknown arrival part ids: "
                f"{unknown_arrivals!r}")
        panels.append({
            "number": panel.index,
            "title": panel.title,
            "action": panel.action,
            "arrivals": [parts_by_id[part_id].name
                         for part_id in panel.arrival_part_ids],
        })
    return schedule, panels


def build_viewer_payload(detail, instruction_manual=None) -> dict:
    """Build the tooltip/hover data contract for one detail.

    ``parts`` is keyed by ``Placed.name`` — the same name every exported GLB
    stamps on its per-part node, so the (phase-C) viewer's raycast pick joins
    a clicked mesh straight to its tooltip row by that name."""
    assembly = detail.assembly

    qty_by_id: dict[str, int] = {}
    for row in detail.bom_table():
        for part_id in row["ids"]:
            qty_by_id[part_id] = row["qty"]

    explode_vectors = _explode_for(detail, assembly)
    labels = part_labels(assembly.parts)
    panel_schedule = None
    instruction_panels = None
    if instruction_manual is not None:
        panel_schedule, instruction_panels = _instruction_panel_payload(
            assembly, instruction_manual)

    parts: dict[str, dict] = {}
    for p in assembly.parts:
        c = p.component
        part_label = labels[p.id]
        specs = []
        for label, value in c.params().items():
            formatted = _format_spec_value(value)
            if formatted is None:
                continue
            specs.append([label, formatted])
        stub = c.stub_of()
        dims = c.describe()
        if stub is not None:
            # A stub's PRIMARY dims line is the full piece, not the modeled
            # portion — the tooltip's whole reason for existing here (see
            # ``Component.stub_of``). The modeled (stub) length still shows,
            # as its own labeled specs row, right alongside the full length.
            dims = stub["full_dims"]
            specs = [["Full length", stub["full_dims"]],
                     ["Modeled portion", stub["modeled_dims"]]] + specs
        explode = explode_vectors.get(p.name, (0.0, 0.0, 0.0))
        parts[p.name] = {
            "id": p.id,
            "type": type(c).__name__,
            "reader_name": part_label.reader_name,
            "instance_index": part_label.index,
            "instance_count": part_label.count,
            "item": part_label.item,
            "dims": dims,
            "fab": _fab_note(c),
            "material": c.material.name,
            "existing": _existing(c),
            "qty": qty_by_id.get(p.id, 1),
            "group": c.bom_group(),
            "specs": specs,
            "assumptions": c.assumptions(),
            "explode": [float(v) for v in explode],
            "stub_of": stub,
        }
        if panel_schedule is not None:
            parts[p.name]["first_panel"] = panel_schedule[p.id]

    slug = "".join(ch if ch.isalnum() else "_" for ch in detail.name.lower()).strip("_")
    payload = {
        "slug": slug,
        "name": detail.name,
        "parts": parts,
        "dimensions": detail.rendered_callouts(),
    }
    if instruction_panels is not None:
        payload["instruction_panels"] = instruction_panels
    return payload


#: Vendored three.js r147 UMD bundle, in load order: core assigns ``THREE``,
#: then the two examples/js add-ons attach ``THREE.GLTFLoader`` /
#: ``THREE.OrbitControls`` to it. Concatenated into one inline <script> ahead
#: of viewer.js so the whole viewer is a single self-contained block (no CDN,
#: strict-CSP-safe).
_VENDOR_ORDER = ("three.min.js", "GLTFLoader.js", "OrbitControls.js")


def vendor_js() -> str:
    """The vendored three.js r147 UMD scripts concatenated in load order —
    ``THREE`` core first, then GLTFLoader and OrbitControls (which attach to
    the global ``THREE``). Prepend this to :func:`viewer_js` in one inline
    <script>."""
    vendor = _HERE / "vendor"
    return "\n".join((vendor / f).read_text() for f in _VENDOR_ORDER)


def viewer_js() -> str:
    """The interactive viewer's JS source (init/raycast/tooltip/pin/callouts/
    explode/theme). Runs after :func:`vendor_js` has populated ``window.THREE``."""
    return (_HERE / "viewer.js").read_text()


def viewer_css() -> str:
    """The interactive viewer's CSS (tooltip/button/canvas/controls styles),
    keyed on the host document's CSS variables for light/dark parity."""
    return (_HERE / "viewer.css").read_text()
