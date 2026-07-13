"""The Construction Process Graph, v1: the fabrication / assembly IR core.

This is FAB-1 of the Construction Process Graph (design: fab-design.md, owner-
approved 2026-07-08). The graph's v1 slice is *fabrication*: per installed part,
the ordered sequence of operations that turns a purchased stick of stock into
the finished, installed solid. The rest of the pipeline used to jump straight
from design intent (a 5/4x6 board, notched around the trunk) to finished
geometry, with nothing representing the operations in between — so the cut list
and the geometry could (and did, retro R28) describe different realities. This
module makes the operations the source of truth and *derives* the installed
geometry from them, so every downstream consumer reads one record.

Three value types and one function:

- :class:`StockRef` — the source material a part is made from (profile, form,
  local cross-section). For a part bought finished and never fabricated the
  stock *is* the part; that case is an empty step list, not a degenerate one.
- :class:`ProcessStep` — one construction-process step. A ``kind`` (an OPEN
  tag, never a closed enum — the v1 kinds ``crosscut``/``ease``/``notch``/
  ``drill`` are all fabrication, and ``cure``/``inspect``/... become new kinds
  with no type change), its parameters, and a ``provenance`` link back to the
  design intent that generated it.
- :class:`ProcessRecord` — one part's ``stock -> ordered steps -> installed
  geometry`` story. The installed geometry is DERIVED (``fold``), never a second
  stored solid that can drift.
- :func:`fold` — apply an ordered step list to stock and return the installed
  solid. Order is load-bearing: a deck board is eased THEN notched
  (``railing.py``), and reversing them is a different solid.

The **fabrication-fold invariant** (:func:`assert_fabrication_fold_invariant`)
is the guard that makes R28's class of defect a build-time failure instead of a
review-time catch a careful reader might miss. See its docstring for the two
clauses.

Authoritative-path decision (fab-design §5/§8, brief FAB-1): the components'
``_build`` **delegates to** ``fold`` — there is exactly ONE path that produces a
fabricated solid, so there is no second copy to drift. ``Component.solid`` still
caches it via the existing ``cache_key`` machinery (never a second stored
solid). The invariant therefore holds *by construction* for every correctly-
delegating component; it exists to catch any FUTURE reintroduction of an
independent geometry path (a subclass that cuts the solid without recording the
step), which is exactly what the CAT-4 / forward-case tests inject.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Errors — teaching errors that name the fix, never bare raises.
# --------------------------------------------------------------------------- #
class FabricationFoldError(AssertionError):
    """The fabrication-fold invariant failed for a part: its installed geometry
    and its declared process steps describe different realities. An
    ``AssertionError`` subclass so existing ``assert``-catching test scaffolding
    still catches it, but with a message that names the part and the fix."""


class ProcessStepIdentityCollision(ValueError):
    """Two steps in one record share a content identity (e.g. two drills
    authored at the identical ``(x, z)`` coordinate). Per fab-design §9 FAB does
    NOT silently renumber or merge — a stable authored key that survives
    insertion is the whole point of keying on content, so a genuine collision is
    a loud limit (INCR-3 precedent), never a silent guess."""


class UnknownProcessStepKind(ValueError):
    """``fold`` was handed a step whose ``kind`` it cannot apply to geometry.
    The v1 geometry-producing kinds are ``crosscut``/``ease``/``notch``/
    ``drill``; a non-geometric process kind (``cure``, ``inspect``) is a valid
    :class:`ProcessStep` but has no place in ``fold`` and must not reach it."""


# --------------------------------------------------------------------------- #
# StockRef
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StockRef:
    """The source material one part is made from.

    ``section`` is the part's LOCAL cross-section ``(y_dim, z_dim)`` in mm —
    the two box dimensions that are not the length. It is oriented in the
    component's own frame so ``fold`` can rebuild the exact stick box the
    component's ``_build`` used (DeckBoard: ``(WIDTH, THICKNESS)``; a 2x6
    Lumber: ``(thickness, depth)``). ``form`` is an open tag (``linear_stick``
    in v1; ``sheet``/``purchased_unit`` later). ``profile`` is the human catalog
    name for the cut list. The purchased-stick length the cut planner packs into
    is deliberately absent here — that is FAB-2's cut-plan surface, not FAB-1's.
    """

    profile: str
    form: str
    section: tuple[float, float]
    material_key: str | None = None


# --------------------------------------------------------------------------- #
# ProcessStep
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProcessStep:
    """One construction-process step: a ``kind``, its parameters, and a
    ``provenance`` link to the design intent that produced it.

    Immutable and byte-stable: ``params`` is stored as a sorted tuple of
    ``(key, value)`` pairs, so two steps built from equal parameters are equal
    and hash equal regardless of construction order. Use the classmethod
    constructors (:meth:`crosscut`, :meth:`ease`, :meth:`notch`, :meth:`drill`)
    rather than the raw initializer — they name the parameters each kind needs.
    """

    kind: str
    params: tuple[tuple[str, Any], ...]
    provenance: str = ""

    def __init__(self, kind: str, params: dict, provenance: str = "") -> None:
        object.__setattr__(self, "kind", str(kind))
        object.__setattr__(
            self, "params", tuple(sorted((str(k), v) for k, v in params.items()))
        )
        object.__setattr__(self, "provenance", str(provenance))

    # -- readable parameter access -----------------------------------------
    def param(self, key: str) -> Any:
        for k, v in self.params:
            if k == key:
                return v
        raise KeyError(f"ProcessStep({self.kind!r}) has no parameter {key!r}")

    def params_dict(self) -> dict:
        return dict(self.params)

    # -- content identity (fab-design §9) ----------------------------------
    @property
    def identity(self) -> tuple:
        """The step's identity WITHIN its record, keyed on authored CONTENT and
        never on position/ordinal — so inserting a step leaves the others'
        identities untouched (the ordinal trap INCR rejected one level up,
        incr-design.md:51-59). A ``drill`` keys on its authored ``(x, z)``
        (diameter is comparable content, not identity, so re-drilling the same
        hole larger reads as a change, not a new hole); a ``notch`` on the
        feature it references; ``crosscut``/``ease`` are one-per-part, so the
        kind alone is a unique key."""
        if self.kind == "drill":
            return ("drill", self.param("x"), self.param("z"))
        if self.kind in ("notch", "bore", "groove"):
            # A material-removing pocket keys on the FEATURE it realises (CL-2):
            # its provenance (the feature's authored id / content key) when it has
            # one, else the feature noun — so re-boring the same feature reads as a
            # change, not a new hole, and two DIFFERENT features never collide.
            return (self.kind, self.provenance or self.param("feature"))
        return (self.kind,)

    # -- constructors, one per v1 kind -------------------------------------
    @classmethod
    def crosscut(cls, to_length_mm: float, provenance: str = "") -> "ProcessStep":
        return cls("crosscut", {"to_length_mm": float(to_length_mm)}, provenance)

    @classmethod
    def ease(cls, radius: float, provenance: str = "", edges: str = "|X") -> "ProcessStep":
        return cls("ease", {"radius": float(radius), "edges": str(edges)}, provenance)

    @classmethod
    def notch(cls, cx: float, cy: float, radius: float, feature: str,
              provenance: str = "") -> "ProcessStep":
        return cls("notch", {"cx": float(cx), "cy": float(cy),
                             "radius": float(radius), "feature": str(feature)},
                   provenance)

    @classmethod
    def bore(cls, cx: float, cy: float, radius: float, feature: str,
             provenance: str = "") -> "ProcessStep":
        """A DESIGNED cylindrical recess (CL-2 ``bore`` FEATURE) — same geometry
        op as a ``notch`` (a full-cylinder pocket through the thickness), but a
        DISTINCT kind so the cut note speaks the feature's own name (a cup hole),
        never the clearance-around-a-member language a notch carries. ``feature``
        is the bore's own noun; the geometry it folds to is identical to a notch
        of the same ``(cx, cy, radius)``."""
        return cls("bore", {"cx": float(cx), "cy": float(cy),
                            "radius": float(radius), "feature": str(feature)},
                   provenance)

    @classmethod
    def drill(cls, x: float, z: float, diameter: float,
              provenance: str = "") -> "ProcessStep":
        return cls("drill", {"x": float(x), "z": float(z),
                             "diameter": float(diameter)}, provenance)

    @classmethod
    def groove(cls, x: float, y: float, length: float, width: float,
               depth: float, feature: str, face: str = "top",
               provenance: str = "") -> "ProcessStep":
        """A rectangular stopped or through groove in a sheet-good face.

        Coordinates are in the part-local XY cutting frame. ``x``/``y`` are
        the lower-left corner, ``length`` runs +X, ``width`` runs +Y, and
        ``depth`` removes material inward from ``top`` (+Z face) or ``bottom``.
        """
        return cls("groove", {
            "x": float(x), "y": float(y), "length": float(length),
            "width": float(width), "depth": float(depth),
            "feature": str(feature), "face": str(face),
        }, provenance)


# --------------------------------------------------------------------------- #
# ProcessRecord
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProcessRecord:
    """One part's fabrication story: ``stock``, an ordered ``steps`` list, and a
    DERIVED installed geometry (``fold(stock, steps)`` — never stored).

    ``steps`` is ordered and the order is semantic (``fold`` applies it strictly
    in order). ``[]`` steps is the honest statement "this part is purchased, not
    made." A content-identity collision among the steps (see
    :attr:`ProcessStep.identity`) is rejected loudly at construction.
    """

    stock: StockRef
    steps: tuple[ProcessStep, ...]
    part_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        seen: dict[tuple, ProcessStep] = {}
        for s in self.steps:
            key = s.identity
            if key in seen:
                raise ProcessStepIdentityCollision(
                    f"{self.part_id or '<part>'}: two {s.kind!r} steps collide on "
                    f"content identity {key!r} — FAB keys operations on authored "
                    f"content (a drill's (x, z), a notch's feature), so two "
                    f"operations at the same content are indistinguishable. Give "
                    f"them distinct authored coordinates/features, or if they are "
                    f"genuinely one operation, declare it once."
                )
            seen[key] = s

    # -- crosscut / stock helpers ------------------------------------------
    def crosscut_length(self) -> float | None:
        """The finished length the ``crosscut`` step cuts stock to (the
        authoritative BOM length, fab-design §5). ``None`` for a purchased-as-is
        part with no crosscut."""
        for s in self.steps:
            if s.kind == "crosscut":
                return s.param("to_length_mm")
        return None

    def stock_volume(self) -> float | None:
        """Volume (mm^3) of the un-fabricated stick — the sharp box after the
        crosscut but before any material-removing step. Analytic (length x the
        two section dims), so it needs no geometry build. ``None`` when there is
        no crosscut to fix the length. This is the reference the invariant's
        material-balance clause measures removed material against."""
        length = self.crosscut_length()
        if length is None:
            return None
        y, z = self.stock.section
        return float(length) * float(y) * float(z)

    def installed_geometry(self):
        """The DERIVED installed solid, ``fold(stock, steps)``. Recomputed on
        demand (fab-design Q1) — the caller is the component's ``_build``, whose
        result ``Component.solid`` already caches via ``cache_key``, so there is
        one caching mechanism and no second stored solid to drift."""
        return fold(self.stock, self.steps)

    # -- carpenter-readable fabrication note (fab-design §6.2, retro R28) ----
    def fab_note(self) -> str:
        """The carpenter-readable fabrication note for this record, DERIVED from
        its own ``steps`` — the SINGLE authoritative fab-note derivation. Both
        the cut-list line (``consolidated_report._cutlist_fab_note`` delegates
        here) and the interactive viewer's hover tooltip
        (``web_viewer.build_viewer_payload``) read this ONE method, so a part's
        cut list and its tooltip can never describe different fabrication (the
        seam that retired retro R28, now also reaching the viewer's pre-FAB
        component-param tooltip).

        v1 names the ``notch`` — the material-removing operation the old cut list
        hid. A record carrying no ``notch`` step gets no note: a plain part,
        truthfully (the absence of the operation is the fact, fab-design §6.2).

        The note reads the FEATURE noun straight off the step's own content (the
        ``feature`` param the record already carries) — it names no domain
        itself. A pocket whose content carries no usable feature noun renders the
        honest generic "(see drawing)" rather than guessing one. The radius shows
        its real value ("1.75\"", not a "2\"" round-off), trailing zeros trimmed
        so a whole-inch radius stays "12\"".

        CL-2 closed the noun gap FAB disclosed here. A ``notch`` (a clearance
        pocket around a MEMBER) speaks that member's name and the tree-face-end
        location ("clearance pocket around the trunk at the tree-face end"); a
        ``bore`` (a DESIGNED recess — the caddy's cup hole) is its OWN kind of
        step carrying its own noun ("cup hole"), so it no longer inherits the
        deck's trunk wording. The kind is what the author declared (clearance_cut
        vs bore), so the note can never mislabel a designed hole as a clearance."""
        from .units import inches

        notes: list[str] = []
        for s in self.steps:
            if s.kind not in ("notch", "bore"):
                continue
            radius = f'{round(inches(s.param("radius")), 3):g}"'
            feature = str(s.param("feature")).strip()
            station = self._station_phrase(s)
            if s.kind == "bore":
                body = (f"{feature} bored clean through the thickness" if feature
                        else "bore through the thickness (see drawing)")
                notes.append(f'bore: {radius} R full-cylinder {body}{station}')
            else:
                body = (f"clearance pocket around the {feature} at the tree-face end"
                        if feature else "clearance pocket (see drawing)")
                notes.append(
                    f'notch: {radius} R full-cylinder {body}, cut through the '
                    f'thickness{station}')
        return " · ".join(notes)

    def _station_phrase(self, step: "ProcessStep") -> str:
        """The cut's STATION — where on the stick to mark before drilling —
        derived from the step's own board-local center and this record's
        crosscut length / section width (the numbers the builder measures
        with a tape from the stick's own ends and edges, before any assembly
        context exists). Added after a naive-builder review of the trebuchet
        document got everything right EXCEPT where along the 48in arm to bore:
        the one number the driller needs was in prose only, never on the
        cut-plan line (the wrong-end bore builds a 1:4 arm). Both distances
        are printed so the mark is checkable from either end; which end is
        which in the ASSEMBLY stays a drawing/label fact, not this line's.
        Degenerate records (no crosscut to fix a length) honestly omit the
        phrase rather than guess. A NOTCH whose center falls outside the
        board's own footprint (a tangential clearance cut around a member
        that only grazes this board) also omits it: a negative tape distance
        is not a station a builder can mark, and the notch's qualitative
        member phrase plus the drawing already locate that cut."""
        from .units import inches

        length = self.crosscut_length()
        if length is None:
            return ""
        cx = float(step.param("cx"))
        cy = float(step.param("cy"))
        width = float(self.stock.section[0]) if self.stock.section else None
        if step.kind == "notch" and not (
                0.0 <= cx <= float(length)
                and (width is None or 0.0 <= cy <= width)):
            return ""
        a, b = inches(cx), inches(length - cx)
        phrase = (f' — center {round(a, 3):g}" from one end '
                  f'({round(b, 3):g}" from the other)')
        if width:
            half = width / 2.0
            if abs(cy - half) <= 0.254:  # within 0.01in of the centerline
                phrase += ", on the width centerline"
            else:
                phrase += (f', {round(inches(cy), 3):g}" from one edge')
        return phrase


# --------------------------------------------------------------------------- #
# fold — apply an ordered step list to stock, return the installed solid.
# --------------------------------------------------------------------------- #
def _rect_point_distance(px: float, py: float,
                         x0: float, x1: float, y0: float, y1: float) -> float:
    """Distance from point ``(px, py)`` to the axis-aligned rectangle
    ``[x0,x1] x [y0,y1]`` (0 if inside). Used to decide whether a notch cylinder
    actually reaches a board's footprint — see :func:`notch_removes_material`."""
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return math.hypot(dx, dy)


def notch_removes_material(cx: float, cy: float, radius: float,
                           length: float, width: float) -> bool:
    """Does a notch cylinder centred at board-local ``(cx, cy)`` with ``radius``
    reach the board footprint ``[0,length] x [0,width]``? This is the §6.2 rule:
    a board the trunk does not cross carries a ``trunk_cut`` whose cylinder falls
    entirely outside its own footprint (a geometric no-op) — the ABSENCE of the
    operation is the fact, so no ``notch`` step is emitted for it and the cut
    list reads "plain", truthfully. Boards the trunk does cross get a real
    ``notch`` step. (Every shipped platform board crosses; the no-op branch is
    exercised by a synthetic board in the tests.)"""
    return _rect_point_distance(cx, cy, 0.0, length, 0.0, width) < radius


def _apply_step(wp, step: ProcessStep, stock: StockRef):
    """Apply one geometry-producing step to a workplane, reproducing exactly the
    boolean/fillet the migrated component's ``_build`` used (so ``fold`` is
    byte-identical to today's geometry, AC1). ``axis_cylinder`` is imported here
    (not at module top) to keep ``core`` free of an import-time dependency on
    ``components``; the geometry is the identical call either way."""
    from ..components._geometry import axis_cylinder  # lazy: avoid core->components cycle

    y_dim, z_dim = stock.section
    if step.kind == "ease":
        radius = step.param("radius")
        if radius > 0:
            try:
                wp = wp.edges(step.param("edges")).fillet(radius)
            except Exception:
                # Easing is cosmetic; a fillet the kernel refuses is skipped, not
                # fatal — matches the migrated _build's own try/except.
                pass
        return wp
    if step.kind in ("notch", "bore"):
        # Full-cylinder pocket through the thickness (+Z), matching
        # DeckBoard._build: axis_cylinder(r, THICKNESS*4, (cx,cy,-THICKNESS), +Z).
        # A ``bore`` (a designed recess) folds to the IDENTICAL geometry as a
        # ``notch`` (a clearance pocket) — the two kinds differ only in the intent
        # the cut note speaks, never in the solid.
        cx, cy, r = step.param("cx"), step.param("cy"), step.param("radius")
        return wp.cut(axis_cylinder(r, z_dim * 4, (cx, cy, -z_dim), (0, 0, 1)))
    if step.kind == "drill":
        # Through-hole along the thickness (+Y), matching Lumber._build:
        # axis_cylinder(d/2, thickness*4, (x, -thickness*2, z), +Y).
        x, z, dia = step.param("x"), step.param("z"), step.param("diameter")
        return wp.cut(axis_cylinder(dia / 2, y_dim * 4, (x, -y_dim * 2, z), (0, 1, 0)))
    if step.kind == "groove":
        import cadquery as cq

        x = step.param("x")
        y = step.param("y")
        length = step.param("length")
        width = step.param("width")
        depth = step.param("depth")
        face = step.param("face")
        if face not in {"top", "bottom"}:
            raise UnknownProcessStepKind(
                f"groove face must be 'top' or 'bottom', got {face!r}"
            )
        z = z_dim - depth if face == "top" else 0.0
        cutter = (
            cq.Workplane("XY")
            .box(length, width, depth, centered=False)
            .translate((x, y, z))
        )
        return wp.cut(cutter)
    raise UnknownProcessStepKind(
        f"fold cannot apply a {step.kind!r} step to geometry — the v1 geometry-"
        f"producing kinds are crosscut/ease/notch/drill/groove. A non-geometric process "
        f"kind (e.g. cure, inspect) is a valid ProcessStep but must not reach fold."
    )


def fold(stock: StockRef, steps) -> Any:
    """Build a part's installed solid by applying ``steps`` to ``stock`` in
    order — the one authoritative fabrication path (fab-design §3).

    The ``crosscut`` step establishes the finished stick box from the stock's
    cross-section; the remaining steps (``ease``/``notch``/``drill``) are applied
    strictly in stored order onto that box. Order is load-bearing: easing before
    notching (as DeckBoard does) is a different solid than the reverse, and
    ``fold`` never reorders. Returns a ``cq.Workplane``. A purchased-as-is part
    (no ``crosscut``, empty or non-geometric steps) has no folded solid — that is
    an honest "this is bought, not made," and callers should not ask ``fold`` for
    one.
    """
    import cadquery as cq  # lazy: keep module import cheap and core-clean

    steps = tuple(steps)
    length = None
    body: list[ProcessStep] = []
    for s in steps:
        if s.kind == "crosscut":
            length = s.param("to_length_mm")
        else:
            body.append(s)
    if length is None:
        raise UnknownProcessStepKind(
            "fold needs a crosscut step to establish the stick length; a "
            "purchased-as-is part (empty steps) is not made from stock and has "
            "no folded solid."
        )
    y_dim, z_dim = stock.section
    wp = cq.Workplane("XY").box(length, y_dim, z_dim, centered=False)
    for s in body:
        wp = _apply_step(wp, s, stock)
    return wp


# --------------------------------------------------------------------------- #
# The fabrication-fold invariant (fab-design §8).
# --------------------------------------------------------------------------- #
#: Volume tolerance (mm^3) below which a removed-material discrepancy is boolean/
#: tessellation float noise, not a real cut. Chosen far above OCCT boolean noise
#: (~1e-6 mm^3 and finer on a non-intersecting cut) and far below the smallest
#: real v1 feature (a ~0.44" drill through a 2x6 removes ~3600 mm^3; the smallest
#: shipped trunk notch removes ~52000 mm^3), so it never masks a real mystery cut
#: nor flaps on noise.
MYSTERY_CUT_TOL_MM3 = 1.0


def _solid_volume(wp) -> float:
    return wp.val().Volume()


def assert_fabrication_fold_invariant(part_id: str, installed_solid, record: ProcessRecord) -> None:
    """Assert the two-clause fabrication-fold invariant for one part, raising a
    :class:`FabricationFoldError` that names the part and the fix if either fails.

    Clause 1 — ``installed geometry == fold(stock, steps)`` byte-identical.
    Catches the FORWARD drift: geometry edited without editing the steps (the
    notch moved, an edge re-eased) — the two now describe different realities.
    Byte-identity uses the same tessellation digest (``geometry_hash``) the
    baseline suite and the solid cache already depend on.

    Clause 2 — every material-removing feature in the installed solid corresponds
    to a declared step, measured as material balance: the solid may not remove
    MORE material than its steps account for. Catches the REVERSE — a "mystery
    cut" with no step behind it, which is exactly the shape of R28
    (retro-index.md:65) running the other way: the trunk notch that hid from the
    BOM was a material-removing feature no representation held. A cut the steps
    do not explain fails here before clause 1 even runs, with a clause-2 message.

    Together they make R28's class — two outputs describing different realities —
    a build-time failure instead of a review-time catch. The invariant holds by
    construction for any component whose ``_build`` delegates to ``fold``; it
    bites on a component whose installed geometry is produced by an independent
    path that has drifted from its record.
    """
    from .buildinfo import geometry_hash  # lazy: core-internal, keeps import cheap

    folded = fold(record.stock, record.steps)
    stock_vol = record.stock_volume()

    # Clause 2 first: a mystery cut (extra material removed) is reported as a
    # missing-step problem, not misattributed to a byte-identity drift.
    if stock_vol is not None:
        declared_removed = stock_vol - _solid_volume(folded)
        actual_removed = stock_vol - _solid_volume(installed_solid)
        if actual_removed > declared_removed + MYSTERY_CUT_TOL_MM3:
            raise FabricationFoldError(
                f"{part_id}: installed geometry removes "
                f"{actual_removed - declared_removed:.1f} mm^3 of material beyond "
                f"what its {len(record.steps)} declared step(s) account for — a "
                f"material-removing feature with no ProcessStep behind it "
                f"(fabrication-fold invariant, clause 2; the reverse of retro "
                f"R28). Declare the operation as a ProcessStep, or remove it from "
                f"the geometry."
            )

    # Clause 1: byte-identity of the installed solid and its declared recipe.
    if geometry_hash(installed_solid) != geometry_hash(folded):
        raise FabricationFoldError(
            f"{part_id}: installed geometry is not byte-identical to "
            f"fold(stock, steps) — the geometry and its {len(record.steps)} "
            f"process step(s) have drifted (fabrication-fold invariant, clause 1). "
            f"Rebuild the installed solid from the steps (make _build delegate to "
            f"fold), or update the steps to match the geometry."
        )


def verify_fabrication(component, part_id: str | None = None) -> None:
    """Build-time guard for one component: derive its :class:`ProcessRecord` and
    assert the fabrication-fold invariant against its freshly-built installed
    geometry. A no-op for a component with no fabrication record (purchased-as-is
    / out of the v1 fabrication scope).

    ``component._build()`` (fresh) is used as the authoritative installed
    geometry rather than ``component.solid``: ``.solid`` may be a BREP reload
    from the persistent cache, whose re-tessellation carries ~1e-10 mm float
    noise (see ``core.buildinfo``) that would false-positive a byte-identity
    check against a fresh ``fold``. Building fresh compares like with like.
    """
    record = _fabrication_record_of(component)
    if record is None:
        return
    pid = part_id or getattr(component, "name", "<part>")
    installed = component._build()
    assert_fabrication_fold_invariant(pid, installed, record)


def verify_assembly_fabrication(assembly) -> None:
    """Build-time guard for a whole assembly: run :func:`verify_fabrication` on
    every fabricated part, keyed by its stable ``Placed.id``. The natural place
    to assert the invariant right after a detail is built."""
    for placed in assembly.parts:
        record = _fabrication_record_of(placed.component)
        if record is None:
            continue
        installed = placed.component._build()
        assert_fabrication_fold_invariant(placed.id, installed, record)


def _fabrication_record_of(component) -> ProcessRecord | None:
    fn = getattr(component, "fabrication_record", None)
    if fn is None:
        return None
    return fn()
