"""``Connection`` — the first-class Construction-Graph edge (Wave 2, item 6).

Elevates "connection" from scattered arithmetic + string-pair validation
lists (the old ``rock_anchor._bearings``/``_bonds``/``_expected_overlaps``)
into an object the platform revolves around::

    Boulder --[rod + epoxy]--> Angle bracket --bears_on--> Leg

A :class:`Connection` declares only the minimal author-intended facts (which
placed parts it joins, the ordered hardware stack between them, which named
datums carry the joint, free-text assumptions); a :class:`ConnectionType`
(P2's "extensible dictionary" — reusable construction knowledge, one entry per
class of joint) DERIVES everything else from that declaration: required
hardware presence, REQUIRED bearing/contact pairs, allowed intersections,
installation order, and load-path edges. ``Connection.generate_checks()``
compiles those derivations into the exact keyword arguments
:func:`detailgen.validation.validate_assembly` already accepts, so a
Connection's validation can never drift from what it declares — geometry
becomes one representation of the connection, not the thing the connection is
inferred *from*.

Design principles this module is bound by (north star, 2026-07-06;
``docs/FRAMEWORK_ROADMAP.md``):

- **P1 (auditable inference)**: every derived fact is a :class:`DerivedFact`
  carrying its source connection, the rule that produced it, the assumptions
  used and a confidence tag. Ambiguous or missing input is a hard diagnostic
  (raised, with a helpful message) — never a silent guess. See
  :meth:`Connection.__post_init__` (unknown datum name) and
  :func:`compile_connections` (installation-order cycle).
- **P2 (extensible dictionary)**: :class:`ConnectionType` is the reusable
  knowledge; a :class:`Connection` is that knowledge applied to specific
  :class:`~detailgen.assemblies.assembly.Placed` parts. Two concrete types
  ship here, both drawn from real details in this repo: :class:`BoltedClamp`
  (the rock anchor's leg thru-bolts) and :class:`ThreadedRodEpoxyAnchor` (the
  rock anchor's rod/leveling-nut/angle stack).
- **P3 (imperative escape hatch)**: :func:`merge_into_spec` merges generated
  entries with a detail's hand-written ``validation_spec()`` lists; generated
  entries win on dedup (see the function docstring), so hand-authored checks
  keep working for anything not yet expressed through a Connection.
- **P4 (compiler diagnostics)**: :func:`compile_connections` returns the
  merged derivation log alongside the compiled spec — what was declared, what
  was inferred, and by which rule.

Non-negotiable review finding (trolley review, Critical-class): the legacy
``expected_overlaps`` PERMITS overlap but cannot REQUIRE contact — a detached
pair (e.g. a trolley wheel 6" off its cable) validated CLEAN. A Connection's
generated ``bearings`` entries are fed straight into
``detailgen.validation.checks.check_bearing``, which already FAILS when two
parts aren't actually touching — so a Connection-declared bearing pair proves
presence of contact, it does not merely permit it. See
``tests/test_connection.py::test_detached_bearing_pair_fails``.

Edge kinds are intentionally an open string, not a closed enum (Step-
placement-miss lesson): this wave only *generates* ``bears_on`` /
``fastened_by`` / ``transfers_load_to`` / ``bonded_to`` (load path, annotation
only — no load calculations) and ``installed_before`` (installation order); a
later wave can add non-structural kinds (``access_via``, ``entered_through``)
without touching this type. ``bonded_to`` (task GLUE) is the adhesive analog
of ``fastened_by``: an edge whose joint has NO fastener — calling a glue bond
"fastened" would misname the mechanism, so the honest kind names it.
"""

from __future__ import annotations

import difflib
from collections import deque
from dataclasses import dataclass, field
from typing import ClassVar

from .assembly import DetailAssembly, Placed
from .event_graph import ProcessFact, build_event_graph
from .installation import (
    EntryFace,
    Exit,
    FastenerInstallation,
    PROVENANCE_ASSUMPTION,
    PROVENANCE_AUTHORED,
    ResolvedInstallation,
    RoleGroup,
    ToolAxis,
    authored_only_contract,
    default_provenance,
    is_fastener,
    resolve_role_group,
    straight_screw_group,
    toe_screw_group,
    tool_envelope_for,
)
from ..core.ontology import TransferClaim
from ..core.registry import Registry
from ..validation.checks import Finding, UNKNOWN_VERDICT

PartRef = "Placed | str"

#: The P2 "extensible dictionary" as a name -> ConnectionType-subclass table,
#: so a serializable ``DetailSpec`` (W2-7) can name a connection type by string
#: (``type: bolted_clamp``) and the compiler resolve it — exactly as the
#: component/material/exporter/check registries let the spec resolve those. The
#: two concrete types below register into it (the W2-6 seam this fills); the
#: dictionary still grows one type at a time (P2), now discoverable by name with
#: the same loud unknown-key diagnostics every other registry gives.
connection_types: Registry = Registry("connection type")


# -- Construction-Graph primitives -------------------------------------------


@dataclass(frozen=True)
class Edge:
    """One Construction-Graph edge between two participating parts.

    ``kind`` is a free-form discriminator rather than a closed enum so later
    waves can introduce non-structural edge kinds without changing this type.
    This wave only generates ``bears_on`` / ``fastened_by`` /
    ``transfers_load_to`` / ``bonded_to`` (load-path annotation — no
    calculations) and ``installed_before`` (installation-order edges, checked
    for cycles by :func:`compile_connections`).
    """

    a: str  # Placed.id
    b: str  # Placed.id
    kind: str
    connection: str = ""  # source Connection.label, for provenance


@dataclass(frozen=True)
class DerivedFact:
    """One machine-readable line of the derivation log (P1/P4): a fact the
    framework derived from a :class:`Connection`, with full provenance —
    what was inferred, which rule produced it, what assumptions were used,
    and a confidence tag (``official`` a declared fact resolved as given,
    ``inferred`` a rule's derivation, ``placeholder`` a stand-in pending real
    data).

    ``source_type`` and ``subjects`` are the P4 Evidence-Graph extension
    (task EVIDENCE) — both OPTIONAL with backward-compatible defaults, so
    every existing call site (and the parallel spec compiler that consumes
    this type) keeps working unchanged:

    - ``source_type`` — the KNOWLEDGE-STRATEGY dimension, ORTHOGONAL to
      ``confidence``: ``authoritative`` (ground truth the compiler must
      honor — an author's direct declaration, a verbatim restatement of one,
      or an intrinsic physical/geometric law), ``verified_heuristic`` (a
      reviewed, promoted construction-knowledge rule derived the fact — the
      default, since the bulk of derivations come from ``ConnectionType``
      rules), or ``llm_hypothesis`` (a candidate rule, NEVER build-blocking —
      none in the codebase today). See
      :mod:`detailgen.validation.evidence` for the rubric + the
      non-blocking guarantee.
    - ``subjects`` — the ``Placed.id``\\ s this fact concerns, so the
      Evidence Graph can link a fact to the exact parts it is about without
      parsing the human-readable ``fact`` string. Empty when the producing
      site does not identify specific parts."""

    fact: str
    connection: str
    rule: str
    assumptions: tuple[str, ...] = ()
    confidence: str = "inferred"
    source_type: str = "verified_heuristic"
    subjects: tuple[str, ...] = ()


@dataclass
class ConnectionChecks:
    """Aggregated output of one or more Connections: the
    :func:`~detailgen.validation.validate_assembly` keyword arguments they
    contribute, plus the findings/derivation-log/edges that don't fit that
    call's shape (hardware-presence findings are already resolved facts, not
    geometric checks).

    The ``*_sources`` maps (pair id-frozenset -> owning Connection's label)
    let :func:`merge_into_spec` name exactly which Connection a dropped
    hand-written entry was overridden BY, rather than a bare "generated".

    ``installs`` (task INSTALL v1) is the resolved fastener installation
    contracts — one :class:`~detailgen.assemblies.installation.
    ResolvedInstallation` per fastener role-group, with per-field provenance
    — stashed here so the axis-1/axis-2 installability checks and
    ``Detail.validate`` consume them WITHOUT recomputing the resolution.

    ``sequence`` (task SEQSCHEMA, resolved by task CPGCORE) is the doc-level
    authored build-order claim — the ``sequence:`` block's stages, in
    declaration order, RESOLVED to the compiled surface (compiled connection
    labels, built ``Placed.id``\\ s — see
    :meth:`~detailgen.details.base.Detail.resolved_sequence`) — landed here
    so the axis-3 consumer reads it off this ONE compiled surface alongside
    ``installs`` rather than reaching back into the spec doc. Empty for
    every ``Detail`` that authors no sequence.

    ``after`` (+process) is the resolved typed process-point constraint
    surface. It stays beside ``sequence`` so the graph, axis-3 checks, direct
    test fallback, derivation log, and later reader projection consume one
    compiled truth rather than re-reading the spec.

    ``event_graph`` (task CPGCORE) is the built Construction Process Graph
    assembly slice (:class:`~detailgen.assemblies.event_graph.EventGraph`)
    over ALL connections + the authored sequence — the ONE order truth the
    axis-3 verdicts and the derived build-sequence reader surface project
    from. ``None`` until :func:`compile_connections` builds it.

    ``fragments`` (task CPGCORE, design §3.2) maps connection label -> the
    owning site fragment/subsystem id, for a COMPOSED site detail; empty for
    a standalone detail (one implicit fragment). No cross-fragment order
    exists in v1 — this map is what lets a composed-site verdict say so by
    name instead of a generic wording."""

    expected_overlaps: set[tuple[Placed, Placed]] = field(default_factory=set)
    bearings: list[tuple[Placed, Placed, str, float]] = field(default_factory=list)
    bonds: list[tuple[Placed, Placed]] = field(default_factory=list)
    overlap_sources: dict[frozenset, str] = field(default_factory=dict)
    bearing_sources: dict[frozenset, str] = field(default_factory=dict)
    bond_sources: dict[frozenset, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    derived: list[DerivedFact] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    installs: list[ResolvedInstallation] = field(default_factory=list)
    sequence: tuple = ()
    after: tuple = ()
    staging: object = None
    event_graph: object = None
    fragments: dict = field(default_factory=dict)


# -- ConnectionType: the reusable-knowledge dictionary (P2) ------------------


class ConnectionType:
    """Reusable construction knowledge for one class of joint.

    Subclass and override the hooks below; a :class:`Connection` is a
    ``ConnectionType`` instance applied to specific declared parts/hardware.
    The dictionary grows one type at a time (P2) — never blocked on
    completeness. Every hook receives the owning :class:`Connection` and
    returns its contribution; :meth:`Connection.generate_checks` records one
    :class:`DerivedFact` per item a hook returns, so a rule can never
    contribute a check invisibly (P1).
    """

    #: Display name for provenance/derivation-log rows and default labels.
    label: ClassVar[str] = "connection"

    # -- ONTOLOGY (task ONTOLOGY): TransferCapability -------------------------
    #: The load classes a joint of this type transfers / does_not_transfer
    #: (:class:`~detailgen.core.ontology.TransferClaim`\\ s), the reusable
    #: knowledge the load-path REPRESENTATION proof stands on. TYPE-level data
    #: (a property of the class of joint, not one placement), so it is a class
    #: attribute, not a per-connection hook. Default: no claims — a type whose
    #: transfer behaviour is not yet characterised makes the load-path proof
    #: refuse to route through it (unknown, never assumed). The concrete types
    #: below each declare an honest, provenance-tagged set. NEVER capacity: a
    #: claim says a class of load is carried onward, not that it is carried
    #: SAFELY.
    transfer_claims: ClassVar[tuple[TransferClaim, ...]] = ()

    def required_hardware(self, conn: "Connection") -> list[Placed]:
        """Hardware this connection's declaration requires to exist in the
        assembly. Default: every declared hardware item (by definition,
        declaring it makes it required) — override for a stronger rule."""
        return list(conn.hardware)

    def bearing_pairs(self, conn: "Connection") -> list[tuple[Placed, Placed, str, float]]:
        """Pairs that must be in REQUIRED flush contact: ``(a, b, axis,
        min_area_mm2)``, fed straight to
        :func:`~detailgen.validation.checks.check_bearing`, which FAILS when
        the pair isn't actually touching. This is what makes a Connection's
        declared contact required rather than merely permitted (the
        trolley-review non-negotiable — see module docstring)."""
        return []

    def allowed_intersections(self, conn: "Connection") -> set[tuple[Placed, Placed]]:
        """Pairs allowed to interpenetrate (a fastener biting the nut/wood it
        is driven into)."""
        return set()

    def bonded_pairs(self, conn: "Connection") -> list[tuple[Placed, Placed]]:
        """Pairs that are bonded/threaded rather than bearing — connectivity
        only (feeds ``check_no_floaters``), not a required-contact proof."""
        return []

    def edges(self, conn: "Connection") -> list[Edge]:
        """Construction-Graph edges this connection contributes: install
        order (``installed_before``) and load-path annotations (``bears_on``
        / ``fastened_by`` / ``transfers_load_to``)."""
        return []

    def install_contract(self, conn: "Connection") -> tuple[RoleGroup, ...] | None:
        """The type's DEFAULT fastener installation contract(s), one
        :class:`~detailgen.assemblies.installation.RoleGroup` per fastener
        role-group (task INSTALL v1 — the typed contract of owner amendment
        #1, carried by the Connection and derived from the type's own
        semantics, so migration is honest, not red noise).

        Return values, distinguished deliberately:

        - ``None`` (the base default) — this type CANNOT represent an
          installation method. Any fastener-class hardware it carries then
          reads blocking ``UNKNOWN — NO INSTALLATION METHOD REPRESENTED``
          (owner amendment #4), unless the spec authors a full contract.
        - ``()`` — this type has, by its own semantics, NO fastener-class
          hardware to contract (e.g. a connector whose field fasteners live
          on its own BOM line); an honest empty statement, never a gap.
        - one ``RoleGroup`` per role-group otherwise, each with per-field
          provenance (guardrail #7) stamped at the source."""
        return None

    @classmethod
    def supported_process_kinds(cls) -> frozenset[str]:
        """Process kinds this reusable joint type can produce.

        This capability surface is type-level so declaration semantics can
        reject an impossible process refinement before geometry.  The runtime
        graph still confirms that :meth:`process_events` actually produced the
        referenced fact; capability alone is never enough to invent an event.
        """
        return frozenset()

    def process_events(self, conn: "Connection") -> tuple[ProcessFact, ...]:
        """Typed non-geometric process facts contributed by this joint.

        The generic default is honestly empty.  Concrete types opt in through
        :meth:`supported_process_kinds` and produce facts from that same
        capability, optionally refining them from ``conn.process``.
        """
        return ()


# -- Connection: declared data + the compile step ----------------------------


@dataclass
class Connection:
    """A first-class Construction-Graph edge:
    ``Post --connected_to--> Bracket --connected_to--> Concrete, using
    Anchor-Bolt-Assembly``.

    ``parts`` are the primary members this connection joins (2+, e.g. a
    boulder and the clamp angle bearing against a leg); ``hardware`` is the
    ordered install stack the connection introduces between/around them
    (nuts, washers, rods, bolts). ``surfaces`` optionally names, per
    participating part's ``Placed.id``, the datum that carries the joint —
    every entry given is validated EAGERLY against that part's real datums
    (a hard diagnostic with suggestions on an unknown name, so a typo is
    caught at declaration time, never buried in a validation report).

    Everything else (bearing pairs, allowed intersections, hardware
    presence, install order, load-path edges) is DERIVED by ``kind`` from
    this minimal declared data — the north-star rule that the spec holds
    only author-intended facts and the platform infers the rest.

    Built on :class:`~detailgen.assemblies.assembly.Placed` handles and part
    ids throughout (never display names) per the binding Wave-1 review
    finding — display names are used only inside generated ``Finding``
    messages, for human readability.

    Dict-friendly by construction (every field is a plain list/dict of
    strings and ``Placed`` handles) so a future serializable ``DetailSpec``
    (W2-7) can round-trip a Connection without this class changing.
    """

    kind: ConnectionType
    parts: list[Placed]
    hardware: list[Placed] = field(default_factory=list)
    surfaces: dict[str, str] = field(default_factory=dict)  # Placed.id -> datum name
    assumptions: list[str] = field(default_factory=list)
    label: str = ""
    #: AUTHORED installation-contract overrides (task INSTALL v1): a
    #: role-group name -> {contract field -> resolved value} map, values
    #: already lowered by the spec compiler into the plain
    #: :mod:`~detailgen.assemblies.installation` leaf types (mm floats,
    #: ``EntryFace``/``ToolAxis``/``Exit``/``ToolEnvelope``, strings). The
    #: EMPTY-STRING key targets EVERY role group (the natural spelling for
    #: the single-group types); a named key targets that group and wins
    #: per-field over the "" entry. ``generate_checks`` resolves these OVER
    #: the type's default contract, stamping ``authored_override`` per field
    #: (guardrail #7). Empty for a connection authoring no override.
    install: dict = field(default_factory=dict)
    #: Typed authored process refinements lowered by the spec compiler.  The
    #: owning ConnectionType decides whether and how each supported fact is
    #: produced; an unsupported or silently dropped fact is a runtime error.
    process: tuple[ProcessFact, ...] = ()

    def __post_init__(self) -> None:
        if len(self.parts) < 2:
            raise ValueError(
                f"Connection {self.label or self.kind.label!r} needs 2+ "
                f"connected parts, got {len(self.parts)}"
            )
        if not self.label:
            self.label = f"{self.kind.label}({'~'.join(p.name for p in self.parts)})"
        for part_id, datum_name in self.surfaces.items():
            part = self._participant(part_id)
            if datum_name not in part.component.datums:
                suggestions = difflib.get_close_matches(
                    datum_name, sorted(part.component.datums), n=3
                )
                hint = f" — did you mean one of {suggestions}?" if suggestions else ""
                raise ValueError(
                    f"Connection {self.label!r}: part {part.name!r} ({part_id}) "
                    f"has no datum {datum_name!r}; available datums: "
                    f"{sorted(part.component.datums)}{hint}"
                )

    def _participant(self, part_id: str) -> Placed:
        for p in (*self.parts, *self.hardware):
            if p.id == part_id:
                return p
        known = [p.id for p in (*self.parts, *self.hardware)]
        raise KeyError(
            f"Connection {self.label!r}: surfaces references part id "
            f"{part_id!r}, not among this connection's parts/hardware {known}"
        )

    def generate_checks(self, assembly: DetailAssembly) -> ConnectionChecks:
        """Compile this connection's declared data (via ``self.kind``'s
        rules) into ``validate_assembly`` kwargs + a derivation log +
        Construction-Graph edges. ``assembly`` is needed only to confirm
        declared hardware is actually part of it (see the hardware-presence
        loop below) — every other hook operates purely on the ``Placed``
        handles this Connection already holds."""
        out = ConnectionChecks()
        rule_name = type(self.kind).__name__
        assumptions = tuple(self.assumptions)

        # Hardware presence (non-negotiable requirement #4 in the task
        # brief): a declared handle that is NOT actually a part of THIS
        # assembly must fail validation, not crash the build.
        # ``assembly._resolve`` is the one place a stale/foreign/never-placed
        # handle is turned into a loud, helpful error (see its docstring) —
        # we catch that and convert it into a Finding so it surfaces in the
        # report exactly like every other check, rather than as an
        # unrecoverable exception.
        #
        # The DerivedFact's confidence describes the KNOWLEDGE being
        # recorded ("hardware X is required"), not the pass/fail OUTCOME of
        # checking it (the Finding right above already carries the
        # present/absent verdict). Rider 4a: that confidence must track WHO
        # produced the list. The base ``required_hardware`` returns exactly
        # ``conn.hardware`` verbatim — the requirement is then an author-
        # declared "official" fact. A subclass that OVERRIDES the hook to
        # INFER extra hardware is instead deriving the requirement, so its
        # facts are tagged "inferred" — never silently mis-labelled official.
        # Detecting the override by identity (rather than adding a per-item
        # confidence to the hook's return type) keeps the hook signature and
        # every shipped type's output unchanged: all current types use the
        # base pass-through, so they stay "official".
        hw_declared = (
            type(self.kind).required_hardware is ConnectionType.required_hardware
        )
        hw_confidence = "official" if hw_declared else "inferred"
        # source_type (KNOWLEDGE STRATEGY, EVIDENCE) is computed from the SAME
        # override-identity signal, not from ``hw_confidence`` — a verbatim
        # author declaration is authoritative ground truth; a rule that INFERS
        # extra hardware is a promoted construction heuristic. Kept orthogonal
        # to confidence by construction (both happen to track the override
        # today, but each reads the producing SOURCE, not the other tag).
        hw_source = "authoritative" if hw_declared else "verified_heuristic"
        for part in self.kind.required_hardware(self):
            try:
                assembly._resolve(part)
                present = True
            except KeyError:
                present = False
            out.findings.append(Finding(
                "connection_hardware", f"{self.label}: {part.name}", present,
                "present" if present else
                "declared hardware not placed in this assembly",
            ))
            out.derived.append(DerivedFact(
                fact=f"hardware {part.name!r} required by {self.label}",
                connection=self.label, rule=f"{rule_name}.required_hardware",
                assumptions=assumptions, confidence=hw_confidence,
                source_type=hw_source, subjects=(part.id,),
            ))

        bearings = self.kind.bearing_pairs(self)
        out.bearings.extend(bearings)
        for (a, b, axis, min_area) in bearings:
            out.bearing_sources[frozenset((a.id, b.id))] = self.label
            out.derived.append(DerivedFact(
                fact=f"REQUIRED bearing {a.name} <-> {b.name} "
                     f"({axis} axis, >= {min_area:.0f} mm²)",
                connection=self.label, rule=f"{rule_name}.bearing_pairs",
                assumptions=assumptions, confidence="inferred",
                subjects=(a.id, b.id),
            ))

        overlaps = self.kind.allowed_intersections(self)
        out.expected_overlaps |= overlaps
        for (a, b) in overlaps:
            out.overlap_sources[frozenset((a.id, b.id))] = self.label
            out.derived.append(DerivedFact(
                fact=f"allowed intersection {a.name} <-> {b.name}",
                connection=self.label, rule=f"{rule_name}.allowed_intersections",
                assumptions=assumptions, confidence="inferred",
                subjects=(a.id, b.id),
            ))

        bonds = self.kind.bonded_pairs(self)
        out.bonds.extend(bonds)
        for (a, b) in bonds:
            out.bond_sources[frozenset((a.id, b.id))] = self.label
            out.derived.append(DerivedFact(
                fact=f"bonded {a.name} <-> {b.name}",
                connection=self.label, rule=f"{rule_name}.bonded_pairs",
                assumptions=assumptions, confidence="inferred",
                subjects=(a.id, b.id),
            ))

        edges = self.kind.edges(self)
        out.edges.extend(edges)
        for e in edges:
            out.derived.append(DerivedFact(
                fact=f"edge {e.a} -[{e.kind}]-> {e.b}",
                connection=self.label, rule=f"{rule_name}.edges",
                assumptions=assumptions, confidence="inferred",
                subjects=(e.a, e.b),
            ))

        self._resolve_install(out, rule_name, assumptions)
        return out

    def _resolve_install(self, out: ConnectionChecks, rule_name: str,
                         assumptions: tuple[str, ...]) -> None:
        """Resolve the fastener installation contracts (task INSTALL v1):
        authored-override fields (``self.install``) OVER the type's default
        contracts (``self.kind.install_contract``), per field, each field
        stamped with its provenance source (owner guardrail #7). Every
        resolved contract lands on ``out.installs`` (the axes branch / doc
        consumption surface) and in the derivation log as ONE DerivedFact
        listing every field WITH its source (per-field visibility in one
        deterministic, readable line).

        Confidence/source_type follow the override-identity pattern of the
        hardware-presence loop above, transposed to per-field provenance: a
        contract whose EVERY field is a verbatim authored declaration is
        ``official``/``authoritative``; any contract carrying type-default
        or assumption-grade fields is a rule's derivation —
        ``inferred``/``verified_heuristic``.

        The core invariant (owner amendment #4): fastener-class hardware
        whose contract does NOT resolve gets a blocking
        ``UNKNOWN — NO INSTALLATION METHOD REPRESENTED`` finding. No
        geometric checks run here — this branch only represents; the
        axis-1/axis-2 checks judge."""
        groups = self.kind.install_contract(self)
        authored = self.install or {}
        resolved: list[ResolvedInstallation] = []
        covered: set[str] = set()

        if groups is None:
            # No type default. An authored full contract (method + fields)
            # binds to ALL fastener-class hardware as one "authored" group;
            # anything less leaves the joint honestly unresolved.
            unknown_roles = sorted(k for k in authored if k)
            if unknown_roles:
                raise ValueError(
                    f"Connection {self.label!r} ({self.kind.label}): install "
                    f"override targets role group(s) {unknown_roles}, but "
                    f"this type declares no default contract (no role "
                    f"groups). Author the contract fields without a role "
                    f"key — they bind to every fastener in the connection."
                )
            fastener_ids = tuple(p.id for p in self.hardware if is_fastener(p))
            r = authored_only_contract(self.label, fastener_ids,
                                       authored.get("", {}))
            if r is not None and r.fasteners:
                resolved.append(r)
                covered.update(r.fasteners)
        else:
            roles = sorted(g.role for g in groups)
            unknown_roles = sorted(k for k in authored
                                   if k and k not in roles)
            if unknown_roles:
                suggestions = [s for k in unknown_roles for s in
                               difflib.get_close_matches(k, roles, n=2)]
                hint = (f" — did you mean one of {suggestions}?"
                        if suggestions else "")
                raise ValueError(
                    f"Connection {self.label!r} ({self.kind.label}): install "
                    f"override targets unknown role group(s) {unknown_roles}; "
                    f"this type's role groups: {roles}{hint} (omit the role "
                    f"to target every group)"
                )
            for g in groups:
                overrides = {**authored.get("", {}),
                             **authored.get(g.role, {})}
                r = resolve_role_group(self.label, g, overrides)
                resolved.append(r)
                covered.update(g.fasteners)

        for r in resolved:
            out.installs.append(r)
            all_authored = all(src == PROVENANCE_AUTHORED
                               for _f, src in r.provenance)
            out.derived.append(DerivedFact(
                fact=r.describe(),
                connection=self.label,
                rule=f"{rule_name}.install_contract",
                assumptions=assumptions + r.notes,
                confidence="official" if all_authored else "inferred",
                source_type=("authoritative" if all_authored
                             else "verified_heuristic"),
                subjects=r.fasteners,
            ))

        uncovered = [p for p in self.hardware
                     if is_fastener(p) and p.id not in covered]
        if uncovered:
            names = ", ".join(p.name for p in uncovered)
            # The reason must state what is actually missing: a type with no
            # default contract at all is a different gap from a type whose
            # role groups exist but do not cover this hardware (a future
            # under-covering type must not fire with a false explanation).
            reason = (
                f"the {self.kind.label!r} type declares no default contract"
                if groups is None else
                f"the {self.kind.label!r} type's default contract role "
                f"groups do not cover this hardware")
            out.findings.append(Finding(
                "install_method", f"{self.label}: {names}", False,
                "UNKNOWN — NO INSTALLATION METHOD REPRESENTED: the hardware "
                "exists and penetrates its members, but no installation "
                "method (entry face, tool axis, exit condition, embedment, "
                f"head, tool envelope) is represented for it — {reason}, "
                "and the spec authors no resolvable install: override. A "
                "connection is not construction-complete without a "
                "represented, checkable installation method (INSTALL core "
                "invariant); declare one via the type's install_contract or "
                "an install: block with at least a method.",
                verdict=UNKNOWN_VERDICT,
            ))


# -- Whole-detail compile step: aggregate + install-order cycle check -------


def compile_connections(assembly: DetailAssembly, connections: list[Connection],
                        sequence: tuple = (),
                        staging=None,
                        fragments: dict | None = None,
                        after: tuple = ()) -> ConnectionChecks:
    """Aggregate every :class:`Connection`'s generated checks into one
    :class:`ConnectionChecks`, run the whole-detail installation-order
    consistency check across ALL connections combined (a single connection's
    sequence can't cycle; a cycle can only emerge from two connections
    disagreeing about relative order, so this must operate on the union),
    then build the merged Construction Process Graph assembly slice (task
    CPGCORE) over connections + the authored ``sequence`` and cycle-check
    THAT — the event-level generalization of the part-level check (the
    part-level check stays: an intra-role-group hardware-chain
    contradiction would be masked by the event collapse).

    A cycle at either level is a HARD diagnostic (raises), never a Finding —
    an install order that contradicts itself isn't a validation failure to
    report around, it's an unrepresentable construction sequence (P1:
    ambiguous inference is a hard diagnostic, never a guess).

    ``sequence`` is the caller's RESOLVED doc-level authored-order claim
    (:meth:`~detailgen.details.base.Detail.resolved_sequence` — compiled
    connection labels + built part ids); a stage naming an unknown
    connection/part is a loud load-time teaching error here. ``fragments``
    is the composed-site connection-label -> fragment-id map (design §3.2);
    ``None``/empty for a standalone detail. ``after`` carries resolved typed
    process point constraints on the same compiled labels; the event graph
    validates every source/target and fragment chain again at runtime."""
    out = ConnectionChecks(sequence=sequence, after=after, staging=staging,
                           fragments=dict(fragments or {}))
    for conn in connections:
        c = conn.generate_checks(assembly)
        out.expected_overlaps |= c.expected_overlaps
        out.bearings.extend(c.bearings)
        out.bonds.extend(c.bonds)
        out.overlap_sources.update(c.overlap_sources)
        out.bearing_sources.update(c.bearing_sources)
        out.bond_sources.update(c.bond_sources)
        out.findings.extend(c.findings)
        out.derived.extend(c.derived)
        out.edges.extend(c.edges)
        out.installs.extend(c.installs)
    _check_install_order(out.edges)
    out.event_graph = build_event_graph(
        assembly, connections, out.edges, out.installs, sequence, staging,
        after=after, fragments=out.fragments)
    _record_process_order_facts(out, connections)
    return out


def _record_process_order_facts(out: ConnectionChecks,
                                connections: list[Connection]) -> None:
    """Project process-order graph truth into the ordinary derivation log.

    Only the two +process rules land here: bond/install-before-cure is a
    derived ConnectionType rule; cure-before-target is the author's direct
    point constraint.  Staging's process-before-join lift remains represented
    by the graph's existing staging provenance rather than duplicating the
    +process facts this increment promises.
    """
    from .event_graph import FAMILY_AUTHORED, FAMILY_NECESSITY

    graph = out.event_graph
    conn_by_label = {conn.label: conn for conn in connections}
    for edge in graph.edges:
        if (edge.family == FAMILY_NECESSITY
                and edge.a.kind == "drive" and edge.b.kind == "process"):
            conn = conn_by_label[edge.a.subject]
            process = graph.process_facts[edge.b]
            out.derived.append(DerivedFact(
                fact=(f"event order {graph.describe(edge.a)} -> "
                      f"{graph.describe(edge.b)} [{edge.family}]: "
                      f"{edge.source}"),
                connection=conn.label,
                rule=f"{type(conn.kind).__name__}.process_events",
                assumptions=(process.why,), confidence="inferred",
                source_type="verified_heuristic",
                subjects=tuple(p.id for p in conn.parts),
            ))
        elif (edge.family == FAMILY_AUTHORED
              and edge.a.kind == "process" and edge.b.kind == "drive"):
            claim = next(
                claim for claim in graph.constraints
                if claim.connection == edge.b.subject
                and any(ref.connection == edge.a.subject
                        and ref.kind == edge.a.group
                        for ref in claim.after))
            target = conn_by_label[claim.connection]
            out.derived.append(DerivedFact(
                fact=(f"event order {graph.describe(edge.a)} -> "
                      f"{graph.describe(edge.b)} [{edge.family}]: "
                      f"{edge.source}"),
                connection=target.label, rule="sequence.after",
                assumptions=(claim.why,), confidence="official",
                source_type="authoritative",
                subjects=tuple(p.id for p in target.parts),
            ))


def _check_install_order(edges: list[Edge]) -> None:
    order_edges = [e for e in edges if e.kind == "installed_before"]
    graph: dict[str, set[str]] = {}
    for e in order_edges:
        graph.setdefault(e.a, set()).add(e.b)
        graph.setdefault(e.b, set())
    indeg = {n: 0 for n in graph}
    for outs in graph.values():
        for m in outs:
            indeg[m] += 1
    q = deque(n for n, d in indeg.items() if d == 0)
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for m in graph[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if seen != len(graph):
        remaining = sorted(n for n in graph if indeg[n] > 0)
        cyclic_edges = [e for e in order_edges if e.a in remaining and e.b in remaining]
        detail = ", ".join(f"{e.a}->{e.b} ({e.connection})" for e in cyclic_edges)
        raise ValueError(
            "Connection install-order graph has a cycle — installation "
            f"order can't contradict itself. Parts involved: {remaining}. "
            f"Conflicting edges: {detail}"
        )


def merge_into_spec(assembly: DetailAssembly, hand_spec: dict, generated: ConnectionChecks) -> dict:
    """Merge a hand-written ``validation_spec()`` dict (the P3 escape hatch —
    details not yet using Connections keep working unchanged) with
    Connection-generated checks. Generated entries WIN on dedup: a
    hand-written entry for a pair the generated set already covers is
    dropped, never double-checked and never allowed to silently override
    the generated fact the other way — the entire point of generating FROM
    the Connection is that validation can't drift from what was declared.

    Every dropped hand-written entry is RECORDED, never silently discarded
    (P4: "what was overridden" is a required diagnostic output) — this
    function mutates ``generated`` in place, appending one
    :class:`DerivedFact` (naming the winning Connection by label) and one
    non-failing ``connection_override`` :class:`~detailgen.validation.checks.
    Finding` per override, so both the derivation log and the printed
    validation report show it. Callers that read ``generated.derived`` /
    ``generated.findings`` AFTER calling this function (as
    ``Detail.validate()`` does) see the override records too.

    ``through_holes`` and ``ground`` have no generated contribution in this
    wave (out of scope — see the task brief) and pass through unchanged.
    """

    def pid(ref: "Placed | str") -> str:
        return assembly._resolve(ref).id

    def subject_of(ref_a: "Placed | str", ref_b: "Placed | str") -> str:
        return f"{assembly._resolve(ref_a).name} <-> {assembly._resolve(ref_b).name}"

    def record_override(kind: str, entry: tuple, source_label: str) -> None:
        subject = subject_of(entry[0], entry[1])
        generated.derived.append(DerivedFact(
            fact=f"hand-written {kind} entry {entry!r} for {subject} "
                 f"DROPPED — superseded by Connection {source_label!r}'s "
                 f"generated {kind} entry for the same pair",
            connection=source_label, rule="merge_into_spec.dedup",
            confidence="official", source_type="authoritative",
            subjects=(pid(entry[0]), pid(entry[1])),
        ))
        generated.findings.append(Finding(
            "connection_override", subject, True,
            f"hand-written {kind} entry overridden by Connection "
            f"{source_label!r} (generated entries always win dedup) — "
            f"see derivation log",
        ))

    merged = dict(hand_spec)

    gen_overlap_keys = {frozenset((a.id, b.id)) for a, b in generated.expected_overlaps}
    kept_overlaps = set()
    for pair in hand_spec.get("expected_overlaps", set()):
        key = frozenset((pid(pair[0]), pid(pair[1])))
        if key in gen_overlap_keys:
            record_override("expected_overlaps", pair,
                             generated.overlap_sources.get(key, "generated"))
        else:
            kept_overlaps.add(pair)
    merged["expected_overlaps"] = kept_overlaps | generated.expected_overlaps

    gen_bearing_keys = {frozenset((a.id, b.id)) for (a, b, *_rest) in generated.bearings}
    kept_bearings = []
    for bspec in hand_spec.get("bearings", []):
        key = frozenset((pid(bspec[0]), pid(bspec[1])))
        if key in gen_bearing_keys:
            record_override("bearings", bspec,
                             generated.bearing_sources.get(key, "generated"))
        else:
            kept_bearings.append(bspec)
    merged["bearings"] = kept_bearings + generated.bearings

    gen_bond_keys = {frozenset((a.id, b.id)) for a, b in generated.bonds}
    kept_bonds = []
    for bond in hand_spec.get("bonds", []):
        key = frozenset((pid(bond[0]), pid(bond[1])))
        if key in gen_bond_keys:
            record_override("bonds", bond,
                             generated.bond_sources.get(key, "generated"))
        else:
            kept_bonds.append(bond)
    merged["bonds"] = kept_bonds + generated.bonds

    merged.setdefault("through_holes", hand_spec.get("through_holes", []))
    merged.setdefault("ground", hand_spec.get("ground"))
    return merged


# -- Positional-unpack role guards (rider 4b / P1) --------------------------
#
# ``ConnectionType`` subclasses unpack ``conn.hardware`` positionally by role
# (``bolt, head_washer, nut_washer, nut = conn.hardware``). A declaration with
# the right COUNT but the wrong ORDER unpacks cleanly and derives a plausible
# but WRONG fact (a washer treated as the bolt). These guards turn that into a
# hard, self-describing diagnostic at unpack time — P1: ambiguous/contradictory
# input is raised, never guessed. Role identity is the component's class name,
# the SAME key ``assembly._type_slug`` derives ``Placed.id`` from, so the check
# stays consistent with part identity and needs no import of the concrete
# component classes (avoids an assemblies->components dependency). Same-type
# adjacent slots (e.g. a stack's three ``HexNut``s) are inherently
# order-indistinguishable by type; this guard catches every CROSS-type misorder
# and every wrong count, which is the class of bug the ledger flagged.

_HANGER = ("JoistHanger",)
_SCREW = ("StructuralScrew",)
_BOX_SCREW = ("StructuralScrew", "ExteriorWoodScrew")
_EXTERIOR_SCREW = ("ExteriorWoodScrew",)
_BOLT = ("HexBolt",)
_WASHER = ("Washer",)
_NUT = ("HexNut",)
_ROD = ("ThreadedRod",)
_EPOXY = ("Epoxy",)
_POST_BASE = ("PostBase",)
_DOWEL = ("WoodDowel",)


def _require_hardware_roles(conn: "Connection", roles: list[tuple[str, ...]]) -> list[Placed]:
    """Assert ``conn.hardware`` matches ``roles`` (one accepted-class-name
    tuple per position) in both COUNT and per-position component TYPE, then
    return it for unpacking. Raises a ``ValueError`` naming the connection,
    the offending slot, what was expected and what was found."""
    hw = conn.hardware
    if len(hw) != len(roles):
        raise ValueError(
            f"Connection {conn.label!r} ({conn.kind.label}): expected "
            f"{len(roles)} hardware item(s) "
            f"[{', '.join('|'.join(r) for r in roles)}], got {len(hw)} "
            f"({[p.name for p in hw]}). Hardware is unpacked positionally by "
            f"role — a wrong-count declaration can't be mapped to roles."
        )
    for i, (part, accepted) in enumerate(zip(hw, roles)):
        actual = type(part.component).__name__
        if actual not in accepted:
            raise ValueError(
                f"Connection {conn.label!r} ({conn.kind.label}): hardware "
                f"slot {i} must be a {' or '.join(accepted)}, got {actual} "
                f"({part.name!r}). Hardware is unpacked positionally by role — "
                f"a wrong-order (same-count) declaration would otherwise "
                f"derive a plausible but WRONG fact instead of failing loudly."
            )
    return hw


# -- Concrete ConnectionTypes (P2 dictionary, seeded from real details) -----


@connection_types.register("bolted_clamp")
class BoltedClamp(ConnectionType):
    """A through-bolt (with a head-side washer and a nut-side washer + nut)
    clamping 2+ flat plates together — exemplar: the rock anchor's leg
    thru-bolts (``details/rock_anchor.py``, leg sandwiched between two steel
    angles); the same shape covers the platform's leg-to-beam carriage
    bolts (not re-authored this wave — see the task brief's scope note).

    Declared data:

    - ``parts``: the clamped plates, ORDERED nearest-the-bolt-head first,
      nearest-the-nut last (2+; any plates in between are sandwiched,
      touched by neither washer directly).
    - ``hardware``: ``[bolt, head_washer, nut_washer, nut]``, in that order.

    ``axis`` is the clamp axis; ``hardware_area``/``end_plate_area`` are the
    minimum accepted bearing areas (mm²) for, respectively, hardware-to-
    hardware contact (bolt/head-washer, nut/nut-washer) and a washer against
    its adjacent END plate. A clamp with 3+ plates only asserts bearing at
    the two OUTER plates the washers actually touch — a middle plate is
    guaranteed on-axis clearance (``through_holes`` probes that separately)
    but not necessarily face contact with its neighbors, which is a distinct
    structural fact this generic rule does not assume; a detail whose middle
    plate genuinely bears on its neighbor (e.g. a clamp angle against the
    leg it squeezes) should declare that as its own bearing fact — see
    :class:`ThreadedRodEpoxyAnchor`'s ``bracket_bearing_*`` params for the
    rock anchor's case of exactly that."""

    label = "bolted_clamp"

    # A through-bolted clamp carries gravity load between the plates it squeezes
    # (double-shear on the bolt / bearing on the plates) and resists in-plane
    # lateral load; it is not a tension/withdrawal connection. Reserved classes
    # are claimable as data even though no proof runs over them yet.
    transfer_claims = (
        TransferClaim("downward_load", True, "inferred", "verified_heuristic",
                      "through-bolt double-shear clamp — representative"),
        TransferClaim("lateral_push", True, "placeholder", "verified_heuristic",
                      "in-plane bearing of a bolted clamp — representative"),
    )

    def __init__(self, axis: str, hardware_area: float, end_plate_area: float):
        self.axis = axis
        self.hardware_area = hardware_area
        self.end_plate_area = end_plate_area

    def _unpack(self, conn: Connection):
        bolt, head_washer, nut_washer, nut = _require_hardware_roles(
            conn, [_BOLT, _WASHER, _WASHER, _NUT])
        return bolt, head_washer, nut_washer, nut

    def bearing_pairs(self, conn: Connection):
        bolt, head_washer, nut_washer, nut = self._unpack(conn)
        plates = conn.parts
        return [
            (bolt, head_washer, self.axis, self.hardware_area),
            (head_washer, plates[0], self.axis, self.end_plate_area),
            (nut_washer, plates[-1], self.axis, self.end_plate_area),
            (nut, nut_washer, self.axis, self.hardware_area),
        ]

    def allowed_intersections(self, conn: Connection):
        bolt, _head_washer, _nut_washer, nut = self._unpack(conn)
        return {(bolt, nut)}

    def bonded_pairs(self, conn: Connection):
        bolt, _head_washer, _nut_washer, nut = self._unpack(conn)
        return [(bolt, nut)]

    def edges(self, conn: Connection):
        bolt, head_washer, nut_washer, nut = self._unpack(conn)
        plates = conn.parts
        # Every plate must be in place before the bolt is driven THROUGH it —
        # that's the only real ordering fact between a plate and the bolt.
        # Deliberately no edge between plates themselves: their relative
        # install order isn't this connection's fact to assert (a plate may
        # be a shared "connected part" of another Connection that already
        # orders it, e.g. ThreadedRodEpoxyAnchor's leg-before-bracket edge —
        # asserting an order here too risks a real cross-connection cycle
        # when two rules disagree about something neither actually knows).
        out = [Edge(p.id, bolt.id, "installed_before", conn.label) for p in plates]
        hw_chain = [bolt, head_washer, nut_washer, nut]
        out += [Edge(a.id, b.id, "installed_before", conn.label)
                for a, b in zip(hw_chain, hw_chain[1:])]
        out.append(Edge(plates[0].id, plates[-1].id, "fastened_by", conn.label))
        return out

    def install_contract(self, conn: Connection):
        # CAT-C's inverse verdict, as data: for a through-bolt the exit is
        # REQUIRED (no-exit FAILs) and access is TWO-SIDED. The hardware
        # stack order names which end is which — the head washer seats on
        # plates[0] (head/driver side), the nut washer on plates[-1]
        # (nut/wrench side) — so both sides are checkable from the contract:
        # entry_face is the head side, exit.faces the nut side.
        bolt, head_washer, nut_washer, nut = self._unpack(conn)
        plates = conn.parts
        contract = FastenerInstallation(
            method="through_bolt",
            entry_face=EntryFace(plates[0].id, "free_face"),
            tool_axis=ToolAxis("shank"),
            exit=Exit("through_exit_required",
                      faces=(EntryFace(plates[-1].id, "free_face"),)),
            embedment="through",
            head="nut_and_washer",
            tool_envelope=tool_envelope_for("through_bolt"),
        )
        return (RoleGroup(
            role="bolt_stack", fasteners=(bolt.id,), contract=contract,
            provenance=default_provenance(),
            stack=(head_washer.id, nut_washer.id, nut.id),
            notes=("two-sided access: driver on the bolt-head side "
                   "(first plate's free face), wrench on the nut side "
                   "(last plate's free face)",)),)


@connection_types.register("threaded_rod_epoxy_anchor")
class ThreadedRodEpoxyAnchor(ConnectionType):
    """Epoxied all-thread rod anchoring a clamp bracket, which in turn bears
    against a third member — exemplar: the rock anchor's rod +
    leveling-nut + angle stack (``details/rock_anchor.py``):
    ``Boulder --[epoxy + rod hardware]--> Angle bracket --bears_on--> Leg``.

    Declared data:

    - ``parts``: ``[anchor_base, bracket, bearing_target]`` (the boulder, the
      clamp angle it anchors, and the member the angle bears against — e.g.
      the leg the anchor squeezes tight; the direct chain the brief's
      canonical example describes).
    - ``hardware``: ``[epoxy, rod, leveling_nut, lower_washer, upper_washer,
      lock_nut, jam_nut]``, in true installation order — the rod threads
      up through the leveling nut and lower washer BEFORE the bracket seats,
      then the upper washer/lock nut/jam nut clamp down on top of it.

    ``bracket_bearing_axis``/``bracket_bearing_area`` describe the bracket's
    REQUIRED bearing against ``bearing_target``.
    """

    label = "threaded_rod_epoxy_anchor"

    # An epoxied all-thread rod clamping a bracket to rock is the anchor whose
    # WHOLE job is to carry the leg's gravity load down into the boulder AND to
    # resist pull-out/uplift (an adhesive anchor's rated failure mode). The
    # downward-load claim is the one a path is proved over today; pull_out is
    # reserved but honestly claimable.
    transfer_claims = (
        TransferClaim("downward_load", True, "inferred", "verified_heuristic",
                      "epoxy-set anchor rod + clamp bracket — representative"),
        TransferClaim("pull_out", True, "placeholder", "verified_heuristic",
                      "adhesive anchor withdrawal resistance — representative"),
    )

    def __init__(self, stack_axis: str, nut_washer_area: float,
                 washer_bracket_area: float, bracket_bearing_axis: str,
                 bracket_bearing_area: float):
        self.stack_axis = stack_axis
        self.nut_washer_area = nut_washer_area
        self.washer_bracket_area = washer_bracket_area
        self.bracket_bearing_axis = bracket_bearing_axis
        self.bracket_bearing_area = bracket_bearing_area

    def _unpack(self, conn: Connection):
        anchor_base, bracket, bearing_target = conn.parts
        epoxy, rod, lev_nut, lo_washer, up_washer, lock_nut, jam_nut = \
            _require_hardware_roles(
                conn, [_EPOXY, _ROD, _NUT, _WASHER, _WASHER, _NUT, _NUT])
        return (anchor_base, bracket, bearing_target,
                epoxy, rod, lev_nut, lo_washer, up_washer, lock_nut, jam_nut)

    def bearing_pairs(self, conn: Connection):
        (_base, bracket, target, _epoxy, _rod, lev_nut, lo_washer, up_washer,
         lock_nut, jam_nut) = self._unpack(conn)
        ax = self.stack_axis
        return [
            (lev_nut, lo_washer, ax, self.nut_washer_area),
            (lo_washer, bracket, ax, self.washer_bracket_area),
            (bracket, up_washer, ax, self.washer_bracket_area),
            (up_washer, lock_nut, ax, self.nut_washer_area),
            (lock_nut, jam_nut, ax, self.nut_washer_area),
            (bracket, target, self.bracket_bearing_axis, self.bracket_bearing_area),
        ]

    def allowed_intersections(self, conn: Connection):
        (_base, _bracket, _target, _epoxy, rod, lev_nut, _lo, _up, lock_nut,
         jam_nut) = self._unpack(conn)
        return {(rod, lev_nut), (rod, lock_nut), (rod, jam_nut)}

    def bonded_pairs(self, conn: Connection):
        base, _bracket, _target, epoxy, rod, lev_nut, _lo, _up, lock_nut, jam_nut = \
            self._unpack(conn)
        return [
            (epoxy, base), (epoxy, rod),
            (rod, lev_nut), (rod, lock_nut), (rod, jam_nut),
        ]

    def edges(self, conn: Connection):
        (base, bracket, target, epoxy, rod, lev_nut, lo_washer, up_washer,
         lock_nut, jam_nut) = self._unpack(conn)
        chain = [base, epoxy, rod, lev_nut, lo_washer, bracket, up_washer,
                 lock_nut, jam_nut]
        out = [Edge(a.id, b.id, "installed_before", conn.label)
               for a, b in zip(chain, chain[1:])]
        out.append(Edge(target.id, bracket.id, "installed_before", conn.label))
        out.append(Edge(rod.id, base.id, "fastened_by", conn.label))
        out.append(Edge(rod.id, bracket.id, "transfers_load_to", conn.label))
        out.append(Edge(bracket.id, target.id, "bears_on", conn.label))
        return out

    def install_contract(self, conn: Connection):
        # An epoxy-set rod is NOT "driven": it is inserted along its own
        # axis into a hole drilled in the anchor base and set in adhesive —
        # method ``epoxy_set`` (an open tag, representing what is true). The
        # rod terminates inside the base (exit none) and its top end is
        # clamped by the washer/lock-nut/jam-nut stack (nut_and_washer). The
        # embedment MINIMUM is the adhesive spec's number, not derivable
        # from type semantics — honestly no declared minimum, provenance
        # ``assumption`` (the owning detail's embedment dimension check /
        # a manufacturer_data override carries the real value).
        (base, _bracket, _target, epoxy, rod, lev_nut, lo_washer, up_washer,
         lock_nut, jam_nut) = self._unpack(conn)
        contract = FastenerInstallation(
            method="epoxy_set",
            entry_face=EntryFace(base.id, "drilled_face"),
            tool_axis=ToolAxis("shank"),
            exit=Exit("none"),
            embedment=None,
            head="nut_and_washer",
            tool_envelope=tool_envelope_for("epoxy_set"),
        )
        return (RoleGroup(
            role="anchor_rod", fasteners=(rod.id,), contract=contract,
            provenance=default_provenance(embedment=PROVENANCE_ASSUMPTION),
            stack=(epoxy.id, lev_nut.id, lo_washer.id, up_washer.id,
                   lock_nut.id, jam_nut.id),
            notes=("epoxy-set anchor rod: no type-level embedment minimum "
                   "(adhesive-spec data); the detail's own embedment "
                   "dimension check carries the authored depth",)),)


@connection_types.register("standoff_post_base")
class StandoffPostBase(ConnectionType):
    """A POST held down onto its FOUNDATION block by an adjustable standoff post
    base (a :class:`~detailgen.components.concrete.PostBase`) — the mechanical
    attachment R29 found missing, where a leg merely *rested* on a pier block
    with no connection joining them (``retro-index.md:66``).

    Declared data:

    - ``parts``: ``[post, block]`` — the post the base carries and the
      foundation body it stands on.
    - ``hardware``: ``[post_base]`` — the single purchased standoff connector
      (its concrete anchor and post fasteners are field hardware carried on the
      post base's own BOM line, not modeled as separate parts in v1; see
      :meth:`~detailgen.components.concrete.PostBase.assumptions`).

    The post base is modeled EMBEDDED at the post/block interface (a formed
    saddle wraps the post end and its plate laps the block pad), so — exactly
    like :class:`FaceMountHanger`'s flange — its contact is a bonded/fastened
    connectivity fact via :meth:`allowed_intersections`/:meth:`bonded_pairs`,
    NOT a new flush-bearing claim: the post's gravity bearing on the block is the
    detail's own declared ``bearing`` and is left undisturbed. What this
    Connection ADDS is the fastened attachment — the uplift/lateral path that a
    bare bearing pair permits contact for but must never stand in for (the
    ``check_bearing``-vs-``expected_overlaps`` lesson, this module's docstring).
    Capacity stays UNKNOWN — the foundation-role obligation pack reports it (see
    :mod:`detailgen.validation.foundation`); a transfer CLAIM is not a proof."""

    label = "standoff_post_base"

    # A standoff post base's whole job is to hold the post DOWN onto the block:
    # it carries gravity into the pad AND resists uplift/lateral once fastened.
    # The claims are honest reserved-class data (no path proof runs over uplift/
    # lateral yet); NEVER capacity — a claim says a load class is carried onward,
    # not that it is carried SAFELY (the foundation obligation keeps capacity
    # UNKNOWN by construction).
    transfer_claims = (
        TransferClaim("downward_load", True, "inferred", "verified_heuristic",
                      "post base seats the post on the pad — representative"),
        TransferClaim("uplift", True, "placeholder", "verified_heuristic",
                      "standoff post base resists uplift once anchored + "
                      "fastened; withdrawal capacity NOT analyzed — representative"),
        TransferClaim("lateral_push", True, "placeholder", "verified_heuristic",
                      "post base restrains the post laterally — representative"),
    )

    def _unpack(self, conn: "Connection"):
        post, block = conn.parts
        (post_base,) = _require_hardware_roles(conn, [_POST_BASE])
        return post, block, post_base

    def allowed_intersections(self, conn: "Connection"):
        post, block, post_base = self._unpack(conn)
        # The saddle wraps the post end and its plate laps the block pad — an
        # embedded connector, not two flush faces (the FaceMountHanger flange
        # pattern), so its overlap with BOTH members is designed, not a collision.
        return {(post_base, post), (post_base, block)}

    def bonded_pairs(self, conn: "Connection"):
        post, block, post_base = self._unpack(conn)
        return [(post_base, block), (post_base, post)]

    def edges(self, conn: "Connection"):
        post, block, post_base = self._unpack(conn)
        # Install order: the block is set, then the post base is fastened onto
        # it (a fresh, isolated ordering fact — the block/post_base are in no
        # other install chain, so this can't join a cross-connection cycle). The
        # load-path annotations state the fastened attachment the bare bearing
        # never did: the post is fastened_by the block through the base, and the
        # base transfers the post's load to the block.
        return [
            Edge(block.id, post_base.id, "installed_before", conn.label),
            Edge(post.id, block.id, "fastened_by", conn.label),
            Edge(post_base.id, block.id, "transfers_load_to", conn.label),
        ]

    def install_contract(self, conn: "Connection"):
        # The only modeled hardware is the post base itself — a purchased
        # CONNECTOR, not a fastener: its concrete anchor and post fasteners
        # are field hardware carried on the post base's own BOM line (see
        # the class docstring / PostBase.assumptions), not modeled parts. An
        # explicit EMPTY contract set is the honest statement — there is no
        # fastener-class hardware here to contract — distinct from the base
        # None ("cannot represent"), so this type never reads as a gap.
        self._unpack(conn)  # keep the role guard (count/type) loud
        return ()


@connection_types.register("face_mount_hanger")
class FaceMountHanger(ConnectionType):
    """A HEADER member (beam or launch leg) carries a HUNG member (joist or
    ladder rung) in a bent-sheet-metal face-mount hanger, screwed to both.

    Exemplar: the zipline platform's beam<->joist hangers (``details/
    platform.py``, architect item 5) — the IDENTICAL mechanism also hangs the
    full-width ladder rungs between the two launch legs (architect item 2),
    just with a leg standing in for the beam. Same Connection type, two
    structurally distinct joints — proving the type generalizes, in the same
    spirit as :class:`BoltedClamp`'s reuse across the rock anchor and the
    platform's leg-to-beam bolts.

    ``seat_axis``/``seat_area`` describe the hung member's REQUIRED bearing on
    the hanger seat; ``n_header_screws``/``n_hung_screws`` are the header-side
    and hung-side fastener counts (both exercised by the platform today — no
    speculative parameters).

    Declared data:

    - ``parts``: ``[header, hung]`` — the beam/leg and the joist/rung.
    - ``hardware``: ``[hanger, *header_screws, *hung_screws]`` (counts fixed
      by the constructor args, so ``hardware`` must be built in that exact
      order).
    """

    label = "face_mount_hanger"

    # A face-mount hanger carries the hung member's gravity load into the header
    # (its seat is the whole point). A PLAIN face-mount hanger, though, does NOT
    # transfer uplift without added hurricane/tension fasteners — an honest
    # does_not_transfer claim (the kind of gap a future uplift proof would
    # catch), kept as data now.
    transfer_claims = (
        TransferClaim("downward_load", True, "inferred", "verified_heuristic",
                      "face-mount joist hanger seat bearing — representative"),
        TransferClaim("uplift", False, "placeholder", "verified_heuristic",
                      "plain face-mount hanger needs ties for uplift — "
                      "representative"),
    )

    def __init__(self, seat_axis: str, seat_area: float,
                 n_header_screws: int, n_hung_screws: int):
        self.seat_axis = seat_axis
        self.seat_area = seat_area
        self.n_header_screws = n_header_screws
        self.n_hung_screws = n_hung_screws

    def _unpack(self, conn: Connection):
        header, hung = conn.parts
        nh, nj = self.n_header_screws, self.n_hung_screws
        hardware = _require_hardware_roles(conn, [_HANGER] + [_SCREW] * (nh + nj))
        hanger = hardware[0]
        header_screws = hardware[1:1 + nh]
        hung_screws = hardware[1 + nh:1 + nh + nj]
        return header, hung, hanger, header_screws, hung_screws

    def bearing_pairs(self, conn: Connection):
        header, hung, hanger, _hs, _js = self._unpack(conn)
        # The hung member's real structural bearing is on the hanger's seat
        # (a REQUIRED contact per the trolley-review non-negotiable — see this
        # module's docstring). The hanger-to-header flange contact is
        # deliberately NOT asserted as a flush bearing here: the flange is
        # modeled embedded into the header face by one sheet-metal gauge (see
        # ``allowed_intersections``), so it is a bonded/fastened connectivity
        # fact, not a flush-face bearing proof.
        return [(hung, hanger, self.seat_axis, self.seat_area)]

    def allowed_intersections(self, conn: Connection):
        header, hung, hanger, header_screws, hung_screws = self._unpack(conn)
        # At a real, this-tight joint, a fastener's head legitimately touches
        # whichever member is on its near side even when that isn't the
        # member it's driven INTO (e.g. a header screw's head sits right at
        # the header face, which is also exactly where the hung member's own
        # end grain lands) — so every screw is allowed against all three
        # joint members, not just the one it's driven into.
        out = {(hanger, header)}
        for s in (*header_screws, *hung_screws):
            out |= {(s, hanger), (s, header), (s, hung)}
        return out

    def bonded_pairs(self, conn: Connection):
        header, hung, hanger, header_screws, hung_screws = self._unpack(conn)
        out = [(hanger, header)]
        out += [(s, header) for s in header_screws]
        out += [(s, hung) for s in hung_screws]
        return out

    def edges(self, conn: Connection):
        header, hung, hanger, header_screws, hung_screws = self._unpack(conn)
        out = [
            Edge(header.id, hanger.id, "installed_before", conn.label),
            Edge(hanger.id, hung.id, "installed_before", conn.label),
        ]
        out += [Edge(hanger.id, s.id, "installed_before", conn.label)
                for s in header_screws]
        # The face-mount technique's real sequence (task INSTALL): the hanger
        # is screwed to the HEADER first, and only then does the hung member
        # drop onto the seat — so every header screw precedes the hung
        # member. This is the machine-readable fact that lets the static
        # tool-access check see that the hung member (which buries the
        # header screws' heads in the final geometry) is not yet present at
        # their own install step (stage: own_connection).
        out += [Edge(s.id, hung.id, "installed_before", conn.label)
                for s in header_screws]
        out += [Edge(hung.id, s.id, "installed_before", conn.label)
                for s in hung_screws]
        out.append(Edge(hung.id, hanger.id, "bears_on", conn.label))
        out.append(Edge(hanger.id, header.id, "transfers_load_to", conn.label))
        return out

    def install_contract(self, conn: Connection):
        # Two role groups, per the type's own role layout: header-side
        # screws drive straight through the hanger flange into the header's
        # hanger-carrying face; hung-side screws drive straight through the
        # side flanges into the hung member's faces. The hanger itself is
        # connector hardware installed BY the header screws — it rides that
        # group's contract as stack, never a contract of its own.
        header, hung, hanger, header_screws, hung_screws = self._unpack(conn)
        # The hanger rides BOTH groups' stacks: the header screws AND the
        # hung screws each drive through one of its flanges, so for either
        # group the hanger is the co-installed connector its fasteners pass
        # — not a corridor blocker and not shank-path material of its own
        # (the INSTALL axes' own-role-group stack scoping made the
        # single-stack shorthand visibly wrong for the hung side).
        return (
            straight_screw_group("header_screws", header_screws, header.id,
                                 "hanger_face", stack=(hanger.id,)),
            straight_screw_group("hung_screws", hung_screws, hung.id,
                                 "hanger_face", stack=(hanger.id,)),
        )


@connection_types.register("toe_screwed")
class ToeScrewed(ConnectionType):
    """A hung member's end grain bears DIRECTLY on the header (no hanger
    metal), secured with toe-driven structural screws.

    Exemplar: the zipline platform's end/rim joist (``details/platform.py``,
    architect item 3) — wedged in a ~3.5" clear gap between a leg's own two
    thru-bolts, which is wide enough for the joist itself but NOT for a
    standard face-mount hanger's corner flanges. Toe-screwing straight through
    the joist end into the beam — a real, common technique for exactly this
    kind of tight retrofit spot — sidesteps the flange entirely; the hung
    member's end-grain-on-header bearing is a separate structural fact the
    owning detail declares itself, not generated by this type.

    ``n_screws`` is the per-joint toe-screw count (exercised by the platform).

    Declared data:

    - ``parts``: ``[header, hung]``.
    - ``hardware``: the toe screws only (no hanger metal)."""

    label = "toe_screwed"

    # A toe-screwed end joist bears its end grain on the header and is held by
    # toe-driven screws — it carries gravity load. Toe-screws into end grain are
    # weak in withdrawal, so no uplift claim is made (deliberately silent: an
    # unknown transfer, not an asserted one).
    transfer_claims = (
        TransferClaim("downward_load", True, "inferred", "verified_heuristic",
                      "end-grain bearing + toe screws — representative"),
    )

    def __init__(self, n_screws: int):
        self.n_screws = n_screws

    def _unpack(self, conn: Connection):
        header, hung = conn.parts
        screws = _require_hardware_roles(conn, [_SCREW] * self.n_screws)
        return header, hung, list(screws)

    def allowed_intersections(self, conn: Connection):
        header, hung, screws = self._unpack(conn)
        out = set()
        for s in screws:
            out |= {(s, header), (s, hung)}
        return out

    def bonded_pairs(self, conn: Connection):
        header, hung, screws = self._unpack(conn)
        return [(s, header) for s in screws] + [(s, hung) for s in screws]

    def edges(self, conn: Connection):
        header, hung, screws = self._unpack(conn)
        out = [Edge(header.id, hung.id, "installed_before", conn.label)]
        out += [Edge(hung.id, s.id, "installed_before", conn.label) for s in screws]
        out.append(Edge(hung.id, header.id, "bears_on", conn.label))
        return out

    def install_contract(self, conn: Connection):
        # CAT-B as data: the type finally says machine-readably what its
        # docstring always said — the real technique is ANGLED off the
        # exposed hung-member (joist) face, while today's drawn solids are
        # straight; the contract carries the declared angle and flags the
        # display idealization (amendment #3 — a reference, never a waiver).
        _header, hung, screws = self._unpack(conn)
        return (toe_screw_group("toe_screws", screws, hung.id),)


@connection_types.register("rail_cap_screwed")
class RailCapScrewed(ConnectionType):
    """A horizontal CAP member (e.g. a top rail) sits flat on a standing
    SUPPORT's (post or leg) top end grain and is fastened with structural
    screws driven straight DOWN through the cap into that end grain.

    Exemplar: the zipline platform's guard top rails (``details/platform.py``,
    task RAILFASTEN) — previously gravity-seated with no declared fastener,
    even though a guard rail is exactly the member a child grabs and pulls
    laterally on.

    Distinct from :class:`ToeScrewed` in both screw axis (vertical, matching
    the cap<->support bearing axis, vs. ``ToeScrewed``'s horizontal screw
    through a header face) and installation order: the SUPPORT stands first
    and the CAP lands on top of it afterward, the reverse of ``ToeScrewed``'s
    header-before-hung sequence.

    ``n_screws`` is the per-joint screw count (exercised by the platform).

    Declared data:

    - ``parts``: ``[support, cap]``.
    - ``hardware``: the vertical screws only (no hanger metal — the direct
      end-grain-to-face bearing is a separate structural fact the owning
      detail declares, the same pattern ``ToeScrewed`` uses).

    Assumption (P1, INFERRED): a screw driven into a post's END GRAIN has
    materially lower withdrawal capacity than the same screw driven into long
    grain — flagged on every declared Connection's ``assumptions``; not
    analyzed to a number here.
    """

    label = "rail_cap_screwed"

    # THE motivating joint: a top rail (a barrier a child grabs) fastened down
    # onto a post's end grain. With the RAILFASTEN screws declared it now
    # transfers gravity load AND represents a lateral_push path — but only
    # REPRESENTED, never proven safe: end-grain screw withdrawal capacity is the
    # exact number left UNKNOWN (the ``assumptions`` on every declared
    # Connection). A rail with NO such connection is the gravity-seated defect
    # (a bare ``bears_on`` and nothing that transfers) the load-path check
    # flags — see ``tests/test_loadpath.py``.
    transfer_claims = (
        TransferClaim("downward_load", True, "inferred", "verified_heuristic",
                      "cap on end grain, screwed down — representative"),
        TransferClaim("lateral_push", True, "placeholder", "verified_heuristic",
                      "guard-rail cap screwed to post; end-grain withdrawal "
                      "capacity NOT analyzed — representative"),
    )

    def __init__(self, n_screws: int):
        self.n_screws = n_screws

    def _unpack(self, conn: Connection):
        support, cap = conn.parts
        screws = _require_hardware_roles(conn, [_SCREW] * self.n_screws)
        return support, cap, list(screws)

    def allowed_intersections(self, conn: Connection):
        support, cap, screws = self._unpack(conn)
        out = set()
        for s in screws:
            out |= {(s, support), (s, cap)}
        return out

    def bonded_pairs(self, conn: Connection):
        support, cap, screws = self._unpack(conn)
        return [(s, support) for s in screws] + [(s, cap) for s in screws]

    def edges(self, conn: Connection):
        support, cap, screws = self._unpack(conn)
        out = [Edge(support.id, cap.id, "installed_before", conn.label)]
        out += [Edge(cap.id, s.id, "installed_before", conn.label) for s in screws]
        out.append(Edge(cap.id, support.id, "bears_on", conn.label))
        return out

    def install_contract(self, conn: Connection):
        # Screws drive straight DOWN through the cap (the through member)
        # into the support's end grain — entry on the cap's free face (its
        # top, opposite the cap<->support interface).
        _support, cap, screws = self._unpack(conn)
        return (straight_screw_group("cap_screws", screws, cap.id),)


@connection_types.register("cleat_screwed")
class CleatScrewed(ConnectionType):
    """A CLEAT block fastened to an adjacent member by axis-aligned screws
    driven through the cleat's FACE into the member's FACE — the hidden-fastener
    joint the standard cabinet/furniture ladder reaches for (a corner block /
    glue cleat) when a show-face screw is unacceptable.

    Exemplar: the armchair caddy's interior cleats (``details/
    armchair_caddy.spec.yaml``, design finding D1) — a small block tucked in
    each top-to-side corner, screwed UP into the top board's underside (face
    grain of the flat-laid top) and, as a second cleat_screwed joint,
    horizontally into the side board's inner face (face grain of the standing
    side). It retires the four screws that used to land on the top SHOW face and
    bit the side's TOP END GRAIN.

    What this type claims — and, deliberately, what it does NOT:

    - **No gravity seat.** Unlike :class:`RailCapScrewed` / :class:`ToeScrewed`,
      this type emits NO ``bears_on`` edge and NO ``bearing_pairs``. A cleat
      holds two parts TOGETHER; it does not, by itself, seat one on the other.
      Any real bearing at the joint (e.g. the caddy top still resting on the
      side's end grain) is a SEPARATE, independently-declared fact via the
      existing bearing machinery — never smuggled in through the fastener. This
      is the exact honesty the design review demanded: reusing a
      ``bears_on``-emitting screwed type here would assert a seat that does not
      exist (task-designreview §3, row D1b).
    - **Face-grain substrate, stated as such.** ``transfer_claims`` names FACE
      grain explicitly — screws into face grain hold materially better in
      withdrawal than the end-grain bite this joint replaces. The claim is only
      as strong as the mechanism: screws through the cleat resist the joined
      members SEPARATING (``pull_out`` — the joint's withdrawal resistance) and
      RACKING (``shear``). It makes NO ``downward_load`` claim — the cleat is
      not a load-bearing seat, and staying SILENT on a class the joint does not
      carry is the honest statement (an unknown transfer, not an asserted one).
      Capacity stays UNKNOWN: a claim says a class is carried onward, never that
      it is carried SAFELY.

    ``n_screws`` is the per-joint screw count (each caddy cleat_screwed joint
    drives 2). Orientation is not a parameter: the derivations (screw<->cleat +
    screw<->member overlap, connectivity bonds, install order, ``fastened_by``)
    are identical whether the screws run up into an underside or sideways into a
    face — so an axis argument would be a speculative parameter no derivation
    reads (the FaceMountHanger "no speculative parameters" discipline). Which
    way the screws run is a geometry fact the placement carries, not a semantic
    one this type needs.

    Assumption (P1, INFERRED): face-grain screw withdrawal is stronger than end
    grain but is NOT analyzed to a number here — flagged on every declared
    Connection's ``assumptions``.

    Declared data:

    - ``parts``: ``[cleat, member]`` — the cleat block and the member it is
      fastened to.
    - ``hardware``: the screws only (no cleat-to-member interpenetration: the
      cleat seats FLUSH against the member, a touching face, not an embedded
      connector like a hanger flange — so no cleat<->member
      ``allowed_intersections``; only the screws bite wood)."""

    label = "cleat_screwed"

    # A screwed cleat's job is to HOLD PARTS TOGETHER, not to seat one on the
    # other: the screws resist the members pulling apart (pull_out) and the joint
    # racking (shear), biting FACE grain both sides. NO downward_load claim (no
    # gravity seat — that is a separately-declared bearing) and NO bears_on edge.
    # Both classes are reserved (claimable as data, no path proof yet); NEVER
    # capacity.
    transfer_claims = (
        TransferClaim("pull_out", True, "placeholder", "verified_heuristic",
                      "screws driven into FACE grain both sides — the joint's "
                      "withdrawal resistance; face-grain holding, capacity NOT "
                      "analyzed — representative"),
        TransferClaim("shear", True, "placeholder", "verified_heuristic",
                      "face-grain screwed cleat resists racking/shear across "
                      "the joint — representative"),
    )

    def __init__(self, n_screws: int):
        self.n_screws = n_screws

    def _unpack(self, conn: Connection):
        cleat, member = conn.parts
        screws = _require_hardware_roles(conn, [_BOX_SCREW] * self.n_screws)
        return cleat, member, list(screws)

    def allowed_intersections(self, conn: Connection):
        cleat, member, screws = self._unpack(conn)
        out = set()
        for s in screws:
            out |= {(s, cleat), (s, member)}
        return out

    def bonded_pairs(self, conn: Connection):
        cleat, member, screws = self._unpack(conn)
        return [(s, cleat) for s in screws] + [(s, member) for s in screws]

    def edges(self, conn: Connection):
        cleat, member, screws = self._unpack(conn)
        # Both the cleat and the member it joins must be in place before a screw
        # is driven through the one into the other — the only ordering fact this
        # joint owns. Deliberately NO cleat<->member order edge: whether the
        # cleat is pre-attached to the member on the bench or offered up in the
        # corner depends on the build sequence, which isn't this connection's to
        # assert (and asserting it risks a cross-connection cycle when the two
        # joints sharing a cleat disagree). The load-path annotation is the plain
        # truth of the joint: the cleat is fastened_by the member. NO bears_on —
        # a cleat holds parts together, it is not a gravity seat.
        out = [Edge(cleat.id, s.id, "installed_before", conn.label) for s in screws]
        out += [Edge(member.id, s.id, "installed_before", conn.label) for s in screws]
        out.append(Edge(cleat.id, member.id, "fastened_by", conn.label))
        return out

    def install_contract(self, conn: Connection):
        # Screws drive straight through the CLEAT (the through member) into
        # the member's face — entry on the cleat's free face (opposite the
        # cleat<->member interface). THE motivating class: the caddy's D6
        # screws, whose heads sit buried mid-plate today, get their honest
        # driven_straight default here — the axis-2 check (later branch)
        # judges the buried entry face against exactly this contract.
        cleat, _member, screws = self._unpack(conn)
        return (straight_screw_group("cleat_screws", screws, cleat.id),)


@connection_types.register("butt_screwed")
class ButtScrewed(ConnectionType):
    """A screwed BUTT joint: one member's end/edge butts against another
    member's FACE, and screws are driven through that face into the butting
    member's END/EDGE GRAIN — the plain glue-and-screw box corner every
    sheet-goods project reaches for.

    Exemplar: the sit-and-reach box (task SITREACH, ``details/
    sit_reach_box.spec.yaml``) — each 3/4" plywood front/back panel is captured
    between the two side panels, screwed through the side's outside face into
    the front/back panel's ply edge (the prior-art standard construction for
    the 12" five-panel test box).

    Vocabulary rationale: this joint is NOT :class:`CleatScrewed` — that type's
    ``transfer_claims`` name FACE grain on both sides, and its exemplar retired
    end-grain screws specifically. Reusing it here would claim a stronger
    substrate than the mechanism has (the caddy design review's D1b lesson:
    never smuggle a claim through a type whose words don't fit). The screws in
    a butt joint bite the butting member's EDGE grain (ply edge / end grain),
    which is materially WEAKER in withdrawal than face grain — this type states
    exactly that and nothing more.

    What this type claims — and, deliberately, what it does NOT:

    - **No gravity seat.** Like :class:`CleatScrewed`, this emits NO
      ``bears_on`` edge and NO bearing: a butt screw holds two parts TOGETHER.
      Any real bearing at the joint (a captured panel standing on the floor, a
      cap resting on an edge) is a SEPARATE, independently-declared fact.
    - **Edge-grain substrate, stated as such.** Screws through the face member
      resist the joined members SEPARATING (``pull_out``) and RACKING
      (``shear``); the withdrawal side of that claim bites EDGE grain and is
      weaker than a face-grain cleat — flagged in the claims and on every
      declared Connection's ``assumptions``. NO ``downward_load`` claim.
      Capacity stays UNKNOWN: a claim says a class is carried, never that it
      is carried SAFELY.

    ``n_screws`` is the per-joint screw count. Orientation is not a parameter
    (the FaceMountHanger "no speculative parameters" discipline): which way
    the screws run is a geometry fact the placement carries.

    Declared data:

    - ``parts``: ``[face_member, butting_member]`` — the member whose FACE the
      screws pass through, then the member whose END/EDGE they bite.
    - ``hardware``: the screws only (the panels meet at a touching plane, not
      an embedded connector — only the screws bite wood)."""

    label = "butt_screwed"

    # A screwed butt joint HOLDS PARTS TOGETHER: pull_out (withdrawal from the
    # butting member's EDGE grain — the weak substrate, named) and shear across
    # the joint plane. NO downward_load (no gravity seat — separately-declared
    # bearing) and NO bears_on edge. Never capacity.
    transfer_claims = (
        TransferClaim("pull_out", True, "placeholder", "verified_heuristic",
                      "screws through the face member into the butting member's "
                      "END/EDGE grain — materially weaker in withdrawal than face "
                      "grain; capacity NOT analyzed — representative"),
        TransferClaim("shear", True, "placeholder", "verified_heuristic",
                      "screwed butt joint resists racking/shear across the joint "
                      "plane — representative"),
    )

    def __init__(self, n_screws: int):
        self.n_screws = n_screws

    def _unpack(self, conn: Connection):
        face_member, butting = conn.parts
        screws = _require_hardware_roles(conn, [_BOX_SCREW] * self.n_screws)
        return face_member, butting, list(screws)

    def allowed_intersections(self, conn: Connection):
        face_member, butting, screws = self._unpack(conn)
        out = set()
        for s in screws:
            out |= {(s, face_member), (s, butting)}
        return out

    def bonded_pairs(self, conn: Connection):
        face_member, butting, screws = self._unpack(conn)
        return ([(s, face_member) for s in screws]
                + [(s, butting) for s in screws])

    def edges(self, conn: Connection):
        face_member, butting, screws = self._unpack(conn)
        # Both members must be in place before a screw is driven through the one
        # into the other — the only ordering fact this joint owns (no
        # member<->member order edge, same reasoning as CleatScrewed). NO
        # bears_on — a butt screw holds parts together, it is not a gravity seat.
        out = [Edge(face_member.id, s.id, "installed_before", conn.label)
               for s in screws]
        out += [Edge(butting.id, s.id, "installed_before", conn.label)
                for s in screws]
        out.append(Edge(butting.id, face_member.id, "fastened_by", conn.label))
        return out

    def install_contract(self, conn: Connection):
        # Screws drive straight through the FACE MEMBER (the through member)
        # into the butting member's edge grain — entry on the face member's
        # free face (its outside, opposite the joint plane).
        face_member, _butting, screws = self._unpack(conn)
        return (straight_screw_group("butt_screws", screws, face_member.id),)


class _ServicePanelScrewed(ConnectionType):
    """One exterior screw retaining a service panel without fixing the joint."""

    edge_kind: ClassVar[str]
    role: ClassVar[str]

    def _unpack(self, conn: Connection):
        frame_member, service_panel = conn.parts
        (screw,) = _require_hardware_roles(conn, [_EXTERIOR_SCREW])
        return frame_member, service_panel, screw

    def allowed_intersections(self, conn: Connection):
        frame_member, service_panel, screw = self._unpack(conn)
        return {(screw, frame_member), (screw, service_panel)}

    def bonded_pairs(self, conn: Connection):
        frame_member, service_panel, screw = self._unpack(conn)
        return [(screw, frame_member), (screw, service_panel)]

    def edges(self, conn: Connection):
        frame_member, service_panel, screw = self._unpack(conn)
        return [
            Edge(frame_member.id, screw.id, "installed_before", conn.label),
            Edge(service_panel.id, screw.id, "installed_before", conn.label),
            Edge(service_panel.id, screw.id, self.edge_kind, conn.label),
        ]

    def install_contract(self, conn: Connection):
        frame_member, _service_panel, screw = self._unpack(conn)
        return (straight_screw_group(self.role, [screw], frame_member.id),)


@connection_types.register("pivot_screwed")
class PivotScrewed(_ServicePanelScrewed):
    """An exterior screw acting as one pivot pin for an opening service panel.

    The connection intentionally has no load-transfer claim, no gravity seat,
    and no member-to-member ``fastened_by`` edge: the panel remains operable.
    """

    label = "pivot_screwed"
    edge_kind = "pivoted_by"
    role = "pivot_screw"


@connection_types.register("service_latch_screwed")
class ServiceLatchScrewed(_ServicePanelScrewed):
    """A removable exterior screw latching an otherwise operable panel.

    The connection represents retention and service access only, not a fixed
    structural joint or an analyzed load path.
    """

    label = "service_latch_screwed"
    edge_kind = "latched_by"
    role = "latch_screw"


@connection_types.register("glued")
class Glued(ConnectionType):
    """Two members joined by an ADHESIVE BOND at a face-to-face mating plane —
    no hardware at all: the adhesive is the joint (task GLUE; the R-GLUE work
    order's plain face-to-face case — design task #22's glued-miter is the
    waterfall sibling, not this type).

    This reusable type owns only one connection's bond and its typed cure.
    When that cure must gate a different connection, the consumer declares
    the cross-connection order with ``sequence.after``; a project-specific
    assembly recipe does not belong in this modeling type.

    What this type claims — and, deliberately, what it does NOT:

    - **No gravity seat.** Like :class:`CleatScrewed` / :class:`ButtScrewed`,
      this emits NO ``bears_on`` edge and NO ``bearing_pairs``: a glue joint
      holds two parts TOGETHER; it does not, by itself, seat one on the other.
      Any real bearing at the joint is a SEPARATE, independently-declared
      fact via the existing bearing machinery — never smuggled in through the
      bond.
    - **Substrate lives on the CONNECTION, not the type.** Bond strength is a
      property of the two mated surfaces (long-grain face-to-face is the
      strong case; end grain starves a glue joint), which is per-placement
      knowledge a generic type cannot honestly assert — a reused type's
      generic text can be true for one consumer and false for the next (the
      R-SUBSTRATE lesson). The ``transfer_claims`` name only the MECHANISM
      (an adhesive bond across the mating plane); every declared Connection's
      ``assumptions`` must name what its two mated faces actually are, plus
      the substrate/capacity boundary. Clamp-and-cure is now the typed
      :meth:`process_events` fact, never parsed from assumptions and never
      misrepresented as a part-level ``installed_before`` edge.
    - **Nothing to contract.** :meth:`install_contract` returns the explicit
      empty ``()`` (never ``None``): by the type's own semantics there is no
      fastener-class hardware to install, so the Fastener-installability
      family honestly has nothing to judge on this joint — the same
      distinction :class:`StandoffPostBase` draws.
    - **Capacity stays UNKNOWN.** Adhesive bond capacity is manufacturer/
      substrate data no claim here supplies; a claim says a load class is
      carried onward, never that it is carried SAFELY.

    The Construction-Graph edge is ``bonded_to`` — the adhesive analog of
    ``fastened_by`` (calling a glue bond "fastened" would misname the
    mechanism). It is load-path-eligible exactly like ``fastened_by``
    (:data:`~detailgen.validation.loadpath.LOAD_BEARING_EDGE_KINDS`), gated
    per load class by this type's transfer claims like every other edge.

    Declared data:

    - ``parts``: ``[member_a, member_b]`` — EXACTLY the two bonded members
      (a bond plane is pairwise; three members glued in a stack are two
      declared joints, each with its own mating plane and assumptions).
    - ``hardware``: NONE — a glued connection declaring hardware is a
      contradiction raised loudly, never absorbed."""

    label = "glued"

    # An adhesive bond HOLDS PARTS TOGETHER: pull_out (the members separating
    # across the mating plane) and shear (racking along it). Substrate is
    # deliberately NOT named here — it is per-connection knowledge (docstring).
    # NO downward_load (no gravity seat — separately-declared bearing) and NO
    # bears_on edge. Never capacity.
    transfer_claims = (
        TransferClaim("pull_out", True, "placeholder", "verified_heuristic",
                      "adhesive bond across the mating plane resists the "
                      "members separating; bond strength depends on the mated "
                      "substrates — named on each connection's assumptions, "
                      "never by this type; capacity NOT analyzed — "
                      "representative"),
        TransferClaim("shear", True, "placeholder", "verified_heuristic",
                      "adhesive bond resists racking/shear along the mating "
                      "plane — representative"),
    )

    @classmethod
    def supported_process_kinds(cls) -> frozenset[str]:
        return frozenset({"cure"})

    def process_events(self, conn: Connection) -> tuple[ProcessFact, ...]:
        authored = tuple(f for f in conn.process if f.kind == "cure")
        if authored:
            return authored
        return (ProcessFact(
            kind="cure",
            instructions=(
                "Follow the selected adhesive label for surface preparation, "
                "application, and fixturing.",
                "Maintain the selected adhesive label's required fixture "
                "state under the actual shop conditions.",
            ),
            completion="selected_label_full_cure",
            why=("Treat cure as complete only at the selected adhesive "
                 "label's full-cure/full-strength condition under the actual "
                 "shop conditions; no generic duration is represented."),
            provenance="connectiontype_default",
        ),)

    def _unpack(self, conn: Connection):
        if len(conn.parts) != 2:
            raise ValueError(
                f"Connection {conn.label!r} ({self.label}): a glued joint "
                f"bonds EXACTLY two members at one mating plane, got "
                f"{len(conn.parts)} parts ({[p.name for p in conn.parts]}). "
                f"A multi-member glue-up is several pairwise joints, each "
                f"with its own mating plane and assumptions."
            )
        _require_hardware_roles(conn, [])  # a glued joint declares NO hardware
        member_a, member_b = conn.parts
        return member_a, member_b

    def bonded_pairs(self, conn: Connection):
        member_a, member_b = self._unpack(conn)
        return [(member_a, member_b)]

    def edges(self, conn: Connection):
        member_a, member_b = self._unpack(conn)
        # The bond is the joint's one graph fact. Deliberately NO
        # installed_before edge: there is no hardware. Clamp-and-cure lives
        # on the typed process-event surface, not as an ordering between the
        # members this joint owns (same reasoning as CleatScrewed's no
        # cleat<->member order edge). NO bears_on — a glue
        # joint holds parts together, it is not a gravity seat.
        return [Edge(member_a.id, member_b.id, "bonded_to", conn.label)]

    def install_contract(self, conn: Connection):
        # No fastener-class hardware by the type's own semantics — the honest
        # explicit ``()`` ("nothing to contract"), never the base ``None``
        # ("cannot represent"). The _unpack keeps the two-member/no-hardware
        # guards loud on this path too.
        self._unpack(conn)
        return ()


@connection_types.register("dowel_reinforced_miter")
class DowelReinforcedMiter(Glued):
    """Two hardwood panels joined at a glued miter and keyed by two dowels.

    The adhesive bond and the wooden keys are distinct facts: ``bonded_to``
    names the glued mating plane, while ``keyed_by`` names the mechanical
    reinforcement.  Neither implies analyzed capacity or a gravity seat.
    """

    label = "dowel_reinforced_miter"

    transfer_claims = (
        TransferClaim(
            "pull_out",
            True,
            "placeholder",
            "verified_heuristic",
            "glued miter mechanically crossed by hardwood dowels resists "
            "corner opening; capacity NOT analyzed — representative",
        ),
        TransferClaim(
            "shear",
            True,
            "placeholder",
            "verified_heuristic",
            "glued miter and crossing hardwood dowels resist racking/shear; "
            "capacity NOT analyzed — representative",
        ),
    )

    def _unpack(self, conn: Connection):
        if len(conn.parts) != 2:
            raise ValueError(
                f"Connection {conn.label!r} ({self.label}): a reinforced "
                f"miter joins EXACTLY two mitered panels, got "
                f"{len(conn.parts)} parts ({[p.name for p in conn.parts]})."
            )
        for part in conn.parts:
            if type(part.component).__name__ != "HardwoodPanel":
                raise ValueError(
                    f"Connection {conn.label!r} ({self.label}): member "
                    f"{part.name!r} must be HardwoodPanel, got "
                    f"{type(part.component).__name__}."
                )
        first, second = conn.parts
        front, back = _require_hardware_roles(conn, [_DOWEL, _DOWEL])
        return first, second, (front, back)

    def allowed_intersections(self, conn: Connection):
        first, second, dowels = self._unpack(conn)
        return {
            (dowel, member)
            for dowel in dowels
            for member in (first, second)
        }

    def bonded_pairs(self, conn: Connection):
        first, second, dowels = self._unpack(conn)
        return [(first, second)] + [
            (dowel, member)
            for dowel in dowels
            for member in (first, second)
        ]

    def edges(self, conn: Connection):
        first, second, dowels = self._unpack(conn)
        out = []
        for dowel in dowels:
            out.append(Edge(first.id, dowel.id, "installed_before", conn.label))
            out.append(Edge(second.id, dowel.id, "installed_before", conn.label))
        out.append(Edge(first.id, second.id, "bonded_to", conn.label))
        out.append(Edge(first.id, second.id, "keyed_by", conn.label))
        return out
