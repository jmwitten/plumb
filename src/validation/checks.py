"""Geometric validation for assembled details.

Three kinds of checks, all reported through ValidationReport:

1. **Interference** — pairwise boolean intersection of placed parts. Solid
   parts must not overlap; fasteners are *expected* to intersect the wood
   they're driven into, so pairs can be allowlisted with an expected-overlap
   volume cap.
2. **Contact** — parts that are supposed to touch (bear on each other)
   actually do, within tolerance.
3. **Dimension** — assert a measured value (extracted by the caller from
   geometry) matches the design intent.

Typical use, at the bottom of every detail script:

    report = validate_assembly(
        detail,
        expected_overlaps={("lag 1", "ledger"), ("lag 1", "rim joist")},
    )
    report.require_clean()   # raises on failures -> broken details can't export
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import NamedTuple

import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from ..assemblies.assembly import DetailAssembly, Placed
from ..core import buildinfo
from ..core.config import DEFAULT, Tolerances
from ..core.diskcache import DiskCache
from ..core.registry import checks, register_check
from ..core.units import IN, fmt_in

_AXV = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}

#: Persistent per-pair verdict cache — S3c lever (d). Each check function
#: below maps its OWN complete input surface into its cache key (the "map
#: each check's inputs" honesty rule from the task brief: a check is only
#: wired into this cache once every value it reads is accounted for).
#: ``check_dimension`` never touches OCCT (pure arithmetic on
#: caller-supplied floats) and is deliberately NOT cached — nothing here
#: is expensive enough to be worth memoizing.
_VERDICT_CACHE = DiskCache("verdicts")


def _checks_code_fingerprint() -> str:
    """sha256 over this module's own source plus ``core/config.py``
    (``Tolerances``'s field definitions and derived-property formulas —
    e.g. ``near_miss``/``push``/``bearing_area_threshold`` — which several
    checks below read through ``tol`` without re-deriving each field
    individually). A behavior change in either file must invalidate every
    persisted verdict, by the same code-version-salting rule the solid
    cache follows (``core.base._component_geometry_fingerprint``).
    Computed once per process — see ``_CHECKS_FP`` below."""
    paths = [Path(__file__), Path(__file__).resolve().parent.parent / "core" / "config.py"]
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()


_CHECKS_FP = _checks_code_fingerprint()


def _load_finding(key: str, check: str, subject: str) -> "Finding | None":
    """Fetch a cached ``(passed, detail)`` verdict and reconstruct a
    ``Finding`` with the CURRENT ``check``/``subject`` text — those two
    fields are never persisted. ``subject`` is derived from the parts'
    CURRENT display names, which are not part of any check's geometric
    input surface (renaming a part can't change whether it interferes with
    another) — reconstructing it fresh at hit time is not just cheaper
    than persisting it, it's the more correct choice, since a persisted
    name could go stale the moment a part is renamed between runs. Any
    failure (missing entry, corrupt JSON) is a miss, never an exception —
    see ``core.diskcache`` module docstring."""
    data = _VERDICT_CACHE.get(key)
    if data is None:
        return None
    try:
        payload = json.loads(data)
        return Finding(check, subject, payload["passed"], payload["detail"])
    except Exception:
        return None


def _store_finding(key: str, finding: Finding) -> None:
    try:
        payload = json.dumps({"passed": finding.passed, "detail": finding.detail}).encode()
    except Exception:
        return
    _VERDICT_CACHE.put(key, payload)


#: The three verdicts a Finding may carry. PASS/FAIL are the historical two;
#: UNKNOWN (task SUPPORT) is a check that RAN but could not resolve its question
#: — it is NON-passing and BLOCKING, distinct from a family that was never
#: analyzed. Emitters today: the support-obligation check (a rung-3 support
#: obligation whose adequacy is not determinable), the foundation-capacity
#: obligation, the install-method core invariant (fastener hardware with no
#: resolvable installation contract), and the installability axis checks
#: (``validation/install.py`` — a tool corridor occupant that the
#: construction process graph relates to the fastener by NO order fact is
#: ``UNKNOWN — build order underdetermined``, naming the occupant and the
#: missing order fact).
PASS_VERDICT = "PASS"
FAIL_VERDICT = "FAIL"
UNKNOWN_VERDICT = "UNKNOWN"


@dataclass
class Finding:
    check: str      # "interference" | "contact" | "dimension"
    subject: str    # what was checked, e.g. "ledger <-> rim joist"
    passed: bool
    detail: str = ""
    #: "" -> derive from ``passed`` (PASS/FAIL, the historical behavior); set
    #: explicitly to ``UNKNOWN_VERDICT`` for an unresolved-but-blocking finding.
    #: An UNKNOWN finding is forced non-passing so it blocks export.
    verdict: str = ""
    #: STEPDOC owner amendment 3 (task CPGCORE, review F-2): True when this
    #: verdict's deciding order facts are DECLARED claims (an axis-3 clear
    #: at a declared build order). STRUCTURED so the coverage summaries'
    #: declared-trust marker can never silently decouple from a re-worded
    #: verdict sentence. Set only by the axis-3 access clears, which are
    #: deliberately never verdict-cached (the cache round-trip persists
    #: only passed/detail).
    declared_order: bool = False

    def __post_init__(self) -> None:
        if not self.verdict:
            self.verdict = PASS_VERDICT if self.passed else FAIL_VERDICT
        elif self.verdict == UNKNOWN_VERDICT:
            self.passed = False  # unknown never certifies

    @property
    def blocking(self) -> bool:
        """This finding stops a clean export: a FAIL, or an unresolved UNKNOWN
        (the directive's "never CLEAN when support is unanswerable")."""
        return self.verdict in (FAIL_VERDICT, UNKNOWN_VERDICT)

    def __str__(self) -> str:
        return f"[{self.verdict}] {self.check}: {self.subject}" + (
            f" — {self.detail}" if self.detail else ""
        )


@dataclass
class ValidationReport:
    assembly_name: str
    findings: list[Finding] = field(default_factory=list)

    #: Bbox-prefilter audit trail for the pairwise interference sweep (P1,
    #: directive #8's honesty rule): every pair is accounted for, so a
    #: silent skip is structurally impossible to introduce without also
    #: breaking `pairs_prefiltered + pairs_fully_checked == pairs_total`.
    #: All zero when `validate_assembly` declares no parts / isn't called.
    pairs_total: int = 0
    pairs_prefiltered: int = 0
    pairs_fully_checked: int = 0
    prefilter_threshold_mm: float = 0.0

    #: Persistent verdict-cache audit trail (S3c lever d, P1's honesty
    #: rule): of the pairs NOT bbox-prefiltered above (`pairs_fully_
    #: checked`), how many were satisfied from a prior run's cached
    #: verdict instead of a fresh boolean-intersection. Always
    #: `<= pairs_fully_checked`; 0 on an empty/disabled cache.
    pairs_from_cache: int = 0

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def failures(self) -> list[Finding]:
        """True FAIL findings only (unchanged from the two-verdict era — an
        UNKNOWN is not a failure). Drives the FAIL counts and messaging."""
        return [f for f in self.findings if f.verdict == FAIL_VERDICT]

    @property
    def unresolved(self) -> list[Finding]:
        """UNKNOWN findings — a check ran but could not resolve (task SUPPORT).
        Blocking but not a failure; reported with its own verdict word."""
        return [f for f in self.findings if f.verdict == UNKNOWN_VERDICT]

    @property
    def blocking(self) -> list[Finding]:
        """Everything that stops a clean export: FAILs + unresolved UNKNOWNs.
        The directive: never CLEAN when a support obligation is unanswerable."""
        return [f for f in self.findings if f.blocking]

    @property
    def ok(self) -> bool:
        return not self.blocking

    def coverage_matrix(self) -> list:
        """Per-invariant-family coverage (Wave 3-1): PASS / FAIL / UNKNOWN —
        NOT ANALYZED, derived from this report's findings. See
        :mod:`detailgen.validation.coverage`. One
        :class:`~detailgen.validation.coverage.FamilyCoverage` per family, in
        canonical order."""
        from .coverage import coverage_matrix
        return coverage_matrix(self)

    def coverage_payload(self) -> list:
        """JSON-serializable form of :meth:`coverage_matrix` for the
        manifest/report payload."""
        from .coverage import coverage_payload
        return coverage_payload(self)

    def require_clean(self) -> None:
        """Raise if anything blocks — call before exporting a detail. Blocks on
        FAILs AND on unresolved UNKNOWNs (a support obligation that ran but could
        not be answered — the directive's "never CLEAN when support is
        unanswerable"). The message names each blocker with its verdict word so
        a FAIL and an UNKNOWN are never conflated."""
        blockers = self.blocking
        if blockers:
            lines = "\n".join(str(f) for f in blockers)
            n_fail = len(self.failures)
            n_unknown = len(self.unresolved)
            parts = []
            if n_fail:
                parts.append(f"{n_fail} validation failure(s)")
            if n_unknown:
                parts.append(f"{n_unknown} unresolved (UNKNOWN, blocking)")
            raise AssertionError(
                f"{self.assembly_name}: {' + '.join(parts)}:\n{lines}"
            )

    def __str__(self) -> str:
        if self.ok:
            state = "CLEAN"
        else:
            bits = []
            if self.failures:
                bits.append(f"{len(self.failures)} FAILURE(S)")
            if self.unresolved:
                bits.append(f"{len(self.unresolved)} UNRESOLVED")
            state = ", ".join(bits)
        header = f"Validation: {self.assembly_name} — {state}"
        return "\n".join([header] + [f"  {f}" for f in self.findings])


def _overlap_volume(a: Placed, b: Placed) -> float:
    """Boolean-intersection volume of two placed parts, in mm^3."""
    inter = a.world_solid().intersect(b.world_solid())
    return sum(s.Volume() for s in inter.vals()) if inter.vals() else 0.0


class _AABB(NamedTuple):
    xmin: float; xmax: float
    ymin: float; ymax: float
    zmin: float; zmax: float


def _part_bbox(p: Placed) -> _AABB:
    """Axis-aligned bounding box of a placed part, covering EVERY solid it
    contributes — not just the first.

    ``world_solid()`` returns a ``Workplane`` that can hold more than one
    ``Shape`` (a multi-body/non-unioned component), and ``_overlap_volume``
    intersects against ALL of them (``Workplane.intersect`` operates on the
    whole compound). Reading only ``.val()`` (the first shape) would let the
    prefilter's box shrink below what the exact check actually acts on for
    such a part — silently breaking the "box is a conservative superset of
    the geometry" argument the whole prefilter's correctness rests on, in a
    way that would never show up on today's single-solid parts (verified: no
    placed part in any of the 4 shipped details has more than one solid) but
    is a structural risk for any future part shape. Single-solid parts (the
    common case) pay one extra, already-cheap ``.vals()`` list access."""
    boxes = [s.BoundingBox() for s in p.world_solid().vals()]
    return _AABB(
        xmin=min(b.xmin for b in boxes), xmax=max(b.xmax for b in boxes),
        ymin=min(b.ymin for b in boxes), ymax=max(b.ymax for b in boxes),
        zmin=min(b.zmin for b in boxes), zmax=max(b.zmax for b in boxes),
    )


def _aabb_gap(ba, bb) -> float:
    """Max-over-axes separating gap (mm) between two AABBs (``_AABB`` or any
    object with matching ``xmin``/``xmax``/... attributes, e.g. a cadquery
    ``BoundBox``); ``0.0`` whenever they overlap or touch on every axis (same
    per-axis logic as ``check_contact``, generalized to 3 axes at once).
    A positive result means the boxes are provably disjoint by that much."""
    return max(
        ba.xmin - bb.xmax, bb.xmin - ba.xmax,
        ba.ymin - bb.ymax, bb.ymin - ba.ymax,
        ba.zmin - bb.zmax, bb.zmin - ba.zmax,
        0.0,
    )


def _interference_key(a: Placed, b: Placed, allowed: bool,
                      max_volume: float | None, tol: Tolerances) -> str:
    """check_interference's complete input surface: it reads ONLY
    ``a.world_solid()``/``b.world_solid()`` (through ``.intersect()``'s
    volume) and ``tol.noise_volume`` — nothing else about ``tol``. A
    boolean-intersection volume is invariant under ANY simultaneous rigid
    motion applied to both operands (rotate/translate the whole pair
    together and the intersection volume is unchanged), so this keys on
    the RELATIVE transform between a and b, not either part's absolute
    world pose — a whole-assembly move that leaves this pair's relative
    placement untouched must still hit."""
    return (
        f"interference|{_CHECKS_FP}|"
        f"{buildinfo.local_geometry_digest(a.component)}|"
        f"{buildinfo.local_geometry_digest(b.component)}|"
        f"{buildinfo.relative_transform_digest(a.world_frame, b.world_frame)}|"
        f"{allowed}|{max_volume}|{tol.noise_volume}"
    )


def check_interference(
    a: Placed,
    b: Placed,
    allowed: bool = False,
    max_volume: float | None = None,
    tol: Tolerances = DEFAULT,
) -> Finding:
    """One pair. ``allowed=True`` for pairs meant to overlap (fastener in
    wood); ``max_volume`` optionally caps even an allowed overlap."""
    subject = f"{a.name} <-> {b.name}"
    key = _interference_key(a, b, allowed, max_volume, tol)
    cached = _load_finding(key, "interference", subject)
    if cached is not None:
        return cached
    vol = _overlap_volume(a, b)
    if vol <= tol.noise_volume:
        finding = Finding("interference", subject, True, "no overlap")
    elif allowed and (max_volume is None or vol <= max_volume):
        finding = Finding("interference", subject, True,
                          f"expected overlap {vol:.0f} mm³")
    else:
        finding = Finding("interference", subject, False,
                          f"unexpected overlap {vol:.0f} mm³")
    _store_finding(key, finding)
    return finding


def _min_distance(a: Placed, b: Placed) -> float:
    """True minimum surface-to-surface distance (mm) via OpenCascade."""
    ext = BRepExtrema_DistShapeShape(
        a.world_solid().val().wrapped, b.world_solid().val().wrapped)
    ext.Perform()
    return ext.Value()


def _contact_key(a: Placed, b: Placed, tolerance: float) -> str:
    """check_contact's complete input surface: each part's WORLD
    axis-aligned bounding box (``tolerance`` is already resolved to its
    final scalar by the caller, so no separate ``tol`` fingerprint is
    needed once that's in the key). A ``BoundBox`` is computed against the
    WORLD X/Y/Z axes, NOT either part's local axes — rotating the whole
    pair together changes each box's extents even though the pair's
    relative placement is unchanged — so, unlike interference, this must
    key on each part's ABSOLUTE world pose (``world_part_digest``, the
    same digest ``build_manifest`` uses for a part hash), not a relative
    transform."""
    return (
        f"contact|{_CHECKS_FP}|"
        f"{buildinfo.world_part_digest(a.component, a.world_frame)}|"
        f"{buildinfo.world_part_digest(b.component, b.world_frame)}|"
        f"{tolerance}"
    )


def check_contact(a: Placed, b: Placed, tolerance: float | None = None,
                  tol: Tolerances = DEFAULT) -> Finding:
    """Bounding-box gap contact test (cheap, coarse). Retained for simple
    rectilinear details; ``check_bearing`` is the rigorous version.

    ``tolerance`` overrides ``tol.contact_bbox_tolerance`` directly if given.
    """
    if tolerance is None:
        tolerance = tol.contact_bbox_tolerance
    subject = f"{a.name} <-> {b.name}"
    key = _contact_key(a, b, tolerance)
    cached = _load_finding(key, "contact", subject)
    if cached is not None:
        return cached
    ba = a.world_solid().val().BoundingBox()
    bb = b.world_solid().val().BoundingBox()
    gaps = []
    for lo_a, hi_a, lo_b, hi_b in (
        (ba.xmin, ba.xmax, bb.xmin, bb.xmax),
        (ba.ymin, ba.ymax, bb.ymin, bb.ymax),
        (ba.zmin, ba.zmax, bb.zmin, bb.zmax),
    ):
        gaps.append(max(lo_a - hi_b, lo_b - hi_a, 0.0))
    gap = max(gaps)
    if gap < tolerance:
        finding = Finding("contact", subject, True, f"gap {gap:.2f} mm")
    else:
        finding = Finding("contact", subject, False,
                          f"gap {fmt_in(gap)} — parts don't bear")
    _store_finding(key, finding)
    return finding


def _bearing_key(a: Placed, b: Placed, axis: str, min_area: float,
                 tol: Tolerances) -> str:
    """check_bearing's complete input surface: the initial min-distance
    gate is relative-invariant (a true min-distance doesn't care about
    absolute pose), but the face-contact proof pushes ``b`` along a FIXED
    WORLD axis (``_AXV[axis]`` is e.g. literal ``(0, 0, 1)`` in world
    coordinates, not either part's local frame) — rotating the whole pair
    together changes the push direction relative to the parts' own
    surfaces, so the measured bearing area is NOT relative-invariant.
    Must key on each part's ABSOLUTE world pose, like check_contact.
    Reads nearly every ``Tolerances`` field (``near_miss``/``contact_eps``/
    ``push`` all derive from ``base``; ``bearing_area_threshold`` reads
    ``bearing_area_ratio``/``bearing_area_floor`` too) — cheaper and more
    honest to key on the whole tolerances object than enumerate each
    field."""
    return (
        f"bearing|{_CHECKS_FP}|"
        f"{buildinfo.world_part_digest(a.component, a.world_frame)}|"
        f"{buildinfo.world_part_digest(b.component, b.world_frame)}|"
        f"{axis.upper()}|{min_area}|{tol!r}"
    )


def check_bearing(a: Placed, b: Placed, axis: str,
                  min_area: float = 0.0, tol: Tolerances = DEFAULT) -> Finding:
    """Rigorous flush-bearing check: true min-distance must be ~0 AND a face
    (not an edge/point) must be in contact.

    The face proof pushes ``b`` by a small epsilon toward ``a`` along ``axis``
    and measures the resulting overlap volume; overlap / push = bearing area.
    A real face contact yields ``area ~ contact_area``; an edge or point kiss
    yields ~0. ``min_area`` (mm^2) is the smallest acceptable bearing area.
    """
    subject = f"{a.name} <-> {b.name}"
    key = _bearing_key(a, b, axis, min_area, tol)
    cached = _load_finding(key, "bearing", subject)
    if cached is not None:
        return cached
    d = _min_distance(a, b)
    if d > tol.near_miss:
        finding = Finding("bearing", subject, False,
                          f"gap {fmt_in(d, 3)} — no contact")
    elif d > tol.contact_eps:
        finding = Finding("bearing", subject, False,
                          f"near miss {d:.4f} mm — likely arithmetic error")
    else:
        n = _AXV[axis.upper()]
        sa = a.world_solid()
        sb = b.world_solid()
        best = 0.0
        for sign in (1, -1):
            moved = sb.translate(tuple(sign * tol.push * v for v in n))
            inter = sa.val().intersect(moved.val())
            vol = inter.Volume() if inter else 0.0
            best = max(best, vol)
        area = best / tol.push
        if area >= tol.bearing_area_threshold(min_area):
            finding = Finding("bearing", subject, True,
                              f"flush, bearing area {area / (IN * IN):.2f} in²")
        else:
            finding = Finding("bearing", subject, False,
                              f"edge/point kiss (area {area / (IN * IN):.3f} in² "
                              f"< {min_area / (IN * IN):.2f})")
    _store_finding(key, finding)
    return finding


def dimension_subject(prose: str, part=None) -> str:
    """A dimension Finding's subject: the design-intent ``prose``, then the
    part(s) it MEASURES, in a shape the finding-subject parsers already slice
    (``views._subject_part_ids`` / ``evidence._subject_part_ids``):
    ``<prose>: <partA> <-> <partB>``. ``part`` is a display name, an iterable of
    display names, or ``None``.

    SM4 item 2 (rev-sm2 follow-up): a dimension subject used to be PROSE ONLY
    (``leg held 1/2" above rock``), so it named no resolvable part and fell in no
    view's findings slice — the honesty gap rev-sm2 flagged. Carrying the part
    name(s) after a ``: `` (the label→parts shape the parsers key on) makes the
    finding sliceable WITHOUT a new parser case: the leading prose is the label,
    the part(s) are the tail. ``None`` leaves the bare prose (the pre-SM4
    behavior — used only where no part is meaningful)."""
    names = [part] if isinstance(part, str) else [p for p in (part or []) if p]
    return f"{prose}: {' <-> '.join(names)}" if names else prose


def check_dimension(
    subject: str,
    actual: float,
    expected: float,
    tolerance: float | None = None,
    tol: Tolerances = DEFAULT,
    part=None,
) -> Finding:
    """Assert a measured mm value equals design intent.

    ``tolerance`` overrides ``tol.dimension_tolerance`` directly if given.
    ``part`` (a display name or iterable of them) is folded into the subject via
    :func:`dimension_subject` so the finding names the member(s) it measures.
    """
    if tolerance is None:
        tolerance = tol.dimension_tolerance
    ok = abs(actual - expected) <= tolerance
    return Finding(
        "dimension", dimension_subject(subject, part), ok,
        f"actual {fmt_in(actual)} vs expected {fmt_in(expected)}",
    )


def _through_hole_key(plate: Placed, axis: str, point: tuple,
                      shank_radius: float, hole_radius: float, span: float,
                      tol: Tolerances) -> str:
    """check_through_hole's complete input surface, per plate: the probe
    cylinders are built directly in WORLD coordinates from ``axis``/
    ``point`` (both given, not derived from any Placed's transform), so
    only the PLATE's absolute world pose matters (``world_part_digest``) —
    ``fastener`` is never read for anything but its display name (its
    world_solid() is never touched), so it's deliberately absent from the
    key; ``fastener.name`` is folded into ``subject`` at hit time instead,
    same reasoning as ``_load_finding``'s docstring."""
    return (
        f"through_hole|{_CHECKS_FP}|"
        f"{buildinfo.world_part_digest(plate.component, plate.world_frame)}|"
        f"{axis.upper()}|{point}|{shank_radius}|{hole_radius}|{span}|"
        f"{tol.noise_volume}"
    )


def check_through_hole(fastener: Placed, plates: list[Placed], axis: str,
                       point: tuple, shank_radius: float,
                       hole_radius: float, span: float,
                       tol: Tolerances = DEFAULT) -> list[Finding]:
    """Confirm a fastener passes through actual holes in the plates on its axis.

    Two probes along the fastener axis: a shank-radius cylinder must NOT hit any
    plate (clearance exists), and a slightly-oversized cylinder MUST hit every
    plate (the hole is where we think it is, and each plate is on-axis).
    """
    n = cq.Vector(*_AXV[axis.upper()])
    base = cq.Vector(*point) - n * (span * 2)
    out = []
    for pl in plates:
        subject = f"{fastener.name} through {pl.name}"
        key = _through_hole_key(pl, axis, point, shank_radius, hole_radius, span, tol)
        cached = _load_finding(key, "through_hole", subject)
        if cached is not None:
            out.append(cached)
            continue
        probe_clear = cq.Solid.makeCylinder(shank_radius, span * 4, base, n)
        probe_present = cq.Solid.makeCylinder(hole_radius, span * 4, base, n)
        pv = pl.world_solid().val()
        clear = probe_clear.intersect(pv)
        present = probe_present.intersect(pv)
        cv = clear.Volume() if clear else 0.0
        pvv = present.Volume() if present else 0.0
        if cv > tol.noise_volume:
            finding = Finding("through_hole", subject, False,
                              "hole too small / mispositioned (shank fouls plate)")
        elif pvv <= tol.noise_volume:
            finding = Finding("through_hole", subject, False,
                              "plate not on the fastener axis")
        else:
            finding = Finding("through_hole", subject, True, "clean through hole")
        _store_finding(key, finding)
        out.append(finding)
    return out


def _floating_link_key(a: Placed, b: Placed, tol: Tolerances) -> str:
    """The bearing/bond link test's complete input surface: it only reads
    ``_min_distance(a, b) <= tol.near_miss`` — a true min-distance, which
    (like check_interference's overlap volume) is invariant under a
    simultaneous rigid motion of both parts, so this keys on the RELATIVE
    transform, same reasoning as ``_interference_key``."""
    return (
        f"floating_link|{_CHECKS_FP}|"
        f"{buildinfo.local_geometry_digest(a.component)}|"
        f"{buildinfo.local_geometry_digest(b.component)}|"
        f"{buildinfo.relative_transform_digest(a.world_frame, b.world_frame)}|"
        f"{tol.near_miss}"
    )


def _cached_linked(a: Placed, b: Placed, tol: Tolerances) -> bool:
    """Cached wrapper around the expensive half of check_no_floaters'
    per-edge test (``_min_distance``, a BRepExtrema call) — NOT wired
    through ``_load_finding``/``_store_finding`` since the result isn't a
    ``Finding`` (it's one boolean edge in a connectivity graph the caller
    assembles itself); same JSON-on-disk mechanism, different payload
    shape. This is the only piece of check_no_floaters that is cached —
    see its own docstring for why the whole-graph BFS itself never is."""
    key = _floating_link_key(a, b, tol)
    data = _VERDICT_CACHE.get(key)
    if data is not None:
        try:
            return json.loads(data)["linked"]
        except Exception:
            pass
    linked = _min_distance(a, b) <= tol.near_miss
    try:
        _VERDICT_CACHE.put(key, json.dumps({"linked": linked}).encode())
    except Exception:
        pass
    return linked


def check_no_floaters(assembly: DetailAssembly, bearings: list, bonds: list,
                      ground: "Placed | str", tol: Tolerances = DEFAULT,
                      self_grounded: "list | None" = None) -> list[Finding]:
    """Every part must connect back to ``ground`` through a chain of bearing
    contacts and declared bonds. Unreachable parts are floating.

    ``bearings``/``bonds`` entries and ``ground`` accept ``Placed`` handles or
    display names, resolved via ``assembly._resolve`` (loud on a bad
    reference — see its docstring). The adjacency graph and reachability set
    are keyed on each part's stable ``id``, so renaming a part between builds
    can't silently drop it out of the connectivity check.

    ``self_grounded`` (task CTXGROUND) lists PRE-EXISTING site bodies declared
    ``role: existing`` + ``grounded_by: site`` — a living tree, a rock outcrop —
    that are grounded EARTH-SIDE in reality, outside the constructed load path.
    They are EXEMPT from the "must reach constructed ground" requirement (so a
    truthful clearance gap around them needs no fake contact bond) but are NOT
    seeded as grounding roots — a constructed part still cannot reach ground
    THROUGH them. The exemption is listed in the finding, in connectivity-rung
    language ("grounded by site … outside constructed load paths"), never
    implying a load-path or support claim.

    Only the expensive per-edge distance test (``_cached_linked``) is
    persistently cached, not this function's own graph-connectivity
    result: the BFS below is pure, cheap Python over however many
    edges there are, so caching it would add a whole-assembly-shaped cache
    key (every part's identity, the full bearings/bonds spec, ground) for
    no measurable benefit — mapping ONLY the genuinely expensive OCCT call
    per the task brief's "cache only what's fully keyed AND worth it"
    guidance."""
    ids = [p.id for p in assembly.parts]
    by_id = {p.id: p for p in assembly.parts}
    adj = {i: set() for i in ids}

    def link(x_id, y_id):
        adj[x_id].add(y_id); adj[y_id].add(x_id)

    for spec in bearings:
        a, b = assembly._resolve(spec[0]), assembly._resolve(spec[1])
        if _cached_linked(a, b, tol):
            link(a.id, b.id)
    for (a, b) in bonds:
        pa, pb = assembly._resolve(a), assembly._resolve(b)
        if _cached_linked(pa, pb, tol):
            link(pa.id, pb.id)

    ground_part = assembly._resolve(ground)
    seen = {ground_part.id}
    q = deque([ground_part.id])
    while q:
        for m in adj[q.popleft()]:
            if m not in seen:
                seen.add(m); q.append(m)

    # Pre-existing self-grounded site bodies are grounded earth-side, outside the
    # constructed load path: exempt from the reachability requirement, but NOT
    # grounding conduits (they were never added to `seen` as roots, so nothing
    # reaches ground THROUGH them).
    exempt_ids = {assembly._resolve(p).id for p in (self_grounded or [])}
    exempt_names = sorted(by_id[i].name for i in exempt_ids if i in by_id)
    exempt_note = (
        f"; grounded by site (existing, outside constructed load paths): "
        f"{', '.join(exempt_names)}" if exempt_names else "")

    floaters = [by_id[i].name for i in ids
                if i not in seen and i not in exempt_ids]
    if floaters:
        return [Finding("floating", ", ".join(floaters), False,
                        f"not connected to ground{exempt_note}")]
    return [Finding("floating", "all parts grounded", True,
                    f"{len(seen)} parts reachable from "
                    f"{ground_part.name!r}{exempt_note}")]


@dataclass
class _SweepContext:
    """One call to :func:`validate_assembly`'s shared state, threaded
    through the registry-driven pipeline stages below. Each stage reads
    the raw kwargs it needs off this object and appends ``Finding``s to
    ``report``; ``resolved_bearings`` is written by the ``bearing`` stage
    and read back by the ``floating`` stage (``check_no_floaters`` needs
    the SAME resolved ``(Placed, Placed, axis, min_area)`` tuples the
    bearing sweep just used) — the one piece of cross-stage state the
    original straight-line function passed between two of its sections."""

    assembly: DetailAssembly
    report: ValidationReport
    expected_overlaps: set
    contacts: list | None
    bearings: list | None
    bonds: list | None
    through_holes: list | None
    ground: "Placed | str | None"
    tol: Tolerances
    spatial: list | None = None
    self_grounded: list | None = None
    resolved_bearings: list = field(default_factory=list)


#: Canonical stage order for the standard sweep (roadmap item 8: "the
#: standard pipeline becomes a registry-driven ordered list"). Each name
#: below resolves through the ``checks`` registry to the stage function
#: registered at import time — see each ``_stage_*`` function's
#: ``@register_check(...)`` decorator. Kept as an explicit tuple (not
#: simply ``checks.names()``) so a third party registering an ADDITIONAL
#: named check under this registry never silently changes what
#: ``validate_assembly``'s default sweep runs — only an explicit change to
#: this tuple does.
_STANDARD_PIPELINE: tuple[str, ...] = (
    "interference", "contact", "bearing", "through_hole", "floating",
    "spatial", "parameters",
)


@register_check("interference")
def _stage_interference(ctx: _SweepContext) -> None:
    """Pairwise interference sweep with the bbox prefilter (lever c,
    directive #8): a pair whose axis-aligned bounding boxes are separated
    by more than ``tol.bbox_prefilter_gap`` cannot possibly produce a
    boolean-intersection volume above 0 — the boxes are conservative
    supersets of the actual solids, so a true gap between them is also a
    gap between the solids. ``check_interference``'s own "no overlap"
    branch (``vol <= tol.noise_volume``) always emits the literal message
    below regardless of the (here, exactly-0) volume, so the fabricated
    Finding is byte-identical to what a full check would produce — see
    ``Tolerances.bbox_prefilter_gap`` for the threshold's derivation.
    Boxes are computed once per part (not per pair) since this loop is
    O(n^2) in the number of parts."""
    assembly, report, tol = ctx.assembly, ctx.report, ctx.tol
    allowed = {
        frozenset((assembly._resolve(a).id, assembly._resolve(b).id))
        for a, b in ctx.expected_overlaps
    }
    boxes = {p.id: _part_bbox(p) for p in assembly.parts}
    threshold = tol.bbox_prefilter_gap
    pairs_total = pairs_prefiltered = pairs_fully_checked = 0
    # Snapshot the verdict cache's hit counter around just this sweep (the
    # ONLY thing that touches _VERDICT_CACHE before this point in a call to
    # validate_assembly) so pairs_from_cache reflects exactly the pairs
    # that survived the bbox prefilter and then hit a persisted verdict —
    # S3c lever (d)'s own audit trail, parallel to pairs_prefiltered/
    # pairs_fully_checked above.
    cache_hits_before = _VERDICT_CACHE.hits
    for a, b in combinations(assembly.parts, 2):
        pairs_total += 1
        if _aabb_gap(boxes[a.id], boxes[b.id]) > threshold:
            pairs_prefiltered += 1
            report.add(Finding("interference", f"{a.name} <-> {b.name}",
                               True, "no overlap"))
            continue
        pairs_fully_checked += 1
        report.add(check_interference(
            a, b, allowed=frozenset((a.id, b.id)) in allowed, tol=tol))
    report.pairs_total = pairs_total
    report.pairs_prefiltered = pairs_prefiltered
    report.pairs_fully_checked = pairs_fully_checked
    report.prefilter_threshold_mm = threshold
    report.pairs_from_cache = _VERDICT_CACHE.hits - cache_hits_before


@register_check("contact")
def _stage_contact(ctx: _SweepContext) -> None:
    """Bbox-gap touch checks (coarse) for each declared ``contacts`` pair."""
    assembly, report, tol = ctx.assembly, ctx.report, ctx.tol
    for ref_a, ref_b in ctx.contacts or []:
        report.add(check_contact(assembly._resolve(ref_a), assembly._resolve(ref_b), tol=tol))


@register_check("bearing")
def _stage_bearing(ctx: _SweepContext) -> None:
    """Rigorous flush-contact checks, each declared ``(a, b, axis,
    min_area_mm2)``. Resolves and stores the pairs on ``ctx`` — the
    ``floating`` stage reuses this exact resolved list."""
    assembly, report, tol = ctx.assembly, ctx.report, ctx.tol
    ctx.resolved_bearings = [
        (assembly._resolve(a), assembly._resolve(b), axis, min_area)
        for (a, b, axis, min_area) in ctx.bearings or []
    ]
    for (a, b, axis, min_area) in ctx.resolved_bearings:
        report.add(check_bearing(a, b, axis, min_area, tol=tol))


@register_check("through_hole")
def _stage_through_hole(ctx: _SweepContext) -> None:
    """Fastener probes, each declared ``(fastener, [plates], axis, point,
    shank_r, hole_r, span)``."""
    assembly, report, tol = ctx.assembly, ctx.report, ctx.tol
    for (fastener, plates, axis, point, shank_r, hole_r, span) in ctx.through_holes or []:
        f = assembly._resolve(fastener)
        pls = [assembly._resolve(p) for p in plates]
        for finding in check_through_hole(f, pls, axis, point, shank_r, hole_r, span, tol=tol):
            report.add(finding)


@register_check("floating")
def _stage_floating(ctx: _SweepContext) -> None:
    """Floating-part connectivity from ``ground``, using the SAME resolved
    bearing pairs the ``bearing`` stage just computed (see ``_SweepContext``
    docstring). No-op when ``ground`` wasn't given."""
    if ctx.ground is None:
        return
    for f in check_no_floaters(ctx.assembly, ctx.resolved_bearings, ctx.bonds or [],
                               ctx.ground, tol=ctx.tol,
                               self_grounded=ctx.self_grounded):
        ctx.report.add(f)


@register_check("spatial")
def _stage_spatial(ctx: _SweepContext) -> None:
    """Spatial-intent invariants (task SPATIAL): each declared
    :class:`~detailgen.validation.spatial.SymmetricAbout` /
    ``FacesToward`` / ``FacesAway`` evaluates itself against the built
    assembly and appends its findings — VALIDATION ONLY, never a placement
    move. No-op (and the ``Spatial intent`` coverage family stays UNKNOWN)
    when a detail declares no ``spatial`` invariants, so merely having the
    feature available never fabricates coverage."""
    for decl in ctx.spatial or []:
        for finding in decl.evaluate(ctx.assembly, ctx.tol.dimension_tolerance):
            ctx.report.add(finding)


@register_check("parameters")
def _stage_parameters(ctx: _SweepContext) -> None:
    """Parameter problems from ``assembly.check()`` (each placed
    component's own ``check()``, aggregated by the assembly)."""
    for problem in ctx.assembly.check():
        ctx.report.add(Finding("parameters", problem, False))


def validate_assembly(
    assembly: DetailAssembly,
    expected_overlaps: set[tuple["Placed | str", "Placed | str"]] = frozenset(),
    contacts: list[tuple["Placed | str", "Placed | str"]] | None = None,
    bearings: list[tuple] | None = None,
    bonds: list[tuple["Placed | str", "Placed | str"]] | None = None,
    through_holes: list[tuple] | None = None,
    ground: "Placed | str | None" = None,
    spatial: list | None = None,
    self_grounded: list | None = None,
    tol: Tolerances = DEFAULT,
) -> ValidationReport:
    """Standard whole-assembly sweep.

    Every part reference below (a bare item or one side of a pair) accepts
    either a ``Placed`` handle (what ``add()``/``place().on()`` return — the
    preferred style, immune to renames) or a display name for convenience.
    All are resolved via ``assembly._resolve``, which never fails silently: a
    bad name or a handle from another assembly raises, naming the offender
    and listing every part actually in the assembly. Internally everything is
    keyed on the part's stable ``id``, not its name.

    - ``expected_overlaps``: pairs allowed to interpenetrate (fastener in wood).
    - ``contacts``: bbox-gap touch checks (coarse).
    - ``bearings``: rigorous flush-contact checks, each ``(a, b, axis, min_area_mm2)``.
    - ``bonds``: adjacency edges that are bonded/threaded rather than bearing
      (epoxy-rock, rod-nut); used only for floating-part connectivity.
    - ``through_holes``: fastener probes, each
      ``(fastener, [plates], axis, point, shank_r, hole_r, span)``.
    - ``ground``: if set, run the floating-part connectivity check from it.
    - ``self_grounded``: pre-existing site bodies (``role: existing`` +
      ``grounded_by: site``) exempt from that connectivity requirement — grounded
      earth-side, outside the constructed load path (task CTXGROUND).
    - ``spatial``: declared spatial-intent invariants
      (:class:`~detailgen.validation.spatial.SymmetricAbout`,
      ``FacesToward``/``FacesAway``) — validation-only, each evaluated against
      the built assembly. See :mod:`detailgen.validation.spatial`.
    - ``tol``: :class:`~detailgen.core.config.Tolerances` to check against;
      defaults to :data:`~detailgen.core.config.DEFAULT`. Pass a detail-specific
      instance to tighten/loosen checks without touching global state.

    Internally, the sweep is a registry-driven ordered pipeline (roadmap
    item 8) — see ``_STANDARD_PIPELINE`` and the ``_stage_*`` functions
    above; each name in that tuple resolves through the ``checks``
    registry to its stage function, run in that fixed order. Behavior is
    unchanged from the pre-registry straight-line implementation this
    replaced — same checks, same order, same verdicts.
    """
    report = ValidationReport(assembly.name)
    ctx = _SweepContext(
        assembly=assembly, report=report, expected_overlaps=expected_overlaps,
        contacts=contacts, bearings=bearings, bonds=bonds,
        through_holes=through_holes, ground=ground, spatial=spatial,
        self_grounded=self_grounded, tol=tol,
    )
    for stage_name in _STANDARD_PIPELINE:
        checks.get(stage_name)(ctx)
    return report
