"""Inspector Mode — the compiler-as-IDE emit path (task INSPECTOR).

The build document's future is the PRIMARY INTERFACE to the compiler: an
engineering IDE / debugger over a construction detail, not a PDF. You click a
component in the 3D model and a panel answers the four questions every
engineering conclusion must survive —

    1. WHAT IS THIS        — type / material / dimensions / params / assumptions
    2. WHY IS IT HERE      — authored declarations vs derived facts, + provenance
    3. HOW DO WE KNOW      — validation, EXPLAINED (never a bare "PASS"), with
       IT'S CORRECT          the honest UNKNOWN picture from the coverage matrix
    4. WHAT DEPENDS ON IT  — construction-graph neighbours, represented load
                             path, and the change-impact set

**The compiler emits; the HTML only consumes.** This module defines the
intermediate representation — a JSON-native *inspector payload* composed of one
:class:`PartInspection` per placed part (an :class:`ObjectDescriptor` +
:class:`Provenance` + :class:`Verification` + :class:`Dependencies`) plus an
assembly-wide :class:`CoverageSummary`. Every field is drawn from the Evidence
Graph's four query methods (``what_is`` / ``why_here`` / ``how_verified`` /
``what_depends_on``, see :mod:`detailgen.validation.evidence`) — this module
NEVER re-derives or re-validates, and holds NO detail-specific knowledge: the
same payload shape emits for any :class:`~detailgen.details.base.Detail`. The
HTML (``inspector_assets/inspector.js``) renders whatever the payload says, so a
family the compiler never analysed renders as NOT ANALYSED, not as a silent
pass.

The one piece of reasoning this layer adds on top of the raw queries is the
**honesty merge** in :meth:`Verification.build`: ``how_verified`` returns only
the families a part's own findings substantiate (all PASS on the rock anchor),
so on its own it would let a part look fully verified. The payload additionally
carries the assembly's whole coverage matrix — all seven families — so the four
UNKNOWN families (structural capacity, code compliance, spatial intent,
functional use on the rock anchor today) are always visible against every part.
A PASS you can see and an UNKNOWN you can see are the same size on screen.
"""

from __future__ import annotations

import base64
import gzip
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_HERE = Path(__file__).parent
_ASSETS = _HERE / "inspector_assets"

#: Payload schema tag — bump when the IR shape changes so a stale HTML can
#: refuse a payload it does not understand (the HTML checks this).
SCHEMA = "inspector/v1"


# --------------------------------------------------------------------------- #
# The intermediate representation (IR) — thin, documented, JSON-native.
# Each dataclass wraps one Evidence-Graph query return under a named shape; the
# HTML panel binds to these field names, nothing else.
# --------------------------------------------------------------------------- #
@dataclass
class ObjectDescriptor:
    """Section 1 (WHAT IS THIS) — the answer to ``what_is``. Identity, material,
    the human dimensions line, the machine params, authored assumptions, and the
    named geometric datums the placement solver hangs off."""

    part_id: str
    name: str
    component_type: str
    material: str
    descriptor: str          # the human "2x6 x 14.0\"" dimension line
    bom_label: str
    params: dict
    assumptions: str
    datums: list
    source_type: str

    @classmethod
    def build(cls, what_is: dict) -> "ObjectDescriptor":
        return cls(
            part_id=what_is["part_id"], name=what_is["name"],
            component_type=what_is["component_type"], material=what_is["material"],
            descriptor=what_is["descriptor"], bom_label=what_is["bom_label"],
            params=what_is["params"], assumptions=what_is["assumptions"] or "",
            datums=what_is["datums"], source_type=what_is["source_type"],
        )


@dataclass
class Provenance:
    """Section 2 (WHY IS IT HERE) — the answer to ``why_here``, split the way the
    KNOWLEDGE STRATEGY splits it: ``authored`` facts (declarations the author
    wrote — ground truth) vs ``derived`` facts (what a promoted compiler rule
    inferred, each carrying its rule, confidence and source_type), plus the
    readable declaration→fact ``chain`` that connects the two."""

    authored: list
    derived: list
    chain: list

    @classmethod
    def build(cls, why_here: dict) -> "Provenance":
        return cls(authored=why_here["authored"], derived=why_here["derived"],
                   chain=why_here["chain"])


@dataclass
class FamilyVerdict:
    """One coverage-family verdict (PASS / FAIL / UNKNOWN — NOT ANALYSED). The
    ``analysed`` flag is the honesty bit the UI keys off: a family with
    ``analysed=False`` is rendered as an open question, never as adequacy."""

    family: str
    verdict: str
    analysed: bool
    checks_run: int
    failures: int
    note: str


@dataclass
class Verification:
    """Section 3 (HOW DO WE KNOW IT'S CORRECT). Two views, deliberately kept
    distinct so neither can mask the other:

    - ``findings`` / ``part_families`` — what was actually checked ABOUT THIS
      PART, every finding pre-EXPLAINED by the graph (``how_verified`` never
      emits a bare verdict: each line names the fact or intrinsic law that
      generated it).
    - ``coverage`` — the assembly-wide seven-family matrix, so the families no
      check touched are visible against this part as NOT ANALYSED.

    ``load_paths`` are the represented support→ground chains this part sits on
    (ONTOLOGY); ``standing_note`` is the coverage disclaimer the model must
    always carry. Together these are the ValidationSummary + EvidenceSummary the
    Inspector spec names."""

    findings: list
    part_families: list          # families THIS part's findings roll into
    coverage: list               # assembly-wide FamilyVerdict[]
    evidence_chain: list
    load_paths: list
    standing_note: str

    @classmethod
    def build(cls, how_verified: dict, coverage_rows) -> "Verification":
        part_family_names = {f["family"] for f in how_verified["family_verdicts"]}
        coverage = []
        for row in coverage_rows:
            analysed = row.checks_run > 0
            coverage.append(asdict(FamilyVerdict(
                family=row.family, verdict=row.verdict, analysed=analysed,
                checks_run=row.checks_run, failures=row.failures, note=row.note,
            )))
        # part_families carries the part-scoped verdict for the families this
        # part actually participates in (PASS/FAIL, with the count backing it).
        part_families = [
            {"family": f["family"], "verdict": f["verdict"],
             "checks_run": f["checks_run"], "failures": f["failures"],
             "note": f["note"]}
            for f in how_verified["family_verdicts"]
        ]
        # sanity: a part can only claim a verdict in a family the assembly
        # actually analysed — otherwise the honesty merge is broken.
        analysed_names = {c["family"] for c in coverage if c["analysed"]}
        stray = part_family_names - analysed_names
        if stray:
            raise InspectorPayloadError(
                f"part claims verdict in un-analysed families {sorted(stray)} — "
                f"how_verified and the coverage matrix disagree")
        return cls(
            findings=how_verified["findings"], part_families=part_families,
            coverage=coverage, evidence_chain=how_verified["evidence_chain"],
            load_paths=how_verified["load_paths"],
            standing_note=how_verified["standing_note"],
        )


@dataclass
class Dependencies:
    """Section 4 (WHAT DEPENDS ON IT) — the answer to ``what_depends_on``:
    construction-graph ``neighbors`` (bears_on / fastened_by / transfers_load_to
    / installed_before, each naming the part on the other end so the UI can make
    it the next selection), the represented ``load_paths`` this part carries, and
    ``invalidated_if_changed`` — the exact facts and checks that would need
    re-deriving / re-checking if this part moved. This is the DependencyGraph +
    change-impact set the Inspector spec names."""

    neighbors: list
    load_paths: list
    invalidated_if_changed: list

    @classmethod
    def build(cls, what_depends_on: dict) -> "Dependencies":
        return cls(
            neighbors=what_depends_on["construction_neighbors"],
            load_paths=what_depends_on["load_paths"],
            invalidated_if_changed=what_depends_on["invalidated_if_changed"],
        )


@dataclass
class PartInspection:
    """The complete four-question record for one placed part — the unit the
    panel binds to when a mesh is clicked."""

    name: str
    part_id: str
    descriptor: dict
    provenance: dict
    verification: dict
    dependencies: dict


@dataclass
class CoverageSummary:
    """Assembly-wide coverage — the seven family verdicts + the standing note,
    surfaced once at the top of the payload so the honest picture is available
    before any part is even selected."""

    families: list
    standing_note: str
    analysed_families: int
    unknown_families: int


class InspectorPayloadError(Exception):
    """The emitted inspector payload violated a completeness/honesty invariant
    (an incomplete part record, a family a part claims but the assembly never
    analysed). Raised loudly — a payload that would mislead must not ship."""


# --------------------------------------------------------------------------- #
# Build the payload (the compiler-emits side)
# --------------------------------------------------------------------------- #
def build_inspector_payload(detail) -> dict:
    """Compile one :class:`~detailgen.details.base.Detail` into the JSON-native
    inspector payload the HTML consumes. Reads ONLY the Evidence Graph's four
    query methods + the coverage matrix — no re-derivation, no detail-specific
    branching. Raises :class:`InspectorPayloadError` if any part comes out
    incomplete."""
    graph = detail.evidence_graph            # validates if needed; cached
    report = detail.report
    coverage_rows = report.coverage_matrix()

    parts: dict[str, dict] = {}
    id_to_name: dict[str, str] = {}
    order: list[str] = []
    for placed in detail.assembly.parts:
        name = placed.name
        descriptor = ObjectDescriptor.build(graph.what_is(name))
        provenance = Provenance.build(graph.why_here(name))
        verification = Verification.build(graph.how_verified(name), coverage_rows)
        dependencies = Dependencies.build(graph.what_depends_on(name))
        inspection = PartInspection(
            name=name, part_id=descriptor.part_id,
            descriptor=asdict(descriptor), provenance=asdict(provenance),
            verification=asdict(verification), dependencies=asdict(dependencies),
        )
        parts[name] = asdict(inspection)
        id_to_name[f"part:{descriptor.part_id}"] = name
        order.append(name)

    _verify_payload_parts(detail, parts)

    coverage = [
        asdict(FamilyVerdict(
            family=row.family, verdict=row.verdict, analysed=row.checks_run > 0,
            checks_run=row.checks_run, failures=row.failures, note=row.note))
        for row in coverage_rows
    ]
    analysed = sum(1 for c in coverage if c["analysed"])
    summary = CoverageSummary(
        families=coverage, standing_note=_standing_note(report),
        analysed_families=analysed, unknown_families=len(coverage) - analysed,
    )

    return {
        "schema": SCHEMA,
        "slug": _slug(detail.name),
        "name": detail.name,
        "coverage": asdict(summary),
        "parts": parts,
        "part_order": order,
        "id_to_name": id_to_name,
    }


def _verify_payload_parts(detail, parts: dict) -> None:
    """Completeness invariant: every placed part has a record with all four
    non-empty sections and a real dimension line (the panel would render an
    empty shell otherwise)."""
    for placed in detail.assembly.parts:
        rec = parts.get(placed.name)
        if rec is None:
            raise InspectorPayloadError(
                f"part {placed.name!r} missing from inspector payload")
        for section in ("descriptor", "provenance", "verification", "dependencies"):
            if not rec.get(section):
                raise InspectorPayloadError(
                    f"part {placed.name!r} has empty {section} section")
        if not rec["descriptor"].get("descriptor"):
            raise InspectorPayloadError(
                f"part {placed.name!r} has no dimension descriptor")
        if not rec["verification"]["coverage"]:
            raise InspectorPayloadError(
                f"part {placed.name!r} carries no coverage matrix — the UNKNOWN "
                f"families would be invisible against it")


def _standing_note(report) -> str:
    from ..validation.coverage import STANDING_NOTE
    return STANDING_NOTE


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


# --------------------------------------------------------------------------- #
# Emit the self-contained HTML (the HTML-consumes side)
# --------------------------------------------------------------------------- #
def inspector_js() -> str:
    return (_ASSETS / "inspector.js").read_text()


def inspector_css() -> str:
    return (_ASSETS / "inspector.css").read_text()


def _web_glb_gzip_b64(assembly, out_dir: Path) -> str:
    """Export a coarse web GLB, gzip it, base64 it — the same pattern the build
    document uses (megabytes ride a ``text/plain`` script, never JSON.parse; the
    browser gunzips with DecompressionStream)."""
    from .export import export_glb
    from ..core.buildinfo import MESH_TOL_LINEAR, MESH_TOL_ANGULAR

    out_dir.mkdir(parents=True, exist_ok=True)
    glb = out_dir / "inspector.web.glb"
    # Coarser than the fine detail.glb so the inline artifact stays small.
    export_glb(assembly, glb, tolerance=max(MESH_TOL_LINEAR, 0.4),
               angular_tolerance=max(MESH_TOL_ANGULAR, 0.6))
    # mtime=0 so the gzip header carries NO wall-clock timestamp — otherwise the
    # emitted HTML would differ byte-for-byte on every run (gzip stamps the
    # current time by default), defeating byte-reproducibility. The GLB payload
    # and the JSON are already deterministic; this closes the last source.
    gz = gzip.compress(glb.read_bytes(), compresslevel=9, mtime=0)
    return base64.b64encode(gz).decode("ascii")


def emit_inspector_html(detail, out_path: str | Path,
                        glb_work_dir: str | Path | None = None) -> Path:
    """Emit ONE self-contained Inspector HTML file for ``detail`` at
    ``out_path`` (opens from ``file://`` with no server). Composes: the payload
    (JSON), the gzipped GLB (base64), the vendored three.js, and the inspector
    JS/CSS — all inline. Returns the written path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = Path(glb_work_dir) if glb_work_dir else out_path.parent / "_glb"

    payload = build_inspector_payload(detail)
    glb_b64 = _web_glb_gzip_b64(detail.assembly, work)
    html = render_inspector_document(payload, glb_b64)
    out_path.write_text(html)
    return out_path


def render_inspector_document(payload: dict, glb_b64: str) -> str:
    """Assemble the full HTML string from an already-built payload + GLB. Pure
    string composition (no filesystem, no detail) — the unit a payload test can
    exercise without a render."""
    from .web_viewer import vendor_js

    slug = payload["slug"]
    # ``</`` escaped so no JSON value can close the <script> early; the base64
    # GLB is plain ASCII and stays out of JSON so the megabytes never hit
    # JSON.parse.
    data_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    title = f"Inspector — {payload['name']}"
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
{inspector_css()}
</style>
</head>
<body>
<div id="inspector-root" data-slug="{_esc(slug)}"></div>
<script type="application/json" id="inspector-data-{_esc(slug)}">{data_json}</script>
<script type="text/plain" id="inspector-glb-{_esc(slug)}">{glb_b64}</script>
<script>
{vendor_js()}
</script>
<script>
{inspector_js()}
</script>
</body>
</html>
"""


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
