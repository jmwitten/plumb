"""``Detail``: the unit of authorship in detailgen.

A **component** is a single part in its own local frame (see
``detailgen.core.base``). A **detail** is a whole construction assembly — the
rock anchor, a ledger connection — authored as one parameterizable object. Every
detail is the same six-stage pipeline, and this base class *is* that pipeline:

    params  →  components + assembly  →  validation  →  rendering  →  docs
      │                │                     │              │           │
   frozen         assemble()          validate() +      render()   _document()
   dataclass                          extra_checks()   (gated!)

How to author a detail
----------------------
Subclass ``Detail`` and provide:

1. ``Params`` — a **frozen dataclass** of the detail's inputs (imperial
   magnitudes; multiply by ``IN``/``FT`` where you build geometry). Its defaults
   are the "as-drawn" detail; overrides re-size the same detail
   (``MyDetail(rod_embed=10.0)``).
2. ``assemble(self, d)`` — place components into the given
   :class:`~detailgen.assemblies.assembly.DetailAssembly` ``d`` using
   ``d.add(...)`` / ``d.place(...).on(...)``. Read inputs from ``self.params``.
   Do **not** thread a handles dict back out: any placed part is retrievable
   afterward by its (unique) name via ``self["that name"]`` — the base owns the
   registry, so validation specs reference parts through the detail instance
   rather than a tuple passed around.

Optional hooks — override only what the detail needs:

- ``validation_spec(self) -> dict`` — kwargs for
  :func:`~detailgen.validation.validate_assembly` (``expected_overlaps``,
  ``bearings``, ``bonds``, ``through_holes``, ``ground``). Reference parts with
  ``self["name"]``.
- ``extra_checks(self) -> list[Finding]`` — design-intent dimension checks
  appended to the report.
- ``cross_check(self) -> dict | None`` — an independent constraint-solver pass
  (verification only; never canonical — see the placement policy in CLAUDE.md).
- ``callouts(self) -> list[Callout]`` — declarative dimension callouts whose
  text is *derived from the live param value* (kills label-vs-param drift).
- ``explode_vectors(self) -> dict`` — per-part offsets for an exploded render.
- ``_export`` / ``_document`` — the CAD artifacts and the markdown report.

Lifecycle is enforced, not merely documented
--------------------------------------------
``render()`` calls ``require_clean()`` first, which builds and validates the
detail if that has not happened yet and **raises** on any validation failure.
There is therefore no way to export a detail through the ``Detail`` API without
a clean validation report — CLAUDE.md's "never export without a clean report"
is a property of the framework here, not a convention an author must remember.
(The low-level ``DetailAssembly`` + exporter functions remain ungated for the
simple ``deck_ledger_example`` walkthrough; a real detail is a ``Detail``.)
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from fractions import Fraction
from pathlib import Path
from typing import Callable, ClassVar

from ..assemblies.assembly import DetailAssembly, Placed
from ..assemblies.connection import Connection, DerivedFact, Edge, compile_connections, merge_into_spec
from ..core.config import DEFAULT as _CONFIG_DEFAULT_TOL
from ..validation import Finding, ValidationReport, validate_assembly
from ..validation.install import (check_installability,
                                  render_install_disclosures_md)


def fmt_frac_in(value_in: float, denom: int = 16) -> str:
    """Format an inch magnitude as an architectural fraction string, e.g.
    ``8.0 -> '8"'``, ``4.5 -> '4-1/2"'``, ``0.5 -> '1/2"'``,
    ``2.75 -> '2-3/4"'``. Rounds to the nearest ``1/denom``."""
    sign = "-" if value_in < 0 else ""
    v = abs(value_in)
    # Round the whole magnitude to the nearest 1/denom FIRST, then split off the
    # whole part — so a value sitting a float-hair below an integer (e.g.
    # 1219.2/25.4 = 47.99999999999999) rounds up to 48" and carries into the
    # whole, instead of splitting to whole=47 + Fraction(0.999...)→1/1 and
    # printing "47-1/1\"". (Splitting before rounding loses that carry.)
    frac = Fraction(v).limit_denominator(denom)
    whole, rem = divmod(frac, 1)
    whole = int(whole)
    if rem == 0:
        return f'{sign}{whole}"'
    if whole == 0:
        return f'{sign}{rem.numerator}/{rem.denominator}"'
    return f'{sign}{whole}-{rem.numerator}/{rem.denominator}"'


_Point = "tuple[float, float, float] | Callable[[object], tuple[float, float, float]]"


@dataclasses.dataclass(frozen=True)
class Callout:
    """A declarative dimension callout whose label text is generated from a
    live parameter value, so it can never drift from the geometry it annotates.

    - ``param``: name of the field on the detail's ``params`` to call out.
    - ``label``: a ``str.format`` template; ``{v}`` is replaced by the formatted
      value (e.g. ``"{v} EMBED"`` with ``rod_embed=8.0`` → ``'8" EMBED'``).
    - ``p0`` / ``p1``: the callout's two endpoints (mm, world frame). Each is
      either a fixed 3-tuple or a callable of ``params`` (so the placement, like
      the text, tracks a re-sized detail).
    - ``fmt``: value formatter; defaults to architectural fractional inches.

    Change the param value and *both* the text and the geometry-derived
    endpoints move, with no other edit — that is the whole point.
    """

    param: str
    label: str = "{v}"
    p0: _Point = (0.0, 0.0, 0.0)
    p1: _Point = (0.0, 0.0, 0.0)
    fmt: Callable[[float], str] = fmt_frac_in

    def value(self, params) -> float:
        return getattr(params, self.param)

    def text(self, params) -> str:
        return self.label.format(v=self.fmt(self.value(params)))

    def render(self, params) -> dict:
        """The manifest/overlay-ready dict: ``{"label", "p0", "p1"}``."""
        return {
            "label": self.text(params),
            "p0": _resolve_point(self.p0, params),
            "p1": _resolve_point(self.p1, params),
        }


def _resolve_point(pt, params) -> list[float]:
    if callable(pt):
        pt = pt(params)
    return [float(x) for x in pt]


class Detail(ABC):
    """Base class for a parameterizable construction detail. See the module
    docstring for the authoring contract."""

    #: Display name of the detail (becomes the ``DetailAssembly`` name).
    name: ClassVar[str] = "detail"
    #: A frozen dataclass of the detail's inputs; subclasses set this.
    Params: ClassVar[type]

    def __init__(self, params=None, **overrides):
        """``MyDetail()`` uses the ``Params`` defaults; ``MyDetail(x=1)`` (or
        ``MyDetail(params=existing, x=1)``) overrides individual fields."""
        if params is None:
            params = self.Params()
        if overrides:
            params = dataclasses.replace(params, **overrides)
        self.params = params
        self._assembly: DetailAssembly | None = None
        self._report: ValidationReport | None = None
        self._derivation_log: list[DerivedFact] = []
        self._connection_edges: list[Edge] = []
        # P4 Evidence Graph (task EVIDENCE): the compiled ConnectionChecks are
        # retained so the graph can be assembled ON DEMAND from lifecycle
        # outputs (see :attr:`evidence_graph`) — never eagerly, so ``validate``
        # stays byte-for-byte the pre-EVIDENCE computation.
        self._connection_checks = None
        self._evidence_graph = None
        #: The merged, resolved validation spec from the last validate() —
        #: reused by extra_checks (the rung-3 support check) for the sweep's
        #: physical-contact graph. None until validate() has run.
        self._validated_spec: dict | None = None

    # -- stage 1-2: params -> components + assembly ---------------------------

    @abstractmethod
    def assemble(self, d: DetailAssembly) -> None:
        """Place this detail's components into ``d`` from ``self.params``.
        Retrieve any placed part afterward via ``self["<part name>"]``."""

    def build(self) -> DetailAssembly:
        """Build once (idempotent) and return the assembled
        :class:`DetailAssembly`. Called implicitly by everything downstream.

        The assembly is registered *before* ``assemble`` runs, so a subclass may
        reference an already-placed part mid-assembly via ``self["name"]``. A
        failed build is rolled back (not cached), so a fixed re-run rebuilds."""
        if self._assembly is None:
            self._assembly = DetailAssembly(self.name)
            try:
                self.assemble(self._assembly)
            except Exception:
                self._assembly = None
                raise
        return self._assembly

    @property
    def assembly(self) -> DetailAssembly:
        return self.build()

    def __getitem__(self, key: str) -> Placed:
        """The base-owned handle registry: look a placed part up by its unique
        name. Raises (listing the known parts) on an unknown key — the same
        loud failure ``DetailAssembly._resolve`` gives everywhere."""
        return self.build()._resolve(key)

    # -- stage 3: validation --------------------------------------------------

    def validation_spec(self) -> dict:
        """Kwargs forwarded to ``validate_assembly`` (``expected_overlaps``,
        ``bearings``, ``bonds``, ``through_holes``, ``ground``, and ``tol`` — a
        ``detailgen.core.config.Tolerances`` instance to tighten/loosen the
        acceptance thresholds for this detail; defaults to ``DEFAULT`` when
        omitted). Override per detail."""
        return {}

    def extra_checks(self) -> list[Finding]:
        """Extra findings (dimension checks, etc.) appended to the report."""
        return []

    def connections(self) -> list[Connection]:
        """Declared :class:`~detailgen.assemblies.connection.Connection`\\ s
        (Wave 2's central abstraction). Their generated validation entries
        MERGE into ``validation_spec()``'s hand-written lists (see
        :func:`~detailgen.assemblies.connection.merge_into_spec`), so a
        detail can adopt Connections incrementally — anything not yet
        expressed through one keeps working via the imperative escape
        hatch. Default: none."""
        return []

    def cross_check(self) -> dict | None:
        """Independent constraint-solver cross-check (verification only)."""
        return None

    def connection_fragments(self) -> dict:
        """Connection label -> owning site fragment/subsystem id, for a
        COMPOSED site detail (task CPGCORE, design §3.2: no cross-fragment
        order exists in v1 — this map lets a composed verdict name the
        cross-fragment gap instead of a generic underdetermined wording).
        Default: empty (a standalone detail is one implicit fragment)."""
        return {}

    def sequence(self) -> tuple:
        """The detail's authored build-order claim (task SEQSCHEMA) — a
        tuple of stages in declaration order. Default: none (an imperative
        ``.py`` detail authors no sequence;
        :class:`~detailgen.spec.compiler.SpecDetail` overrides this with its
        loaded ``sequence:`` block's stages, spec-local names)."""
        return ()

    def resolved_sequence(self) -> tuple:
        """The authored stages RESOLVED to the compiled surface (task
        CPGCORE): every stage's ``connections`` entries are compiled
        connection labels and its ``parts`` entries are built ``Placed.id``
        s — the names the event graph is keyed by. Landed on
        ``ConnectionChecks.sequence`` by :meth:`validate` /
        :func:`compile_connections`, which raises a loud teaching error on
        any name that resolves to nothing.

        Base default: :meth:`sequence` passed through verbatim (an
        imperative detail that authors stages must author them against
        compiled labels/ids directly). ``SpecDetail`` overrides this to
        expand repeat-template labels to their built instances and map
        authored component ids to ``Placed`` ids; a composed site replays
        each fragment's resolved stages under the fragment's own chain so
        no cross-fragment order is ever invented (design §3.2)."""
        return self.sequence()

    def resolved_after(self) -> tuple:
        """Typed process point constraints resolved to compiled labels.

        Imperative details author none by default. ``SpecDetail`` resolves
        authored labels (and rejects ambiguous repeat expansion); composed
        sites replay each fragment under its own chain. The compiled graph
        consumes these constraints beside the resolved authored stages.
        """
        return ()

    def resolved_staging(self):
        """The detail's staging claim resolved to built ids.

        Imperative details author none by default. ``SpecDetail`` overrides
        this bridge for the typed ``sequence.subassemblies`` / ``assembly``
        surface, exactly beside :meth:`resolved_sequence`.
        """
        return None

    def validate(self) -> ValidationReport:
        """Build (if needed) and run the full validation sweep, caching the
        report. Validating an unbuilt detail builds it first.

        Declared ``connections()`` are compiled (aggregated across all of
        them, so a whole-detail installation-order cycle can be caught —
        see :func:`compile_connections`) and merged with the hand-written
        ``validation_spec()`` before the standard sweep runs; their
        hardware-presence findings and derivation log are recorded
        alongside the report (see :attr:`derivation_log`,
        :attr:`connection_edges`)."""
        assembly = self.build()
        hand_spec = self.validation_spec()
        conns = self.connections()
        sequence = self.resolved_sequence()
        after = self.resolved_after()
        staging = self.resolved_staging()
        self._evidence_graph = None  # invalidate any prior build
        if conns or sequence or after or staging is not None:
            generated = compile_connections(
                assembly, conns, sequence=sequence, after=after,
                staging=staging,
                fragments=self.connection_fragments())
            spec = merge_into_spec(assembly, hand_spec, generated)
            self._derivation_log = generated.derived
            self._connection_edges = generated.edges
            self._connection_checks = generated
            connection_findings = generated.findings
        else:
            spec = hand_spec
            self._derivation_log = []
            self._connection_edges = []
            self._connection_checks = None
            connection_findings = []
        report = validate_assembly(assembly, **spec)
        # Stash the merged, resolved validation spec so extra_checks (e.g. the
        # rung-3 support check) can reuse the SAME physical-contact graph
        # (bearings + bonds) and ground terminal the sweep just ran on.
        self._validated_spec = spec
        for finding in connection_findings:
            report.add(finding)
        # Installability axes (task INSTALL v1): axis-1 termination + axis-2
        # static access, derived from each fastener's resolved contract on
        # ConnectionChecks.installs. Appended AFTER the connection findings —
        # findings order is part of byte-identical determinism.
        if conns and self._connection_checks is not None:
            for finding in check_installability(
                    assembly, conns, self._connection_checks,
                    tol=spec.get("tol") or _CONFIG_DEFAULT_TOL):
                report.add(finding)
        for finding in self.extra_checks():
            report.add(finding)
        self._report = report
        return report

    @property
    def report(self) -> ValidationReport | None:
        """The last validation report, or ``None`` if never validated."""
        return self._report

    @property
    def derivation_log(self) -> list[DerivedFact]:
        """The last validate()'s Connection derivation log (P1/P4): every
        fact derived from a declared Connection, with provenance. Empty
        until :meth:`validate` has run at least once."""
        return self._derivation_log

    @property
    def connection_edges(self) -> list[Edge]:
        """The last validate()'s Construction-Graph edges contributed by
        declared Connections (install order + load path). Empty until
        :meth:`validate` has run at least once."""
        return self._connection_edges

    @property
    def evidence_graph(self):
        """The P4 :class:`~detailgen.validation.evidence.EvidenceGraph` for this
        detail's last validation — the queryable "why do we believe this?"
        graph over the whole chain (authored declarations → derived facts →
        checks/findings → family verdicts). Assembled lazily and cached from
        lifecycle outputs (the derivation log, Construction-Graph edges, the
        validation report + its coverage matrix); building it changes no
        validation outcome. Validates first if needed. See
        :mod:`detailgen.validation.evidence` and its four Inspector queries
        (``what_is`` / ``why_here`` / ``how_verified`` / ``what_depends_on``)."""
        from ..validation.evidence import EvidenceGraph

        if self._report is None:
            self.validate()
        if self._evidence_graph is None:
            self._evidence_graph = EvidenceGraph.from_detail(self)
        return self._evidence_graph

    def require_clean(self) -> ValidationReport:
        """Validate if not yet done, then raise unless the report is clean.
        This is the gate every export path passes through."""
        if self._report is None:
            self.validate()
        self._report.require_clean()
        return self._report

    # -- stage 4-5: rendering (gated) + documentation -------------------------

    def render(self, out_dir: str | Path) -> Path:
        """Export the detail's artifacts into ``out_dir`` as a CERTIFIED artifact.
        **Gated**, and the only export verb that certifies: it calls
        ``require_clean`` before writing anything, so a detail with a missing or
        dirty validation report cannot reach ``outputs/``. The file-writing hooks
        it drives (``_export``/``_document``) are deliberately non-public, so no
        public verb bypasses the gate for a *certified* export. The ungated
        counterpart for a *documentation* surface is :meth:`render_documentation`
        (it draws the geometry and SURFACES the honest verdict rather than
        refusing). Returns the output directory."""
        self.require_clean()
        return self._render_into(out_dir)

    def render_documentation(self, out_dir: str | Path) -> Path:
        """UNGATED documentation render — draws the geometry and SURFACES the
        honest per-family verdict, for a DOCUMENTATION surface (the build-doc
        pipeline), never a certified artifact export.

        Unlike :meth:`render` it does NOT call ``require_clean``: a document about
        an honestly-blocked model is more useful than no document, *precisely
        because* it shows the block loudly — the coverage matrix it writes reports
        e.g. "Structural capacity: UNKNOWN — UNRESOLVED" (designer-directive §3 +
        the epistemic ladder: honest-non-clean beats refuse-to-render). It writes
        the SAME geometry/manifest/coverage/evidence files ``render`` does, so a
        documentation consumer sees the real model with its real verdict; it just
        never claims the result is certified. Certified export to ``outputs/``
        stays exclusively behind the gated :meth:`render`. Validates first if
        needed, so the surfaced verdict is real."""
        if self._report is None:
            self.validate()
        return self._render_into(out_dir)

    def _render_into(self, out_dir: str | Path) -> Path:
        """Shared writer for :meth:`render` (gated) and
        :meth:`render_documentation` (ungated): the gate is the ONLY difference
        between a certified export and a documentation render, so the file-writing
        steps live here once and cannot drift between the two paths."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        self._export(out)
        self._document(out)
        self._write_coverage_matrix(out)
        self._write_install_disclosures(out)
        self._write_build_sequence(out)
        self._write_evidence_graph(out)
        return out

    def coverage_matrix(self) -> list:
        """The invariant-family coverage matrix (Wave 3-1) for this detail's
        last validation — PASS / FAIL / UNKNOWN — NOT ANALYZED per family. A
        lifecycle-level accessor so callers reach the matrix off the Detail,
        not only off the raw report. Validates first if needed."""
        if self._report is None:
            self.validate()
        return self._report.coverage_matrix()

    def _write_coverage_matrix(self, out_dir: Path) -> None:
        """Emit the coverage matrix on the per-detail report surface, at the
        lifecycle level so EVERY detail carries it without per-detail wiring
        (the honesty guarantee is a property of the framework, not something an
        author can forget). Appends the matrix section to the detail's
        ``validation_report.md`` when ``_document`` wrote one, else writes a
        standalone ``coverage_matrix.md``; always writes the machine-readable
        ``coverage_matrix.json`` payload."""
        import json

        from ..validation.coverage import render_coverage_matrix_md

        matrix_md = render_coverage_matrix_md(self._report)
        report_md = out_dir / "validation_report.md"
        if report_md.exists():
            with report_md.open("a") as fh:
                fh.write("\n" + matrix_md)
        else:
            (out_dir / "coverage_matrix.md").write_text(matrix_md)
        (out_dir / "coverage_matrix.json").write_text(
            json.dumps(self._report.coverage_payload(), indent=1))

    def _write_install_disclosures(self, out_dir: Path) -> None:
        """Emit the fastener-installation disclosures on the per-detail
        report surface, at the LIFECYCLE level like the coverage matrix
        (owner guardrail #7's doc half — honesty review F2: the derivation
        log carries every resolved contract with per-field provenance, but
        the per-connection sampling cap kept the contract lines off every
        rendered page, and no per-fastener axis verdict printed at all, so
        a reader of a BLOCKED doc saw the family FAIL with no reason on
        paper). Appends to ``validation_report.md`` when present, else
        writes ``install_disclosures.md``. Silent (no file, no section)
        only when the detail declares no installation contracts — then the
        coverage matrix's UNKNOWN — NOT ANALYZED row is the whole truth."""
        md = render_install_disclosures_md(self)
        if not md:
            return
        report_md = out_dir / "validation_report.md"
        if report_md.exists():
            with report_md.open("a") as fh:
                fh.write("\n" + md)
        else:
            (out_dir / "install_disclosures.md").write_text(md)

    def _write_build_sequence(self, out_dir: Path) -> None:
        """Emit the derived Build Sequence section (task CPGCORE, the
        STEPDOC v1-core reader surface) on the per-detail report surface,
        at the LIFECYCLE level like the coverage matrix and the install
        disclosures — a projection of the event graph's canonical
        linearization, nothing hand-typed. Appends to
        ``validation_report.md`` when present, else writes
        ``build_sequence.md``. Silent only when the detail carries no event
        graph (no connections, no authored sequence) — no order content
        exists to derive."""
        from ..validation.build_sequence import render_build_sequence_md

        md = render_build_sequence_md(self)
        if not md:
            return
        report_md = out_dir / "validation_report.md"
        if report_md.exists():
            # Idempotent (review-cpgcore F-4): a repeated document() into
            # the same out_dir must not stack a second copy — this section
            # is the last one appended to the report, so a previous copy is
            # cut from its heading to end-of-file before the fresh append.
            text = report_md.read_text()
            marker = "## Build sequence (derived)"
            if marker in text:
                text = text[:text.index(marker)].rstrip() + "\n"
            report_md.write_text(text + "\n" + md)
        else:
            (out_dir / "build_sequence.md").write_text(md)

    def _write_evidence_graph(self, out_dir: Path) -> None:
        """Emit the machine-readable Evidence Graph alongside the derivation
        report (task EVIDENCE, req 3): the queryable proof graph as JSON, for
        the Inspector and any downstream audit tooling. Lifecycle-level so
        every rendered detail carries it without per-detail wiring."""
        import json

        (out_dir / "evidence_graph.json").write_text(
            json.dumps(self.evidence_graph.to_dict(), indent=1))

    def _export(self, out_dir: Path) -> None:
        """Write CAD artifacts. Default: a single STEP. Override for GLB /
        manifest / multi-view output. **Internal hook** — driven by
        :meth:`_render_into` (the shared writer behind ``render`` and
        ``render_documentation``); call one of those, not this directly."""
        from ..rendering.export import export_step
        export_step(self.assembly, out_dir / f"{_slug(self.name)}.step")

    def _document(self, out_dir: Path) -> None:
        """Write the human-readable report/documentation. Default: nothing.
        Override to emit a validation-report markdown. **Internal hook** —
        driven by :meth:`_render_into` (after ``_export``), so ``self.report``
        and ``self.cross_check()`` are available; never call it directly."""
        return None

    # -- render extras --------------------------------------------------------

    def callouts(self) -> list[Callout]:
        """Declarative, param-derived dimension callouts (default: none)."""
        return []

    def rendered_callouts(self) -> list[dict]:
        """The callouts resolved against the live params — overlay/manifest
        ready. Text and endpoints reflect the current param values."""
        return [c.render(self.params) for c in self.callouts()]

    def explode_vectors(self) -> dict:
        """Per-part explode offsets (mm) for an exploded render (default: none)."""
        return {}

    # -- bill of materials (delegates to the assembly's single source) --------

    def bom(self) -> list[dict]:
        return self.assembly.bom()

    def bom_table(self) -> list[dict]:
        return self.assembly.bom_table()


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
