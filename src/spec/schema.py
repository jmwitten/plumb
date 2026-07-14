"""The DetailSpec **schema** — the typed, frozen internal model a spec loads
into, and the strict key-checking that turns a raw mapping into it.

The dataclasses here are the real schema (the controller's syntax decision:
typed Python is the model, YAML/JSON is one serialization of it). Each carries
ONLY author-intended facts, per the schema test — a placement is a mate
relationship (datum-on-datum), never a resolved transform; a connection is a
type name + participating part ids, never the bearing/overlap lists it implies
(those the compiler derives, exactly as W2-6's ``Connection`` already does).

Loading is STRICT (the brief's binding requirement): an unknown key is a hard
:class:`~detailgen.spec.values.SpecValueError`-style diagnostic with did-you-mean
suggestions (:func:`_take`), and a missing required key names the field and shows
an example — never a silent default. Every default the loader *does* apply
(an omitted placement is an identity frame; an omitted ``on_datum`` is ``top``)
is a real inference recorded in the derivation log by the compiler, not a
silent fill here.
"""

from __future__ import annotations

import difflib
from dataclasses import InitVar, dataclass, field

# The install-contract closed vocabularies (task INSTALL v1) are owned by the
# leaf contract module — the spec surface names the SAME sets, imported (never
# duplicated) so the two can't drift. ``method`` stays an OPEN tag, like
# ``ProcessStep.kind``.
from ..assemblies.installation import (  # noqa: F401  (re-exported vocabulary)
    EXIT_CONDITIONS as INSTALL_EXIT_CONDITIONS,
    HEAD_CONDITIONS as INSTALL_HEAD_CONDITIONS,
)


class SpecSchemaError(ValueError):
    """A structural problem in a spec mapping: an unknown key, a missing
    required field, or a wrong-shaped value. Message is in the teaching style
    (what was wrong + what is valid / an example)."""


def _take(mapping, known: dict, context: str) -> dict:
    """Validate ``mapping``'s keys against ``known`` (name -> whether required)
    and return a ``{name: value_or_MISSING}`` dict. Unknown key -> hard error
    with did-you-mean; missing required -> hard error naming the field."""
    if not isinstance(mapping, dict):
        raise SpecSchemaError(
            f"{context}: expected a mapping with keys {sorted(known)}, "
            f"got {type(mapping).__name__}"
        )
    for key in mapping:
        if key not in known:
            suggestions = difflib.get_close_matches(str(key), sorted(known), n=3)
            hint = f" — did you mean one of {suggestions}?" if suggestions else ""
            raise SpecSchemaError(
                f"{context}: unknown key {key!r}; allowed keys: "
                f"{sorted(known)}{hint}"
            )
    out = {}
    for name, required in known.items():
        if name in mapping:
            out[name] = mapping[name]
        elif required:
            raise SpecSchemaError(
                f"{context}: missing required key {name!r}; "
                f"required keys: {sorted(k for k, r in known.items() if r)}"
            )
        else:
            out[name] = _MISSING
    return out


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


# -- placement ---------------------------------------------------------------


@dataclass(frozen=True)
class MateSpec:
    """Place a part by making its ``datum`` coincide with the target part's
    datum — the Wave-1 mate API in declarative form. Authoring keys are
    ``datum`` (this part's datum), ``to`` (the target component id), ``to_datum``
    (the target's datum, default ``top``); ``to``/``to_datum`` rather than
    ``on``/``on_datum`` because YAML 1.1 parses a bare ``on`` key as boolean
    ``True``. The remaining freedoms (a standoff ``offset`` along the seat axes,
    a ``rotate`` about the mate normal, a ``flip``) are the same named modifiers
    ``_Mate.on`` accepts; a placement is NEVER a raw transform here. Field names
    below keep ``on``/``on_datum`` to match that mate API."""

    datum: str
    on: str
    on_datum: str = "top"
    offset: tuple = (0.0, 0.0, 0.0)
    rotate: float = 0.0
    flip: bool = False
    # Whether ``on_datum`` was omitted (defaulted to ``top``) — a provenance
    # bookkeeping flag the compiler logs (P1). Excluded from equality so a spec
    # round-trips identically whether or not the serializer re-emits the
    # now-explicit datum (see :mod:`~detailgen.spec.serialize`).
    on_datum_defaulted: bool = field(default=False, compare=False)


@dataclass(frozen=True)
class RawSpec:
    """The raw-transform escape hatch (brief requirement 3): global-axis
    ``rotate`` (a list of ``[axis, degrees]``) then a translate to ``at``, for
    a part positioned off a global measurement rather than a neighbour. Marked
    explicitly (a ``raw:`` block) and logged loudly as an escape-hatch fact —
    it is not a mate and does not pretend to be."""

    at: tuple
    rotate: tuple = ()


#: The world-frame axes a MOUNT standoff / mirror can name. A mount registers a
#: part against a target along ONE of these axes (the mate normal); the closed
#: set keeps the relation a construction semantic, not free geometry.
MOUNT_AXES = ("X", "Y", "Z")

#: Alias -> lumber-style face datum. A mount names the part face by construction
#: role (``inner`` = the face toward the target); the lowering resolves the alias
#: to the component's real datum. An alias that the component does not carry is a
#: teaching error at load, so a typo can never silently pick the wrong face.
MOUNT_FACE_ALIASES = {
    "inner": "face_near",
    "outer": "face_far",
    "top": "top",
    "base": "base",
    "near_end": "end_near",
    "far_end": "end_far",
}


@dataclass(frozen=True)
class MountSpec:
    """Place a part by a **construction RELATION** against a named target, from
    which the compiler derives the full rigid transform — translation *and*
    rotation — plus the contact the relation implies, the dependency edge, the
    placement sentence, and the affected-region edges (CL-1, retro R2/R3). The
    author never writes a coordinate array or a ``rotate`` clause: the rotation
    is *computed from the face pair*, and ``mirror`` derives the opposite-hand
    instance from the one declaration (killing the mirror-negation ``= -…`` twin
    and the hand ``["Z",180]`` spin — the SM3b frame-composition class).

    The relation is a small CLOSED set (owner amendment §11.2: ``flush`` /
      ``offset`` / ``centered`` / ``clear_by`` + ``mirror``, plus ``face`` /
      ``to`` / ``axis`` / ``spin``; the ``ground`` datum relation is the R3
      grounding case, added by the CL-1 fix-round ruling):

    - ``to`` — the target part id; it supplies the reference frame (its ``axis``
      datum, else ``base``) the relation is expressed in.
    - ``face`` — this part's registering face, by construction role
      (:data:`MOUNT_FACE_ALIASES`; e.g. ``inner``). Its outward normal is turned
      to point *at* the target — that is the derived rotation.
    - ``axis`` — the target-frame axis the standoff is measured along (the mate
      normal), one of :data:`MOUNT_AXES`.
    - the STANDOFF, exactly one of: ``flush`` (faces meet over area — from which a
      **bearing** is DERIVED), ``clear_by`` (a gap of this length beyond the
      target surface — a standoff, no contact), or ``offset`` (a signed length
      from the target surface — a standoff, no contact).
    - ``center`` — the target-frame axes (a list) the part's face datum is
      centered on (pins the in-plane translation; e.g. a beam centered on the
      trunk axis).
    - ``ground`` — optional: the R3 grounding relation (cl0-design.md §3.1;
      cl-design-plan verb family 1 "grounding is a relation to the ground
      datum"). A value-language length: the part's ``base`` datum sits this height
      ABOVE the world grade datum (Z=0). Unlike a raw Z coordinate, it DERIVES a
      grounding/elevation fact + evidence edge + doc sentence (the standoff to a
      named datum, exactly like ``clear_by`` is a standoff to the target surface).
    - ``mirror`` — optional axis; derive the opposite-hand instance rigidly.

    (``spin`` — a bare angle about the mate normal — was carried in CL-1 but is
    REMOVED in CL-2 per the CL-1 review ruling: the face-pair already pins all
    three rotational DOF, so ``spin`` derived nothing and shipped unused. It
    failed the owner's one question and is dropped rather than kept as
    low-information geometry sugar; re-add it only paired with the knowledge it
    would derive.)

    All of translation and rotation must be pinned (6 DOF) by the relation — an
    under- or over-constrained mount is a teaching error at semantic-analysis
    time, never a silent guess. This node LOWERS (``detailgen.spec.lowering``)
    into the frozen spec IR before anything downstream runs; assembly/validation/
    evidence/presentation are untouched."""

    to: str
    face: str
    axis: str
    flush: bool = False
    clear_by: object = None      # value-language length, or None
    offset: object = None        # signed value-language length, or None
    center: tuple = ()           # subset of MOUNT_AXES
    ground: object = None        # value-language length (base height above grade), or None
    mirror: str = ""             # "" | one of MOUNT_AXES


#: The FEATURE kinds CL-2 ships. ``clearance_cut`` is the design's named kind
#: (cl0-design.md §3.2, REPLAY A); ``bore`` is the CL-2 addition — a DESIGNED
#: cylindrical recess at an authored location that references NO member (routed
#: through the vocabulary-gap directive: the caddy cup hole is a bore, not a
#: clearance around anything, so mislabeling it ``clearance_cut`` would make the
#: model lie). See ``FeatureSpec``.
#:
#: ``drill`` (the design's third kind, cl0-design §3.2) is DEFERRED, for the same
#: reason CL-1 deferred the trolley legs rather than widen the grammar mid-task:
#: the platform's four ``through_holes`` probes carry a tuned shank clearance
#: (``bolt_dia/2 - 0.01`` inner, ``+ 0.03`` outer) and a hand ``span``, so a thin
#: ``drill: {through, dia, axis}`` cannot reproduce them byte-equal without
#: RE-INTRODUCING those hand numbers — the exact hand-value anti-pattern FEATURE
#: exists to kill. Deriving them honestly needs a shank-FIT rule (inner/outer from
#: a fit class) + a plate-STACKUP derivation (span from the pierced plates'
#: thicknesses) — a rule-pack design (cl0-design §5), not a coordinate-free
#: signature. That is the identified next increment; drill is escalated, not
#: shipped thin.
FEATURE_KINDS = ("clearance_cut", "bore")


@dataclass(frozen=True)
class FeatureSpec:
    """A subtractive FEATURE on a placed component (CL-2, retro R9/R14): the
    author names the feature and the part it concerns *by name*, never by a
    board-local coordinate, and the compiler derives the cut geometry, the
    invariant the feature mandates, the evidence edge, the doc/callout facts, the
    cache-key contribution, the affected-region edges, and the fabrication
    :class:`~detailgen.core.process_graph.ProcessStep` (whose provenance is this
    feature's identity, so the cut note + tooltip finally speak the feature's own
    name). Lowers (``detailgen.spec.lowering.lower_feature``) into today's frozen
    geometry — a pure ``declaration + placed positions -> cut`` expansion.

    Identity (Q3, fab-design §9). ``id`` is the AUTHORED stable key FAB/INCR and
    the cut note key on; ``name`` is the display noun the cut note renders. When
    neither is given, the identity falls back to a CONTENT key derived from the
    declaration (``clearance_cut:<around>``), which is the honest substitute for an
    unnamed interim surface — exactly the residual fab-design §9 disclosed, now
    closable by authoring an ``id``/``name``.

    The two kinds CL-2 ships, each a construction intent (never a raw coordinate):

    - ``clearance_cut`` — fit the part *around* a member (``around``: the member
      id) with a radial ``gap``. The board-local cut center is DERIVED from the
      member's placed position re-expressed in the featured part's frame — the
      world->local negation the author does by hand today (the ``= -…`` twin, R9)
      dies. The rendered noun is the member's own name (``trunk``).
    - ``bore`` — a DESIGNED cylindrical recess of diameter ``dia`` at an authored
      board-local ``at`` center (default: the featured part's center), optionally
      stopping short at ``depth`` (default: through). References no member and
      mandates no clearance invariant — it is a hole the design *wants*, not a
      fit around something. Its noun is the feature's own ``name`` (``cup hole``).

    (``drill`` — the design's third kind — is DEFERRED; see :data:`FEATURE_KINDS`.)
    """

    kind: str
    id: str = ""
    name: str = ""
    # clearance_cut
    around: str = ""
    gap: object = None
    # bore
    at: tuple = ()          # authored board-local center (x, y), or () => part center
    depth: object = None    # value-length; None => through the thickness
    dia: object = None


@dataclass(frozen=True)
class ComponentSpec:
    """One placed part: a spec-local ``id`` (how connections/validation refer
    to it), the display ``name`` (unique within the detail), the constructor
    ``params`` (mapped to kwargs; values in the :mod:`~detailgen.spec.values`
    language), and ``place`` — a mate, a raw escape hatch, or ``None`` (identity
    at the origin, an inferred default logged by the compiler).

    Exactly one of ``type`` / ``imperative`` names the component to build:
    ``type`` resolves a registered component by name (the normal path);
    ``imperative`` is the P3 escape hatch — a dotted path to a Python callable
    ``f(name=..., **params) -> Component`` for geometry the DSL cannot express.
    Its use is logged loudly in the derivation report (P3: imperative code is the
    escape hatch, and every escape is a diagnostic output).

    ``was`` is the OPT-IN revision-rename surface (incr-design.md §3.2): the
    ``id`` this member carried in a PRIOR revision. It is inert to compilation —
    it never affects the built geometry — and exists only so the revision diff
    (:mod:`detailgen.incremental.revision_diff`) reads a re-keyed member as
    ``persisted (renamed)`` instead of ``vanished(old) + appeared(new)``. A
    member never renamed leaves it ``""`` and needs nothing. Whether the named
    old id actually existed (and is now gone) is a diff-time question — it needs
    the prior revision — so it is checked there, not at load."""

    id: str
    type: str = ""
    imperative: str = ""
    name: str = ""
    reader_name: str = ""
    params: dict = field(default_factory=dict)
    place: object = None  # MateSpec | RawSpec | None
    #: subtractive FEATUREs on this part (CL-2) — a tuple of :class:`FeatureSpec`,
    #: resolved AFTER placement (each references other placed parts by name).
    features: tuple = ()
    was: str = ""  # prior-revision id (opt-in rename surface, incr-design §3.2)
    # Whether ``name`` was omitted (defaulted to ``id``) — provenance flag,
    # excluded from equality for the same round-trip reason as
    # ``MateSpec.on_datum_defaulted``.
    name_defaulted: bool = field(default=False, compare=False)


# -- repeat (the one deliberately-deferred language construct) ----------------


@dataclass(frozen=True)
class RepeatSpec:
    """Generate a FAMILY of otherwise-identical entries by iterating a loop
    index. The one language construct the W2-7 review deferred until the
    platform benchmark (124 parts, ~5x the rock anchor's repetition) proved it
    necessary — without it a spec would unroll every joist, deck board, screw
    and bolt into hundreds of near-duplicate blocks (the "Python-as-YAML"
    anti-goal).

    Deliberately MINIMAL: an integer index ``var`` runs ``start`` (default 0)
    up to but not including ``count`` (an int, a ``$param``/``derived`` name, or
    a ``= expr`` — so the COUNT can itself be DERIVED, e.g. ``= n_joists``, and
    the author never writes "3"). The index binds into the value namespace, so a
    ``body`` entry's ``= expr`` placements and its ``{var}`` id/name templates
    resolve per iteration. Bodies may nest (a ``RepeatSpec`` inside ``body``),
    and the SAME node type expands both the components and the connections list.

    It carries NO stride tables, no value lists, no string vars — the mirror
    (+Y/-Y) asymmetry that a value list would encode is authored explicitly and
    left to a future ``SymmetricAbout`` spatial invariant (task SPATIAL). Grow
    the language slowly.
    """

    var: str
    count: object          # int | "$name" | "= expr"
    body: list             # list of ComponentSpec | ConnectionSpec | RepeatSpec
    start: int = 0


# -- connections -------------------------------------------------------------


#: The one completion condition +process v1 can represent. The token records
#: an ordering predicate, never a duration: the selected adhesive label and
#: actual shop conditions determine when it has been reached.
PROCESS_CURE_COMPLETIONS = ("selected_label_full_cure",)


@dataclass(frozen=True)
class CureProcessSpec:
    """An authored refinement of a glued connection's cure process fact.

    ``instructions`` and ``why`` are project/product-selection facts. The
    closed ``completion`` token deliberately represents no generic time.
    Runtime process events remain the ConnectionType's responsibility; this
    schema node is the replayable authoring fact that +process will compile.
    """

    instructions: tuple[str, ...]
    completion: str
    why: str


@dataclass(frozen=True)
class ProcessFactSpec:
    """Connection-local authored process facts.

    V1 has one closed process key, ``cure``. An omitted ``process:`` block is
    this empty value, preserving every existing connection byte-for-byte.
    """

    cure: CureProcessSpec | None = None


#: The finding kinds an ``expect:`` may pin (CL-3, retro R7/R12/R19/R20). A
#: closed set — an expectation names a divergence its OWNING declaration could
#: actually produce, so a typo or an impossible pairing (a ``connection`` pinning
#: a ``through_hole`` it can't emit) is a teaching error at load, not a pin that
#: silently matches nothing. These are exactly the check kinds a Connection's
#: derived closure (bearings, allowlisted interferences, hardware presence) and
#: the shared-member site checks (bond/floating) surface.
EXPECT_CHECKS = ("bearing", "interference", "connection_hardware",
                 "bond", "floating", "dimension")


@dataclass(frozen=True)
class ExpectSpec:
    """An EXPECTED divergence attached to the DECLARATION that owns it (CL-3,
    retro R7/R12/R19/R20) — a *pin* that rides on the connection/mount/feature it
    concerns, never in a global side-file divorced from its subject.

    The author declares the ``check`` kind (one of :data:`EXPECT_CHECKS`), a
    justification ``reason``, and ``count`` — how many findings of that kind on
    this joint the pin owns (default 1). The SUBJECT is IMPLIED by the owning
    declaration (its parts / label), never re-typed — so the pin cannot drift
    from what it pins.

    Coverage is SUBJECT-PRECISE and COUNT-BOUNDED (the CL-3 fix-round tightening,
    review-cl3.md §4): a pin covers only findings whose subject is INTERNAL to its
    own joint (every named part is one of the connection's own parts/hardware, or
    the finding is the joint's own hardware-presence line) — a finding that pulls
    in a foreign part is NEVER absorbed — and it covers at most ``count`` of them.
    A same-kind finding BEYOND ``count`` is NEW and surfaces loudly (the safe
    direction): one more bearing divergence than the pin declared is an
    unexplained divergence, never silently pinned. A ``count`` the joint cannot
    fill (fewer such findings than declared) is an ORPHAN — a teaching error, so a
    pin can never outlive the divergence it described (the R12 orphan-pin /
    24-vs-20 miscount class becomes impossible). When the owning declaration is
    RETIRED, its expectations retire with it (§3.4 field 6) — no orphans left
    behind.

    (Per-kind-per-joint over-cover — one pin silently absorbing every same-kind
    finding on the joint — was the CL-3 round-1 defect; ``count`` + the
    internal-subject predicate is the exact-set discipline the old
    ``site_divergence.json`` had, recovered on the attached form.)"""

    check: str
    reason: str
    count: int = 1


@dataclass(frozen=True)
class InstallSpec:
    """An AUTHORED fastener-installation override attached to the connection
    it refines (task INSTALL v1) — the spec surface of the
    :class:`~detailgen.assemblies.installation.FastenerInstallation`
    contract. Every field is OPTIONAL: an ``install:`` block overrides only
    the fields it names (each stamped ``authored_override`` in the resolved
    contract's per-field provenance, guardrail #7); everything else keeps
    the ConnectionType's default. Authoring keys::

        install:
          method: pocket_screw          # OPEN tag (like ProcessStep.kind)
          entry: {part: rail, face: inner_face}   # member + semantic face
          angle: 15                     # degrees off the entry face (0 = along shank)
          exit: concealed_exit          # one of INSTALL_EXIT_CONDITIONS
          exit_faces: [{part: side, face: outer_face}]  # the declared face-set
          embedment: "= screw_len / 2"  # value-language length, or "through"
          head: recessed_in_pocket      # one of INSTALL_HEAD_CONDITIONS
          tool: {length: 6 in, dia: 1 in}          # the clearance envelope
          stage: own_connection
          role: cleat_screws            # optional role-group targeting

    ``role`` names which of the type's fastener role-groups the override
    targets (omit it to target every group — the natural spelling for the
    single-group types); an unknown role is a teaching error at resolution.
    Value-language fields (``embedment``, ``tool.length``/``tool.dia``) are
    kept RAW here and resolved by the compiler, exactly like connection
    params — so they work inside ``repeat:`` bodies, as does a ``{var}``
    template in ``entry.part``/``exit_faces[].part``."""

    method: str = ""
    entry_part: str = ""
    entry_face: str = ""
    angle: object = None       # degrees off the entry face; None = not overridden
    exit: str = ""             # one of INSTALL_EXIT_CONDITIONS; "" = not overridden
    exit_faces: tuple = ()     # ((part, face), ...) — the declared exit face-set
    embedment: object = None   # value-language length | "through"; None = not overridden
    head: str = ""             # one of INSTALL_HEAD_CONDITIONS; "" = not overridden
    tool_length: object = None  # value-language length (with tool_dia)
    tool_dia: object = None
    stage: str = ""
    role: str = ""


@dataclass(frozen=True)
class ConnectionSpec:
    """A declared Connection (W2-6's central abstraction), by spec-local ids:
    a ``type`` resolved through the connection-types registry with its ``params``
    (kwargs), the ``parts`` it joins and the ordered ``hardware`` stack, the
    ``surfaces`` that carry the joint (part id -> datum name), free-text
    ``assumptions``, and a ``label``. Everything the joint IMPLIES — required
    bearings, allowed intersections, install order, load path — the compiler
    derives from this, never the spec."""

    type: str
    parts: list
    hardware: list = field(default_factory=list)
    params: dict = field(default_factory=dict)
    surfaces: dict = field(default_factory=dict)
    assumptions: list = field(default_factory=list)
    label: str = ""
    #: EXPECTED divergences (CL-3) pinned to THIS connection — a tuple of
    #: :class:`ExpectSpec`. Empty for a connection with no pinned divergence. The
    #: pin's subject is the connection (its label/parts); the compiler derives the
    #: pin accounting and the expected-vs-new classification from where each
    #: expectation is attached, never a global side-set.
    expect: tuple = ()
    #: AUTHORED installation-contract override (task INSTALL v1) — an
    #: :class:`InstallSpec` or ``None``. Unlike ``expect`` (a doc-side pin),
    #: this is COMPILED INTO the built Connection (its ``install`` field), so
    #: the contract is present where ``generate_checks`` resolves it.
    install: object = None
    #: AUTHORED process-fact refinement (+process). This remains typed spec
    #: data in Task 1; Task 2 lowers it onto runtime Connection/process events.
    process: ProcessFactSpec = field(default_factory=ProcessFactSpec)


# -- validation (the escape-hatch checks not yet Connection-owned) -----------


@dataclass(frozen=True)
class ThroughHoleSpec:
    """A fastener-through-hole probe (``check_through_hole``): ``part`` must
    pass cleanly through each of ``passes_through`` along ``axis`` at ``center``,
    its shank (``r_inner``) clearing and an oversized probe (``r_outer``)
    striking every plate over ``span``. Through-hole probes are not yet
    Connection-generated (brief scope), so they stay authored here."""

    part: str
    passes_through: list
    axis: str
    center: list
    r_inner: object
    r_outer: object
    span: object


@dataclass(frozen=True)
class DimensionSpec:
    """A design-intent dimension check: a bounding-box extreme of ``part``
    (``measure`` one of xmin/xmax/ymin/ymax/zmin/zmax, optionally ``negate``d)
    must equal ``expected`` within ``tolerance``. Covers the rock anchor's
    "leg held 1/2\\" above rock" / "rod embedment 8\\"" checks declaratively so
    the spec subsumes the imperative detail's ``extra_checks`` too.

    Two generalizations (task SM3b) grow the language only as far as the tree/
    trolley fragments' own imperative ``extra_checks`` require — no speculative
    features:

    - **cross-part difference** (``minus_part`` + ``minus_measure``): the checked
      value is ``measure(part) - minus_measure(minus_part)`` — a distance between
      two members (the trolley's "grab bar height above deck" = grab-bar ``zmid``
      minus deck-rim ``zmax``; "hanger length" = cable ``zmid`` minus bar
      ``zmid``). A single-part check leaves both ``minus_*`` ``None``.
    - **threshold comparison** (``op``): ``eq`` (default — ``|actual-expected| <=
      tolerance``, the equality check unchanged), or ``ge`` / ``gt`` for a
      one-sided threshold (``actual >= expected`` / ``actual > expected``; the
      tree's "lag embeds in solid trunk wood" is a strict ``>``). A threshold op
      ignores ``tolerance``."""

    name: str
    part: str
    measure: str
    expected: object
    tolerance: object = None
    negate: bool = False
    op: str = "eq"
    minus_part: object = None
    minus_measure: object = None


@dataclass(frozen=True)
class BearingSpec:
    """A design-intent flush-bearing declaration (``check_bearing``): parts
    ``a`` and ``b`` bear on each other along ``axis`` over at least ``area`` mm².
    Unlike the rock anchor's — where every bearing fell out of a declared
    Connection — a real multi-member detail has bearings a connection does NOT
    own (a leg clamped flat to a beam, a joist's end grain on the beam, decking
    resting on joists). Those stay authored here, exactly like ``through_holes``:
    the escape-hatch checks the Construction Graph does not yet generate."""

    a: str
    b: str
    axis: str
    area: object


@dataclass(frozen=True)
class BondSpec:
    """A floating-part connectivity declaration (``check_no_floaters``): parts
    ``a`` and ``b`` are bonded (fastened or in honest tangent contact — mesh to
    rail, deck to trunk, leg to boulder). A bare id-pair; no geometry."""

    a: str
    b: str


@dataclass(frozen=True)
class OverlapSpec:
    """An allowlisted interference (``validate_assembly(expected_overlaps=...)``):
    parts ``a`` and ``b`` are DESIGNED to interpenetrate (a lag threading into
    solid trunk wood, a driven screw in a post, an undersized trolley-wheel bore
    gripping the cable), so their interference is reported PASS, not a collision.
    A bare id-pair; the escape-hatch allowlist the Construction Graph does not yet
    own, exactly like ``bearings``/``bonds``."""

    a: str
    b: str


@dataclass(frozen=True)
class ContactSpec:
    """A per-joint bbox-gap touch check (``check_contact``): parts ``a`` and ``b``
    must touch (coarse bounding-box proof), naming the exact joint rather than a
    whole-assembly floating sweep. The trolley's two disconnected islands prove
    every part's neighbor contact this way. A bare id-pair."""

    a: str
    b: str


@dataclass(frozen=True)
class ValidationSpec:
    ground: object = None  # spec-local id or None
    through_holes: list = field(default_factory=list)
    dimensions: list = field(default_factory=list)
    bearings: list = field(default_factory=list)
    bonds: list = field(default_factory=list)
    expected_overlaps: list = field(default_factory=list)
    contacts: list = field(default_factory=list)


# -- support / stability representation (task SUPPORT) -----------------------

#: The four plan-view edges a walking surface can overhang / cantilever over. A
#: declared_cantilever names one, whitelisting that edge's overhang as intended.
SUPPORT_EDGES = ("+X", "-X", "+Y", "-Y")


@dataclass(frozen=True)
class DeclaredCantilever:
    """An author's explicit declaration that the occupied surface cantilevers
    beyond its supports on ``edge`` (rung 3: this makes the overhang INTENDED,
    so the support check reports it REPRESENTED — never that it is adequate,
    which is rung 4/UNKNOWN). ``note`` is optional provenance."""

    edge: str
    note: str = ""


@dataclass(frozen=True)
class WalkingSurfaceScheme:
    """The support/stability obligation a ``walking_surface`` role generates,
    with the author's declared satisfaction of it (task SUPPORT). Authored as a
    mapping value in the ``roles:`` block:

        deck_0:
          role: walking_surface
          members: [deck_0, ..., deck_5]   # union footprint (default: [key])
          supports: [leg_pY, leg_mY]       # members that carry it to a foundation
          declared_cantilever: [{edge: -X, note: "..."}]   # optional intended overhang
          deferred_support: "tree-end legs deferred"        # optional => FAIL by construction

    Exactly one of ``supports`` / ``deferred_support`` must be present (a
    ``declared_cantilever`` also satisfies the "declare something" obligation) —
    the loader raises a teaching error otherwise. ``key`` is the roles-block cid
    this scheme is declared under; ``label`` is the human name in findings."""

    key: str
    members: tuple[str, ...]
    supports: tuple[str, ...] = ()
    declared_cantilever: tuple[DeclaredCantilever, ...] = ()
    deferred_support: str = ""
    label: str = ""


# -- foundation systems (task FAB-3, retire R29) -----------------------------


@dataclass(frozen=True)
class PostBaseSpec:
    """The post base of a foundation system — the purchased standoff connector
    that holds a post DOWN onto its foundation body (the attachment R29 found
    missing). ``type`` is the component to instantiate (a registered
    :class:`~detailgen.components.concrete.PostBase`, e.g. ``standoff_post_base``);
    ``params`` are its constructor kwargs (value language); ``uplift`` records
    that a rated mechanical connection is DECLARED (never a capacity number).
    ``id`` optionally names the created part (defaults to ``<block>_base``)."""

    type: str
    params: dict = field(default_factory=dict)
    uplift: str = "declared"
    id: str = ""


@dataclass(frozen=True)
class FoundationSpec:
    """One foundation system (task FAB-3): a post BEARING on a foundation body,
    plus the post base that ATTACHES it. Authored in the ``foundations:`` block::

        foundations:
          - label: "pier -Y"
            supports: leg_mY          # the post it carries
            block: pier_mY            # the foundation body (a placed component)
            post_base:                # the attachment — the missing R29 piece
              type: standoff_post_base
              uplift: declared
              params: {width: 3.5 in, length: 3.5 in, height: 2 in}
            bearing_on_grade: field_verify   # honest UNKNOWN, never a number
            frost_depth: 48 in        # optional: enables the embedment check

    ``block``/``supports`` reference components declared earlier; the compiler
    creates + places the ``post_base`` and derives a post->block
    :class:`~detailgen.assemblies.connection.Connection` from this. Everything the
    system's ADEQUACY would require (uplift/lateral/soil capacity) stays UNKNOWN
    by construction — the foundation-role obligation pack reports it. ``type`` is
    an informational block class / product string. A foundation with NO
    ``post_base`` is an explicitly-undesigned attachment (the obligation pack
    FAILs it), never a silent pass."""

    label: str
    supports: str
    block: str
    post_base: object = None  # PostBaseSpec | None
    bearing_on_grade: str = "field_verify"
    frost_depth: object = None  # value-language length, or None
    type: str = ""


# -- spatial intent (task SPATIAL, P6) ---------------------------------------


#: Planned spatial vocabulary reserved by NAME only (adopted middle path): a
#: real invariant is committed one motivating bug at a time, so these are
#: documented and produce a teaching error — never a parse-and-noop stub, which
#: would be a FAKE invariant (a CLEAN report implying a proof that never ran).
RESERVED_SPATIAL_NAMES = ("parallel", "perpendicular", "aligned_with")

#: The spatial invariants that ARE provable today — named in the teaching error
#: so an author learns the current vocabulary at the point of the mistake.
PROVABLE_SPATIAL_NAMES = ("symmetric_about", "faces_toward", "faces_away")


def reserved_spatial_error(name: str) -> str:
    """The teaching-error text for a reserved spatial name — the verbatim style
    adopted in the SPATIAL design block: what is reserved AND what is currently
    provable, so the author can act."""
    return (
        f"spatial invariant {name!r} is reserved for the spatial layer, not yet "
        f"provable; currently provable: {', '.join(PROVABLE_SPATIAL_NAMES)}"
    )


@dataclass(frozen=True)
class SymmetricSpec:
    """A declared mirror symmetry (``symmetric_about``): the pairs must be
    mirror images about ``plane`` (``XY``/``YZ``/``XZ``). Supply pairs as
    explicit ``pairs`` (``[[a, b], ...]`` spec-local ids) and/or a ``mirror``
    name-substitution selector ``[plus, minus]`` (e.g. ``["+Y", "-Y"]``) that
    discovers every part pair whose display names differ only by that
    substitution — the RAILFIX +Y/-Y audit as a reusable selector. ``tol`` (a
    length) overrides the default AABB-reflection tolerance."""

    plane: str
    pairs: tuple = ()
    mirror: object = None  # (plus, minus) or None
    tol: object = None


@dataclass(frozen=True)
class FacesSpec:
    """A declared facing (``faces_toward`` / ``faces_away``): ``part``'s facing
    — a world axis (``facing``) or a body-fixed datum's world +Z
    (``facing_datum``) — must point ``sense`` (``toward``/``away``) a target
    part (``target``, a spec-local id) or a world direction (``target_dir``).
    ``tol`` is the signed-projection margin about zero."""

    part: str
    sense: str  # "toward" | "away"
    facing: object = None       # (x, y, z) world axis, or None
    facing_datum: object = None  # datum name, or None
    target: object = None       # spec-local id, or None
    target_dir: object = None   # (x, y, z) world direction, or None
    tol: object = None


@dataclass(frozen=True)
class SpatialSpec:
    """The whole ``spatial:`` block: declared spatial-intent invariants
    (:class:`SymmetricSpec`, :class:`FacesSpec`). Empty when a detail declares
    none — the compiler then adds no ``spatial`` checks and the coverage
    matrix's Spatial-intent family stays UNKNOWN (honest, not fabricated)."""

    symmetric: tuple = ()
    faces: tuple = ()


# -- presentation surfaces (task 4B-2) ---------------------------------------
# The five capabilities the four ``.py`` details carried that the spec language
# could not yet express: param-derived dimension callouts, per-part explode
# vectors, the report prose, an escape-hatch cross-check, and GLB/manifest
# export. Each is authored intent (AD#4/#5): a callout endpoint or a prose value
# is written in the VALUE LANGUAGE, so a re-sized family moves its callouts and a
# param cited in prose can never drift from the geometry it annotates.


@dataclass(frozen=True)
class CalloutSpec:
    """A param-derived dimension callout (compiles to a
    :class:`~detailgen.details.base.Callout`): ``param`` names the field the
    label reports, ``label`` is a ``{v}`` template, and ``p0``/``p1`` are the two
    endpoints as value-language ``[x, y, z]`` triples (each coord a length —
    a bare number is mm, a ``$name``/``= expr``/``"n in"`` a directive), so the
    endpoints track a re-sized detail exactly as the ``.py`` Callout's callable
    endpoints do. The value formatter is architectural fractional inches (the
    only one the four details use), not authored here."""

    param: str
    label: str
    p0: tuple
    p1: tuple


@dataclass(frozen=True)
class ExplodeSpec:
    """One part's exploded-view offset: a spec-local component ``id`` and a
    value-language ``vector`` ``[x, y, z]``. ``SpecDetail.explode_vectors()``
    maps each id to its display NAME (the key the viewer/manifest use), exactly
    as the ``.py`` details' hand-built name-keyed dict does."""

    id: str
    vector: tuple


@dataclass(frozen=True)
class CrossCheckSpec:
    """The independent constraint-solver cross-check as an escape-hatch
    REFERENCE (not a new DSL): ``ref`` is a dotted path to a callable
    ``f(detail) -> dict``, resolved and called exactly like a
    :class:`ComponentSpec` ``imperative`` hook — an authored escape from the
    declarative language, logged loudly in the derivation report."""

    ref: str


@dataclass(frozen=True)
class ExportSpec:
    """CAD-artifact export knobs: the GLB mesh tolerances (``glb_tolerance`` /
    ``glb_angular_tolerance``, the two per-detail values the ``.py`` ``_export``
    passed) and whether to merge explode vectors into the manifest parts
    (``inject_explode``). A ``export:`` block switches ``SpecDetail`` from the
    base single-STEP default to the STEP + GLB + manifest output the details
    produce; its step file is ``<slug(name)>.step`` (the base convention, which
    already reproduces every detail's filename)."""

    glb_tolerance: float
    glb_angular_tolerance: float
    inject_explode: bool = False
    # The trolley authored its explode vectors in authoring units (inches) and
    # multiplied by the unit factor at injection; the rock/tree details authored
    # them already in internal mm. This flag reproduces that per-detail choice so
    # BOTH ``explode_vectors()`` (raw) and the injected manifest are byte-equal.
    explode_authoring_units: bool = False


# -- doc / report prose ------------------------------------------------------
# The report is an ORDERED list of sections. Authored prose (title, architect
# notes, assumptions, field-verify text) is a ``prose`` section whose ``{token}``
# interpolations resolve through the value language + a small report-context
# namespace; the computed sections (findings loops, sampled derivation log,
# sampled hardware presence, the BOM table) are named section kinds the shared
# renderer fills from the live model. Adjacent sections are joined by exactly one
# blank line (the uniform spacing every ``.py`` report already uses).


@dataclass(frozen=True)
class ProseSection:
    """Authored prose: ``text`` (multi-line) carried verbatim except for
    ``{expr}`` / ``{expr:fmt}`` interpolation tokens — a value-language
    expression over params/derived (a cited param can't drift) or a
    report-context name (a finding count, the result verdict, a cross-check
    value). A bare token with no ``:fmt`` renders an integral value as an int."""

    text: str


#: The closed vocabulary of Finding ``check`` kinds a ``doc`` ``findings:``
#: section may filter on — the invariant + provenance kinds a Finding carries
#: (mirrors ``detailgen.validation.coverage.KIND_TO_FAMILY`` plus the
#: ``connection_override`` marker). A findings section names exactly ONE, so an
#: unknown name is a typo that would SILENTLY render an empty section — the
#: loader rejects it with a did-you-mean, in the same closed-enum style as a
#: dimension ``op`` or a spatial ``sense``. Kept here with the schema's other
#: vocabularies rather than importing the validation layer into the loader.
RENDERABLE_CHECK_KINDS = (
    "interference", "dimension", "bearing", "through_hole", "floating",
    "contact", "connection_hardware", "parameters", "symmetric_about",
    "faces_toward", "faces_away", "load_path", "connection_override",
    # INSTALL (task INSTALL): the installability kinds are renderable in a
    # ``findings:`` section but deliberately NOT in EXPECT_CHECKS — an
    # installability FAIL must not be pinnable/silenceable from a spec.
    "install_method", "install_termination", "install_access",
)


@dataclass(frozen=True)
class FindingsSection:
    """A findings loop: ``header`` then one ``- PASS/FAIL <subject> — <detail>``
    line per finding whose ``check`` matches (one of
    :data:`RENDERABLE_CHECK_KINDS` — e.g. ``bearing`` / ``through_hole`` /
    ``floating`` / ``contact`` / ``dimension`` / ``connection_hardware``)."""

    header: str
    check: str


@dataclass(frozen=True)
class DerivationLogSection:
    """The Construction-Graph derivation-log sample: ``header`` + interpolated
    ``preamble`` + a ``**N facts derived** from **M declared Connections**``
    summary + sampled facts. ``mode`` is ``first_n`` (the first ``cap`` facts,
    then ``...and K more.``) or ``per_connection`` (up to ``cap`` per source
    connection, then ``...and K more facts for '<label>'.``)."""

    header: str
    preamble: str
    mode: str = "first_n"
    cap: int = 8


@dataclass(frozen=True)
class HardwarePresenceSection:
    """Connection-hardware-presence findings sampled PER CONNECTION LABEL (the
    ``<label>: <part>`` subject prefix): ``header`` then up to ``cap`` lines per
    label (then ``...and K more for '<label>' (all <word>).``), then a
    ``**N hardware-presence checks** across **M declared Connections**`` summary
    — so one busy joint can't crowd every other out of the document."""

    header: str
    cap: int = 2


@dataclass(frozen=True)
class BomTableSection:
    """The bill-of-materials markdown table: ``header``, a blank line, the fixed
    ``| Qty | Item | ... |`` header rows, then one row per ``bom_table()`` entry."""

    header: str


@dataclass(frozen=True)
class DocSpec:
    """The whole ``doc:`` block: the output ``report`` filename and the ordered
    ``sections``. Empty (the base default) writes no report."""

    report: str = "validation_report.md"
    sections: tuple = ()


# -- retirement (CL-3, retro R10) --------------------------------------------

#: What a ``retire:`` record may name. A ``connection`` (by label) drops the
#: joint and its ENTIRE derived closure — the bearings, allowlisted
#: interferences, hardware-presence findings, evidence edges, and attached
#: expectations it owned — automatically, because every one of those facts is
#: DERIVED from the connection (ownership is complete), so deletion IS the edit.
#: A ``member`` (by component id) drops a placed part, but only if nothing
#: surviving still references it (else a teaching error lists the dependents).
RETIRE_KINDS = ("connection", "member")


@dataclass(frozen=True)
class RetireSpec:
    """An INTENTIONAL removal with provenance (CL-3, retro R10). Retirement was
    not a language operation: making the platform free-standing (TREEFREE) meant
    hand-unwinding ~9 files — the connection, its bearings/bonds/through-holes,
    the pinned-divergence set, the report prose, the test goldens, the evidence
    edges. ``retire:`` records the removal and its ``reason``, and the compiler
    unwinds the retired declaration's whole derived closure by construction
    (fields 2/3/5/6 of the owning verb's derivation table are all owned by it).

    ``kind`` is one of :data:`RETIRE_KINDS`; ``target`` is the connection LABEL or
    the member id; ``reason`` is the audit trail (WHY — the knowledge silent
    deletion would lose). Retiring a connection is always safe (its closure is
    owned); retiring a member still referenced by a surviving declaration is a
    teaching error naming the dependents — the author retires or re-points them
    explicitly, never leaving a check validating against a part that is gone."""

    kind: str
    target: str
    reason: str


# -- sequence (task SEQSCHEMA, stepdoc-cpg-design.md §3.1 family 3) ----------

#: The staging vocabulary itself is closed: a whole detail is either built
#: apart and set onto its context, or explicitly built in place. Undeclared
#: context is neither — it remains UNORDERED. ``after:`` is the orthogonal
#: +process point-constraint surface, represented by :class:`AuthoredAfter`.
ASSEMBLY_MODES = ("bench_then_set", "in_situ")


@dataclass(frozen=True)
class AuthoredStage:
    """One named stage of a spec-level ``sequence:`` block — a REPRESENTED-
    rung authored order claim: "the listed connections/parts happen in this
    named group, and this group's position among the detail's other stages
    IS its position in the build." This is the ``authored_sequence`` edge
    family (design §3.1 item 3): declared order where the model doesn't
    derive one, e.g. the caddy's *side screws after the rail-glue cure*, the
    platform's *toe screws before the leg bolts*.

    Vocabulary discipline (owner amendment 5, BINDING): "stage" is the
    AUTHORED SEQUENCE GROUPING declared here — never the reader-facing
    presentation unit (a "step"), which is a different, later type. The two
    names must never be used interchangeably in code, spec surface, docs, or
    error messages.

    ``connections`` name existing connection labels; ``parts`` name existing
    component authored ids — both checked against the rest of the loaded doc
    by :func:`~detailgen.spec.semantics.analyze_sequence` (the loader builds
    one stage in isolation and has no view of the doc's other declarations,
    exactly like ``retire:``'s target-existence check). At least one of the
    two must be non-empty: a stage naming nothing claims no order over
    anything.

    ``why`` is REQUIRED, non-empty free text — the authored-embedment-
    override precedent applied to order claims: an order claim ships with
    its defense, never a bare assertion.

    Stages are TOTALLY ORDERED by their declaration position in
    ``SequenceSpec.stages`` — that tuple position IS the order; there is no
    separate index field to drift from it."""

    name: str
    why: str
    connections: tuple = ()
    parts: tuple = ()


@dataclass(frozen=True)
class AuthoredSubassembly:
    """One named unit assembled in its own bench frame before it joins root.

    ``parts`` are authored component ids. A part may belong to at most one
    unit (loader-enforced and defended again after compile); nesting is not a
    v1 feature. ``why`` is the provenance of the staging claim and is required
    anywhere the claim is authored or rendered.
    """

    name: str
    why: str
    parts: tuple = ()


@dataclass(frozen=True)
class AuthoredAssembly:
    """Whole-detail staging sugar or its explicit in-place mirror.

    ``bench_then_set`` normalizes to one unit containing every constructed
    (non-context) part. ``in_situ`` creates no bench unit and explicitly makes
    context present from the root build. The mapping form is deliberate: a
    scalar could not carry the mandatory ``why`` without an ambiguous loose
    field on the enclosing sequence block.
    """

    mode: str
    why: str


@dataclass(frozen=True)
class AuthoredProcessRef:
    """One typed process prerequisite named by a point constraint.

    ``kind`` is closed to ``cure`` by the loader in v1; ``connection`` is the
    source connection's authored label. A typed node keeps labels verbatim and
    avoids parsing a string mini-language such as ``cure(label)``.
    """

    kind: str
    connection: str


@dataclass(frozen=True)
class AuthoredAfter:
    """A target connection constrained after one or more process facts.

    The target and sources remain authored labels here. The compiler resolves
    each to exactly one built connection; repeat ambiguity is loud in v1.
    """

    connection: str
    after: tuple[AuthoredProcessRef, ...]
    why: str


@dataclass(frozen=True)
class SequenceSpec:
    """A detail spec's authored construction-order and staging claims.

    ``stages`` are authored order groups. ``subassemblies`` and ``assembly``
    are the unified +staging surface: explicit named units, or whole-detail
    sugar / in-place mirror. A sequence block may carry either kind alone;
    an entirely absent block is the empty default below. ``after`` carries
    typed point constraints from a process fact to a target connection. Each
    claim carries ``why`` provenance and is resolved only at compile time,
    beside stages and staging.
    """

    stages: tuple = ()
    subassemblies: tuple = ()
    assembly: AuthoredAssembly | None = None
    after: tuple[AuthoredAfter, ...] = ()


# -- the whole document ------------------------------------------------------


@dataclass(frozen=True)
class DesignReviewSpec:
    """Opt-in binding from a production DetailSpec to its design review."""

    record: str
    selected_concept: str


@dataclass(frozen=True)
class DetailSpecDoc:
    """A whole DetailSpec: metadata, the param/derived dimension blocks, the
    placed components, the declared connections, and the escape-hatch
    validation. This is what a loader produces and the compiler consumes."""

    name: str
    type: str = "detail"
    units: str = "in"
    params: dict = field(default_factory=dict)
    derived: dict = field(default_factory=dict)
    components: list = field(default_factory=list)
    connections: list = field(default_factory=list)
    validation: ValidationSpec = field(default_factory=ValidationSpec)
    spatial: SpatialSpec = field(default_factory=SpatialSpec)
    # -- ONTOLOGY (task ONTOLOGY): role declarations ---------------------------
    # Author intent: the load-system Role of a part (support / connector /
    # ground — :mod:`detailgen.core.ontology`), by spec-local component id, the
    # SAME id space connections/validation use. Everything the roles IMPLY (the
    # load-path REPRESENTATION) the compiler derives; this block only declares
    # what each part IS. Empty for a detail that declares no roles (its Load-path
    # family then honestly stays UNKNOWN). Kept in its OWN field + loader/
    # serializer section, disjoint from the SPATIAL spec block, to ease the merge.
    roles: dict = field(default_factory=dict)
    # -- SUPPORT (task SUPPORT): occupied-surface support/stability obligations -
    # Structured schemes for ``walking_surface`` roles, keyed by the same cid as
    # the ``roles`` entry (whose flat value is then "walking_surface"). Authored
    # inside the ``roles:`` block; split out here so the load-path helper sees a
    # plain id->role map while the support check sees typed schemes. Empty for a
    # detail with no walking surface (its Support/Stability family stays UNKNOWN).
    support_schemes: dict = field(default_factory=dict)
    # -- FAB-3 (retire R29): foundation systems --------------------------------
    # A post bearing on a foundation body, plus the post base attaching it. The
    # compiler creates+places each post base, derives a post->block Connection,
    # and the foundation-role obligation pack (attachment / embedment / capacity)
    # reports on them. Empty for a detail with no foundation system (its
    # foundation obligations then simply don't run — no fabricated coverage).
    foundations: tuple = ()
    # -- CTXGROUND (task CTXGROUND): pre-existing self-grounded site bodies -----
    # cids declared ``role: existing`` + ``grounded_by: site`` — grounded
    # earth-side, exempt from the constructed-connectivity floating check. Empty
    # unless a detail declares a context body it grounds by the site.
    context_grounds: frozenset = frozenset()
    # -- presentation surfaces (task 4B-2) -------------------------------------
    # The five capabilities the imperative details carried beyond the declarative
    # lifecycle. Each is empty for a detail that declares none, so a spec without
    # a presentation block round-trips and compiles exactly as before.
    callouts: tuple = ()
    explode: tuple = ()
    doc: DocSpec = field(default_factory=DocSpec)
    cross_check: object = None  # CrossCheckSpec | None
    export: object = None       # ExportSpec | None
    # -- RETIRE (task CL-3, retro R10): intentional removals with provenance ----
    # A tuple of :class:`RetireSpec`. Each names a connection (by label) or a
    # member (by id) that is retired, with the reason. The compiler applies these
    # BEFORE expanding connections, so a retired connection's whole derived
    # closure (bearings/interferences/hardware/edges + attached expectations)
    # simply never generates — deletion is the edit. Empty for a detail that
    # retires nothing, so a retire-free spec round-trips and compiles unchanged.
    retire: tuple = ()
    # -- SEQSCHEMA (task SEQSCHEMA): the authored ``sequence:`` block -----------
    # A :class:`SequenceSpec` of named, totally-ordered stages (design
    # §3.1's ``authored_sequence`` family). Defaults empty for a detail that
    # declares no sequence, so a sequence-free spec round-trips and compiles
    # unchanged. Plumbing only here — no event graph, no axis-3 semantics;
    # this is the parsed+validated authoring surface the next task consumes.
    sequence: SequenceSpec = field(default_factory=SequenceSpec)
    # Optional pre-model design-selection governance. ``InitVar`` keeps the new
    # binding out of legacy dataclass/asdict projections; ``__post_init__``
    # retains the typed value for the compiler and explicit serializer.
    design_review: InitVar[DesignReviewSpec | None] = None
    # Whether ``units`` was omitted (defaulted to ``in``) — a provenance flag the
    # compiler records as an inferred fact (P1: a silent default that scales
    # every length 25.4x is exactly the kind of assumption the log must surface).
    # Excluded from equality so a spec round-trips identically either way.
    units_defaulted: bool = field(default=False, compare=False)

    def __post_init__(self, design_review: DesignReviewSpec | None) -> None:
        object.__setattr__(self, "design_review", design_review)
