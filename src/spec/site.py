"""SITEMODEL (task SM1 SITECORE): compile a ``kind: site`` document into ONE
validated :class:`~detailgen.details.base.Detail` composed from spec fragments.

The north star (progress.md ADOPTED DIRECTION #1): one compiled site model
always exists; a member referenced by two subsystems is ONE node in the
Construction Graph, so cross-subsystem disagreement is UNREPRESENTABLE. This is
the same move as computed-placement and Connections — make the bug inexpressible,
don't detect it.

What this module adds on top of the existing spec system (no second dialect):

- **A fragment IS a DetailSpecDoc.** ``details/platform.spec.yaml`` and
  ``details/rock_anchor.spec.yaml`` load with the unchanged loader and still
  compile standalone byte-identically. In-site they are re-hosted, not
  re-parsed: each fragment compiles to its own :class:`SpecDetail`, is built once
  for its geometry, then its parts are re-placed into ONE shared
  :class:`~detailgen.assemblies.assembly.DetailAssembly` under the subsystem's
  declared placement, and its ``_by_id`` map is rewritten to the SITE parts so
  every connection / validation / spatial / role it declares resolves against
  the site's Placed objects.

- **Namespaced identity.** A fragment's spec-local component id ``cid`` becomes
  the qualified site id ``<subsystem_id>/<cid>``; its display name becomes
  ``<subsystem_id>/<name>`` (the uniquifying rule — a subsystem's own names are
  already unique, so the prefix makes them unique across the one assembly).

- **Shared members = single node (``bind:``).** A component that models only a
  PORTION of another subsystem's member (``component.stub_of()`` is not None —
  today the rock-anchor leg stub, whose full run is the platform's launch leg)
  is NOT instantiated in-site. Its qualified id resolves — by identity, an
  ``is`` — to the real member's Placed object, so every reference to it (mates,
  connections, bearings, bonds, dimensions, roles) checks the REAL geometry.
  That is the single-node guarantee: there is no second copy to diverge.

- **Context-body dedup (``dedup:``).** A subsystem may carry a CONTEXT copy of a
  physical feature another subsystem models for real (the platform's bare
  context boulder vs the rock anchor's real boulder with the epoxy rod holes and
  the load path). Declared ``dedup: {drop, keep}`` retires the context copy and
  redirects references to the real member — the same single-node discipline for
  a feature that is not a partial-member stub.

The placement escape hatch is honest and declared (like a part ``raw:``): a
subsystem ``place:`` is identity or a raw transform whose numbers are the OWNING
fragment's own dimensions, referenced by QUALIFIED name (``= platform.leg_station``)
so a site placement can never hardcode a number a fragment already owns — the
drift class this phase kills.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from ..assemblies.assembly import DetailAssembly, Placed, SpecReferenceError
from ..assemblies.connection import Connection, DerivedFact
from ..core import IN
from ..core.config import DEFAULT
from ..core.frame import Frame
from ..details.base import Detail
from ..validation import Finding, check_dimension, dimension_subject
from .compiler import _BBOX_MEASURES, SpecCompileError, SpecDetail, compile_spec
from .loader import (
    _as_list,
    _build_connection,
    _build_placement,
    _build_spatial,
    _build_validation,
    _default,
    load_spec_file,
)
from .schema import (
    ConnectionSpec,
    MateSpec,
    RawSpec,
    SpatialSpec,
    SpecSchemaError,
    ValidationSpec,
    _MISSING,
    _take,
)
from .values import UNIT_FACTORS, Resolver, SpecValueError

def _is_context_body(component) -> bool:
    """Whether a component is an EXISTING/CONTEXT body (a natural feature or
    other pre-existing element, not a purchased/structural member). The same
    predicate ``scripts/_site_overview.is_existing`` applies to a BOM row,
    inlined here (not imported — ``scripts/`` is off-limits) so ``dedup:`` can
    only retire a context body, never a real structural part. A boulder reads
    ``source='generated'`` but carries an ``(existing)`` label; a purchased part
    (bolt, angle, lumber) is neither."""
    source = getattr(component, "source", "generated")
    return source != "generated" or "(existing)" in component.bom_label()


_AXIS_LETTERS = ("X", "Y", "Z")
_AXIS_VECS = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}


def _remap_axis(axis: str, rotate: list) -> str:
    """Map a fragment-frame axis LETTER (a ``bearing`` / ``through_hole`` axis,
    consumed as a WORLD-frame direction by the checks — ``_AXV[axis]``, checks.py)
    to the world axis it lands on under a subsystem's right-angle ``rotate``. A
    bearing's face-push and a through-hole's probe cylinder are symmetric in the
    push SIGN, so only the axis letter (not its sense) matters. Under no rotation
    the letter is returned unchanged (byte-identical to SM1's pure-translation
    subsystems)."""
    if not rotate:
        return axis
    letter = axis.upper()
    if letter not in _AXIS_VECS:
        return axis
    frame = Frame.from_at_rotate((0.0, 0.0, 0.0), rotate)
    d = frame.transform_direction(_AXIS_VECS[letter])
    dominant = max(range(3), key=lambda i: abs(d[i]))
    return _AXIS_LETTERS[dominant]


#: Confidence a subsystem placement carries as a provenance fact (brief req 1):
#: EXACT (field-verified / identity) or ASSUMED (derived from stated conventions,
#: not independently verified — the placement table's honest caveat, promoted
#: into a declared model fact).
_CONFIDENCES = ("EXACT", "ASSUMED")


# --------------------------------------------------------------------------- #
# Schema — the site document (a sibling of DetailSpecDoc, not a rewrite).
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SubsystemRef:
    """One entry in a site's ``subsystems:`` list: a fragment reference placed
    into the site frame with declared provenance.

    - ``id``: the spec-local subsystem id; the namespace prefix for every part
      the fragment contributes (``<id>/<cid>``).
    - ``fragment``: path to the fragment spec, relative to the site document.
    - ``place``: identity (``None``) or a :class:`RawSpec` transform — same
      vocabulary as component placement, a declared escape hatch with
      provenance, never a solver. Its values may reference any fragment's
      params/derived by QUALIFIED name (``= platform.leg_station``).
    - ``basis`` / ``confidence``: the placement table's basis text and
      EXACT/ASSUMED confidence, carried as provenance facts.
    - ``bind``: ``{stub_cid: <subsystem_id>/<cid>}`` — retire a partial-member
      stub and resolve it to the real member (req 3).
    """

    id: str
    fragment: str
    place: object = None  # RawSpec | None (identity)
    basis: str = ""
    confidence: str = ""
    bind: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DedupRef:
    """A declared context-body dedup: the qualified ``drop`` id is a CONTEXT
    copy of the same physical feature the qualified ``keep`` id models for real;
    in-site the ``drop`` body is not instantiated and every reference to it
    resolves to ``keep`` (single node). ``basis`` records why they are the same
    physical feature (provenance)."""

    drop: str
    keep: str
    basis: str = ""


@dataclass(frozen=True)
class SiteSpecDoc:
    """A whole site document: the composed subsystems, the context-body dedups,
    and the site-level cross-subsystem intent blocks (connections / validation /
    spatial) whose ids are QUALIFIED (``<subsystem_id>/<cid>``). A sibling of
    :class:`~detailgen.spec.schema.DetailSpecDoc`; the same loader strictness and
    teaching-error culture apply."""

    name: str
    kind: str = "site"
    units: str = "in"
    subsystems: tuple = ()
    dedup: tuple = ()
    connections: list = field(default_factory=list)
    validation: ValidationSpec = field(default_factory=ValidationSpec)
    spatial: SpatialSpec = field(default_factory=SpatialSpec)
    ground: object = None  # site-wide connectivity terminal (one ground)
    views: tuple = ()  # SM2 VIEWS: named scope selectors over the one model
    units_defaulted: bool = field(default=False, compare=False)


# --------------------------------------------------------------------------- #
# Loader — strict, same _take / did-you-mean culture as the rest of src/spec.
# --------------------------------------------------------------------------- #
def is_site_document(raw: dict) -> bool:
    """True if a parsed mapping is a site document (``kind: site``). Used by a
    polymorphic caller that may be handed either a detail or a site spec."""
    return isinstance(raw, dict) and raw.get("kind") == "site"


def load_site_text(text: str, *, fmt: str = "yaml") -> SiteSpecDoc:
    """Parse site-document ``text`` (``fmt`` = ``"yaml"`` or ``"json"``) into a
    :class:`SiteSpecDoc` — the same structural path as :func:`load_site_file`,
    without a file (used by tests that build a document inline)."""
    import json

    import yaml

    raw = json.loads(text) if fmt == "json" else yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"a site document must be a mapping at top level, got "
            f"{type(raw).__name__}")
    return _build_site_doc(raw)


def load_site_file(path: str | Path) -> SiteSpecDoc:
    """Load a site document from YAML/JSON into :class:`SiteSpecDoc`."""
    import json

    import yaml

    path = Path(path)
    text = path.read_text()
    raw = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"a site document must be a mapping at top level, got "
            f"{type(raw).__name__}"
        )
    return _build_site_doc(raw)


def _build_site_doc(raw: dict) -> SiteSpecDoc:
    f = _take(raw, {
        "name": True, "kind": True, "units": False,
        "subsystems": True, "dedup": False,
        "connections": False, "validation": False, "spatial": False,
        "ground": False,
        "views": False,  # SM2 VIEWS
    }, "site spec")
    if f["kind"] != "site":
        raise SpecSchemaError(
            f"site spec: 'kind' must be 'site', got {f['kind']!r}")
    subs = tuple(_build_subsystem(s, i)
                 for i, s in enumerate(_as_list(f["subsystems"], "subsystems")))
    if not subs:
        raise SpecSchemaError(
            "site spec: 'subsystems' must list at least one fragment reference")
    dedup = () if f["dedup"] is _MISSING else tuple(
        _build_dedup(d, i) for i, d in enumerate(_as_list(f["dedup"], "dedup")))
    connections = ([] if f["connections"] is _MISSING
                   else [_build_connection(c, i)
                         for i, c in enumerate(_as_list(f["connections"], "connections"))])
    validation = (ValidationSpec() if f["validation"] is _MISSING
                  else _build_validation(f["validation"]))
    spatial = (SpatialSpec() if f["spatial"] is _MISSING
               else _build_spatial(f["spatial"]))
    # --- SM2 VIEWS: parse the views: block (view layer lives in views.py) ----
    from .views import build_views
    views = () if f["views"] is _MISSING else build_views(f["views"])
    return SiteSpecDoc(
        name=f["name"], kind="site",
        units=_default(f["units"], "in"),
        units_defaulted=f["units"] is _MISSING,
        subsystems=subs, dedup=dedup,
        connections=connections, validation=validation, spatial=spatial,
        ground=None if f["ground"] is _MISSING else f["ground"],
        views=views,
    )


def _build_subsystem(raw: dict, index: int) -> SubsystemRef:
    ctx = f"subsystems[{index}]"
    f = _take(raw, {
        "id": True, "fragment": True, "place": False,
        "basis": False, "confidence": False, "bind": False,
    }, ctx)
    place = None
    if f["place"] is not _MISSING and f["place"] != "identity":
        place = _build_placement(f["place"], f"{ctx} ({f['id']!r}) place")
        if isinstance(place, MateSpec):
            raise SpecSchemaError(
                f"{ctx} ({f['id']!r}): a subsystem 'place' is 'identity' or a "
                f"'raw:' transform (a declared placement with provenance), not a "
                f"datum mate onto another subsystem")
    confidence = "" if f["confidence"] is _MISSING else str(f["confidence"])
    if confidence and confidence not in _CONFIDENCES:
        raise SpecSchemaError(
            f"{ctx} ({f['id']!r}): 'confidence' must be one of "
            f"{list(_CONFIDENCES)}, got {confidence!r}")
    bind = {}
    if f["bind"] is not _MISSING:
        if not isinstance(f["bind"], dict):
            raise SpecSchemaError(
                f"{ctx} bind: expected a mapping of stub_cid -> "
                f"'<subsystem>/<cid>', got {type(f['bind']).__name__}")
        for k, v in f["bind"].items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise SpecSchemaError(
                    f"{ctx} bind: each entry is 'stub_cid: <subsystem>/<cid>' "
                    f"(both strings), got {k!r}: {v!r}")
            bind[k] = v
    return SubsystemRef(
        id=f["id"], fragment=f["fragment"], place=place,
        basis=_default(f["basis"], ""), confidence=confidence, bind=bind)


def _build_dedup(raw: dict, index: int) -> DedupRef:
    ctx = f"dedup[{index}]"
    f = _take(raw, {"drop": True, "keep": True, "basis": False}, ctx)
    return DedupRef(drop=f["drop"], keep=f["keep"], basis=_default(f["basis"], ""))


# --------------------------------------------------------------------------- #
# Compiler — SiteDetail: one Detail, one assembly, one validation sweep.
# --------------------------------------------------------------------------- #
class SiteDetail(Detail):
    """A :class:`~detailgen.details.base.Detail` whose lifecycle is driven by a
    :class:`SiteSpecDoc`: it composes each subsystem fragment into ONE
    DetailAssembly and REPLAYS every fragment's connections / validation /
    spatial / roles onto that one assembly with namespaced, single-node
    identity. Because it is a ``Detail``, ``validate`` / ``require_clean`` / the
    gated ``render`` / the BOM all work unchanged — the site is a detail."""

    Params = SpecDetail.Params  # the empty stand-in; the doc is the source of truth

    def __init__(self, doc: SiteSpecDoc, base_dir: str | Path):
        if doc.units not in UNIT_FACTORS:
            raise SpecCompileError(
                f"unknown authoring unit {doc.units!r}; known: "
                f"{sorted(UNIT_FACTORS)}")
        self.doc = doc
        self.base_dir = Path(base_dir)
        self.unit = doc.units
        self.name = doc.name
        # Detail state (driven directly, as SpecDetail does — no Python Params).
        self.params = None
        self._assembly = None
        self._report = None
        self._derivation_log = []
        self._connection_edges = []
        self._connection_checks = None
        self._evidence_graph = None
        self._by_id: dict[str, Placed] = {}
        self._site_log: list[DerivedFact] = []

        self._sub_by_id = {sub.id: sub for sub in doc.subsystems}

        # -- load + compile each fragment (a fragment IS a DetailSpecDoc) --------
        self._frags: dict[str, SpecDetail] = {}
        self._order: list[str] = []
        for sub in doc.subsystems:
            if sub.id in self._frags:
                raise SpecCompileError(
                    f"duplicate subsystem id {sub.id!r}; subsystem ids must be "
                    f"unique (they are the part-namespace prefix)")
            frag = compile_spec(load_spec_file(self.base_dir / sub.fragment))
            if frag.unit != doc.units:
                raise SpecCompileError(
                    f"subsystem {sub.id!r} fragment authored in {frag.unit!r} "
                    f"but the site is authored in {doc.units!r}; a qualified "
                    f"placement ref carries the fragment's authoring-unit "
                    f"magnitude, so this phase requires one shared authoring "
                    f"unit across the site and its fragments")
            self._frags[sub.id] = frag
            self._order.append(sub.id)

        # -- qualified site value namespace (<subsystem_id>.<name>) --------------
        # Site placements are expressed in the OWNING fragment's numbers, so a
        # placement can never hardcode a value a fragment already owns.
        site_ns: dict[str, float] = {}
        for sid, frag in self._frags.items():
            for k, v in frag.namespace.items():
                site_ns[f"{sid}.{k}"] = v
        self._site_ns = site_ns
        self._site_resolver = Resolver(site_ns, UNIT_FACTORS[doc.units])

        # -- resolve each subsystem placement transform (declared, not solved) --
        self._transforms: dict[str, Frame] = {}
        for sub in doc.subsystems:
            self._transforms[sub.id] = self._resolve_transform(sub)

    # -- placement transforms -------------------------------------------------

    def _resolve_transform(self, sub: SubsystemRef) -> Frame:
        if sub.place is None:
            return Frame.identity()
        place = sub.place
        assert isinstance(place, RawSpec)  # loader guarantees identity|raw
        try:
            at = tuple(self._site_resolver.resolve_length(v) for v in place.at)
        except SpecValueError as e:
            raise SpecCompileError(
                f"subsystem {sub.id!r} placement: {e}") from None
        rotate = [(str(axis), float(deg)) for axis, deg in place.rotate]
        if rotate:
            self._guard_rotated_subsystem(sub, rotate)
        return Frame.from_at_rotate(at, rotate)

    def _guard_rotated_subsystem(self, sub: SubsystemRef, rotate: list) -> None:
        """SM3b lands the rotated-subsystem generalization SM1 deferred, but
        scoped to RIGHT-ANGLE rotations about Z (90/180/270): those map each
        fragment axis exactly onto a world axis, so a ``bearing`` /
        ``through_hole`` axis letter remaps to a definite world axis
        (:func:`_remap_axis`) and a ``dimension`` bbox measure re-expresses in the
        fragment frame by an exact axis relabel — no float slop. Any OTHER
        rotation (a non-90 angle, or a tilt about X/Y) does NOT map axes onto
        axes: a fragment face would straddle two world axes and every
        frame-dependent check would be silently wrong. Teach loudly rather than
        validate wrong — the general-rotation remap stays queued."""
        for axis, deg in rotate:
            off = abs(deg - round(deg / 90.0) * 90.0)
            if str(axis).upper() != "Z" or off > 1e-9:
                raise SpecCompileError(
                    f"subsystem {sub.id!r} placement rotation {rotate} is not a "
                    f"right-angle rotation about Z (90/180/270). This phase remaps "
                    f"frame-dependent checks (bearing/through-hole axis letters, "
                    f"dimension bbox measures) only for right-angle Z rotations, "
                    f"which map each fragment axis exactly onto a world axis; a "
                    f"non-right-angle or off-Z rotation would leave those checks "
                    f"silently wrong. General-rotation remapping is queued")

    def _rotate_of(self, sid: str) -> list:
        """The subsystem's right-angle ``rotate`` list (``[(axis, deg), ...]``),
        empty for an identity or pure-translation placement — the input the
        axis/measure remaps key off."""
        sub = self._sub_by_id[sid]
        if sub.place is None:
            return []
        return [(str(axis), float(deg)) for axis, deg in sub.place.rotate]

    # -- stage 1-2: compose the one assembly ----------------------------------

    def assemble(self, d: DetailAssembly) -> None:
        self._by_id = {}

        # Build every fragment once (its own frame) for geometry + its _by_id.
        for frag in self._frags.values():
            frag.build()

        # Which qualified ids are RETIRED (not instantiated): bound stubs +
        # dropped context bodies. Resolved to the real member afterward.
        binds: dict[str, str] = {}       # <sid>/<stub_cid> -> real qid
        for sub in self.doc.subsystems:
            for stub_cid, real_qid in sub.bind.items():
                binds[f"{sub.id}/{stub_cid}"] = real_qid
        drops: dict[str, str] = {dd.drop: dd.keep for dd in self.doc.dedup}
        self._validate_retirements(binds, drops)
        retired = set(binds) | set(drops)

        # PASS 1: instantiate every non-retired part into the ONE assembly, with
        # the subsystem transform applied and a namespaced display name.
        for sid in self._order:
            frag = self._frags[sid]
            transform = self._transforms[sid]
            for cid, fp in frag._by_id.items():
                qid = f"{sid}/{cid}"
                if qid in retired:
                    continue
                comp = fp.component
                comp.name = f"{sid}/{comp.name}"  # NAMESPACING RULE
                world = transform.compose(fp.world_frame)
                placed = d._append(comp, world, at=world.origin, rotate=[])
                self._by_id[qid] = placed

        # PASS 2: resolve every retired id to its real member — BY IDENTITY.
        # A bound stub / dropped context body is now the same Placed object the
        # real member is: cross-subsystem disagreement is unrepresentable.
        for stub_qid, real_qid in binds.items():
            self._by_id[stub_qid] = self._resolve_qid(
                real_qid, f"bind target of {stub_qid!r}")
            self._log(f"bound stub {stub_qid!r} resolves to real member "
                      f"{real_qid!r} (single node — identity, no copy)",
                      "site.bind")
        for drop_qid, keep_qid in drops.items():
            self._by_id[drop_qid] = self._resolve_qid(
                keep_qid, f"dedup keep of {drop_qid!r}")
            self._log(f"context body {drop_qid!r} deduped to real member "
                      f"{keep_qid!r} (single node — identity, no copy)",
                      "site.dedup")

        # PASS 3: re-host each fragment onto the site parts. Every id a fragment
        # references now resolves to the SITE Placed (real member for retired
        # ids), so its connections / validation / spatial / roles check the one
        # model — WITHOUT re-parsing or a second dialect.
        for sid, frag in self._frags.items():
            for cid in list(frag._by_id):
                frag._by_id[cid] = self._by_id[f"{sid}/{cid}"]

    def _validate_retirements(self, binds: dict, drops: dict) -> None:
        """Teaching-error gate for ``bind:`` / ``dedup:`` and the honesty rule
        that a partial-member stub must be retired in-site (req 3)."""
        # bind: local cid must exist and be a STUB; target must be a known qid.
        stub_qids: set[str] = set()
        for sid in self._order:
            frag = self._frags[sid]
            for cid, fp in frag._by_id.items():
                if fp.component.stub_of() is not None:
                    stub_qids.add(f"{sid}/{cid}")
        for sub in self.doc.subsystems:
            frag = self._frags[sub.id]
            for stub_cid in sub.bind:
                if stub_cid not in frag._by_id:
                    known = sorted(frag._by_id)
                    hint = difflib.get_close_matches(stub_cid, known, n=3)
                    tip = f" — did you mean one of {hint}?" if hint else ""
                    raise SpecCompileError(
                        f"subsystem {sub.id!r} bind: no component {stub_cid!r} "
                        f"in the fragment{tip}; components: {known}")
                if f"{sub.id}/{stub_cid}" not in stub_qids:
                    raise SpecCompileError(
                        f"subsystem {sub.id!r} bind: component {stub_cid!r} is "
                        f"not a partial-member stub (component.stub_of() is "
                        f"None); only stubs are bindable this phase. Bindable "
                        f"stubs: {sorted(stub_qids)}")
        # Every stub MUST be bound in-site (a floating restatement is the bug).
        for stub_qid in stub_qids:
            if stub_qid not in binds:
                raise SpecCompileError(
                    f"partial-member stub {stub_qid!r} is not bound in-site; a "
                    f"stub restates a portion of another subsystem's real "
                    f"member and must be retired via 'bind: {{<stub_cid>: "
                    f"<subsystem>/<cid>}}'. Bound-real candidates (non-stub "
                    f"parts): see the other subsystems' components")
        # dedup drop/keep must be known qids; and a DROP must be an existing/
        # context body — never a real structural member. Without this,
        # `dedup: {drop, keep}` is waiver machinery: an author could drop a real
        # part (a bolt, an angle) and silently delete a genuine finding (rev-sm1
        # attack A). Dedup asserts two subsystems model the SAME physical
        # feature; only a context copy (the boulder) is deduped to another
        # subsystem's real one, never a load-bearing part.
        for dd in self.doc.dedup:
            for qid, role in ((dd.drop, "drop"), (dd.keep, "keep")):
                sid = qid.split("/", 1)[0]
                cid = qid.split("/", 1)[1] if "/" in qid else ""
                if sid not in self._frags or cid not in self._frags[sid]._by_id:
                    raise self._unknown_qid(qid, f"dedup {role}")
            drop_comp = self._frags[dd.drop.split("/", 1)[0]]._by_id[
                dd.drop.split("/", 1)[1]].component
            if not _is_context_body(drop_comp):
                raise SpecCompileError(
                    f"dedup drop {dd.drop!r} is a structural part "
                    f"(source=generated, not an existing/context body): "
                    f"{drop_comp.bom_label()!r}. dedup retires an "
                    f"existing/context body that another subsystem models for "
                    f"real (e.g. a context boulder) — it is not a waiver for a "
                    f"real member. Bind a stub, or resolve the interference; do "
                    f"not dedup a structural part")

    # -- stage 3: connections + validation replayed onto the one assembly -----

    def connections(self) -> list[Connection]:
        self.build()
        out: list[Connection] = []
        self._conn_fragments = {}
        for sid in self._order:
            frag_conns = self._frags[sid].connections()
            for c in frag_conns:
                self._conn_fragments[c.label] = sid
            out.extend(frag_conns)
        # site-level cross-subsystem connections (qualified ids)
        for i, cspec in enumerate(self.doc.connections):
            c = self._build_site_connection(cspec, i)
            self._conn_fragments[c.label] = "site"
            out.append(c)
        return out

    def connection_fragments(self) -> dict:
        """Connection label -> owning subsystem id (task CPGCORE, design
        §3.2): the composed site's fragment map, so an axis-3
        underdetermined verdict whose fastener and occupant belong to
        DIFFERENT fragments can name the cross-fragment gap (no site-level
        sequencing exists in v1 — CPG v2 territory) instead of a generic
        wording. Site-level cross-subsystem connections map to
        ``"site"``."""
        if getattr(self, "_conn_fragments", None) is None:
            self.connections()
        return dict(self._conn_fragments)

    def resolved_sequence(self) -> tuple:
        """Replay each fragment's RESOLVED authored stages under the
        fragment's own chain (task CPGCORE, design §3.2: one CPG per
        fragment's order claims — stages of different fragments must never
        be cross-ordered, so each fragment's stages carry its subsystem id
        as their chain and the event graph orders only within a chain).
        Stage names are qualified ``<sid>/<name>`` for provenance display;
        part ids already resolve to the SITE's Placed objects because the
        fragments are re-hosted onto the one assembly (PASS 3)."""
        from ..assemblies.event_graph import ResolvedStage

        self.build()
        out = []
        for sid in self._order:
            for st in self._frags[sid].resolved_sequence():
                out.append(ResolvedStage(
                    name=f"{sid}/{st.name}", why=st.why, chain=sid,
                    connections=st.connections, parts=st.parts))
        return tuple(out)

    def validation_spec(self) -> dict:
        self.build()
        bearings: list = []
        bonds: list = []
        through_holes: list = []
        expected_overlaps: set = set()
        contacts: list = []
        for sid in self._order:
            frag = self._frags[sid]
            transform = self._transforms[sid]
            rotate = self._rotate_of(sid)
            sub = frag.validation_spec()
            # A bearing's ``axis`` is a WORLD-frame letter (checks.py pushes ``b``
            # along ``_AXV[axis]``), so under a right-angle subsystem rotation it
            # must be remapped to the axis the fragment's bearing face now lies
            # on (rev-sm1: bearings are as frame-dependent as through-hole axes).
            for (a, b, axis, area) in sub.get("bearings", []):
                bearings.append((a, b, _remap_axis(axis, rotate), area))
            bonds.extend(sub.get("bonds", []))
            expected_overlaps |= sub.get("expected_overlaps", set())
            contacts.extend(sub.get("contacts", []))
            # A through-hole probe carries an ABSOLUTE center point AND an axis
            # LETTER in the fragment's frame; re-express BOTH under the subsystem
            # transform (SM1 re-expressed the center for translation — SM3b
            # extends it to the axis letter for right-angle rotation). bonds
            # reference resolved Placed handles (site geometry) and need no fix-up.
            for t in frag.doc.validation.through_holes:
                fastener, plates, axis, point, r_i, r_o, span = frag._build_through_hole(t)
                point = transform.compose(Frame.translation(point)).origin
                through_holes.append((fastener, plates, _remap_axis(axis, rotate),
                                      point, r_i, r_o, span))
            # fragment-level 'ground' is subsumed by the site-wide ground below;
            # 'spatial' is aggregated separately (namespaced selectors).
        spatial: list = []
        for sid in self._order:
            spatial.extend(self._scoped_spatial(sid))
        # site-level blocks (qualified ids)
        v = self.doc.validation
        for b in v.bearings:
            bearings.append(self._site_bearing(b))
        for b in v.bonds:
            bonds.append(self._site_bond(b))
        spec: dict = {}
        if bearings:
            spec["bearings"] = bearings
        if bonds:
            spec["bonds"] = bonds
        if through_holes:
            spec["through_holes"] = through_holes
        if expected_overlaps:
            spec["expected_overlaps"] = expected_overlaps
        if contacts:
            spec["contacts"] = contacts
        if spatial:
            spec["spatial"] = spatial
        ground = self._site_ground()
        if ground is not None:
            spec["ground"] = ground
        # CTXGROUND: aggregate each fragment's self-grounded existing bodies
        # (namespaced), so a pre-existing site feature stays exempt from the
        # floating check on the COMPOSED model (the frame the STRUCT branch will
        # open the trunk's growth gap in).
        self_grounded = [
            self._resolve_qid(f"{sid}/{cid}", f"{sid} grounded_by: site")
            for sid in self._order
            for cid in self._frags[sid].doc.context_grounds]
        if self_grounded:
            spec["self_grounded"] = self_grounded
        return spec

    def extra_checks(self) -> list[Finding]:
        self.build()
        out: list[Finding] = []
        # Every fragment's design-intent dimension checks, now measured against
        # the SITE geometry (the honest surfacing of req 3: a check written in a
        # fragment's frame runs against the real member it is bound to — the tree
        # beam-tangent check now reads the platform's REAL beam).
        for sid in self._order:
            frag = self._frags[sid]
            rotate = self._rotate_of(sid)
            if not rotate:
                # Identity / pure translation: the fragment's own check reads the
                # site-frame bbox directly — byte-identical to SM1 (a bbox measure
                # is translation-invariant for the Z checks in play, and identity
                # for the tree). No re-expression.
                for dim in frag.doc.validation.dimensions:
                    out.append(frag._build_dimension_check(dim))
            else:
                # Right-angle rotated subsystem: re-express each bbox measure in
                # the FRAGMENT frame (the frame the check's `expected` is authored
                # in) via the exact inverse transform, so a fragment X/Y measure
                # maps to the world axis it now lies on with no float slop.
                inv = self._transforms[sid].inverse()
                for dim in frag.doc.validation.dimensions:
                    out.append(self._rotated_dimension_check(frag, dim, inv))
        out.extend(self._support_findings())
        out.extend(self._foundation_findings())
        return out

    # -- SUPPORT (task SUPPORT): rung-3 role-obligation check, site-wide --------
    # The RCA's core site finding: SiteDetail.extra_checks ran NO role-based
    # check — the whole-structure model never even reached rung 2. Every
    # fragment's walking_surface obligation is now proven against the ONE
    # composed assembly (namespaced, single-node identity), so the platform's
    # unsupported tree end surfaces on the model that composes the real structure.

    def _support_findings(self) -> list[Finding]:
        from ..validation.support import (
            ResolvedSurface, check_support, foundation_ids)
        schemes = [(sid, cid, s) for sid in self._order
                   for cid, s in self._frags[sid].doc.support_schemes.items()]
        if not schemes:
            return []
        # Foundations: every fragment's ground-role body, resolved to its site
        # part (bind/dedup-aware via _resolve_qid) — a member is never a ground.
        roles_by_part = {}
        for sid in self._order:
            for cid, role in self._frags[sid].doc.roles.items():
                part = self._resolve_qid(f"{sid}/{cid}", f"{sid} roles")
                roles_by_part[part] = role
        surfaces = []
        for sid, cid, s in schemes:
            ctx = f"{sid} walking_surface {cid!r}"
            key_part = self._resolve_qid(f"{sid}/{cid}", ctx)
            # Lenient support resolution (task SUPPORT v1.1): a declared support
            # absent from the composed model is a tracked existence obligation.
            missing = tuple(f"{sid}/{p}" for p in s.supports
                            if f"{sid}/{p}" not in self._by_id)
            surfaces.append(ResolvedSurface(
                label=s.label or key_part.name,
                members=tuple(self._resolve_qid(f"{sid}/{m}", f"{ctx}.members")
                              for m in s.members),
                supports=tuple(self._resolve_qid(f"{sid}/{p}", f"{ctx}.supports")
                               for p in s.supports if f"{sid}/{p}" in self._by_id),
                cantilever_edges={c.edge: c.note for c in s.declared_cantilever},
                deferred_support=s.deferred_support,
                missing_supports=missing))
        spec = self._validated_spec or {}
        return check_support(
            surfaces, foundations=foundation_ids(roles_by_part),
            bearings=spec.get("bearings", []), bonds=spec.get("bonds", []),
            tol=spec.get("tol", DEFAULT))

    # -- FAB-3 (retire R29): foundation-role obligations, site-wide -------------
    # The mirror of _support_findings: every fragment's foundation system is
    # proven against the ONE composed assembly (single-node identity), so a
    # pier a platform leg rests on is the SAME node whether seen from the
    # platform fragment or the site — and its attachment/embedment/capacity
    # verdicts are computed once, over the real bearings the sweep ran on.

    def _foundation_findings(self) -> list[Finding]:
        from ..validation.foundation import ResolvedFoundation, check_foundations
        from ..validation.support import foundation_ids
        roles_by_part = {}
        for sid in self._order:
            for cid, role in self._frags[sid].doc.roles.items():
                part = self._resolve_qid(f"{sid}/{cid}", f"{sid} roles")
                roles_by_part[part] = role
        fids = foundation_ids(roles_by_part)
        if not fids:
            return []
        systems = []
        for sid in self._order:
            frag = self._frags[sid]
            for i, fspec in enumerate(frag.doc.foundations):
                ctx = f"{sid} foundation {fspec.label!r}"
                post = self._resolve_qid(f"{sid}/{fspec.supports}", f"{ctx}.supports")
                block = self._resolve_qid(f"{sid}/{fspec.block}", f"{ctx}.block")
                pb = (None if fspec.post_base is None
                      else self._resolve_qid(
                          f"{sid}/{frag._post_base_id(fspec)}", f"{ctx}.post_base"))
                frost = (None if fspec.frost_depth is None
                         else frag.resolver.resolve_length(fspec.frost_depth))
                systems.append(ResolvedFoundation(
                    label=f"{sid}/{fspec.label}", post=post, block=block,
                    post_base=pb,
                    uplift=("" if fspec.post_base is None else fspec.post_base.uplift),
                    bearing_on_grade=fspec.bearing_on_grade, frost_depth=frost))
        spec = self._validated_spec or {}
        return check_foundations(
            systems, foundation_ids=fids, bearings=spec.get("bearings", []))

    def _scoped_spatial(self, sid: str) -> list:
        """A fragment's spatial invariants, with any ``mirror`` name-selector
        SCOPED to that subsystem's own parts. A fragment's mirror invariant
        ("the platform is +Y/-Y symmetric") is about ITS members; run unscoped
        over the one site assembly, its ``+Y``/``-Y`` substitution reaches
        another subsystem's parts that use a different labeling (the tree's a/b
        stations swap on the 180-rotated -Y side), pairing the wrong parts and
        reporting a FALSE asymmetry for a fragment that is physically symmetric.
        Pre-discovering pairs within the subsystem keeps the invariant honest and
        byte-identical to SM1 (where rock_anchor happened to carry no +Y names)."""
        from ..validation.spatial import SymmetricAbout, _discover_mirror_pairs
        out = []
        for decl in self._frags[sid]._build_spatial_decls():
            if isinstance(decl, SymmetricAbout) and decl.mirror is not None:
                subset = SimpleNamespace(
                    parts=[p for p in self.assembly.parts
                           if p.name.startswith(f"{sid}/")])
                pairs = tuple(decl.pairs) + tuple(
                    _discover_mirror_pairs(subset, decl.mirror))
                out.append(SymmetricAbout(plane=decl.plane, pairs=pairs,
                                          mirror=None, tol=decl.tol))
            else:
                out.append(decl)
        return out

    def _rotated_dimension_check(self, frag, dim, inv: Frame) -> Finding:
        actual = self._fragment_frame_measure(frag, dim.part, dim.measure,
                                              dim.name, inv)
        if dim.minus_part is not None:
            actual = actual - self._fragment_frame_measure(
                frag, dim.minus_part, dim.minus_measure, dim.name, inv)
        if dim.negate:
            actual = -actual
        expected = frag.resolver.resolve_length(dim.expected)
        # SM4 item 2: subject carries the SITE-resolved member name(s) (the real
        # bound member — e.g. the trolley grab bar vs the platform's end joist),
        # so the finding slices into the views that scope those members.
        parts = frag._dimension_parts(dim)
        if dim.op == "eq":
            tol = (None if dim.tolerance is None
                   else frag.resolver.resolve_length(dim.tolerance))
            return check_dimension(dim.name, actual=actual, expected=expected,
                                   tolerance=tol, part=parts)
        passed = actual >= expected if dim.op == "ge" else actual > expected
        return Finding(
            "dimension", dimension_subject(dim.name, parts), passed,
            f"actual {actual / IN:.2f}\" {dim.op} expected {expected / IN:.2f}\"")

    def _fragment_frame_measure(self, frag, part_id, measure, dim_name, inv: Frame):
        """A part's bbox ``measure`` re-expressed in the fragment frame: transform
        the eight site-frame AABB corners back through ``inv`` and re-measure. For
        a right-angle rotation the box stays axis-aligned, so this is exact."""
        if measure not in _BBOX_MEASURES:
            raise SpecCompileError(
                f"dimension {dim_name!r}: unknown measure {measure!r}; "
                f"known: {sorted(_BBOX_MEASURES)}")
        part = frag._resolve_part(part_id, f"dimension {dim_name!r}")
        bb = part.world_solid().val().BoundingBox()
        xs, ys, zs = [], [], []
        for x in (bb.xmin, bb.xmax):
            for y in (bb.ymin, bb.ymax):
                for z in (bb.zmin, bb.zmax):
                    px, py, pz = inv.transform_point((x, y, z))
                    xs.append(px); ys.append(py); zs.append(pz)
        fb = SimpleNamespace(xmin=min(xs), xmax=max(xs), ymin=min(ys),
                             ymax=max(ys), zmin=min(zs), zmax=max(zs))
        return _BBOX_MEASURES[measure](fb)

    # -- authored-id bridge (INCR-1) ------------------------------------------

    def _retired_ids(self) -> frozenset:
        """The qualified ids that are ALIASES, not members of their own: every
        ``bind:``-ed partial-member stub and every ``dedup:``-ed context body.
        In-site each resolves BY IDENTITY to the real member (PASS 2 of
        :meth:`assemble`), so several qualified ids address ONE built node; this
        set is exactly the non-canonical ones, so the authored-id bridge picks the
        real member (the one id NOT here) as the canonical identity. Mirrors the
        ``binds``/``drops`` construction in :meth:`assemble` (read-only)."""
        retired = set()
        for sub in self.doc.subsystems:
            for stub_cid in sub.bind:
                retired.add(f"{sub.id}/{stub_cid}")
        for dd in self.doc.dedup:
            retired.add(dd.drop)
        return frozenset(retired)

    def reverse_by_id(self) -> dict:
        """The reverse of :attr:`_by_id`: ``{Placed: canonical qualified id}`` —
        one entry per built site part, with ``bind:``/``dedup:`` aliases collapsed
        onto the real member they resolve to (INCR-1). Builds first if needed."""
        from .identity import AuthoredIdentity
        return AuthoredIdentity(self).reverse_by_id()

    # -- site-level reference resolution (qualified ids) ----------------------

    def _resolve_qid(self, qid: str, ctx: str) -> Placed:
        try:
            return self._by_id[qid]
        except KeyError:
            raise self._unknown_qid(qid, ctx) from None

    def _unknown_qid(self, qid: str, ctx: str) -> SpecReferenceError:
        known = sorted(self._by_id)
        hint = difflib.get_close_matches(qid, known, n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        return SpecReferenceError(
            f"{ctx}: unknown qualified id {qid!r}{tip}; a cross-subsystem "
            f"reference is '<subsystem_id>/<component_id>' (retired stubs and "
            f"deduped bodies resolve to their real member)")

    def _build_site_connection(self, cspec: ConnectionSpec, index: int) -> Connection:
        from ..assemblies.connection import connection_types
        from .compiler import build_install_overrides

        label = cspec.label or f"site connection {index}"
        try:
            kind_cls = connection_types.get(cspec.type)
        except KeyError as e:
            raise SpecCompileError(str(e)) from None
        try:
            kind = kind_cls(**{k: self._site_resolver.resolve(v)
                               for k, v in cspec.params.items()})
        except TypeError as e:
            raise SpecCompileError(
                f"site connection {label!r} ({cspec.type}): {e}") from None
        parts = [self._resolve_qid(p, f"site connection {label!r}")
                 for p in cspec.parts]
        hardware = [self._resolve_qid(h, f"site connection {label!r}")
                    for h in cspec.hardware]
        surfaces = {self._resolve_qid(sid, f"site connection {label!r}").id: datum
                    for sid, datum in cspec.surfaces.items()}
        # INSTALL v1: the SAME lowering as the standalone compiler's
        # _build_connection (the shared helper), against the site resolver and
        # qualified-id resolution — a site compile must never silently lose a
        # contract override the spec carries.
        install = build_install_overrides(
            cspec.install, self._site_resolver, self._resolve_qid, {},
            f"site connection {label!r}")
        try:
            return Connection(kind=kind, parts=parts, hardware=hardware,
                              surfaces=surfaces,
                              assumptions=list(cspec.assumptions), label=label,
                              install=install)
        except (ValueError, KeyError) as e:
            raise SpecCompileError(f"site connection {label!r}: {e}") from None

    def _site_bearing(self, b) -> tuple:
        a = self._resolve_qid(b.a, "site validation.bearings")
        bb = self._resolve_qid(b.b, "site validation.bearings")
        return (a, bb, b.axis, self._site_resolver.resolve(b.area))

    def _site_bond(self, b) -> tuple:
        return (self._resolve_qid(b.a, "site validation.bonds"),
                self._resolve_qid(b.b, "site validation.bonds"))

    def _site_ground(self):
        # SM4 item 1 (rev-sm3b item D): the site's ground terminal is declared
        # NESTED under `validation:` (site.spec.yaml: `validation: {ground:
        # rock_anchor/boulder}`), so read `validation.ground` — a top-level
        # `ground:` key is the fallback. SM1 read only the top-level key, so the
        # nested value was silently unread: `check_no_floaters` never ran on the
        # composed site (floating OFF site-wide). Wiring it surfaces the trolley
        # hardware island (posts/handle/strap/screws sit 2.25-5.5" off the real
        # legs, so the hanging hardware descends from nothing grounded).
        ground_ref = (self.doc.validation.ground
                      if self.doc.validation.ground is not None
                      else self.doc.ground)
        if ground_ref is not None:
            return self._resolve_qid(ground_ref, "site validation.ground")
        return None

    # -- provenance -----------------------------------------------------------

    def _log(self, fact: str, rule: str) -> None:
        self._site_log.append(DerivedFact(
            fact=fact, connection="site", rule=rule, confidence="inferred"))

    def site_facts(self) -> list[DerivedFact]:
        """The site-level provenance: subsystem placements (basis + confidence),
        binds and dedups. Recorded as source-typed facts like everything else."""
        facts: list[DerivedFact] = []
        for sub in self.doc.subsystems:
            frame = self._transforms[sub.id]
            origin = tuple(round(c, 4) for c in frame.origin)
            conf = sub.confidence or "EXACT"
            facts.append(DerivedFact(
                fact=f"subsystem {sub.id!r} placed at site origin {origin} "
                     f"[{conf}] — {sub.basis or 'identity'}",
                connection="site", rule="site.placement",
                confidence="official" if conf == "EXACT" else "inferred",
                assumptions=() if conf == "EXACT"
                else (f"placement basis ASSUMED: {sub.basis}",)))
        return facts + list(self._site_log)

    # --- SM2 VIEWS: thin accessors (the view layer lives in spec/views.py) ---
    def views(self) -> list:
        """Every view declared in the site document, bound to this compiled
        site. A view is a scope selector over the one model; see
        :mod:`detailgen.spec.views`."""
        from .views import views_of
        return views_of(self)

    def view(self, name: str):
        """One named :class:`~detailgen.spec.views.View` (did-you-mean on miss)."""
        from .views import view_of
        return view_of(self, name)

    def views_including(self, part_ref: str) -> list:
        """Reverse query — the names of the views whose scope contains a part
        ("where else does this appear?", the Inspector seam)."""
        from .views import views_including
        return views_including(self, part_ref)


def compile_site_file(path: str | Path) -> SiteDetail:
    """Load and compile a site document into a runnable :class:`SiteDetail`.
    Geometry builds lazily on first ``validate``/``build``."""
    path = Path(path)
    return SiteDetail(load_site_file(path), base_dir=path.parent)
