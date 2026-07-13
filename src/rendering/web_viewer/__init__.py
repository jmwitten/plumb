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


def build_viewer_payload(detail) -> dict:
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

    parts: dict[str, dict] = {}
    for p in assembly.parts:
        c = p.component
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
            "item": c.bom_label(),
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

    slug = "".join(ch if ch.isalnum() else "_" for ch in detail.name.lower()).strip("_")
    return {
        "slug": slug,
        "name": detail.name,
        "parts": parts,
        "dimensions": detail.rendered_callouts(),
    }


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
