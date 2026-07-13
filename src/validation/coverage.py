"""Coverage matrix by invariant family (Wave 3-1).

The point of this module is *honesty*: a "validated CLEAN" report is only as
strong as the checks that actually ran, and a reader who sees no FAIL should
never conclude that everything that matters was examined. Every report surface
carries a **coverage matrix** that reports, per invariant family, one of:

    PASS                 — >=1 check of the family ran and all passed
    FAIL                 — >=1 check of the family failed
    UNKNOWN — NOT ANALYZED — no check of the family ran

This is the permits-vs-requires lesson applied to reporting: removing every
check of a family flips PASS -> UNKNOWN, it never silently stays PASS (see
``tests/test_coverage_matrix.py`` ::
``test_removing_every_check_of_a_family_flips_pass_to_unknown``).

Family assignment is DATA-DRIVEN, keyed on the check *kind* (the first field
of every :class:`~detailgen.validation.checks.Finding`) via :data:`KIND_TO_FAMILY`
below — NOT per-detail and NOT per-check-call. A Connection that generates
checks therefore inherits its family purely from the kind string its findings
carry, with no edit to ``src/assemblies/connection.py``. A finding whose kind
is not in the table is a hard error (:class:`UnmappedCheckKind`), so a new
check can never silently escape the matrix.

Why the matrix derives from ``report.findings`` and nothing else: every check
in this codebase emits exactly one Finding per invocation (even a
bbox-prefiltered interference pair emits a byte-identical PASS finding), so the
findings list *is* the audit trail of checks that ran. "checks run" and
"findings" therefore coincide numerically today; they are reported as separate
provenance fields because they are separate concepts (a future check kind that
stays silent on success — as ``parameters`` does — would make them diverge, and
we deliberately do NOT let a silent pass certify a family: coverage requires a
recorded verdict, not merely an executed line).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .checks import FAIL_VERDICT, UNKNOWN_VERDICT

#: The nine invariant families, in the fixed canonical order every report
#: surface renders them (user directive, WAVE 3 SHAPE). Do not reorder — the
#: order is part of the report contract.
INVARIANT_FAMILIES: tuple[str, ...] = (
    "Physical geometry",
    "Spatial intent",
    "Construction completeness",
    # Task INSTALL adds the ninth family directly after Construction
    # completeness: it is that invariant's installability rung (owner amendment
    # #4 — hardware existing and penetrating the right members is not
    # construction-complete unless it also carries a represented, checkable
    # installation method). Its own claims climb the installability ladder
    # REPRESENTED < GEOMETRY-PROVEN < SEQUENCE-PROVEN (owner guardrail #6).
    "Fastener installability",
    "Functional use",
    "Load-path representation",
    "Support/Stability representation",
    "Structural capacity",
    "Code compliance",
)

#: Data-driven check-kind -> invariant-family table. This is the *entire*
#: family-assignment mechanism: tag lives at the kind level so a
#: Connection-generated check (e.g. ``connection_hardware``) inherits its
#: family without any per-detail wiring.
#:
#: Rationale for the two non-empty families:
#:   * Physical geometry — the solid model is itself physically valid: no
#:     two distinct solids share space (``interference``) and measured
#:     dimensions equal design intent (``dimension``).
#:   * Construction completeness — every intended connection is realized in
#:     the geometry: parts that must bear DO bear (``bearing``/``contact``),
#:     no part floats disconnected (``floating``), fasteners pass through
#:     their holes (``through_hole``), declared hardware is present
#:     (``connection_hardware``), and each component's own parameters are
#:     self-consistent (``parameters``).
#:
#:   * Spatial intent — declared mirror symmetry (``symmetric_about``) and
#:     facing direction (``faces_toward``/``faces_away``) hold: validation-only
#:     spatial invariants (task SPATIAL), the first activation of a family that
#:     was UNKNOWN on every detail before. A detail that declares no spatial
#:     invariants still reports UNKNOWN here (no check ran) — merely having the
#:     feature available fabricates no coverage.
#:
#: The remaining four families (Functional use, Load-path representation,
#: Structural capacity, Code compliance) have NO check kind today and so report
#: UNKNOWN on every current detail — which is the honest state, and the whole
#: reason this matrix exists.
KIND_TO_FAMILY: dict[str, str] = {
    "interference": "Physical geometry",
    "dimension": "Physical geometry",
    # A `clearance` finding (CL-2 clearance_cut FEATURE) proves a measured radial
    # gap between a featured part and the member it is fitted around equals the
    # design intent — a measured-geometry-equals-intent invariant, like dimension.
    "clearance": "Physical geometry",
    "symmetric_about": "Spatial intent",
    "faces_toward": "Spatial intent",
    "faces_away": "Spatial intent",
    "contact": "Construction completeness",
    "bearing": "Construction completeness",
    "through_hole": "Construction completeness",
    "floating": "Construction completeness",
    "connection_hardware": "Construction completeness",
    "parameters": "Construction completeness",
    # -- ONTOLOGY (task ONTOLOGY) additive block; SPATIAL adds its own kinds in
    # a separate block — keep these two disjoint for the merge --------------
    # A ``load_path`` finding asserts a typed support→ground path is REPRESENTED
    # (never "safe" — capacity stays UNKNOWN). It activates the Load-path
    # representation family, which was UNKNOWN on every detail before this task.
    "load_path": "Load-path representation",
    # -- SUPPORT (task SUPPORT) -------------------------------------------------
    # A ``support`` finding asserts a walking_surface's occupied region is
    # SUPPORTED (rung 3): its support scheme reaches a foundation AND the
    # occupied footprint sits over that scheme (or is a declared cantilever).
    # PASS = represented; FAIL = an undeclared unsupported region / deferred
    # support; UNKNOWN = a support exists but coverage is unresolved (blocks).
    # Rung 4 (force/moment/capacity) stays UNKNOWN — support ≠ adequate.
    "support": "Support/Stability representation",
    # -- FAB-3 (retire R29): foundation-role obligations ------------------------
    # The mirror of the support check: a post that BEARS on a foundation must be
    # ATTACHED to it (a declared post base), and the foundation body must be
    # founded. These are rung-3 REPRESENTATION obligations — same family as the
    # support check, since "roles generate support AND stability obligations"
    # (support-invariant-directive.md) and a foundation role is the stability
    # mirror of walking_surface's support role.
    "foundation_attachment": "Support/Stability representation",
    "foundation_embedment": "Support/Stability representation",
    # A ``foundation_capacity`` finding is the rung-4 honest UNKNOWN: uplift /
    # lateral / soil bearing are NOT ANALYZED by construction (design risk R2 —
    # never a capacity number). It lands in Structural capacity (rung 4), NOT
    # Support/Stability (rung 3), so representing the attachment (rung 3) and
    # refusing to certify its capacity (rung 4) stay DISTINCT verdicts — the
    # epistemic ladder the directive forbids blurring. Emitted as UNKNOWN, it
    # makes Structural capacity UNRESOLVED (blocking): a foundation shown but not
    # proven adequate can no longer read CLEAN.
    "foundation_capacity": "Structural capacity",
    # -- INSTALL (task INSTALL) -------------------------------------------------
    # The three installability check kinds, mapped BEFORE any emitter exists
    # (UnmappedCheckKind is a hard crash, so mapping-first is the safe landing
    # order; the emitters arrive in later INSTALL branches). Until they emit,
    # the family honestly reads UNKNOWN — NOT ANALYZED on every detail.
    #   * ``install_method`` — the core invariant (owner amendment #4): the
    #     fastener carries a resolvable FastenerInstallation contract. A PASS
    #     here is the REPRESENTED rung only — a declared method, never proof
    #     it can be driven.
    #   * ``install_termination`` — verdict axis 1: the shank/bolt path judged
    #     against the CONTRACT's exit condition and embedment (GEOMETRY-PROVEN
    #     against modeled geometry).
    #   * ``install_access`` — verdict axes 2+3: the declared tool envelope
    #     swept along the contract's tool axis from the entry face, occupants
    #     judged on the Construction Process Graph (a provably-present
    #     occupant FAILs with the proving order facts; a declared-order clear
    #     says declared; an unrelated occupant stays UNKNOWN — build order
    #     underdetermined, naming the gap).
    "install_method": "Fastener installability",
    "install_termination": "Fastener installability",
    "install_access": "Fastener installability",
}

#: Finding kinds that are PROVENANCE / bookkeeping markers, not invariant
#: checks — deliberately excluded from the coverage matrix. They carry no
#: verdict about whether a family holds, so counting them would spuriously
#: inflate a family's ``checks_run`` and could lie a family into PASS.
#:
#: ``connection_override`` (emitted by ``merge_into_spec``'s dedup at
#: ``connection.py`` when a Connection-generated spec entry supersedes a
#: hand-written one — the supported incremental-Connection-adoption path) is a
#: ``passed=True`` marker recording that a drop happened and is auditable in
#: the derivation log; it evidences nothing about physical geometry or
#: construction completeness. Excluding it (rather than mapping it into
#: Construction completeness) keeps ``checks_run`` honest.
#:
#: This is an EXPLICIT, reviewed exclusion — the ONLY escape from the "every
#: kind maps to a family" rule. A genuinely unknown kind (neither mapped nor
#: listed here) still raises :class:`UnmappedCheckKind` loudly, so a new check
#: can't silently vanish from the matrix.
PROVENANCE_ONLY_KINDS: frozenset[str] = frozenset({"connection_override"})

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN — NOT ANALYZED"
#: A family whose check(s) RAN but returned an unresolved UNKNOWN verdict (task
#: SUPPORT). Distinct from NOT-ANALYZED — the question WAS examined and the
#: honest answer is "cannot determine" — and it BLOCKS a clean export. Emitters:
#: the support-obligation check (Support/Stability), the foundation-capacity
#: obligation (Structural capacity), and the INSTALL family's checks — the
#: install-method core invariant (no resolvable contract) and the axis checks'
#: ``UNKNOWN — build order underdetermined`` (a tool corridor occupant the
#: construction process graph relates to the fastener by no order fact —
#: the verdict names the occupant and the missing order fact).
UNRESOLVED = "UNKNOWN — UNRESOLVED"

#: Standing note rendered beside every matrix (binding wording rule): the
#: system may say a load path "is REPRESENTED", never that anything "is safe".
STANDING_NOTE = (
    "UNKNOWN — NOT ANALYZED = no check of this family ran; UNKNOWN — UNRESOLVED "
    "= a check ran but could not answer (and blocks). Absence of a FAIL is not "
    "evidence of adequacy. The epistemic ladder, weakest to strongest, is "
    "connected-to-ground, then load-path-REPRESENTED, then support-REPRESENTED, "
    "then structurally-adequate. This build reaches at most support-REPRESENTED "
    "(rung 3): a supported occupied region is REPRESENTED, not proven safe. "
    "Fastener installability climbs its own ladder, weakest to strongest: "
    "installation-method-REPRESENTED, then GEOMETRY-PROVEN, then "
    "SEQUENCE-PROVEN — a rung RESERVED for a future geometric-necessity "
    "derivation; this build claims it nowhere. A represented installation "
    "method is a declared claim, not proof the fastener can be driven; "
    "sequence-dependent access is judged against the construction process "
    "graph, and a clear that rests on a DECLARED build order (an authored "
    "sequence: stage or a ConnectionType technique edge) is resolved on "
    "paper, never proved. "
    "Structural capacity and code compliance are NOT ANALYZED unless a PASS "
    "appears in those rows."
)


class UnmappedCheckKind(KeyError):
    """A check kind with no invariant-family assignment. Raised loudly so a
    new check kind cannot silently escape the coverage matrix — add it to
    :data:`KIND_TO_FAMILY` (a deliberate, reviewed decision about which
    family it evidences)."""

    def __str__(self) -> str:  # KeyError would repr-wrap the message
        return self.args[0] if self.args else super().__str__()


def family_of(kind: str) -> str:
    """The invariant family a check *kind* evidences. Loud on an unmapped
    kind — see :class:`UnmappedCheckKind`."""
    try:
        return KIND_TO_FAMILY[kind]
    except KeyError:
        raise UnmappedCheckKind(
            f"check kind {kind!r} has no invariant-family assignment; add it to "
            f"detailgen.validation.coverage.KIND_TO_FAMILY"
        ) from None


@dataclass(frozen=True)
class FamilyCoverage:
    """One row of the coverage matrix: a family's verdict plus the provenance
    (P1/P4) of how it was derived — which check kinds ran, how many findings,
    how many failed, and a human-readable derivation note."""

    family: str
    verdict: str
    checks_run: int
    findings: int
    failures: int
    #: ``(kind, count)`` pairs of the check kinds that ran in this family,
    #: sorted by kind — the "which checks ran" provenance.
    ran_kinds: tuple[tuple[str, int], ...]
    note: str
    #: How many of the family's clears rest on a DECLARED build order (task
    #: CPGCORE, STEPDOC owner amendment 3): declared-trust visibility is a
    #: product requirement — every surface that renders this row's verdict
    #: must carry the marker when this is non-zero, so "resolved" never
    #: reads as "proved". Default 0 keeps the field additive.
    declared: int = 0

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "verdict": self.verdict,
            "checks_run": self.checks_run,
            "findings": self.findings,
            "failures": self.failures,
            "ran_kinds": [list(rk) for rk in self.ran_kinds],
            "note": self.note,
            "declared_order_clears": self.declared,
        }

    @property
    def verdict_display(self) -> str:
        """The verdict string every READER surface renders (amendment 3):
        the bare verdict, plus the declared-trust marker whenever any of
        the family's clears rest on a declared build order. ``verdict``
        itself stays the pure algebra token for programmatic consumers
        (CSS classes, gating)."""
        if not self.declared:
            return self.verdict
        return (f"{self.verdict} ({self.declared} clear(s) at a DECLARED "
                f"build order — resolved on paper, declared, not "
                f"sequence-proven)")


def coverage_matrix(report) -> list[FamilyCoverage]:
    """Compute the coverage matrix for a :class:`ValidationReport` — one
    :class:`FamilyCoverage` per family in :data:`INVARIANT_FAMILIES` order.

    Derived entirely from ``report.findings`` (the audit trail of checks that
    ran). Verdict rules: FAIL if any finding in the family failed; else PASS if
    >=1 check of the family ran; else UNKNOWN."""
    return _coverage_from_findings(report.findings)


def aggregate_coverage_matrix(reports) -> list[FamilyCoverage]:
    """The DOCUMENT-LEVEL roll-up: one coverage matrix over the UNION of checks
    that ran across every report in ``reports``.

    Same verdict algebra as a single report, applied to the pooled findings — so
    a family is PASS iff >=1 check of it ran *somewhere* and none failed; FAIL if
    any check of it failed in any report; UNKNOWN — UNRESOLVED if a support check
    was unresolved (and none failed); and UNKNOWN — NOT ANALYZED iff no check of
    it ran in ANY report. That is the honest whole-document statement the
    reader-facing headline leads with: a family reads NOT ANALYZED only when
    nothing in the entire document examined it."""
    return _coverage_from_findings([f for r in reports for f in r.findings])


def _coverage_from_findings(all_findings) -> list[FamilyCoverage]:
    """Core of the matrix: bucket ``all_findings`` by family and derive each
    family's verdict + provenance. Shared by the single-report
    :func:`coverage_matrix` and the multi-report :func:`aggregate_coverage_matrix`
    so both use one verdict algebra."""
    by_family: dict[str, list] = {fam: [] for fam in INVARIANT_FAMILIES}
    for f in all_findings:
        if f.check in PROVENANCE_ONLY_KINDS:
            continue  # bookkeeping marker, not an invariant check
        by_family[family_of(f.check)].append(f)

    rows: list[FamilyCoverage] = []
    for fam in INVARIANT_FAMILIES:
        fs = by_family[fam]
        checks_run = len(fs)
        failures = sum(1 for f in fs if f.verdict == FAIL_VERDICT)
        unresolved = sum(1 for f in fs if f.verdict == UNKNOWN_VERDICT)
        # Declared-trust visibility (STEPDOC owner amendment 3): a clear
        # that rests on a DECLARED build order is resolved, never proved —
        # any summary surface counting it as resolved must say so, so the
        # marker rides the family's derivation note. Keyed on the
        # STRUCTURED Finding.declared_order flag (review F-2), never on the
        # verdict sentence's wording.
        declared = sum(1 for f in fs if f.passed
                       and getattr(f, "declared_order", False))
        ran = tuple(sorted(Counter(f.check for f in fs).items()))
        # Verdict precedence: a real FAIL dominates; else an unresolved UNKNOWN
        # (ran but couldn't answer, blocking) dominates a PASS; else PASS if any
        # check ran; else the family was never analyzed.
        if failures:
            verdict = FAIL
        elif unresolved:
            verdict = UNRESOLVED
        elif checks_run:
            verdict = PASS
        else:
            verdict = UNKNOWN
        rows.append(FamilyCoverage(
            family=fam, verdict=verdict, checks_run=checks_run,
            findings=checks_run, failures=failures, ran_kinds=ran,
            note=_derivation_note(verdict, ran, failures, unresolved,
                                  declared),
            declared=declared,
        ))
    return rows


def _derivation_note(verdict: str, ran_kinds, failures: int,
                     unresolved: int = 0, declared: int = 0) -> str:
    # Declared-trust visibility (STEPDOC owner amendment 3): "resolved"
    # must never read as "proved" on any summary surface.
    declared_note = (
        f"; {declared} clear(s) hold at a DECLARED build order — resolved "
        f"on paper, declared, not sequence-proven" if declared else "")
    if not ran_kinds:
        return "no check of this family ran"
    ran_str = ", ".join(f"{k}×{n}" for k, n in ran_kinds)
    if verdict == FAIL:
        return (f"{failures} failure(s) across checks that ran ({ran_str})"
                f"{declared_note}")
    if verdict == UNRESOLVED:
        return (f"{unresolved} unresolved UNKNOWN — analyzed but not "
                f"determinable, blocks CLEAN ({ran_str}){declared_note}")
    return f"all checks passed ({ran_str}){declared_note}"


def coverage_payload(report) -> list[dict]:
    """JSON-serializable coverage matrix (machine-readable report payload)."""
    return [row.to_dict() for row in coverage_matrix(report)]


# -- rendering -----------------------------------------------------------

def render_coverage_matrix_md(report) -> str:
    """Markdown coverage-matrix section, with the standing note. Rendered into
    every per-detail validation report."""
    rows = coverage_matrix(report)
    lines = [
        "## Coverage matrix — what this build actually analyzed",
        "",
        f"> {STANDING_NOTE}",
        "",
        "| Invariant family | Verdict | Checks run | Findings | Failures | Checks that ran |",
        "| --- | --- | --: | --: | --: | --- |",
    ]
    for r in rows:
        ran = ", ".join(f"{k}×{n}" for k, n in r.ran_kinds) or "—"
        lines.append(
            f"| {r.family} | {r.verdict_display} | {r.checks_run} | "
            f"{r.findings} | {r.failures} | {ran} |"
        )
    lines.append("")
    return "\n".join(lines)


#: CSS class per verdict, for the HTML renderer (styled by the caller's sheet).
#: UNRESOLVED shares the FAIL class — a blocking verdict reads as not-clean.
_VERDICT_CLASS = {PASS: "cov-pass", FAIL: "cov-fail", UNKNOWN: "cov-unknown",
                  UNRESOLVED: "cov-fail"}


def render_coverage_matrix_html(report, *, caption: str | None = None,
                                include_note: bool = True) -> str:
    """Self-contained HTML ``<table>`` for the consolidated report. Verdict
    cells carry ``cov-pass`` / ``cov-fail`` / ``cov-unknown`` classes; the
    standing note is emitted as a ``<p class="cov-note">`` unless
    ``include_note=False`` (so a multi-detail section can share one note)."""
    from html import escape

    rows = coverage_matrix(report)
    out = ['<table class="coverage">']
    if caption:
        out.append(f"<caption>{escape(caption)}</caption>")
    out.append(
        "<tr><th>Invariant family</th><th>Verdict</th><th>Checks run</th>"
        "<th>Failures</th><th>Checks that ran</th></tr>"
    )
    for r in rows:
        ran = escape(", ".join(f"{k}×{n}" for k, n in r.ran_kinds) or "—")
        cls = _VERDICT_CLASS[r.verdict]
        out.append(
            f'<tr><td>{escape(r.family)}</td>'
            f'<td class="{cls}">{escape(r.verdict_display)}</td>'
            f"<td>{r.checks_run}</td><td>{r.failures}</td><td>{ran}</td></tr>"
        )
    out.append("</table>")
    if include_note:
        out.append(f'<p class="cov-note">{escape(STANDING_NOTE)}</p>')
    return "\n".join(out)


# -- reader-facing headline verdict --------------------------------------
#
# Owner directive (Joel, 2026-07-08 §3): "CLEAN" as the prominent verdict
# visually communicates more confidence than the system possesses. The PRIMARY
# reader-facing headline of a report/doc surface is the PER-FAMILY breakdown —
# exactly what has been established, family by family — DERIVED from the coverage
# matrix, never hand-written, so it can never diverge from the matrix it heads.
# ("CLEAN"/require_clean stays as the internal/API verdict; this changes
# reader-facing prominence and wording, not verdict semantics.)

#: Severity order the compact one-line headline groups families in: the honest
#: not-clean states lead, PASS next, NOT-ANALYZED last. (The prominent HTML
#: headline keeps canonical family order instead — see render_headline_html.)
_HEADLINE_VERDICT_ORDER = (FAIL, UNRESOLVED, PASS, UNKNOWN)


def headline_by_verdict(rows) -> list[tuple[str, tuple[str, ...]]]:
    """Group coverage ``rows`` as ``[(verdict, (family, ...)), ...]`` — verdicts
    in severity order (:data:`_HEADLINE_VERDICT_ORDER`), families in canonical
    order within each. The compact inline form of the per-family headline.
    A family whose clears lean on a declared build order carries the
    amendment-3 marker on its NAME here (the verdict token is the group
    key, so the marker cannot ride it)."""
    grouped: list[tuple[str, tuple[str, ...]]] = []
    for verdict in _HEADLINE_VERDICT_ORDER:
        fams = tuple(
            r.family + (f" ({r.declared} declared-order clear(s) — "
                        f"resolved, not proved)" if r.declared else "")
            for r in rows if r.verdict == verdict)
        if fams:
            grouped.append((verdict, fams))
    return grouped


def render_headline_line(rows) -> str:
    """The per-family headline as one plain-text/markdown line, DERIVED from the
    matrix: ``'Physical geometry, Construction completeness: PASS · Structural
    capacity, Code compliance: UNKNOWN — NOT ANALYZED'``. Leads with what is
    established; the honest UNKNOWN/FAIL states render as themselves."""
    return " · ".join(
        f"{', '.join(fams)}: {verdict}"
        for verdict, fams in headline_by_verdict(rows)
    )


def render_headline_html(rows) -> str:
    """The PRIMARY reader-facing verdict as a prominent HTML list — one row per
    invariant family in canonical order, each carrying its coverage verdict
    (PASS / FAIL / UNKNOWN — NOT ANALYZED / UNKNOWN — UNRESOLVED), colour-coded by
    the caller's ``cov-*`` classes. DERIVED from ``rows`` (a coverage matrix), so
    the headline and the matrix below it can never disagree."""
    from html import escape

    items = "".join(
        f'<li class="vh-row"><span class="vh-fam">{escape(r.family)}</span>'
        f'<span class="vh-verdict {_VERDICT_CLASS[r.verdict]}">'
        f'{escape(r.verdict_display)}</span></li>'
        for r in rows
    )
    return f'<ul class="verdict-headline">{items}</ul>'
