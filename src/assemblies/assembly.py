"""DetailAssembly: compose Components into a construction detail.

Components build themselves in local frames (see each class's datum note); the
assembly owns all placement. There are two ways to place a part, and both
resolve to the **same** stored world transform (a :class:`Frame`):

Mate API (preferred) — position a part by making one of its named datums
coincide with a datum on an already-placed part, in construction vocabulary::

    detail.place(washer, "base").on(nut, "top")            # stack a washer
    detail.place(angle, "base_hole_0_bottom").on(          # seat + spin 180
        washer, "top", rotate=180)

Low-level escape hatch — rotations about the global axes (in list order) then a
translation, for parts positioned off global measurements rather than off a
neighbor::

    detail.add(ledger, at=(0, 0, 0), rotate=[("X", 90)])
    detail.add(lag, at=(4*IN, 0, 5*IN), rotate=[("Y", -90)])

Because a datum encodes a real surface (origin *and* orientation), the mate API
makes a placement sign error unrepresentable rather than a silently valid-but-
wrong solid. Interference and clearance checks between placed parts live in
``detailgen.validation`` and operate on this class.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy

from ..core.base import Component
from ..core.frame import Frame
from ..core.materials import MATERIALS, Material


class SpecReferenceError(KeyError):
    """A validation-spec / mate reference names a part that is not in the
    assembly (a stale id, a typo, or a part removed after the spec was
    written). A subclass of :class:`KeyError` for backward compatibility —
    existing ``except KeyError`` callers keep catching it — but with a clean,
    self-explaining message (naming the bad reference, offering did-you-mean
    suggestions, and listing the known parts) instead of a bare crash deep in a
    check stage. The TRIAGE fix from the RAILFASTEN review: an
    ``expected_overlaps`` entry naming a missing id used to surface as an
    unhandled ``KeyError`` in ``_stage_interference``."""

    def __str__(self) -> str:  # plain KeyError repr-wraps its message
        return self.args[0] if self.args else super().__str__()


def _type_slug(component: Component) -> str:
    """Snake-case tag derived from the component's *type*, e.g. ``HexNut`` ->
    ``hex_nut``. Used as the stem of a stable ``Placed.id`` — deliberately
    independent of the display ``name``, which is free text an author can
    rename without disturbing identity."""
    cls = type(component).__name__.lstrip("_")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cls).lower()


@dataclass(eq=False)
class Placed:
    """A Component with its placement resolved into a world :class:`Frame`.

    ``world_frame`` is canonical — ``world_solid`` uses it and nothing else.
    ``at``/``rotate`` are retained only as informational metadata describing how
    the author expressed the placement (``add`` records its arguments; the mate
    API records the resolved world origin).

    ``id`` is this part's stable identity within the assembly: a type-derived
    slug plus an ordinal (``hex_nut-0``, ``hex_nut-1``, ...), assigned once at
    placement time by :meth:`DetailAssembly._append` in build order. It never
    changes, including if ``component.name`` is edited after placement —
    validation specs and the BOM key on ``id`` for exactly this reason.

    ``eq=False`` keeps identity-based equality/hashing (the default for a
    plain object) rather than the dataclass-generated field-by-field
    comparison: a ``Placed`` *is* a handle, so two instances are only "the
    same part" if they're the same object — this is also what lets handles be
    used directly as ``set``/``dict`` members in validation specs
    (``expected_overlaps={(a, b)}``)."""

    component: Component
    world_frame: Frame
    at: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotate: list[tuple[str, float]] = field(default_factory=list)
    id: str = ""

    @property
    def name(self) -> str:
        return self.component.name

    def world_solid(self) -> cq.Workplane:
        """The component's geometry transformed into assembly coordinates.

        ``.moved`` only sets a new ``TopLoc_Location``; the returned solid
        still shares the underlying OCCT ``TShape`` with the process-wide
        cached local solid (``Component.solid`` / ``_SOLID_CACHE``). That is
        exactly why an exporter must never tessellate THIS result in place —
        the triangulation would land on the shared ``TShape`` and shift a
        later exact ``BoundingBox()``/``Volume()`` read on the same cached
        solid. Callers that mesh use
        :meth:`DetailAssembly.isolated_world_solids` instead; plain readers
        (validation, oracles) use this cheaper shared form."""
        loc = self.world_frame.location
        wp = self.component.solid
        return cq.Workplane("XY").newObject([o.moved(loc) for o in wp.vals()])

    def datum_world(self, name: str) -> Frame:
        """A named local datum of this part, expressed in world coordinates."""
        return self.world_frame.compose(self.component.datum(name))


@dataclass
class _Mate:
    """Fluent placement builder returned by ``DetailAssembly.place``. Complete
    it with ``.on(target, target_datum, ...)``."""

    assembly: "DetailAssembly"
    component: Component
    part_datum: str

    def on(
        self,
        target: "Placed | str",
        target_datum: str = "top",
        *,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotate: float = 0.0,
        flip: bool = False,
    ) -> "Placed":
        """Place the component so its ``part_datum`` coincides with ``target``'s
        ``target_datum``. Remaining degrees of freedom are named modifiers,
        all resolved in the target datum frame:

        - ``offset=(dx, dy, dz)``: shift along the target datum axes; ``dz`` > 0
          opens a standoff gap along the mate normal.
        - ``rotate=degrees``: spin the part about the mate normal (+Z).
        - ``flip=True``: turn the part end-for-end (180 deg about the datum X),
          reversing its +Z for the occasional part that seats the other way.
        """
        tgt = self.assembly._resolve(target)
        seat = tgt.datum_world(target_datum)

        # Modifiers are expressed in the seat (target datum) frame:
        # translate (offset), then flip, then spin about the normal.
        modifier = Frame.translation(tuple(float(v) for v in offset))
        if flip:
            modifier = modifier.compose(Frame.rotation(180, axis=(1, 0, 0)))
        if rotate:
            modifier = modifier.compose(Frame.rotation(float(rotate), axis=(0, 0, 1)))
        seat = seat.compose(modifier)

        part_local = self.component.datum(self.part_datum)
        world_frame = seat.compose(part_local.inverse())
        return self.assembly._append(
            self.component, world_frame, at=world_frame.origin, rotate=[]
        )


class DetailAssembly:
    def __init__(self, name: str):
        self.name = name
        self.parts: list[Placed] = []
        self._id_seq: dict[str, int] = {}

    # -- placement -------------------------------------------------------------

    def add(
        self,
        component: Component,
        at: tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotate: list[tuple[str, float]] | None = None,
    ) -> Placed:
        """Low-level placement: ``rotate`` is a list of ("X"|"Y"|"Z", degrees)
        applied in order about the **global** axes, then a translation. Prefer
        ``place(...).on(...)`` for parts that seat on a neighbor; use ``add`` for
        parts positioned off global measurements."""
        at = tuple(float(v) for v in at)
        rotate = list(rotate or [])
        world_frame = Frame.from_at_rotate(at, rotate)
        return self._append(component, world_frame, at=at, rotate=rotate)

    def place(self, component: Component, part_datum: str = "origin") -> _Mate:
        """Begin a datum mate: ``place(part, "base").on(other, "top")``. The
        placement is completed (and the part added) by the returned builder's
        ``.on`` call."""
        return _Mate(self, component, part_datum)

    def _append(
        self,
        component: Component,
        world_frame: Frame,
        at: tuple[float, float, float],
        rotate: list[tuple[str, float]],
    ) -> Placed:
        if any(p.name == component.name for p in self.parts):
            raise ValueError(
                f"Duplicate part name {component.name!r} — give parts unique "
                f"names so validation reports are unambiguous"
            )
        slug = _type_slug(component)
        seq = self._id_seq.get(slug, 0)
        self._id_seq[slug] = seq + 1
        placed = Placed(component, world_frame, tuple(float(v) for v in at),
                        list(rotate), id=f"{slug}-{seq}")
        self.parts.append(placed)
        return placed

    def _resolve(self, ref: "Placed | str") -> Placed:
        """Resolve a mate target or validation-spec reference into the
        ``Placed`` part it names. This is the *one* place both the mate API
        (``place().on()``) and validation specs (``validate_assembly``,
        ``check_no_floaters``, ...) turn a reference into a part, so a typo
        or a stale reference fails the same helpful way everywhere.

        Accepts a ``Placed`` handle (checked by identity against this
        assembly's own parts — a handle from a different assembly is a bug,
        never silently treated as a match) or a display name (matched by
        current ``name``, so it follows a rename). An unresolvable reference
        always raises, listing every part actually in the assembly — never a
        bare ``KeyError`` that leaves the offender unnamed."""
        known = [f"{p.name!r} ({p.id})" for p in self.parts]
        if isinstance(ref, Placed):
            for p in self.parts:
                if p is ref:
                    return p
            raise SpecReferenceError(
                f"handle {ref.name!r} ({ref.id}) is not a part of assembly "
                f"{self.name!r}{self._did_you_mean(ref.name)} — "
                f"known parts: {known}"
            )
        for p in self.parts:
            if p.name == ref:
                return p
        raise SpecReferenceError(
            f"no part named {ref!r} in assembly {self.name!r}"
            f"{self._did_you_mean(ref)} — known parts: {known}"
        )

    def _did_you_mean(self, ref) -> str:
        """A `` — did you mean 'x', 'y'?`` fragment for the closest existing
        part names to ``ref`` (fuzzy, difflib), or ``""`` when nothing is
        close. Turns a stale/typo'd reference into a one-glance fix."""
        if not isinstance(ref, str):
            return ""
        names = [p.name for p in self.parts]
        close = difflib.get_close_matches(ref, names, n=3, cutoff=0.6)
        if not close:
            return ""
        suggestions = ", ".join(repr(n) for n in close)
        return f" — did you mean {suggestions}?"

    # -- outputs ---------------------------------------------------------------

    def isolated_world_solids(self):
        """Yield ``(placed, world Workplane)`` for every part, where each solid
        gets its OWN OCCT ``TShape``/``TFace`` (via ``BRepBuilderAPI_Copy``) —
        sharing no topology node with the process-wide solid cache
        (``Component.solid`` / ``_SOLID_CACHE``). A triangulation a mesh-
        emitting exporter builds therefore lands on the copy's ``TFace``, never
        the cache's, so a cached solid's later exact ``BoundingBox()`` /
        ``Volume()`` read is untouched. This is the source-level fix for the
        export-mutates-geometry contamination; the tessellating exporters
        (GLB, STL, PNG) consume it, ordinary readers use the cheaper shared
        :meth:`Placed.world_solid`.

        The copy is made ONCE per unique ``cache_key`` and reused across every
        placement of that component (memoized below), so identical parts —
        e.g. a detail's repeated washers/bolts — still mesh only once, exactly
        the sharing ``world_solid`` inherited for free from the cache. Without
        this memo, a 124-part detail meshed all 124 solids instead of its ~23
        distinct geometries (measured ~8x slower on GLB export).

        ``copyGeom=False``: copy only the topology, SHARE the underlying
        ``Geom`` surfaces/curves. Isolation lives entirely in the ``TFace``
        (where OCCT stores triangulation), so sharing the heavy geometry is
        safe and avoids a full deep copy; ``copyMesh`` defaults ``False`` so no
        stale mesh is carried onto the copy."""
        memo: dict = {}
        for p in self.parts:
            key = p.component.cache_key()
            iso = memo.get(key)
            if iso is None:
                iso = [cq.Shape.cast(BRepBuilderAPI_Copy(o.wrapped, False).Shape())
                       for o in p.component.solid.vals()]
                memo[key] = iso
            loc = p.world_frame.location
            yield p, cq.Workplane("XY").newObject([o.moved(loc) for o in iso])

    def to_cq_assembly(self, isolated: bool = False) -> cq.Assembly:
        """Colored cq.Assembly (used by all exporters in detailgen.rendering).

        ``isolated=True`` builds it from cache-isolated world solids
        (:meth:`isolated_world_solids`) so a mesh-emitting exporter cannot
        mutate cached geometry — the GLB exporter passes it; STEP (BREP, never
        tessellates) does not need it."""
        asm = cq.Assembly(name=self.name)
        if isolated:
            for p, wp in self.isolated_world_solids():
                mat: Material = p.component.material
                asm.add(wp, name=p.name, color=cq.Color(*mat.rgba))
        else:
            for p in self.parts:
                mat = p.component.material
                asm.add(p.world_solid(), name=p.name, color=cq.Color(*mat.rgba))
        return asm

    def compound(self, isolated: bool = False) -> cq.Compound:
        """All world-space solids fused into one Compound (STL, bbox).

        ``isolated=True`` (used by the STL exporter) fuses cache-isolated world
        solids (:meth:`isolated_world_solids`) so meshing the compound cannot
        poison the shared solid cache; the default shared form is for plain
        readers (bbox, geometry_hash, which copies internally already)."""
        if isolated:
            solids = [s for _, wp in self.isolated_world_solids() for s in wp.vals()]
        else:
            solids = [s for p in self.parts for s in p.world_solid().vals()]
        return cq.Compound.makeCompound(solids)

    def check(self) -> list[str]:
        """Aggregate parameter problems from every part."""
        problems: list[str] = []
        for p in self.parts:
            problems.extend(p.component.check())
        return problems

    def _part_row(self, p: Placed) -> dict:
        """Canonical per-part BOM data — the SINGLE source both ``bom`` (flat,
        per-part) and ``bom_table`` (aggregated by quantity) derive from, so the
        two paths can never disagree about a part's material, group or identity.
        Everything either shape needs is computed here exactly once."""
        c = p.component
        return {
            "id": p.id,
            "name": p.name,
            "type": type(c).__name__,
            "material": c.material.name,
            "item": c.bom_label(),
            "dimensions": c.describe(),
            "source": getattr(c, "source", "generated"),
            "assumptions": c.assumptions(),
            "group": c.bom_group(),
            "params": c.params(),
            "length_mm": c.bom_length_mm(),
            "stub_of": c.stub_of(),
        }

    def bom(self) -> list[dict]:
        """Flat per-part rows (id, name, type, material + the part's public
        params). Derived from :meth:`_part_row`."""
        rows = []
        for p in self.parts:
            r = self._part_row(p)
            rows.append({"id": r["id"], "name": r["name"], "type": r["type"],
                         "material": r["material"], **r["params"]})
        return rows

    def bom_table(self) -> list[dict]:
        """Aggregated bill of materials: identical parts collapse into one row
        with a quantity. Columns: item, qty, material, dimensions, source,
        assumptions, ids, length_mm. Aggregation keys on ``bom_group()`` (type
        + description) — never on the display name — so renaming a part can't
        split or duplicate a row; ``ids`` lists the stable id of every part
        folded into the row, for tracing a BOM line back to specific parts.
        ``source`` is always 'generated' for parametric parts; ``load_step``
        imports report 'imported STEP'. ``length_mm`` is the machine-readable
        cut length from :meth:`Component.bom_length_mm` (``None`` for parts
        with no single length axis) — every part folded into one group is, by
        construction of ``bom_group``, geometrically identical, so they share
        one ``length_mm`` value; added for cut-planning (``core.cutplan``)
        that needs a real number rather than ``describe()``'s display string.
        ``stub_of`` (from :meth:`Component.stub_of`) is likewise shared across
        a group's identical parts — ``None`` for ordinary parts, else the
        partial-member metadata the interactive-viewer tooltip reads.
        Derived from the same :meth:`_part_row` as :meth:`bom`."""
        groups: dict[str, dict] = {}
        for p in self.parts:
            r = self._part_row(p)
            key = r["group"]
            if key not in groups:
                groups[key] = {
                    "item": r["item"],
                    "qty": 0,
                    "material": r["material"],
                    "dimensions": r["dimensions"],
                    "source": r["source"],
                    "assumptions": r["assumptions"],
                    "ids": [],
                    "length_mm": r["length_mm"],
                    "stub_of": r["stub_of"],
                }
            groups[key]["qty"] += 1
            groups[key]["ids"].append(r["id"])
        return list(groups.values())


def load_step(path: str, name: str, material_key: str = "steel_galv") -> Component:
    """Wrap a manufacturer STEP file (assets/manufacturer/) as a Component
    so it can be placed, validated and colored like native parts."""

    class _ImportedPart(Component):
        def __init__(self):
            super().__init__(name)
            self.material_key = material_key
            self.path = path
            self.source = "imported STEP"

        def _build(self) -> cq.Workplane:
            return cq.importers.importStep(path)

    return _ImportedPart()
