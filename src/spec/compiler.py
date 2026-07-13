"""The DetailSpec **compiler**: a :class:`DetailSpecDoc` in, a working
:class:`~detailgen.details.base.Detail` out.

This is the front-end the north star describes — ``Intent → DetailSpec →
Construction Graph → assembly/validation/BOM``. It compiles a *declarative*
document onto the exact machinery a hand-authored detail uses: components
resolve through the components registry, placement compiles to the Wave-1 mate
API (or the marked raw escape hatch), connections instantiate the W2-6
``Connection`` objects (so every check/edge/install-order they generate flows
automatically), and the whole thing is a ``Detail`` subclass — so ``validate``,
``require_clean``, the gated ``render``, and the BOM all work unchanged.

The compiler DERIVES and everything it derives is logged with provenance (P1/P4):
every param and derived dimension, every part's resolved world placement (naming
the mate or flagging the raw escape hatch), and — via the unchanged
``Detail.validate`` path — every Connection-generated bearing/overlap/bond/edge.
A spec author writes the intent; :meth:`SpecDetail.derivation_report` shows
everything the platform inferred from it.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from ..assemblies.assembly import DetailAssembly, Placed
from ..assemblies.connection import Connection, DerivedFact, connection_types
from ..assemblies.installation import EntryFace, Exit, ToolAxis, ToolEnvelope
from ..core import IN
from ..core.config import DEFAULT
from ..core.registry import components as component_registry
from ..details.base import Detail
from ..validation import Finding, check_dimension, dimension_subject
from ..validation.spatial import FacesAway, FacesToward, SymmetricAbout
from .schema import (
    BearingSpec,
    BondSpec,
    ComponentSpec,
    ConnectionSpec,
    DetailSpecDoc,
    DimensionSpec,
    FacesSpec,
    FeatureSpec,
    MateSpec,
    MountSpec,
    MOUNT_AXES,
    MOUNT_FACE_ALIASES,
    RawSpec,
    RepeatSpec,
    SymmetricSpec,
    ThroughHoleSpec,
)
from .lowering import lower_feature, lower_mount
from .values import UNIT_FACTORS, Resolver, SpecValueError, evaluate, lookup

#: Bounding-box extractors a ``dimensions`` check may name (design-intent
#: dimension checks — the rock anchor's "leg 1/2\" above rock" etc.). Kept a
#: closed, named set so ``measure: zmim`` is a loud diagnostic, not a guess.
_BBOX_MEASURES = {
    "xmin": lambda bb: bb.xmin, "xmax": lambda bb: bb.xmax,
    "ymin": lambda bb: bb.ymin, "ymax": lambda bb: bb.ymax,
    "zmin": lambda bb: bb.zmin, "zmax": lambda bb: bb.zmax,
    # span (a member's overall length along an axis) and midpoint (its center
    # on an axis) — needed by a real detail whose design-intent checks assert an
    # overall length or a centered station, not just a single extreme face.
    "xlen": lambda bb: bb.xmax - bb.xmin, "ylen": lambda bb: bb.ymax - bb.ymin,
    "zlen": lambda bb: bb.zmax - bb.zmin,
    "xmid": lambda bb: (bb.xmin + bb.xmax) / 2,
    "ymid": lambda bb: (bb.ymin + bb.ymax) / 2,
    "zmid": lambda bb: (bb.zmin + bb.zmax) / 2,
}


class SpecCompileError(ValueError):
    """A spec was structurally valid but could not compile: an unknown
    component/connection type, an unknown or forward-referenced part id, or an
    unresolvable value. Always names the offender and what would be valid."""


@dataclass(frozen=True)
class _NoParams:
    """A ``Detail`` requires a ``Params`` dataclass; a compiled spec carries its
    dimensions in the spec's own ``params``/``derived`` blocks, so this is an
    intentionally empty stand-in — the spec, not a Python params object, is the
    source of truth for a ``SpecDetail``."""


class ParamsProxy:
    """Read-only, attribute-access view over a compiled spec's resolved
    param+derived namespace (authoring-unit magnitudes — the same raw numbers a
    ``.py`` detail's frozen ``Params`` dataclass carries, before the ``* IN``).

    A ``.py`` detail exposes its inputs as ``detail.params.<field>``; the
    equivalent for a ``SpecDetail`` is this proxy over ``doc.params`` +
    ``doc.derived``, so a consumer written against ``.params.<field>`` (a
    :class:`~detailgen.details.base.Callout`, ``_site_overview``) works unchanged
    on either path. It is deliberately read-only: a spec instance is one frozen
    member of a family, and the way to get a *different* member is to recompile
    with overrides (:func:`compile_spec`), not to mutate a live instance —
    trying to set a field says exactly that."""

    __slots__ = ("_ns",)

    def __init__(self, namespace: dict[str, float]):
        object.__setattr__(self, "_ns", dict(namespace))

    def __getattr__(self, name: str) -> float:
        try:
            return object.__getattribute__(self, "_ns")[name]
        except KeyError:
            ns = object.__getattribute__(self, "_ns")
            hint = difflib.get_close_matches(name, sorted(ns), n=3)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise AttributeError(
                f"compiled spec has no param or derived dimension {name!r}; "
                f"its namespace is {sorted(ns)}{tip} (a SpecDetail's .params "
                f"exposes only the spec's params: + derived: dimensions)"
            ) from None

    def __setattr__(self, name: str, value) -> None:
        raise AttributeError(
            f"a compiled spec's .params are read-only (cannot set {name!r}); a "
            f"SpecDetail is one frozen member of a family — recompile with "
            f"compile_spec(doc, overrides={{{name!r}: ...}}) to change a param"
        )

    def __contains__(self, name: str) -> bool:
        return name in object.__getattribute__(self, "_ns")

    def __repr__(self) -> str:
        ns = object.__getattribute__(self, "_ns")
        inner = ", ".join(f"{k}={v:g}" for k, v in ns.items())
        return f"ParamsProxy({inner})"


class SpecDetail(Detail):
    """A :class:`~detailgen.details.base.Detail` whose lifecycle is driven by a
    :class:`DetailSpecDoc` rather than imperative Python. Its ``assemble`` /
    ``connections`` / ``validation_spec`` / ``extra_checks`` REPLAY the spec
    onto the standard machinery; every hook the base class already gates
    (``validate``, ``render``) therefore works with no override."""

    Params = _NoParams

    def __init__(self, doc: DetailSpecDoc, overrides: dict | None = None):
        if doc.units not in UNIT_FACTORS:
            raise SpecCompileError(
                f"unknown authoring unit {doc.units!r}; known: "
                f"{sorted(UNIT_FACTORS)}"
            )
        # Semantic-analysis pass (§3.5): mount dangling refs, DOF completeness,
        # relation cycles — teaching errors at COMPILE time, before any geometry
        # is built (retro R4: turn a ~3-min build+validate discovery into an
        # instant compile error).
        from .semantics import (
            analyze_features, analyze_mounts, analyze_retires, analyze_sequence)
        analyze_mounts(doc)
        analyze_features(doc)
        analyze_retires(doc)
        analyze_sequence(doc)
        self.doc = doc
        self.unit = doc.units
        self.unit_factor = UNIT_FACTORS[doc.units]
        # A param-override compile re-binds named ``params:`` values, then lets
        # ``derived:`` recompute from the overridden namespace — the declarative
        # twin of the ``.py`` family's ``dataclass.replace(params, ...)``. An
        # empty/absent overrides map takes the identical code path as the plain
        # compile (no override facts, no re-bind), so the no-override result is
        # byte-for-byte the original (test-enforced).
        self.overrides = dict(overrides) if overrides else {}
        self.namespace, self._spec_log = _build_namespace(
            doc, self.unit, self.unit_factor, self.overrides)
        self.resolver = Resolver(self.namespace, self.unit_factor)
        # Detail's own state (we drive it directly rather than through
        # Detail.__init__, since a SpecDetail has no Python Params to build).
        # ``.params`` is a read-only proxy over the resolved param+derived
        # namespace, so a consumer written against a ``.py`` detail's
        # ``.params.<field>`` works unchanged against a SpecDetail.
        self.params = ParamsProxy(self.namespace)
        self._assembly = None
        self._report = None
        self._derivation_log = []
        self._connection_edges = []
        self._by_id: dict[str, Placed] = {}
        #: CPGCORE resolution bridges: authored (template) component id ->
        #: the built instance cids it expanded to, and authored connection
        #: label (template) -> the compiled labels it expanded to. What lets
        #: resolved_sequence() expand a stage's repeat-template references
        #: to every built instance. _conn_instances is (re)built by
        #: connections(); None until it has run at least once.
        self._cid_instances: dict[str, list[str]] = {}
        self._conn_instances: dict[str, list[str]] | None = None
        self._mount_contacts = []
        #: FEATURE-derived clearance invariants (CL-2), filled by the post-placement
        #: feature pass and consumed by extra_checks as derived clearance findings.
        self._feature_clearances = []
        #: RETIRE (CL-3): the connection labels + member ids retired by this doc.
        #: Consumed at expansion so a retired connection's whole derived closure
        #: (bearings/interferences/hardware/edges + attached expectations) simply
        #: never generates, and a retired member is not placed — deletion is the
        #: edit. The retire-with-dependents / orphan-retire guards already ran in
        #: the semantic pass, so these sets are safe to honour blindly here.
        self._retired_conns = frozenset(
            r.target for r in doc.retire if r.kind == "connection")
        self._retired_members = frozenset(
            r.target for r in doc.retire if r.kind == "member")
        # Record each retirement as an audit fact (WHY it was removed) — the
        # provenance silent deletion would lose (§3.3 field 4). Provenance channel
        # is ``retire:<target>`` (like ``repeat:<var>``), NOT a declared
        # connection, so it never trips the evidence orphan-fact guard.
        for r in doc.retire:
            self._spec_log.append(DerivedFact(
                fact=f"{r.kind} {r.target!r} RETIRED — {r.reason}. Its derived "
                     f"closure unwinds automatically (no hand-unwind).",
                connection=f"retire:{r.target}", rule="spec.retire",
                confidence="inferred",
            ))
        self.name = doc.name
        # P3/escape-hatch: a declared cross_check is a dotted-path reference to
        # arbitrary verification Python (not a DSL) — log it loudly at compile,
        # exactly like an imperative component hook, so the derivation report
        # always shows the escape even if cross_check() is never called.
        if doc.cross_check is not None:
            self._spec_log.append(DerivedFact(
                fact=f"cross_check is an IMPERATIVE reference to "
                     f"{doc.cross_check.ref!r} — an independent constraint solve "
                     f"(verification only, never canonical); a P3 escape hatch, "
                     f"not the declarative language",
                connection="cross_check", rule="spec.cross_check.imperative_ref",
                assumptions=("dotted-path escape hatch, not a declarative check",),
                confidence="placeholder",
            ))

    # -- stage 1-2: params -> components + assembly ---------------------------

    def assemble(self, d: DetailAssembly) -> None:
        self._by_id = {}
        #: (cid, placed, target, contact) per MOUNT placement — the derived
        #: contacts a mount asserts (§3.1 field 3), merged into validation below.
        self._mount_contacts = []
        self._feature_clearances = []
        self._expand_components(d, self.doc.components, self.resolver, {})
        self._expand_foundations(d)
        # FEATURE pass (CL-2): runs AFTER every part is placed, because a feature
        # derives its board-local cut from the REFERENCED part's placed position
        # (the world->local negation the author does by hand today). The installed
        # solid is still lazy, so applying the cut here is byte-identical to the
        # same cut authored as the old ``trunk_cut`` param.
        self._expand_features(d, self.doc.components, self.resolver, {})

    # -- FAB-3 (retire R29): foundation systems -------------------------------

    def _post_base_id(self, fspec) -> str:
        """The component id of a foundation's post base — the author's explicit
        ``post_base.id`` or the derived default ``<block>_base``."""
        return fspec.post_base.id or f"{fspec.block}_base"

    def _expand_foundations(self, d: DetailAssembly) -> None:
        """Create + place each foundation system's post base (task FAB-3, §7).
        The block and post are already-placed components; the post base is a NEW
        purchased part the foundation declaration introduces — mated onto the
        block's top pad so it stands between the block and the post it fastens
        down. A foundation with no post base introduces no part (an explicitly-
        undesigned attachment the obligation pack FAILs)."""
        for i, fspec in enumerate(self.doc.foundations):
            if fspec.post_base is None:
                continue
            self._place_post_base(d, fspec, i)

    def _place_post_base(self, d: DetailAssembly, fspec, index: int) -> None:
        ctx = f"foundations[{index}] ({fspec.label!r})"
        block = self._resolve_part(fspec.block, f"{ctx} block")
        pb_id = self._post_base_id(fspec)
        if pb_id in self._by_id:
            raise SpecCompileError(
                f"{ctx}: post base id {pb_id!r} collides with an existing "
                f"component id — set a distinct post_base.id")
        pb = fspec.post_base
        kwargs = self._resolve_params(pb.params, f"{ctx} post_base", self.resolver)
        try:
            cls = component_registry.get(pb.type)
        except KeyError as e:
            raise SpecCompileError(str(e)) from None
        name = f"post base {fspec.label}"
        try:
            component = cls(name=name, **kwargs)
        except TypeError as e:
            raise SpecCompileError(
                f"{ctx}: post base ({pb.type}): {e} — check the param names match "
                f"the component's constructor"
            ) from None
        _check_datum(component, "bottom", f"{ctx}: post base datum")
        _check_datum(block.component, "top", f"{ctx}: block {fspec.block!r} datum")
        placed = d.place(component, "bottom").on(block, "top", offset=(0.0, 0.0, 0.0))
        self._by_id[pb_id] = placed
        self._spec_log.append(DerivedFact(
            fact=f"foundation {fspec.label!r}: post base {name!r} created + placed "
                 f"on {block.name}.top (mate) — the attachment R29 found missing; "
                 f"uplift {pb.uplift}",
            connection=pb_id, rule="spec.foundation.post_base",
            confidence="inferred", subjects=(placed.id,)))

    def _expand_components(self, d, entries, resolver: Resolver, bindings: dict):
        """Place a components list, expanding any :class:`RepeatSpec` in place.
        ``resolver``/``bindings`` carry the active loop-index namespace so a
        nested repeat, an ``= expr`` placement and a ``{var}`` id/name all
        resolve against the same per-iteration scope."""
        for entry in entries:
            if isinstance(entry, RepeatSpec):
                self._run_repeat(entry, resolver, bindings,
                                 lambda body, r, b: self._expand_components(d, body, r, b))
            elif entry.id in self._retired_members:
                # RETIRE (CL-3): a retired member is not placed. The semantic pass
                # already proved nothing surviving references it.
                continue
            else:
                self._place_component(d, entry, resolver, bindings)

    def _run_repeat(self, rep: RepeatSpec, resolver: Resolver, bindings: dict,
                    process_body) -> None:
        """Resolve a repeat's (possibly DERIVED) count, then run ``process_body``
        once per index with the index bound into a child namespace + bindings.
        The count being a ``= n_joists`` expression is the compression lever:
        the author declares a family + a spacing rule, the compiler derives HOW
        MANY."""
        if rep.var in resolver.namespace:
            raise SpecCompileError(
                f"repeat variable {rep.var!r} shadows an existing param/derived "
                f"dimension or an enclosing loop index; choose a fresh name "
                f"(in scope: {sorted(resolver.namespace)})"
            )
        count = self._resolve_count(rep.count, resolver)
        self._spec_log.append(DerivedFact(
            fact=f"repeat {rep.var!r} expanded to {count} iteration(s) "
                 f"(index {rep.start}..{rep.start + count - 1}) from count "
                 f"{rep.count!r}",
            connection=f"repeat:{rep.var}", rule="spec.repeat.expand",
            confidence="inferred",
        ))
        for i in range(rep.start, rep.start + count):
            child_ns = {**resolver.namespace, rep.var: float(i)}
            child_resolver = Resolver(child_ns, resolver.unit_factor)
            child_bindings = {**bindings, rep.var: i}
            process_body(rep.body, child_resolver, child_bindings)

    def _resolve_count(self, count, resolver: Resolver) -> int:
        """A repeat count: a bare non-negative int, or a ``$name`` / ``= expr``
        over the (loop-aware) namespace resolving to one. Dimensionless — a
        count is not a length, so no unit factor is applied. A non-integral or
        negative result is a teaching diagnostic, never a silent floor."""
        if isinstance(count, bool):
            raise SpecCompileError(f"repeat count must be an integer, got {count!r}")
        if isinstance(count, int):
            value = float(count)
        elif isinstance(count, str):
            text = count.strip()
            try:
                if text.startswith("$"):
                    value = lookup(resolver.namespace, text[1:].strip())
                elif text.startswith("="):
                    value = evaluate(text[1:].strip(), resolver.namespace)
                else:
                    raise SpecCompileError(
                        f"repeat count {count!r} must be a bare integer, a "
                        f"$name, or a '= expr' (an authoring-unit scalar, not a "
                        f"length)"
                    )
            except SpecValueError as e:
                raise SpecCompileError(f"repeat count {count!r}: {e}") from None
        else:
            raise SpecCompileError(
                f"repeat count must be an integer or a $/= expression, got "
                f"{count!r}"
            )
        n = round(value)
        if abs(value - n) > 1e-9 or n < 0:
            raise SpecCompileError(
                f"repeat count {count!r} resolved to {value!r}; a count must be "
                f"a non-negative whole number (a derived count like a joist "
                f"tally should use '//' so it floors to an integer)"
            )
        return int(n)

    def _place_component(self, d: DetailAssembly, cspec: ComponentSpec,
                         resolver: Resolver, bindings: dict) -> None:
        cid = _interp(cspec.id, bindings, f"component id {cspec.id!r}")
        name = _interp(cspec.name, bindings, f"component {cid!r} name")
        reader_name = ""
        if cspec.reader_name:
            reader_name = _interp(
                cspec.reader_name, bindings, f"component {cid!r} reader_name")
        if cid in self._by_id:
            raise SpecCompileError(
                f"duplicate component id {cid!r} — ids must be unique so "
                f"connections and validation can reference them (a repeat whose "
                f"body ids omit the loop {'{var}'} collides on every iteration)"
            )
        kwargs = self._resolve_params(cspec.params, f"component {cid!r}", resolver)
        if cspec.imperative:
            component = self._build_imperative(cspec, kwargs, cid, name)
        else:
            component = self._build_registered(cspec, kwargs, cid, name)
        placed = self._apply_placement(d, cspec, component, resolver, bindings, cid, name)
        placed.reader_name = reader_name
        self._by_id[cid] = placed
        self._cid_instances.setdefault(cspec.id, []).append(cid)
        if bindings:
            self._log_repeat_instance(cid, placed, bindings)
        if cspec.name_defaulted:
            self._spec_log.append(DerivedFact(
                fact=f"component {cid!r} display name defaulted to its id",
                connection=cid, rule="spec.component.name_default",
                confidence="inferred",
            ))

    def _log_repeat_instance(self, cid: str, placed: Placed, bindings: dict) -> None:
        """Back-link a repeated placement to the repeat declaration(s) + index
        that produced it (rev-specplat rec 1, P1 granularity). The single
        ``spec.repeat.expand`` fact says a repeat ran N times; it does NOT say
        which built part is which iteration. This threads ``{var}={index}`` for
        every enclosing loop into the specific part's provenance, so ``joist
        0+Y`` traces to ``repeat 'j'`` at index 0 (and, when nested, to the full
        ``{k}=1, {j}=2`` coordinate) — a repeated part is now as traceable as a
        hand-placed one. ``subjects`` carries the real ``Placed.id`` so the fact
        concerns the actual part; ``connection`` names the innermost repeat so
        it groups under the loop it most directly came from."""
        coord = ", ".join(f"{{{var}}}={idx}" for var, idx in bindings.items())
        innermost = next(reversed(bindings))
        self._spec_log.append(DerivedFact(
            fact=f"component {cid!r} is repeat instance {coord}",
            connection=f"repeat:{innermost}", rule="spec.repeat.instance",
            confidence="inferred", subjects=(placed.id,),
        ))

    def _build_registered(self, cspec: ComponentSpec, kwargs: dict, cid, name):
        try:
            cls = component_registry.get(cspec.type)
        except KeyError as e:
            raise SpecCompileError(str(e)) from None
        try:
            return cls(name=name, **kwargs)
        except TypeError as e:
            raise SpecCompileError(
                f"component {cid!r} ({cspec.type}): {e} — check the param "
                f"names match the component's constructor"
            ) from None

    def _build_imperative(self, cspec: ComponentSpec, kwargs: dict, cid, name):
        """P3 escape hatch: build a component from a dotted-path callable for
        geometry the DSL cannot express. Imported and called as
        ``f(name=..., **params)``; its use is logged loudly (placeholder
        confidence — an authored escape from the declarative language)."""
        fn = _import_callable(cspec.imperative)
        try:
            component = fn(name=name, **kwargs)
        except Exception as e:
            raise SpecCompileError(
                f"component {cid!r}: imperative hook {cspec.imperative!r} "
                f"raised {type(e).__name__}: {e}"
            ) from None
        self._spec_log.append(DerivedFact(
            fact=f"component {name!r} built by IMPERATIVE hook "
                 f"{cspec.imperative!r} — geometry the DSL cannot express (P3 "
                 f"escape hatch)",
            connection=cid, rule="spec.component.imperative_hook",
            assumptions=("imperative escape hatch, not a registered component type",),
            confidence="placeholder",
        ))
        return component

    def _apply_placement(self, d: DetailAssembly, cspec: ComponentSpec, component,
                         resolver: Resolver, bindings: dict, cid, name) -> Placed:
        place = cspec.place
        if place is None:
            placed = d.add(component)
            self._spec_log.append(DerivedFact(
                fact=f"{name!r} placed at the origin (identity) — no "
                     f"placement declared",
                connection=cid, rule="spec.placement.identity_default",
                confidence="inferred",
            ))
            return placed
        if isinstance(place, RawSpec):
            at = tuple(resolver.resolve_length(v) for v in place.at)
            rotate = [(str(axis), float(deg)) for axis, deg in place.rotate]
            placed = d.add(component, at=at, rotate=rotate)
            self._spec_log.append(DerivedFact(
                fact=f"{name!r} placed by RAW transform at "
                     f"{tuple(round(c, 4) for c in placed.world_frame.origin)} "
                     f"(rotate {rotate}) — imperative escape hatch",
                connection=cid, rule="spec.placement.raw",
                assumptions=("raw global-axis transform, not a mate",),
                confidence="placeholder",
            ))
            return placed
        if isinstance(place, MateSpec):
            on_id = _interp(place.on, bindings, f"mate target {place.on!r}")
            target = self._resolve_part(on_id, f"placement of {cid!r}")
            # Datum names are the hardest vocabulary for an author to get right;
            # validate BOTH sides of the mate eagerly so a typo is a teaching
            # diagnostic (available datums + did-you-mean), not a raw KeyError
            # leaked from deep in the mate API.
            _check_datum(component, place.datum,
                         f"placement of {cid!r}: part datum")
            _check_datum(target.component, place.on_datum,
                         f"placement of {cid!r}: target {on_id!r} datum")
            offset = tuple(resolver.resolve_length(v) for v in place.offset)
            placed = d.place(component, place.datum).on(
                target, place.on_datum, offset=offset,
                rotate=float(place.rotate), flip=place.flip,
            )
            self._spec_log.append(DerivedFact(
                fact=f"{name!r} world placement derived from mate "
                     f"{name}.{place.datum} onto {target.name}.{place.on_datum} "
                     f"-> origin "
                     f"{tuple(round(c, 4) for c in placed.world_frame.origin)}",
                connection=cid, rule="spec.placement.mate",
                confidence="inferred",
            ))
            if place.on_datum_defaulted:
                self._spec_log.append(DerivedFact(
                    fact=f"{name!r} mate target datum defaulted to 'top'",
                    connection=cid, rule="spec.placement.on_datum_default",
                    confidence="inferred",
                ))
            return placed
        if isinstance(place, MountSpec):
            return self._apply_mount(d, place, component, resolver, cid, name)
        raise SpecCompileError(
            f"component {cid!r}: unrecognized placement {place!r}"
        )

    def _apply_mount(self, d: DetailAssembly, mount: MountSpec, component,
                     resolver: Resolver, cid, name) -> Placed:
        """Place a part from a MOUNT relation: resolve the target + relation
        values, LOWER (pure) to a world frame, place it, and record the derived
        facts (the transform's provenance, the dependency edge, the placement
        sentence). The rotation is DERIVED — no hand ``rotate`` — and ``mirror``
        gives the opposite hand with no ``= -…`` twin (retro R2/R3)."""
        target = self._resolve_part(mount.to, f"mount of {cid!r}")
        # Target reference frame: its ``axis`` datum (a centered spine) if it has
        # one, else ``base``. The standoff / center / mirror axes are named in it.
        tdatums = target.component.datums
        tdname = "axis" if "axis" in tdatums else "base"
        target_frame = target.datum_world(tdname)
        # Surface distance from the target frame origin along the standoff axis =
        # half the target's world-bbox extent on that axis (exact for the analytic
        # bodies MOUNT targets today). ``flush``/``clear_by``/``offset`` measure
        # from that surface.
        surface_offset = _target_half_extent(target, mount.axis)
        face_name = MOUNT_FACE_ALIASES[mount.face]
        _check_datum(component, face_name, f"mount of {cid!r}: face {mount.face!r}")
        _check_datum(component, "base", f"mount of {cid!r}: base datum")
        low = lower_mount(
            mount,
            face_datum=component.datum(face_name),
            base_datum=component.datum("base"),
            target_frame=target_frame,
            surface_offset=surface_offset,
            clear_by=(None if mount.clear_by is None
                      else resolver.resolve_length(mount.clear_by)),
            offset=(None if mount.offset is None
                    else resolver.resolve_length(mount.offset)),
            ground_above=(None if mount.ground is None
                          else resolver.resolve_length(mount.ground)),
        )
        placed = d._append(component, low.world_frame,
                           at=low.world_frame.origin, rotate=[])
        self._spec_log.append(DerivedFact(
            fact=f"{name!r} placed by MOUNT relation ({mount.face} face vs "
                 f"{target.name}, along {mount.axis}) -> origin "
                 f"{tuple(round(c, 4) for c in placed.world_frame.origin)}"
                 f"{' (opposite hand, mirror ' + mount.mirror + ')' if mount.mirror else ''}"
                 f"{' — rotation derived' if low.rotated else ''}",
            connection=cid, rule="spec.placement.mount",
            confidence="inferred", source_type="authoritative",
            subjects=(placed.id,),
        ))
        # Evidence/ownership edge (§3.1 field 4): who this part registers against
        # — the compiled answer to "who depends on the target", not a hand grep.
        self._spec_log.append(DerivedFact(
            fact=f"{name!r} registers against {target.name!r} "
                 f"(mount dependency edge)",
            connection=cid, rule="spec.mount.evidence",
            confidence="inferred", source_type="authoritative",
            subjects=(placed.id, target.id),
        ))
        # Grounding fact (R3): a ``ground`` relation references the base to the
        # world grade datum — a DERIVED elevation fact (with doc sentence), not a
        # bare Z number. Placement-level only (an elevation reference), never a
        # load-path bond, so it adds no floating/ground finding.
        if low.grounded:
            self._spec_log.append(DerivedFact(
                fact=f"{name!r} base grounded to the grade datum: {low.doc_sentence}",
                connection=cid, rule="spec.mount.ground",
                confidence="inferred", source_type="authoritative",
                subjects=(placed.id,),
            ))
        self._mount_contacts.append((cid, placed, target, low.contact))
        return placed

    # -- stage 2.5: FEATURE resolution (CL-2, retro R9/R14) -------------------

    def _expand_features(self, d, entries, resolver: Resolver, bindings: dict):
        """Resolve every component's FEATUREs, expanding repeats in place — the
        same walk ``_expand_components`` does, but AFTER placement so a feature's
        referenced part is already in ``_by_id``."""
        for entry in entries:
            if isinstance(entry, RepeatSpec):
                self._run_repeat(entry, resolver, bindings,
                                 lambda body, r, b: self._expand_features(d, body, r, b))
            elif isinstance(entry, ComponentSpec) and entry.features:
                self._apply_features(entry, resolver, bindings)

    def _apply_features(self, cspec: ComponentSpec, resolver: Resolver,
                        bindings: dict) -> None:
        cid = _interp(cspec.id, bindings, f"component id {cspec.id!r}")
        placed = self._resolve_part(cid, f"features of {cid!r}")
        component = placed.component
        if not hasattr(component, "apply_feature_cut"):
            raise SpecCompileError(
                f"features of {cid!r}: component type {cspec.type!r} does not "
                f"accept a FEATURE cut (only board-like components do today); "
                f"drop the 'features:' block or use a supporting component")
        for feat in cspec.features:
            self._apply_feature(cid, placed, component, feat, resolver, bindings)

    def _apply_feature(self, cid: str, placed: Placed, component,
                       feat: FeatureSpec, resolver: Resolver, bindings: dict) -> None:
        """Lower ONE feature (pure), install its derived board-local cut, and
        record the derived facts (evidence edge, doc sentence, clearance
        invariant, callout anchor, affected region). The board-local cut center is
        DERIVED from the referenced part's placed position — the world->local
        negation the author does by hand (R9) never appears."""
        base_local = component.datum("base").origin
        part_center = (base_local[0], base_local[1])
        if feat.kind == "clearance_cut":
            gap = resolver.resolve_length(feat.gap)
            if gap < 0:
                raise SpecCompileError(
                    f"feature on {cid!r}: clearance_cut gap resolves to "
                    f"{gap:.3f}mm (negative) — a clearance gap is the material a "
                    f"part keeps clear of a member; it cannot be negative.")
            member_id = _interp(feat.around, bindings, f"feature around {feat.around!r}")
            member = self._resolve_part(member_id, f"feature on {cid!r} clearance_cut")
            mdatums = member.component.datums
            axis_world = member.datum_world("axis" if "axis" in mdatums else "base").origin
            member_radius = _member_radius(member)
            low = lower_feature(
                feat, part_frame=placed.world_frame, part_center_local=part_center,
                member_axis_world=axis_world, member_radius=member_radius,
                member_name=member.name, gap=gap, unit_factor=resolver.unit_factor)
        else:  # bore
            dia = resolver.resolve_length(feat.dia)
            at_local = (None if not feat.at
                        else tuple(resolver.resolve_length(v) for v in feat.at))
            low = lower_feature(
                feat, part_frame=placed.world_frame, part_center_local=part_center,
                member_axis_world=None, member_radius=None, dia=dia, at_local=at_local)
        cx, cy, radius = low.cut
        component.apply_feature_cut(cx, cy, radius, noun=low.noun,
                                    step_kind=low.step_kind, provenance=low.provenance)
        self._record_feature_facts(cid, placed, component, feat, low)

    def _record_feature_facts(self, cid, placed, component, feat, low) -> None:
        """Emit the §3.2 derived facts for one lowered feature — kept in sync by
        construction because they all share the one declaration."""
        from ..core.process_graph import notch_removes_material
        cx, cy, radius = low.cut
        reaches = notch_removes_material(cx, cy, radius, component.length, component.WIDTH)
        self._spec_log.append(DerivedFact(
            fact=f"feature {low.provenance!r} on {placed.name!r}: derived a "
                 f"board-local {low.step_kind} at ({round(cx, 3)}, {round(cy, 3)}) "
                 f"R{round(radius, 3)}mm — center DERIVED from the referenced "
                 f"placement, not hand-authored",
            connection=cid, rule=f"spec.feature.{low.kind}",
            confidence="inferred", source_type="authoritative", subjects=(placed.id,)))
        if low.clears:
            # Evidence/ownership edge (§3.2 field 4): who this part is fitted around.
            self._spec_log.append(DerivedFact(
                fact=f"{placed.name!r} is fitted around {low.clears!r} "
                     f"(clearance_cut feature edge)",
                connection=cid, rule="spec.feature.evidence",
                confidence="inferred", source_type="authoritative",
                subjects=(placed.id,) + ((low.clears,) if low.clears in self._by_id else ())))
        if not reaches:
            # The §6.2 geometric no-op, surfaced as a teaching NOTE (not a silent
            # skip): the member does not cross this board, so no cut is emitted and
            # its cut list reads plain — truthfully.
            self._spec_log.append(DerivedFact(
                fact=f"feature {low.provenance!r} on {placed.name!r} is a geometric "
                     f"no-op (the cut cylinder falls outside the board footprint); "
                     f"no {low.step_kind} step emitted — this board clears without a cut",
                connection=cid, rule="spec.feature.noop",
                confidence="inferred", subjects=(placed.id,)))
        # Clearance invariant (§3.2 field 3) — only for a clearance_cut that
        # actually cuts (a no-op board clears the member trivially; a bore mandates
        # none). Consumed by extra_checks as a DERIVED ge clearance finding.
        if low.clearance is not None and reaches:
            member = self._by_id.get(low.clearance[0])
            if member is not None:
                self._feature_clearances.append(
                    (cid, placed, member, low.clearance[1], low.provenance, low.noun))
        # Callout anchor (§3.2 field 5): the notch/bore dimension callout, DERIVED
        # from the feature (label + radius), anchored on the featured part — a
        # derivation-log fact so the anchor is a visible, queryable output. (Live
        # rendering as a `Callout` object is a presentation-layer follow-up; the
        # ANCHOR is derived here, which is what CAT Test 1 asserts.)
        label, cradius = low.callout
        self._spec_log.append(DerivedFact(
            fact=f"feature {low.provenance!r} on {placed.name!r}: derived a "
                 f"dimension callout anchor '{label}' (R{round(cradius, 3)}mm) "
                 f"on the featured part",
            connection=cid, rule="spec.feature.callout",
            confidence="inferred", subjects=(placed.id,)))

    def connections(self) -> list[Connection]:
        self.build()  # ensure parts are placed and self._by_id populated
        out: list[Connection] = []
        self._conn_instances = {}
        self._expand_connections(self.doc.connections, self.resolver, {}, out)
        self._append_foundation_connections(out)
        return out

    def sequence(self) -> tuple:
        """The loaded+validated ``sequence:`` block's stages (task SEQSCHEMA),
        in declaration order — spec-local labels/ids (a connection's
        ``label``, a component's authored ``id``), the authored claim
        verbatim. The compiled form the event graph consumes is
        :meth:`resolved_sequence`."""
        return self.doc.sequence.stages

    def resolved_sequence(self) -> tuple:
        """The authored stages resolved to the compiled surface (task
        CPGCORE): repeat-template connection labels expand to every built
        instance's label, component ids map to built ``Placed`` ids (a
        template cid expands to all its instances). analyze_sequence
        already proved every name exists in the DOC; this bridge maps them
        onto what the doc BUILT — a name that built nothing (e.g. a
        retired connection) is a loud teaching error, never a silent
        no-op."""
        from ..assemblies.event_graph import ResolvedStage

        stages = self.doc.sequence.stages
        if not stages:
            return ()
        self.build()
        if self._conn_instances is None:
            self.connections()
        out = []
        for st in stages:
            labels: list[str] = []
            for ref in st.connections:
                expanded = self._conn_instances.get(ref)
                if not expanded:
                    raise SpecCompileError(
                        f"sequence stage {st.name!r}: connection {ref!r} "
                        f"built no instance (retired, or its repeat ran "
                        f"zero times) — an authored order claim cannot "
                        f"order a connection that does not exist in the "
                        f"built detail")
                labels.extend(expanded)
            pids: list[str] = []
            for ref in st.parts:
                if ref in self._by_id:
                    pids.append(self._by_id[ref].id)
                    continue
                instances = self._cid_instances.get(ref)
                if not instances:
                    raise SpecCompileError(
                        f"sequence stage {st.name!r}: part {ref!r} built no "
                        f"instance (retired, or its repeat ran zero times) "
                        f"— an authored order claim cannot order a part "
                        f"that does not exist in the built detail")
                pids.extend(self._by_id[cid].id for cid in instances)
            out.append(ResolvedStage(
                name=st.name, why=st.why, chain="",
                connections=tuple(labels), parts=tuple(pids)))
        return tuple(out)

    def resolved_staging(self):
        """Resolve typed staging claims to built part ids exactly once.

        Explicit subassemblies expand repeat-template component ids just like
        :meth:`resolved_sequence`. ``bench_then_set`` is normalized here to
        one unit containing every non-context built part, so the event graph,
        installability, and reader surfaces consume one representation rather
        than separately interpreting the sugar.
        """
        from ..assemblies.event_graph import ResolvedStaging, ResolvedUnit

        seq = self.doc.sequence
        if not seq.subassemblies and seq.assembly is None:
            return None
        self.build()

        def expand(ref: str, owner: str) -> tuple[str, ...]:
            if ref in self._by_id:
                return (self._by_id[ref].id,)
            instances = self._cid_instances.get(ref)
            if not instances:
                raise SpecCompileError(
                    f"{owner}: part {ref!r} built no instance (retired, or "
                    f"its repeat ran zero times) — a staging claim cannot "
                    f"place a part that does not exist in the built detail")
            return tuple(self._by_id[cid].id for cid in instances)

        context: list[str] = []
        for ref, role in self.doc.roles.items():
            if role == "existing":
                context.extend(expand(ref, "staging context"))
        context_parts = frozenset(context)

        if seq.subassemblies:
            units = []
            for unit in seq.subassemblies:
                pids: list[str] = []
                for ref in unit.parts:
                    pids.extend(expand(
                        ref, f"sequence subassembly {unit.name!r}"))
                units.append(ResolvedUnit(
                    name=unit.name, why=unit.why, parts=tuple(pids)))
            return ResolvedStaging(
                mode="subassemblies", units=tuple(units),
                context_parts=context_parts)

        authored = seq.assembly
        if authored.mode == "bench_then_set":
            built = tuple(p.id for p in self.assembly.parts
                          if p.id not in context_parts)
            units = (ResolvedUnit(
                name="whole detail", why=authored.why, parts=built),)
        else:  # explicit in_situ: no bench frames
            units = ()
        return ResolvedStaging(
            mode=authored.mode, why=authored.why, units=units,
            context_parts=context_parts)

    def _append_foundation_connections(self, out: list) -> None:
        """One post->block :class:`~detailgen.assemblies.connection.Connection`
        per foundation system that declares a post base (task FAB-3) — wired
        through the EXISTING Connection machinery (hardware presence, install
        order, load-path edges), never a parallel one. The post base is the
        connection's hardware; capacity stays UNKNOWN (the obligation pack)."""
        for i, fspec in enumerate(self.doc.foundations):
            if fspec.post_base is None:
                continue
            ctx = f"foundations[{i}] ({fspec.label!r})"
            post = self._resolve_part(fspec.supports, f"{ctx} supports")
            block = self._resolve_part(fspec.block, f"{ctx} block")
            pb = self._resolve_part(self._post_base_id(fspec), f"{ctx} post_base")
            kind = connection_types.get("standoff_post_base")()
            out.append(Connection(
                kind=kind, parts=[post, block], hardware=[pb],
                assumptions=[
                    f"Post base holds {post.name} down onto foundation "
                    f"{block.name} (uplift {fspec.post_base.uplift}); "
                    f"uplift/lateral/soil capacity NOT analyzed (rung 4)."],
                label=f"foundation {fspec.label}"))

    def _expand_connections(self, entries, resolver: Resolver, bindings: dict,
                            out: list) -> None:
        """Build a connections list, expanding any :class:`RepeatSpec` the SAME
        way the components list does — so the joints for a repeated joist row
        author once and reference the ``{k}``-generated part ids per iteration."""
        for entry in entries:
            if isinstance(entry, RepeatSpec):
                self._run_repeat(entry, resolver, bindings,
                                 lambda body, r, b: self._expand_connections(body, r, b, out))
            elif entry.label in self._retired_conns:
                # RETIRE (CL-3): a retired connection never instantiates, so its
                # entire derived closure — bearings, allowlisted interferences,
                # hardware-presence findings, install order, load-path edges — is
                # withdrawn by construction. This IS the ~9-file hand-unwind,
                # collapsed to the one ``retire:`` declaration (REPLAY C).
                continue
            else:
                built = self._build_connection(entry, len(out), resolver, bindings)
                if self._conn_instances is not None and entry.label:
                    # authored-label -> compiled-label bridge (CPGCORE): a
                    # repeat body's template label records every instance it
                    # expanded to, so a sequence: stage naming the template
                    # resolves to all of them (one stage's own members are
                    # mutually unordered, so claiming the template claims
                    # every instance — exactly the honest reading).
                    self._conn_instances.setdefault(
                        entry.label, []).append(built.label)
                out.append(built)

    def _build_connection(self, conn: ConnectionSpec, index: int,
                          resolver: Resolver, bindings: dict) -> Connection:
        label = _interp(conn.label, bindings, f"connection label {conn.label!r}")
        try:
            kind_cls = connection_types.get(conn.type)
        except KeyError as e:
            raise SpecCompileError(str(e)) from None
        kind_kwargs = self._resolve_params(conn.params, f"connection {label or index!r}", resolver)
        try:
            kind = kind_cls(**kind_kwargs)
        except TypeError as e:
            raise SpecCompileError(
                f"connection {label or index!r} ({conn.type}): {e} — check "
                f"the param names match the connection type's constructor"
            ) from None
        ctx = f"connection {label or index!r}"
        parts = [self._resolve_part(_interp(p, bindings, ctx), ctx) for p in conn.parts]
        hardware = [self._resolve_part(_interp(h, bindings, ctx), ctx) for h in conn.hardware]
        surfaces = {self._resolve_part(_interp(sid, bindings, ctx), ctx).id: datum
                    for sid, datum in conn.surfaces.items()}
        install = build_install_overrides(
            conn.install, resolver, self._resolve_part, bindings, ctx)
        # Connection.__post_init__ validates surface datum names (with its own
        # did-you-mean) and part counts — surface those as spec diagnostics
        # rather than a leaked ValueError/KeyError.
        try:
            return Connection(
                kind=kind, parts=parts, hardware=hardware, surfaces=surfaces,
                assumptions=list(conn.assumptions), label=label,
                install=install,
            )
        except (ValueError, KeyError) as e:
            raise SpecCompileError(f"{ctx}: {e}") from None

    def validation_spec(self) -> dict:
        self.build()
        spec: dict = {}
        v = self.doc.validation
        if v.through_holes:
            spec["through_holes"] = [self._build_through_hole(t) for t in v.through_holes]
        bearings: list = []
        self._expand_checks(v.bearings, self.resolver, {}, bearings,
                            self._build_bearing)
        bonds: list = []
        self._expand_checks(v.bonds, self.resolver, {}, bonds, self._build_bond)
        # MOUNT-derived contacts (§3.1 field 3): a mount that ASSERTS a contact
        # emits it here, from the SAME relation that placed the part — so the
        # placement and its proof cannot disagree (the CAT §7 Test 2 wrongness
        # class). A positioning-only mount asserts nothing and adds nothing.
        for _cid, placed, target, contact in self._mount_contacts:
            if contact is None:
                continue
            kind = contact[0]
            if kind == "bearing":
                bearings.append((placed, target, contact[2],
                                 _mount_face_area(placed, contact[2])))
            elif kind == "bond":
                bonds.append((placed, target))
        if bearings:
            spec["bearings"] = bearings
        if bonds:
            spec["bonds"] = bonds
        overlaps: list = []
        self._expand_checks(v.expected_overlaps, self.resolver, {}, overlaps,
                            self._build_pair)
        if overlaps:
            spec["expected_overlaps"] = set(overlaps)
        contacts: list = []
        self._expand_checks(v.contacts, self.resolver, {}, contacts,
                            self._build_pair)
        if contacts:
            spec["contacts"] = contacts
        if v.ground is not None:
            self._require_ground_is_foundation(v.ground)
            spec["ground"] = self._resolve_part(v.ground, "validation.ground")
        # CTXGROUND: pre-existing self-grounded site bodies, exempt from the
        # floating check (resolved to placed parts here so the sweep keys on ids).
        if self.doc.context_grounds:
            spec["self_grounded"] = [
                self._resolve_part(cid, "roles (grounded_by: site)")
                for cid in self.doc.context_grounds]
        spatial = self._build_spatial_decls()
        if spatial:
            spec["spatial"] = spatial
        return spec

    def _build_spatial_decls(self) -> list:
        """Compile the ``spatial:`` block into validation-only declaration
        objects (task SPATIAL), each carrying RESOLVED ``Placed`` handles so its
        findings key on the same part display names the imperative path uses —
        the source of the spec/imperative equivalence for spatial findings. The
        ``mirror`` name selector passes through unresolved (it discovers pairs by
        display name at check time, identically on both paths)."""
        sp = self.doc.spatial
        out: list = []
        for s in sp.symmetric:
            out.append(self._build_symmetric(s))
        for x in sp.faces:
            out.append(self._build_faces(x))
        return out

    def _build_symmetric(self, s: SymmetricSpec) -> SymmetricAbout:
        ctx = "spatial.symmetric"
        pairs = tuple((self._resolve_part(a, ctx), self._resolve_part(b, ctx))
                      for a, b in s.pairs)
        tol = None if s.tol is None else self.resolver.resolve_length(s.tol)
        return SymmetricAbout(plane=s.plane, pairs=pairs, mirror=s.mirror, tol=tol)

    def _build_faces(self, x: FacesSpec):
        ctx = "spatial.faces"
        part = self._resolve_part(x.part, ctx)
        facing = x.facing_datum if x.facing_datum is not None else x.facing
        target = (self._resolve_part(x.target, ctx) if x.target is not None
                  else x.target_dir)
        tol = 0.0 if x.tol is None else float(x.tol)
        cls = FacesToward if x.sense == "toward" else FacesAway
        return cls(part=part, facing=facing, target=target, tol=tol)

    def _expand_checks(self, entries, resolver: Resolver, bindings: dict,
                       out: list, build_leaf) -> None:
        """Expand a validation list (bearings/bonds) the SAME way components and
        connections expand — a repeat over the joist row or the deck field
        authors its bearings once, referencing the ``{k}``/``{j}`` parts."""
        for entry in entries:
            if isinstance(entry, RepeatSpec):
                self._run_repeat(entry, resolver, bindings,
                                 lambda body, r, b: self._expand_checks(body, r, b, out, build_leaf))
            else:
                out.append(build_leaf(entry, resolver, bindings))

    def _build_bearing(self, bspec: BearingSpec, resolver: Resolver, bindings: dict) -> tuple:
        ctx = "validation.bearings"
        a = self._resolve_part(_interp(bspec.a, bindings, ctx), ctx)
        b = self._resolve_part(_interp(bspec.b, bindings, ctx), ctx)
        area = resolver.resolve(bspec.area)
        return (a, b, bspec.axis, area)

    def _build_bond(self, bspec: BondSpec, resolver: Resolver, bindings: dict) -> tuple:
        ctx = "validation.bonds"
        a = self._resolve_part(_interp(bspec.a, bindings, ctx), ctx)
        b = self._resolve_part(_interp(bspec.b, bindings, ctx), ctx)
        return (a, b)

    def _build_pair(self, spec, resolver: Resolver, bindings: dict) -> tuple:
        """Resolve an ``expected_overlaps`` / ``contacts`` id-pair to a
        ``(Placed, Placed)`` tuple — the shape ``validate_assembly`` consumes for
        both (an allowlisted interference; a per-joint touch check)."""
        ctx = "validation.expected_overlaps/contacts"
        a = self._resolve_part(_interp(spec.a, bindings, ctx), ctx)
        b = self._resolve_part(_interp(spec.b, bindings, ctx), ctx)
        return (a, b)

    def _build_through_hole(self, t: ThroughHoleSpec) -> tuple:
        fastener = self._resolve_part(t.part, "through_hole")
        plates = [self._resolve_part(p, "through_hole.passes_through")
                  for p in t.passes_through]
        point = tuple(self.resolver.resolve_length(c) for c in t.center)
        return (
            fastener, plates, t.axis, point,
            self.resolver.resolve_length(t.r_inner),
            self.resolver.resolve_length(t.r_outer),
            self.resolver.resolve_length(t.span),
        )

    def extra_checks(self) -> list[Finding]:
        self.build()
        out = []
        for dim in self.doc.validation.dimensions:
            out.append(self._build_dimension_check(dim))
        out.extend(self._load_path_findings())
        out.extend(self._support_findings())
        out.extend(self._foundation_findings())
        out.extend(self._feature_clearance_findings())
        return out

    def _feature_clearance_findings(self) -> list[Finding]:
        """The clearance invariant a ``clearance_cut`` FEATURE mandates (§3.2 field
        3), DERIVED — not hand-authored: the featured part must clear the member it
        is fitted around by at least the declared gap. Proven with the SAME true
        surface-to-surface min-distance the bearing check already uses (no new
        geometry-kernel capability — §9); the check and the cut it validates are
        the ONE ``clearance_cut`` declaration, so they can never disagree. Emitted
        only for a cut that actually reaches the part (a no-op board clears
        trivially and gets the teaching note instead)."""
        from ..validation.checks import _min_distance
        out: list[Finding] = []
        for _cid, placed, member, gap, ident, noun in self._feature_clearances:
            dist = _min_distance(placed, member)
            passed = dist >= gap - 1e-6
            out.append(Finding(
                "clearance",
                f"{placed.name} clears {member.name} by the {noun} gap [{ident}]",
                passed,
                f"min surface distance {dist / IN:.3f}\" >= gap {gap / IN:.3f}\""))
        return out

    # -- ONTOLOGY (task ONTOLOGY): role declarations -> load-path check --------
    # Kept in its own section, disjoint from the SPATIAL spec block. The spec's
    # ``roles:`` maps component IDs to roles; ``roles()`` resolves those to
    # display NAMES so the shared load-path helper resolves parts identically to
    # the imperative path (equivalence, req 7).

    def roles(self) -> dict:
        self.build()
        out = {}
        for cid, role in self.doc.roles.items():
            out[self._resolve_part(cid, "roles").name] = role
        return out

    def _load_path_findings(self) -> list[Finding]:
        from ..validation.loadpath import load_path_findings
        return load_path_findings(
            roles_by_name=self.roles(), assembly=self.assembly,
            connections=self.connections(), edges=self.connection_edges,
            load_class="downward_load")

    # -- SUPPORT (task SUPPORT): rung-3 support-obligation check ----------------

    def _require_ground_is_foundation(self, ground_cid) -> None:
        """Teaching guard (task SUPPORT req 2): a ``validation.ground`` terminal
        that carries a DECLARED role must be a FOUNDATION (``ground``), never a
        structural member. This kills the ``ground: leg_pY`` degeneracy — a leg
        is role ``support``, so naming it the ground is the exact mistake the RCA
        traced. Silent (backward-compatible) when the detail declares no role for
        that part; the support check still fails a surface whose supports reach
        no foundation."""
        from ..core.ontology import OntologyError, is_foundation_role
        role = self.doc.roles.get(ground_cid)
        if role is not None and not is_foundation_role(role):
            raise OntologyError(
                f"validation.ground {ground_cid!r} has role {role!r}, a "
                f"structural member — the ground terminal must be a FOUNDATION "
                f"(a body with role 'ground': a boulder/pier/footing). Declare "
                f"the real foundation and point ground at it; do not relabel a "
                f"member as ground.")

    def _foundations_by_part(self) -> dict:
        """``{placed_part: role}`` for every declared role — the input the
        foundation-id helper filters to ``ground`` bodies."""
        return {self._resolve_part(cid, "roles"): role
                for cid, role in self.doc.roles.items()}

    def _resolved_surfaces(self) -> list:
        from ..validation.support import ResolvedSurface
        out = []
        for cid, s in self.doc.support_schemes.items():
            ctx = f"roles[{cid!r}] walking_surface"
            # Resolve supports LENIENTLY (task SUPPORT v1.1): a declared support
            # missing from the model is a tracked existence obligation, reported
            # by the check as a FAIL — not a hard compile crash.
            missing = tuple(p for p in s.supports if p not in self._by_id)
            out.append(ResolvedSurface(
                label=s.label or self._resolve_part(cid, ctx).name,
                members=tuple(self._resolve_part(m, f"{ctx}.members")
                              for m in s.members),
                supports=tuple(self._resolve_part(p, f"{ctx}.supports")
                               for p in s.supports if p in self._by_id),
                cantilever_edges={c.edge: c.note for c in s.declared_cantilever},
                deferred_support=s.deferred_support,
                missing_supports=missing))
        return out

    def _support_findings(self) -> list[Finding]:
        if not self.doc.support_schemes:
            return []
        from ..validation.support import check_support, foundation_ids
        spec = self._validated_spec or {}
        return check_support(
            self._resolved_surfaces(),
            foundations=foundation_ids(self._foundations_by_part()),
            bearings=spec.get("bearings", []), bonds=spec.get("bonds", []),
            tol=spec.get("tol", DEFAULT))

    # -- FAB-3 (retire R29): foundation-role obligation pack -------------------

    def _resolved_foundations(self) -> list:
        from ..validation.foundation import ResolvedFoundation
        out = []
        for i, fspec in enumerate(self.doc.foundations):
            ctx = f"foundations[{i}] ({fspec.label!r})"
            post = self._resolve_part(fspec.supports, f"{ctx} supports")
            block = self._resolve_part(fspec.block, f"{ctx} block")
            pb = (None if fspec.post_base is None
                  else self._resolve_part(self._post_base_id(fspec),
                                          f"{ctx} post_base"))
            frost = (None if fspec.frost_depth is None
                     else self.resolver.resolve_length(fspec.frost_depth))
            out.append(ResolvedFoundation(
                label=fspec.label, post=post, block=block, post_base=pb,
                uplift=("" if fspec.post_base is None else fspec.post_base.uplift),
                bearing_on_grade=fspec.bearing_on_grade, frost_depth=frost))
        return out

    def _foundation_findings(self) -> list[Finding]:
        """The foundation-role obligation findings (task FAB-3). Runs whenever the
        detail has a FOUNDATION body a member bears on — even with NO ``foundations:``
        block, so an undeclared attachment (the R29 shape that read CLEAN) FAILs
        the attachment obligation loudly, not silently passes."""
        from ..validation.foundation import check_foundations
        from ..validation.support import foundation_ids
        fids = foundation_ids(self._foundations_by_part())
        if not fids:
            return []
        spec = self._validated_spec or {}
        return check_foundations(
            self._resolved_foundations(), foundation_ids=fids,
            bearings=spec.get("bearings", []))

    def _bbox_measure(self, part_id, measure, dim_name):
        if measure not in _BBOX_MEASURES:
            raise SpecCompileError(
                f"dimension {dim_name!r}: unknown measure {measure!r}; "
                f"known: {sorted(_BBOX_MEASURES)}"
            )
        part = self._resolve_part(part_id, f"dimension {dim_name!r}")
        bb = part.world_solid().val().BoundingBox()
        return _BBOX_MEASURES[measure](bb)

    def _dimension_parts(self, dim: DimensionSpec) -> list:
        """The display name(s) of the member(s) a dimension MEASURES: the checked
        part, plus the ``minus_part`` for a cross-part difference. Folded into the
        Finding subject (SM4 item 2) so it names — and slices to — the member(s)
        it is about."""
        parts = [self._resolve_part(dim.part, f"dimension {dim.name!r}").name]
        if dim.minus_part is not None:
            parts.append(self._resolve_part(
                dim.minus_part, f"dimension {dim.name!r}").name)
        return parts

    def _build_dimension_check(self, dim: DimensionSpec) -> Finding:
        actual = self._bbox_measure(dim.part, dim.measure, dim.name)
        if dim.minus_part is not None:
            # Cross-part difference: a distance between two members (SM3b).
            actual = actual - self._bbox_measure(dim.minus_part, dim.minus_measure,
                                                 dim.name)
        if dim.negate:
            actual = -actual
        expected = self.resolver.resolve_length(dim.expected)
        parts = self._dimension_parts(dim)  # SM4 item 2: subject carries the part(s)
        if dim.op == "eq":
            tolerance = (None if dim.tolerance is None
                         else self.resolver.resolve_length(dim.tolerance))
            return check_dimension(dim.name, actual=actual, expected=expected,
                                   tolerance=tolerance, part=parts)
        # Threshold comparison (ge/gt) — a one-sided bound, tolerance ignored.
        passed = actual >= expected if dim.op == "ge" else actual > expected
        return Finding(
            "dimension", dimension_subject(dim.name, parts), passed,
            f"actual {actual / IN:.2f}\" {dim.op} expected {expected / IN:.2f}\"")

    # -- provenance -----------------------------------------------------------

    def derivation_report(self) -> list[DerivedFact]:
        """The full derivation log (P4): the spec-level facts (params, derived
        dimensions, every resolved placement, defaults + escape hatches) plus
        the Connection-generated facts from the last :meth:`validate`. Validates
        first if needed, so the Connection layer's facts are present."""
        if self._report is None:
            self.validate()
        return list(self._spec_log) + list(self._derivation_log)

    # -- presentation surfaces (task 4B-2) ------------------------------------
    # The five capabilities the imperative details carried beyond the
    # declarative lifecycle. Each REPLAYS its ``doc`` block onto the SAME base
    # hooks (``Callout`` objects, the name-keyed explode dict, ``_export`` /
    # ``_document``), so a consumer reading a SpecDetail through the Detail API
    # gets byte-identical output to the ``.py`` twin.

    def callouts(self) -> list:
        """Compile the ``callouts:`` block to param-derived
        :class:`~detailgen.details.base.Callout` objects. Each endpoint is a
        callable that resolves its value-language coordinates against the live
        param namespace, so ``rendered_callouts()`` tracks a re-sized family
        member exactly as the imperative callable endpoints do."""
        return [self._build_callout(c) for c in self.doc.callouts]

    def _build_callout(self, cspec):
        from ..details.base import Callout
        return Callout(param=cspec.param, label=cspec.label,
                       p0=self._callout_point(cspec.p0),
                       p1=self._callout_point(cspec.p1))

    def _callout_point(self, coords):
        """A callout endpoint as a callable of ``params`` (the base ``Callout``
        contract): resolves each value-language coordinate to mm. Closes over
        this member's resolver — the family way to move an endpoint is to
        recompile with overrides, which yields a fresh resolver + callouts."""
        resolver = self.resolver

        def point(_params, coords=tuple(coords), resolver=resolver):
            try:
                return [resolver.resolve_length(c) for c in coords]
            except SpecValueError as e:
                raise SpecCompileError(f"callout endpoint {coords!r}: {e}") from None

        return point

    def explode_vectors(self) -> dict:
        """Compile the ``explode:`` block to a display-name-keyed offset dict
        (the key the viewer/manifest use). Each id resolves to its part's display
        name; each vector coordinate resolves through the value language (a bare
        number passes through, a directive resolves to mm) — reproducing each
        detail's own unit convention."""
        self.build()
        out: dict = {}
        for e in self.doc.explode:
            name = self._resolve_part(e.id, "explode").name
            out[name] = tuple(self.resolver.resolve(c) for c in e.vector)
        return out

    def cross_check(self) -> dict | None:
        """Resolve and call the ``cross_check:`` escape-hatch reference
        (``f(detail) -> dict``), or ``None`` when none is declared. The
        reference itself was logged loudly at compile (see ``__init__``)."""
        if self.doc.cross_check is None:
            return None
        fn = _import_callable(self.doc.cross_check.ref)
        return fn(self)

    def _export(self, out_dir) -> None:
        """Replay the ``export:`` block: STEP + GLB + manifest (with the
        param-derived dimension callouts, and explode vectors merged in when
        declared), sharing the same exporter machinery the imperative details
        call. With no ``export:`` block, falls back to the base single-STEP
        default. Internal hook — invoked only by the gated ``render``."""
        exp = self.doc.export
        if exp is None:
            return super()._export(out_dir)
        from ..details.base import _slug
        from ..rendering.export import export_glb, export_manifest, export_step
        detail = self.assembly
        export_step(detail, out_dir / f"{_slug(self.name)}.step")
        export_glb(detail, out_dir / "detail.glb",
                   tolerance=exp.glb_tolerance,
                   angular_tolerance=exp.glb_angular_tolerance)
        mpath = export_manifest(detail, out_dir / "detail.manifest.json",
                                extra={"dimensions": self.rendered_callouts()})
        if exp.inject_explode:
            self._inject_explode(mpath, exp.explode_authoring_units)

    def _inject_explode(self, manifest_path, authoring_units: bool) -> None:
        """Merge explode vectors into the manifest parts (post-export), matching
        each detail's convention: vectors authored in internal mm are written
        as-is; vectors authored in authoring units are scaled by the unit
        factor first (the trolley's per-detail choice)."""
        import json

        ev = self.explode_vectors()
        data = json.loads(manifest_path.read_text())
        for part in data["parts"]:
            offset = ev.get(part["name"], (0, 0, 0))
            if authoring_units:
                part["explode"] = [c * self.unit_factor for c in offset]
            else:
                part["explode"] = list(offset)
        manifest_path.write_text(json.dumps(data, indent=1))

    def _document(self, out_dir) -> None:
        """Render the ``doc:`` block to its report file (default: nothing).
        Internal hook — invoked only by the gated ``render``, after ``_export``,
        so the validation report, BOM and cross-check are available."""
        from .report import render_report

        doc = self.doc.doc
        if not doc.sections:
            return None
        (out_dir / doc.report).write_text(render_report(self, doc))

    # -- helpers --------------------------------------------------------------

    def _resolve_params(self, params: dict, ctx: str, resolver: Resolver | None = None) -> dict:
        resolver = resolver or self.resolver
        try:
            return {k: resolver.resolve(v) for k, v in params.items()}
        except SpecValueError as e:
            raise SpecCompileError(f"{ctx}: {e}") from None

    def _resolve_part(self, part_id, ctx: str) -> Placed:
        if not isinstance(part_id, str):
            raise SpecCompileError(
                f"{ctx}: part reference must be a component id (string), got "
                f"{part_id!r}"
            )
        try:
            return self._by_id[part_id]
        except KeyError:
            known = sorted(self._by_id)
            hint = difflib.get_close_matches(part_id, known, n=3)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise SpecCompileError(
                f"{ctx}: unknown component id {part_id!r}; placed so far: "
                f"{known}{tip} (a mate/connection can only reference a part "
                f"declared earlier in components)"
            ) from None

    # -- authored-id bridge (INCR-1) ------------------------------------------

    def _retired_ids(self) -> frozenset:
        """Authored ids that are ALIASES for another member's identity rather
        than a member of their own — empty for a standalone detail (every id
        names its own part). The site overrides this with its ``bind:``-ed stubs
        and ``dedup:``-ed context bodies, which resolve BY IDENTITY to a real
        member (site.py). Consumed by :class:`~detailgen.spec.identity.AuthoredIdentity`
        to pick the canonical id for a single-node member."""
        return frozenset()

    def reverse_by_id(self) -> dict:
        """The reverse of :attr:`_by_id`: ``{Placed: canonical authored id}`` —
        the insertion-stable identity key for every built part (INCR-1). Builds
        first if needed; raises on a P1 ambiguity (see
        :class:`~detailgen.spec.identity.AuthoredIdentity`)."""
        from .identity import AuthoredIdentity
        return AuthoredIdentity(self).reverse_by_id()


def build_install_overrides(ispec, resolver, resolve_part, bindings: dict,
                            ctx: str) -> dict:
    """Lower an authored :class:`~detailgen.spec.schema.InstallSpec` into the
    ``Connection.install`` override map (task INSTALL v1): ``{role: {contract
    field: resolved value}}``, values in the plain
    :mod:`~detailgen.assemblies.installation` leaf types. Shared by BOTH
    connection-build paths — the standalone compiler's
    :meth:`SpecDetail._build_connection` and the site's
    ``_build_site_connection`` — so a site compile can never silently lose a
    contract the standalone spec carries.

    Value-language lengths (``embedment``, ``tool.length``/``tool.dia``)
    resolve through ``resolver`` and ``{var}`` part templates through the
    ACTIVE ``bindings``, exactly like the connection's parts/label — so an
    ``install:`` inside a ``repeat:`` body resolves per iteration. Returns
    ``{}`` for ``ispec=None`` (no authored override)."""
    if ispec is None:
        return {}
    fields: dict = {}
    try:
        if ispec.method:
            fields["method"] = ispec.method
        if ispec.entry_part:
            pid = resolve_part(_interp(ispec.entry_part, bindings, ctx), ctx).id
            fields["entry_face"] = EntryFace(pid, ispec.entry_face)
        if ispec.angle is not None:
            a = float(ispec.angle)
            # angle 0 = straight along the shank; any other declared angle is
            # the angled semantics — and today's drawn solids never model an
            # angle, so the axis is flagged idealized (amendment #3: verdicts
            # along it are REPRESENTED-rung until angled placement vocabulary
            # lands and the compiler can prove the solid matches).
            fields["tool_axis"] = (
                ToolAxis("shank") if a == 0.0
                else ToolAxis("angled", angle_deg=a, axis_idealized=True))
        if ispec.exit:
            faces = tuple(
                EntryFace(resolve_part(_interp(p, bindings, ctx), ctx).id, face)
                for p, face in ispec.exit_faces)
            fields["exit"] = Exit(ispec.exit, faces)
        if ispec.embedment is not None:
            fields["embedment"] = (
                "through" if ispec.embedment == "through"
                else resolver.resolve_length(ispec.embedment))
        if ispec.head:
            fields["head"] = ispec.head
        if ispec.tool_length is not None:
            fields["tool_envelope"] = ToolEnvelope(
                resolver.resolve_length(ispec.tool_length),
                resolver.resolve_length(ispec.tool_dia))
        if ispec.stage:
            fields["stage"] = ispec.stage
    except SpecValueError as e:
        raise SpecCompileError(f"{ctx} install: {e}") from None
    return {ispec.role: fields}


_INTERP_RE = re.compile(r"\{(\w+)\}")


def _interp(text, bindings: dict, ctx: str):
    """Substitute ``{var}`` loop indices in an id/name/label/part-ref template.
    Only whole ``{identifier}`` tokens are touched, and only against the ACTIVE
    loop ``bindings`` (integers), so a template outside any repeat, or a string
    with no braces, passes through untouched. A ``{token}`` with no matching
    loop variable is a teaching diagnostic (the vars in scope), never a silent
    literal ``{token}`` leaking into a part id."""
    if not isinstance(text, str) or "{" not in text:
        return text

    def repl(m: re.Match) -> str:
        var = m.group(1)
        if var not in bindings:
            raise SpecCompileError(
                f"{ctx}: template references {{{var}}} but no loop variable "
                f"{var!r} is in scope; active loop indices: {sorted(bindings)} "
                f"(a {{var}} token only resolves inside a matching repeat)"
            )
        v = bindings[var]
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)

    return _INTERP_RE.sub(repl, text)


def _mount_face_area(placed, axis: str) -> float:
    """The nominal bearing area a mounted part presents on its registering face
    — the product of its world-bbox extents on the two axes perpendicular to the
    standoff ``axis``. Derived from the SAME placed geometry the relation
    produced, so the bearing the mount asserts and the transform it computes are
    one fact (the CAT §7 Test 2 class)."""
    bb = placed.world_solid().vals()[0].BoundingBox()
    ext = {"X": bb.xmax - bb.xmin, "Y": bb.ymax - bb.ymin, "Z": bb.zmax - bb.zmin}
    others = [ext[a] for a in ("X", "Y", "Z") if a != axis]
    return others[0] * others[1]


def _member_radius(member) -> float:
    """The cross-sectional radius a ``clearance_cut`` fits a part around. Reads the
    member's DECLARED size (``radius`` / ``diameter``) when it has one — exact, so
    ``radius = member_radius + gap`` reproduces the hand ``= trunk_dia/2 + gap`` to
    the bit — and falls back to half the member's world-bbox X extent otherwise
    (a rounded read of the placed geometry, for a member with no declared radius).
    The bbox of a cylinder overshoots the true radius by OCCT's box gap, so the
    declared size is the one that keeps the migrated notch byte-identical."""
    comp = member.component
    r = getattr(comp, "radius", None)
    if r is not None:
        return float(r)
    dia = getattr(comp, "diameter", None)
    if dia is not None:
        return float(dia) / 2.0
    return _target_half_extent(member, "X")


def _target_half_extent(target, axis: str) -> float:
    """Half the target part's world bounding-box extent along ``axis`` — the
    distance from its reference-frame origin out to its surface, the datum a
    MOUNT ``clear_by`` / ``flush`` / ``offset`` measures from. Exact for the
    analytic bodies MOUNT targets (a trunk cylinder's radius, a member's
    half-thickness); a pure read of the placed geometry, so lowering stays
    deterministic."""
    bb = target.world_solid().vals()[0].BoundingBox()
    span = {"X": bb.xmax - bb.xmin, "Y": bb.ymax - bb.ymin,
            "Z": bb.zmax - bb.zmin}[axis]
    return span / 2.0


def _check_datum(component, datum_name: str, ctx: str) -> None:
    """Raise a teaching :class:`SpecCompileError` (available datums +
    did-you-mean) if ``component`` has no datum ``datum_name`` — the same style
    as the registry/value diagnostics, for the one vocabulary axis (datum names)
    that is per-component and easiest to mistype."""
    datums = component.datums
    if datum_name not in datums:
        known = sorted(datums)
        hint = difflib.get_close_matches(datum_name, known, n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        raise SpecCompileError(
            f"{ctx}: component {component.name!r} has no datum {datum_name!r}; "
            f"available datums: {known}{tip}"
        )


def _import_callable(dotted: str):
    """Resolve ``"package.module.func"`` to the callable it names, or raise a
    :class:`SpecCompileError` explaining the expected form. Used only by the P3
    imperative escape hatch — a spec's one door to arbitrary Python, so the
    failure is a loud, specific diagnostic, never an opaque ImportError."""
    import importlib

    if "." not in dotted:
        raise SpecCompileError(
            f"imperative hook {dotted!r} must be a dotted path "
            f"'package.module.callable'"
        )
    module_path, attr = dotted.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise SpecCompileError(
            f"imperative hook {dotted!r}: cannot import module "
            f"{module_path!r} ({e})"
        ) from None
    try:
        fn = getattr(module, attr)
    except AttributeError:
        raise SpecCompileError(
            f"imperative hook {dotted!r}: module {module_path!r} has no "
            f"attribute {attr!r}"
        ) from None
    if not callable(fn):
        raise SpecCompileError(
            f"imperative hook {dotted!r} resolved to a non-callable {fn!r}"
        )
    return fn


def _build_namespace(doc: DetailSpecDoc, unit: str, unit_factor: float,
                     overrides: dict | None = None):
    """Resolve the ``params`` then ``derived`` blocks into one authoring-unit
    namespace, logging each as an authored (``official``) or derived
    (``inferred``) fact. Derived entries may reference params and earlier
    derived entries — evaluated in document order.

    ``overrides`` (a ``name -> authoring-unit number`` map) re-binds named
    ``params:`` values BEFORE the ``derived:`` block runs, so every derived
    dimension recomputes from the overridden inputs — the declarative twin of
    the ``.py`` family's ``dataclass.replace``. An empty/absent map is the plain
    compile with no perturbation (byte-identical): the loop below only diverges
    when a param name is actually in ``overrides``.

    The authoring unit itself is the first logged fact (P1): when ``units:`` was
    omitted the default is recorded as an *inferred* assumption — omitting it
    silently would scale every length 25.4x for an author who meant mm, with no
    trace; when declared it is an ``official`` fact."""
    overrides = overrides or {}
    _validate_overrides(doc, overrides)
    ns: dict[str, float] = {}
    log: list[DerivedFact] = []
    if doc.units_defaulted:
        log.append(DerivedFact(
            fact=f"authoring unit not declared; defaulted to {unit!r} — params, "
                 f"derived dimensions and $/= directives are interpreted in "
                 f"{unit} (declare 'units: mm' to change this)",
            connection="spec", rule="spec.units.default", confidence="inferred",
        ))
    else:
        log.append(DerivedFact(
            fact=f"authoring unit = {unit!r} (declared)", connection="spec",
            rule="spec.units", confidence="official",
        ))
    for name, value in doc.params.items():
        if name in overrides:
            ns[name] = _override_value(overrides[name], name)
            log.append(DerivedFact(
                fact=f"param {name} = {ns[name]:g} {unit} (OVERRIDDEN from spec "
                     f"default {value!r}) — this is one member of the param "
                     f"family; derived dimensions recompute from it",
                connection="spec", rule="spec.params.override",
                confidence="official",
            ))
        else:
            ns[name] = _eval_dimension(value, ns, f"param {name!r}")
            log.append(DerivedFact(
                fact=f"param {name} = {ns[name]:g} {unit}", connection="spec",
                rule="spec.params", confidence="official",
            ))
    for name, value in doc.derived.items():
        ns[name] = _eval_dimension(value, ns, f"derived {name!r}")
        log.append(DerivedFact(
            fact=f"derived {name} = {value!r} = {ns[name]:g} {unit}",
            connection="spec", rule="spec.derived", confidence="inferred",
        ))
    return ns, log


def _validate_overrides(doc: DetailSpecDoc, overrides: dict) -> None:
    """Reject a param-override map that names something the spec cannot rebind,
    in the same teaching style as the rest of the compiler: a DERIVED name (it
    is computed, not an input), or an unknown name (with did-you-mean over the
    overridable params). Only ``params:`` entries are overridable — ``derived:``
    dimensions recompute from them."""
    param_names = sorted(doc.params)
    for name in overrides:
        if name in doc.params:
            continue
        if name in doc.derived:
            raise SpecCompileError(
                f"cannot override {name!r}: it is a DERIVED dimension, computed "
                f"by the spec's derived: block from the params, not an input. "
                f"Override the param(s) it is computed from instead — the "
                f"overridable params are {param_names}"
            )
        hint = difflib.get_close_matches(name, param_names, n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        raise SpecCompileError(
            f"unknown override param {name!r}; this spec's overridable params "
            f"are {param_names}{tip} (only params: entries can be overridden; "
            f"derived: dimensions recompute from them)"
        )


def _override_value(value, name: str) -> float:
    """A param override must be a bare number in the doc's authoring units — the
    declarative twin of assigning a float to a frozen-dataclass field. A string
    directive / non-number is a teaching diagnostic naming the expected form."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecCompileError(
            f"override for param {name!r} must be a bare number in the doc's "
            f"authoring units (e.g. {name}=42.0), got {value!r}; a compiled "
            f"family member re-binds a param to a magnitude, not a $/=/unit "
            f"directive"
        )
    return float(value)


def _eval_dimension(value, namespace: dict, ctx: str) -> float:
    """A params/derived entry to an authoring-unit magnitude. A bare number is
    an authoring-unit magnitude; a ``$name``/``= expr`` string references the
    namespace. Unit-suffixed quantities are deliberately rejected here — they
    belong at use-sites; params/derived carry the doc's single authoring unit,
    so a stray ``"8 mm"`` amid an inch doc is a mistake worth catching."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise SpecCompileError(
            f"{ctx}: a dimension must be a number or a $/= expression, got "
            f"{value!r}"
        )
    if isinstance(value, (int, float)):
        return float(value)
    text = value.strip()
    try:
        if text.startswith("$"):
            return lookup(namespace, text[1:].strip())
        if text.startswith("="):
            return evaluate(text[1:].strip(), namespace)
    except SpecValueError as e:
        raise SpecCompileError(f"{ctx}: {e}") from None
    raise SpecCompileError(
        f"{ctx}: a dimension must be a bare number (authoring units) or a "
        f"$name / = expression; got {value!r}. Unit-suffixed quantities like "
        f"'8 in' belong at component/placement use-sites, not in params/derived."
    )


def compile_spec(doc: DetailSpecDoc, overrides: dict | None = None) -> SpecDetail:
    """Compile a loaded :class:`DetailSpecDoc` into a runnable
    :class:`SpecDetail`. Structural loading already happened (see
    :mod:`~detailgen.spec.loader`); this resolves vocabulary and values and
    wires the standard machinery. Geometry is built lazily on first
    ``validate``/``build`` (the CadQuery cost is not paid at compile).

    ``overrides`` compiles ONE member of the spec's param family: a
    ``name -> authoring-unit number`` map re-binding named ``params:`` values
    before ``derived:`` recomputes — the declarative twin of
    ``Platform(rail_height=42)``. Omitting it (or passing ``{}``) is the plain,
    byte-identical compile. Unknown / derived / non-numeric overrides are
    teaching :class:`SpecCompileError`\\ s."""
    return SpecDetail(doc, overrides)


def compile_spec_file(path, overrides: dict | None = None) -> SpecDetail:
    """File-level convenience: structurally load the spec at ``path`` (see
    :func:`~detailgen.spec.loader.load_spec_file`) and :func:`compile_spec` it,
    optionally as a param-family member via ``overrides``. The one-call twin of
    loading a ``.py`` detail module and constructing ``Detail(**overrides)``."""
    from .loader import load_spec_file

    return compile_spec(load_spec_file(path), overrides)
