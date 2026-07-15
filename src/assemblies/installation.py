"""``FastenerInstallation`` — the typed fastener installation contract
(task INSTALL v1, ``installability-design.md``).

The measured defect class this exists for: 14 shipped fasteners across 3
delivered documents whose heads are buried mid-plate, whose real technique is
angled but modeled straight, or whose station sits at the joint interface —
every one validated CLEAN because *no installation method was represented at
all* (phase0-sweep-results.md). The owner's core invariant (amendment #4):

    a connection is not construction-complete merely because its hardware
    exists and penetrates the right members — it must also carry a
    represented, checkable installation method.

This module is the CONTRACT the invariant runs on: a typed value carried by
the :class:`~detailgen.assemblies.connection.Connection` for its fastener-class
hardware (per role-group), supplied by DEFAULT from the ConnectionType's own
semantics (``ConnectionType.install_contract``) and overridable/refinable per
field in the spec (``install:`` block). Checks DERIVE from the contract —
never from global geometric rules, which are FALSE for through-bolts, pocket
screws, countersunk hardware and intentionally concealed exits (owner
amendment #1).

Binding principles this module carries (owner sign-off, 2026-07-10):

- **Field-level provenance (guardrail #7).** A ConnectionType default is
  useful but not universally authoritative: every resolved contract field
  carries its source — one of :data:`PROVENANCE_SOURCES`
  (``connectiontype_default | manufacturer_data | authored_override |
  assumption``) — so a reviewer can see WHICH fields are assumption-grade
  (:meth:`ResolvedInstallation.assumption_fields`).
- **The epistemic ladder (guardrail #6).** A declared method is REPRESENTED,
  not proven: claims climb exactly ``REPRESENTED < GEOMETRY-PROVEN <
  SEQUENCE-PROVEN`` and never "declared-PASS". This module only DECLARES;
  the axis-1/axis-2 checks (a later branch) climb the ladder against modeled
  geometry, and a verdict resting on a declared-but-unmodeled condition
  (:attr:`ToolAxis.axis_idealized`) stays on the REPRESENTED rung.
- **Display idealization is never a waiver (amendment #3).** A toe screw
  drawn straight is acceptable visually only because the contract carries the
  actual angled semantics (``ToolAxis("angled", angle_deg=..,
  axis_idealized=True)``) — the flag tells every consumer that the drawn
  solid does not model the angle, so geometry-based verdicts on that axis are
  REPRESENTED-rung, never GEOMETRY-PROVEN.
- **Honest content, never a fake.** A field the producing knowledge cannot
  honestly state is carried as ``None``/``""`` with provenance
  ``assumption`` — an explicit "not declared", never a fabricated value.

Deliberately a LEAF module: plain frozen dataclasses of strings/floats/tuples
(the Connection docstring's dict-friendly serializability rule), importing
only ``core.units`` — no spec/, no validation/, no geometry. The spec layer
lowers its ``install:`` block INTO these types; ``Connection.generate_checks``
resolves and logs them; the axes branch consumes
:attr:`~detailgen.assemblies.connection.ConnectionChecks.installs` without
recomputing anything.

Consumption surface for the axis-1/axis-2 branch
------------------------------------------------
Each :class:`ResolvedInstallation` on ``ConnectionChecks.installs`` binds one
role-group's contract to its connection label and the driven fasteners'
``Placed.id``\\ s. The checks read:

- ``contract.method`` — an OPEN tag (like ``ProcessStep.kind``) selecting the
  verdict shape: ``through_bolt`` REQUIRES an exit + two-sided access;
  ``driven_straight``/``toe_screw``/``pocket_screw`` forbid undeclared exits.
- ``contract.entry_face`` — the member + semantic face the tool enters from
  (axis-2 sweeps the envelope from here; a buried entry face is the caddy
  class).
- ``contract.tool_axis`` — ``shank`` means "use the fastener's own ``axis``
  datum" (``components/fasteners.py``); ``angled`` means "the declared
  ``angle_deg`` off the entry face IS the semantics", and
  ``axis_idealized=True`` caps any verdict along it at REPRESENTED.
- ``contract.exit`` — the exit CONDITION judged by axis-1 (an undeclared face
  exit FAILs naming the face; a required through-exit that is absent FAILs;
  ``exit.faces`` names the concealed/nut-side faces so both bolt ends are
  checkable).
- ``contract.embedment`` — minimum bite (mm) or ``"through"``; ``None`` is an
  honest "no declared minimum" (provenance ``assumption``).
- ``contract.tool_envelope`` — the swept driver cylinder; ALWAYS resolved
  (module default 6in x 1in per the design's F-6) and printable
  (:meth:`ToolEnvelope.describe`) so every verdict can name the value it used.
- ``fasteners``/``stack`` — the driven fastener ids vs. the non-driven stack
  hardware (washers/nuts/epoxy) covered by the same single contract.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

from ..core.units import IN, fmt_in

# -- closed vocabularies ------------------------------------------------------

#: Allowed exit conditions (CLOSED — the design's §contract): ``none`` (the
#: shank terminates inside wood, the common screw case), ``concealed_exit``
#: (the shank exits, on DECLARED non-show faces — a disclosed design fact,
#: not a defect), ``through_exit_required`` (the exit is REQUIRED — a
#: through-bolt with no exit FAILs; the inverse verdict of the screw cases,
#: from the same checker).
EXIT_CONDITIONS = ("none", "concealed_exit", "through_exit_required")

#: Allowed head conditions (CLOSED): where the head/top of the stack ends up.
#: ``recessed_in_pocket`` judges against a MODELED void where vocabulary
#: exists and against the declared condition (disclosed, REPRESENTED rung)
#: where it does not yet (design §verdict axes).
HEAD_CONDITIONS = ("proud", "flush_countersunk", "recessed_in_pocket",
                   "nut_and_washer")

#: Tool-axis modes (CLOSED): ``shank`` — the tool drives along the fastener's
#: own ``axis`` datum (the drawn solid IS the semantics); ``angled`` — the
#: declared ``angle_deg`` off the entry face is the semantics (toe/pocket).
TOOL_AXIS_MODES = ("shank", "angled")

#: Field-level provenance sources (owner guardrail #7, CLOSED).
PROVENANCE_TYPE_DEFAULT = "connectiontype_default"
PROVENANCE_MANUFACTURER = "manufacturer_data"
PROVENANCE_AUTHORED = "authored_override"
PROVENANCE_ASSUMPTION = "assumption"
PROVENANCE_SOURCES = (PROVENANCE_TYPE_DEFAULT, PROVENANCE_MANUFACTURER,
                      PROVENANCE_AUTHORED, PROVENANCE_ASSUMPTION)

#: Component class names that are FASTENER-class — hardware that is DRIVEN or
#: SET and therefore owes an installation contract. Washers/nuts/epoxy/hangers
#: /post bases are stack or connector hardware: they ride a fastener's single
#: contract (``ResolvedInstallation.stack``) or carry field fasteners on their
#: own BOM line, never a contract of their own. Class-name matching keeps this
#: module free of a components import, exactly like connection.py's
#: positional-unpack role guards.
FASTENER_COMPONENT_CLASSES = (
    "LagScrew", "StructuralScrew", "ExteriorWoodScrew", "HexBolt",
    "ThreadedRod",
)

#: The toe-screw tool-axis angle off the entry face this vocabulary DECLARES
#: when nothing better is known — typical toe-screw/toenail technique, an
#: ASSUMPTION-grade value (stamped ``assumption`` in the provenance map),
#: never manufacturer data.
TOE_SCREW_ANGLE_DEG = 30.0

#: v1 declares NO method-specific envelope data (an empty map is honest —
#: inventing per-method driver sizes would be fake manufacturer_data). Fill
#: entries here as real tool knowledge lands; :func:`tool_envelope_for`
#: already consults it.
METHOD_TOOL_ENVELOPES: dict[str, "ToolEnvelope"] = {}


def is_fastener(placed) -> bool:
    """Whether a ``Placed`` part is FASTENER-class hardware (owes a
    contract). See :data:`FASTENER_COMPONENT_CLASSES`."""
    return type(placed.component).__name__ in FASTENER_COMPONENT_CLASSES


# -- contract leaf types ------------------------------------------------------


@dataclass(frozen=True)
class EntryFace:
    """WHERE the tool/fastener enters, as data (never prose): the member (a
    ``Placed.id`` once resolved; a spec-local id only transiently inside the
    loader) plus a SEMANTIC face descriptor. The descriptor names the face by
    construction role, not by coordinate — the vocabulary this branch uses:

    - ``free_face`` — the through-member's face OPPOSITE the joint interface
      (where a straight-driven screw's head lands);
    - ``exposed_face`` — the hung member's exposed face a toe screw enters;
    - ``hanger_face`` — the member face a hanger flange is mounted to;
    - ``drilled_face`` — the anchor body's face the rod hole is drilled into;
    - ``inner_face`` — the member's concealed interior face a pocket is
      bored into (an authored pocket-screw contract's entry — the caddy's
      rail joints).

    The set is OPEN (a descriptor is data the axes branch maps to geometry
    per method; an unknown descriptor degrades a verdict to honest UNKNOWN,
    never a guess)."""

    part: str
    face: str

    def describe(self) -> str:
        return f"{self.part}.{self.face}"


@dataclass(frozen=True)
class ToolAxis:
    """The driven/tool axis. ``mode`` is one of :data:`TOOL_AXIS_MODES`;
    ``angle_deg`` (angled mode) is the declared angle off the entry face
    plane. ``axis_idealized=True`` states that the DRAWN solid does not model
    the angle (today's screws are axis-aligned solids) — the flagged display
    simplification of owner amendment #3, which is a *reference to this
    contract*, never a waiver: consumers must cap verdicts along an
    idealized axis at the REPRESENTED rung."""

    mode: str
    angle_deg: float = 0.0
    axis_idealized: bool = False

    def describe(self) -> str:
        if self.mode == "shank":
            return "along the shank"
        s = f"angled {self.angle_deg:g}° off the entry face"
        if self.axis_idealized:
            s += " (drawn solid is straight — display idealization, verdicts REPRESENTED-rung)"
        return s


@dataclass(frozen=True)
class Exit:
    """The allowed exit condition (:data:`EXIT_CONDITIONS`) plus the declared
    face-set: for ``concealed_exit`` the non-show faces the shank may exit;
    for ``through_exit_required`` the far-side face(s) the exit MUST reach
    (a through-bolt's nut side — which makes BOTH bolt ends checkable)."""

    condition: str
    faces: tuple[EntryFace, ...] = ()

    def describe(self) -> str:
        if not self.faces:
            return self.condition
        return f"{self.condition} via {', '.join(f.describe() for f in self.faces)}"


@dataclass(frozen=True)
class ToolEnvelope:
    """The static tool-clearance envelope: a cylinder ``length`` long and
    ``dia`` across (both mm) swept along the tool axis from the entry face.
    Deliberately crude — v1 claims exactly "a declared envelope along a
    declared axis", no torque/swing-arc/two-hands modeling (design §what this
    deliberately does NOT do) — and always PRINTABLE so every verdict names
    the value it used."""

    length: float
    dia: float

    def describe(self) -> str:
        return f"{fmt_in(self.length)} x {fmt_in(self.dia)} dia tool envelope"


#: Module-default tool envelope (design F-6): a 6in x 1in driver cylinder
#: swept along the tool axis. Per-method overridable via
#: :data:`METHOD_TOOL_ENVELOPES`, per-connection overridable via the spec's
#: ``install: {tool: ...}`` — and the USED value is printable in every
#: verdict (:meth:`ToolEnvelope.describe`).
DEFAULT_TOOL_ENVELOPE = ToolEnvelope(6 * IN, 1 * IN)


def tool_envelope_for(method: str) -> ToolEnvelope:
    """The default envelope for ``method``: the method-specific entry when
    real tool knowledge exists (:data:`METHOD_TOOL_ENVELOPES`), else the
    module default (design F-6)."""
    return METHOD_TOOL_ENVELOPES.get(method, DEFAULT_TOOL_ENVELOPE)


@dataclass(frozen=True)
class FastenerInstallation:
    """The declared contract for one fastener role-group (design §The
    FastenerInstallation contract). ``method`` is an OPEN tag (the
    Step-placement-miss lesson: ``driven_straight | pocket_screw | toe_screw
    | through_bolt | captive | epoxy_set | ...`` — new methods must not
    require touching this type); every other field is either a closed-
    vocabulary string, a leaf dataclass above, or an honest ``None``/``""``
    ("not declared" — legal content whose provenance is then
    ``assumption``, never a fabricated value).

    ``embedment`` is the minimum bite into the anchor member in mm, the
    literal string ``"through"``, or ``None`` (no declared minimum).
    ``stage`` is an install-step reference — v1 knows only
    ``"own_connection"`` (installed at this connection's own step); the real
    sequence vocabulary is Construction Process Graph territory (axis 3)."""

    method: str
    entry_face: EntryFace | None = None
    tool_axis: ToolAxis | None = None
    exit: Exit | None = None
    embedment: object = None  # float mm | "through" | None
    head: str = ""            # one of HEAD_CONDITIONS, or "" = not declared
    tool_envelope: ToolEnvelope | None = None
    stage: str = "own_connection"


#: Canonical field order of the contract — the order provenance maps and
#: derivation-log lines list fields in (determinism).
CONTRACT_FIELDS = tuple(f.name for f in fields(FastenerInstallation))


def default_provenance(**overrides: str) -> tuple[tuple[str, str], ...]:
    """A per-field provenance map for a TYPE-DEFAULT contract: every field
    ``connectiontype_default`` except the named ``overrides`` (e.g.
    ``embedment=PROVENANCE_ASSUMPTION``). Returned in canonical field order
    as a tuple of ``(field, source)`` pairs — hashable, deterministic,
    dict-friendly."""
    for name, source in overrides.items():
        if name not in CONTRACT_FIELDS:
            raise ValueError(
                f"default_provenance: {name!r} is not a contract field; "
                f"fields: {CONTRACT_FIELDS}")
        if source not in PROVENANCE_SOURCES:
            raise ValueError(
                f"default_provenance: {source!r} is not a provenance source; "
                f"sources: {PROVENANCE_SOURCES}")
    return tuple((name, overrides.get(name, PROVENANCE_TYPE_DEFAULT))
                 for name in CONTRACT_FIELDS)


@dataclass(frozen=True)
class RoleGroup:
    """One fastener role-group's DEFAULT contract, as produced by
    ``ConnectionType.install_contract``: the role name (the key an
    ``install:`` override targets), the driven fasteners' ``Placed.id``\\ s,
    the contract, its per-field default provenance (built with
    :func:`default_provenance` so assumption-grade fields are stamped at the
    source), the non-driven ``stack`` hardware ids the same contract covers
    (a bolt stack's washers/nut, an anchor's epoxy/nuts), and free-text
    ``notes`` explaining any assumption-grade content (flow into the derived
    fact's assumptions)."""

    role: str
    fasteners: tuple[str, ...]
    contract: FastenerInstallation
    provenance: tuple[tuple[str, str], ...]
    stack: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedInstallation:
    """A RESOLVED contract bound to its joint: authored-override fields
    overlaid on the type default, each field stamped with its source
    (guardrail #7). This is the object the axis-1/axis-2 checks and
    ``Detail.validate`` consume from ``ConnectionChecks.installs`` — nothing
    downstream re-resolves."""

    connection: str                # owning Connection.label
    role: str                      # role-group name within the connection
    fasteners: tuple[str, ...]     # driven fastener Placed.ids
    contract: FastenerInstallation
    provenance: tuple[tuple[str, str], ...]  # (field, source), canonical order
    stack: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def provenance_map(self) -> dict[str, str]:
        return dict(self.provenance)

    @property
    def assumption_fields(self) -> tuple[str, ...]:
        """The fields a reviewer must treat as assumption-grade (guardrail
        #7's 'see WHICH fields')."""
        return tuple(f for f, s in self.provenance
                     if s == PROVENANCE_ASSUMPTION)

    def describe(self) -> str:
        """The deterministic one-line rendering used verbatim as the
        derivation-log fact: every field with its value AND its source, in
        canonical order — per-field provenance visibility in one readable
        line."""
        pm = self.provenance_map
        c = self.contract
        rendered = {
            "method": c.method or "NOT DECLARED",
            "entry_face": c.entry_face.describe() if c.entry_face else "not declared",
            "tool_axis": c.tool_axis.describe() if c.tool_axis else "not declared",
            "exit": c.exit.describe() if c.exit else "not declared",
            "embedment": ("through" if c.embedment == "through"
                          else f"{fmt_in(c.embedment)} min bite"
                          if c.embedment is not None else "no declared minimum"),
            "head": c.head or "not declared",
            "tool_envelope": (c.tool_envelope.describe() if c.tool_envelope
                              else "not declared"),
            "stage": c.stage,
        }
        parts = "; ".join(f"{name}={rendered[name]} [{pm[name]}]"
                          for name in CONTRACT_FIELDS)
        return (f"install contract {self.role!r} for {self.connection}: {parts}")


# -- resolution ---------------------------------------------------------------


def _checked_overrides(overrides: dict, context: str) -> dict:
    for name in overrides:
        if name not in CONTRACT_FIELDS:
            raise ValueError(
                f"{context}: install override names unknown contract field "
                f"{name!r}; contract fields: {CONTRACT_FIELDS}")
    return overrides


#: Which contract FIELD each default-explaining note prefix belongs to
#: (matched against the note strings the group builders emit). When that
#: field is authored, its default's explanatory note no longer describes
#: the resolved value and carrying it forward would be an honest-looking
#: lie ("embedment default = half the under-head length" beside
#: ``embedment=... [authored_override]``) — the note is dropped; the
#: authored WHY belongs in the connection's own ``assumptions``.
_DEFAULT_NOTE_FIELDS = (
    ("embedment", "embedment default"),
    ("embedment", "no declared embedment minimum"),
    ("tool_axis", "toe-screw tool axis"),
)


def resolve_role_group(connection_label: str, group: RoleGroup,
                       overrides: dict) -> ResolvedInstallation:
    """Overlay authored-override fields on ``group``'s type-default contract
    (per FIELD — an override refines, it never wipes the rest of the
    default), stamping each overridden field ``authored_override`` and
    leaving every other field's default provenance (including its
    ``assumption`` stamps) intact. Notes explaining an overridden field's
    DEFAULT (:data:`_DEFAULT_NOTE_FIELDS`) are dropped — they describe a
    value the resolved contract no longer carries."""
    _checked_overrides(overrides, f"connection {connection_label!r}")
    contract = replace(group.contract, **overrides) if overrides else group.contract
    provenance = tuple(
        (name, PROVENANCE_AUTHORED if name in overrides else source)
        for name, source in group.provenance)
    notes = tuple(
        n for n in group.notes
        if not any(field in overrides and n.startswith(prefix)
                   for field, prefix in _DEFAULT_NOTE_FIELDS))
    return ResolvedInstallation(
        connection=connection_label, role=group.role,
        fasteners=group.fasteners, contract=contract,
        provenance=provenance, stack=group.stack, notes=notes)


def authored_only_contract(connection_label: str, fastener_ids: tuple[str, ...],
                           overrides: dict) -> ResolvedInstallation | None:
    """Build a contract PURELY from authored fields, for a connection whose
    type declares no default (``install_contract() is None``). Resolvable
    only when the author declares at least a ``method`` — otherwise ``None``
    (the joint stays blocking-UNKNOWN, the core invariant). Un-authored
    fields carry honest not-declared content with provenance ``assumption``
    — EXCEPT ``tool_envelope``, which always resolves (the design requires a
    printable used-value in every verdict) to the method default, also
    stamped ``assumption`` here because no type semantics vouch for it."""
    _checked_overrides(overrides, f"connection {connection_label!r}")
    method = overrides.get("method", "")
    if not method:
        return None
    base = FastenerInstallation(
        method=method, tool_envelope=tool_envelope_for(method))
    contract = replace(base, **overrides)
    provenance = tuple(
        (name, PROVENANCE_AUTHORED if name in overrides
         else PROVENANCE_ASSUMPTION)
        for name in CONTRACT_FIELDS)
    return ResolvedInstallation(
        connection=connection_label, role="authored",
        fasteners=fastener_ids, contract=contract, provenance=provenance,
        notes=("contract authored on a type with no default install "
               "contract; un-authored fields are not declared (assumption)",))


# -- default-contract builders (shared by the concrete ConnectionTypes) -------

_HALF_BITE_NOTE = ("embedment default = half the fastener's under-head "
                   "length (rule of thumb), NOT derived from joint geometry")


def _half_length_embedment(screws) -> tuple[object, tuple[str, ...]]:
    """The assumption-grade embedment default for driven screws: half the
    under-head length (of the SHORTEST screw in the group, conservative).
    Returns ``(embedment_mm | None, notes)`` — ``None`` (with its note) for
    a component that carries no ``length``, never a fabricated number."""
    lengths = [getattr(s.component, "length", None) for s in screws]
    if not lengths or any(ln is None for ln in lengths):
        return None, ("no declared embedment minimum (fastener carries no "
                      "under-head length)",)
    return 0.5 * min(lengths), (_HALF_BITE_NOTE,)


def straight_screw_group(role: str, screws, entry_part_id: str,
                         entry_face: str = "free_face",
                         stack: tuple[str, ...] = ()) -> RoleGroup:
    """The shared default for a straight-driven screw group
    (cleat/rail-cap/butt/hanger screws): ``driven_straight`` along the
    shank, entering ``entry_part_id``'s ``entry_face``, no exit, proud head,
    module-default tool envelope. Embedment is the half-length rule —
    stamped ``assumption``. ``stack`` names non-driven hardware this same
    contract covers (a hanger installed by its screws)."""
    embedment, notes = _half_length_embedment(screws)
    contract = FastenerInstallation(
        method="driven_straight",
        entry_face=EntryFace(entry_part_id, entry_face),
        tool_axis=ToolAxis("shank"),
        exit=Exit("none"),
        embedment=embedment,
        head="proud",
        tool_envelope=tool_envelope_for("driven_straight"),
    )
    return RoleGroup(
        role=role, fasteners=tuple(s.id for s in screws), contract=contract,
        provenance=default_provenance(embedment=PROVENANCE_ASSUMPTION),
        stack=stack, notes=notes)


def toe_screw_group(role: str, screws, entry_part_id: str) -> RoleGroup:
    """The ``toe_screwed`` default: the type finally says machine-readably
    what its docstring always said — the REAL technique is ANGLED
    (:data:`TOE_SCREW_ANGLE_DEG` off the exposed hung-member face, an
    assumption-grade angle), while today's drawn solids are straight, so the
    axis is flagged ``axis_idealized`` (amendment #3: a display fact
    referencing this contract, never a waiver)."""
    embedment, notes = _half_length_embedment(screws)
    contract = FastenerInstallation(
        method="toe_screw",
        entry_face=EntryFace(entry_part_id, "exposed_face"),
        tool_axis=ToolAxis("angled", angle_deg=TOE_SCREW_ANGLE_DEG,
                           axis_idealized=True),
        exit=Exit("none"),
        embedment=embedment,
        head="proud",
        tool_envelope=tool_envelope_for("toe_screw"),
    )
    return RoleGroup(
        role=role, fasteners=tuple(s.id for s in screws), contract=contract,
        provenance=default_provenance(
            tool_axis=PROVENANCE_ASSUMPTION, embedment=PROVENANCE_ASSUMPTION),
        notes=notes + (
            f"toe-screw tool axis {TOE_SCREW_ANGLE_DEG:g}° off the entry "
            f"face is typical technique (assumption, not manufacturer data); "
            f"drawn solids are straight today — display idealization flagged "
            f"on the contract",))
