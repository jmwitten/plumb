"""Dimensional lumber.

**This module is the documented reference implementation of the Component
contract** — read it top to bottom before writing a new component.

The pattern every component follows:

1. Parameters in ``__init__``, converted/stored in mm, nothing built yet.
2. ``_build()`` constructs geometry in a *documented local frame*.
3. ``check()`` flags parameter problems (never raises for geometry reasons).
4. Convenience constructors/attributes expose real-world semantics
   (nominal sizes here) so detail scripts read like a cut list.

Local frame (datum)
-------------------
A Lumber member is modeled with its **length along +X**, laid flat:

    X: 0 .. length          (member run)
    Y: 0 .. width           (the *narrow* face dimension, e.g. 1.5" on a 2x8)
    Z: 0 .. depth           (the *wide* face dimension, e.g. 7.25" on a 2x8)

so the origin is the bottom-left end corner. Assemblies rotate it on edge,
plumb, etc. — the component never bakes in an installed orientation.

Example
-------
    from detailgen.core import FT
    from detailgen.components import Lumber

    joist = Lumber("2x8", length=8 * FT, name="rim joist", treated=True)
    joist.solid           # cq.Workplane, built on first access
    joist.check()         # [] — parameters OK
    joist.actual          # (38.1, 184.15) mm — 1.5" x 7.25"
"""

from __future__ import annotations

import math

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import IN, FT, fmt_in

#: Nominal size -> actual (thickness, depth) in mm, per US softwood standard
#: (PS 20). Thickness is the narrow face ("2" -> 1.5"), depth the wide face.
NOMINAL_SIZES: dict[str, tuple[float, float]] = {
    "1x2": (0.75 * IN, 1.5 * IN),
    "1x4": (0.75 * IN, 3.5 * IN),
    "1x6": (0.75 * IN, 5.5 * IN),
    "2x2": (1.5 * IN, 1.5 * IN),
    "2x4": (1.5 * IN, 3.5 * IN),
    "2x6": (1.5 * IN, 5.5 * IN),
    "2x8": (1.5 * IN, 7.25 * IN),
    "2x10": (1.5 * IN, 9.25 * IN),
    "2x12": (1.5 * IN, 11.25 * IN),
    "4x4": (3.5 * IN, 3.5 * IN),
    "4x6": (3.5 * IN, 5.5 * IN),
    "6x6": (5.5 * IN, 5.5 * IN),
}

#: Common stock lengths (mm); check() warns when a member exceeds the longest.
STOCK_LENGTHS = [8 * FT, 10 * FT, 12 * FT, 14 * FT, 16 * FT, 20 * FT]


@register_component("lumber")
class Lumber(Component):
    """A straight dimensional-lumber member. Optional ``end_cuts`` entries
    are mappings with ``end`` (``near``/``far``), conventional
    ``miter_angle_degrees`` off square, and ``long_face`` (``top``/``bottom``);
    they require ``length_semantics="long_point_to_long_point"`` and expose
    physical ``cut_near``/``cut_far`` mating datums.

    Parameters
    ----------
    nominal:
        Nominal size string, key of NOMINAL_SIZES (e.g. ``"2x8"``).
    length:
        Member length in mm (use ``n * FT`` / ``n * IN``).
    name:
        Human label used in assemblies, BOMs and validation reports.
        Defaults to the nominal size.
    treated:
        Pressure-treated (drives material/color only).
    """

    def __init__(
        self,
        nominal: str,
        length: float,
        name: str | None = None,
        treated: bool = False,
        ease_radius: float = 0.0,
        holes: tuple = (),
        full_length: float | None = None,
        end_cuts: tuple = (),
        length_semantics: str | None = None,
    ):
        super().__init__(name or nominal)
        if nominal not in NOMINAL_SIZES:
            raise ValueError(
                f"Unknown nominal size {nominal!r}; known: {sorted(NOMINAL_SIZES)}"
            )
        self.nominal = nominal
        self.length = float(length)
        self.treated = treated
        #: long-edge easing radius (mm); 0 = square edges (bbox preserved either way)
        self.ease_radius = float(ease_radius)
        #: through-holes along the thickness (+Y) axis: [(x, z, diameter)] in mm
        self.holes = list(holes)
        self.material_key = "lumber_pt" if treated else "lumber_spf"
        #: partial-member metadata (mm) — set when this instance models only a
        #: stub of a longer continuous run whose full length lives in another
        #: detail (e.g. the rock-anchor leg stub, full run = the platform's
        #: launch leg). Underscored so it stays out of ``params()``/BOM specs;
        #: surfaced instead through ``stub_of()``. ``None`` for ordinary lumber.
        self._full_length = None if full_length is None else float(full_length)
        self._end_cuts = self._normalize_end_cuts(end_cuts, length_semantics)
        self._length_semantics = (
            "long_point_to_long_point" if self._end_cuts else None
        )

        for end, miter_angle, _long_face in self._end_cuts:
            setback = self.depth * math.tan(math.radians(miter_angle))
            if setback >= self.length:
                raise ValueError(
                    f"lumber {end} end cut setback must be shorter than the "
                    f"authored long-point length; got {setback:g} mm setback "
                    f"for {self.length:g} mm length"
                )

    @staticmethod
    def _normalize_end_cuts(end_cuts, length_semantics):
        raw_cuts = tuple(end_cuts or ())
        if not raw_cuts:
            if length_semantics is not None:
                raise ValueError(
                    "lumber length_semantics is only valid when end_cuts are authored"
                )
            return ()
        if length_semantics != "long_point_to_long_point":
            raise ValueError(
                "lumber end_cuts require "
                "length_semantics='long_point_to_long_point'"
            )

        normalized = []
        allowed_keys = {"end", "miter_angle_degrees", "long_face"}
        for index, cut in enumerate(raw_cuts):
            if not isinstance(cut, dict):
                raise ValueError(
                    f"lumber end_cuts[{index}] must be a mapping with "
                    "end, miter_angle_degrees, and long_face"
                )
            unknown = set(cut) - allowed_keys
            missing = allowed_keys - set(cut)
            if unknown or missing:
                raise ValueError(
                    f"lumber end_cuts[{index}] must contain exactly "
                    "end, miter_angle_degrees, and long_face; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}"
                )
            end = str(cut["end"])
            long_face = str(cut["long_face"])
            if end not in {"near", "far"}:
                raise ValueError("lumber end cut end must be 'near' or 'far'")
            if long_face not in {"top", "bottom"}:
                raise ValueError(
                    "lumber end cut long_face must be 'top' or 'bottom'"
                )
            try:
                miter_angle = float(cut["miter_angle_degrees"])
            except (TypeError, ValueError):
                raise ValueError(
                    "lumber end cut miter_angle_degrees must be numeric"
                ) from None
            if not 0.0 < miter_angle < 90.0:
                raise ValueError(
                    "lumber end cut miter_angle_degrees must be between 0 and "
                    "90 degrees off square"
                )
            normalized.append((end, miter_angle, long_face))

        ends = [cut[0] for cut in normalized]
        if len(set(ends)) != len(ends):
            raise ValueError("lumber end_cuts may contain each end only once")
        if len({cut[2] for cut in normalized}) > 1:
            raise ValueError(
                "lumber long_point_to_long_point end cuts must retain the "
                "same long_face"
            )
        return tuple(sorted(normalized, key=lambda cut: cut[0] != "near"))

    @property
    def end_cuts(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "end": end,
                "miter_angle_degrees": angle,
                "long_face": long_face,
            }
            for end, angle, long_face in self._end_cuts
        )

    @property
    def length_semantics(self) -> str | None:
        return self._length_semantics

    def params(self) -> dict:
        params = super().params()
        if self._end_cuts:
            params["end_cuts"] = self.end_cuts
            params["length_semantics"] = self.length_semantics
        return params

    # -- real-world semantics -------------------------------------------------

    @property
    def actual(self) -> tuple[float, float]:
        """Actual (thickness, depth) in mm — e.g. 2x8 -> (38.1, 184.15)."""
        return NOMINAL_SIZES[self.nominal]

    @property
    def thickness(self) -> float:
        return self.actual[0]

    @property
    def depth(self) -> float:
        return self.actual[1]

    # -- Component contract ----------------------------------------------------

    def fabrication_record(self, part_id: str = ""):
        """This member's fabrication story: establish the authored length,
        ease the long edges (if any), make each semantic end cut, then drill
        each hole — in that order (see ``process_graph.fold``). The installed
        solid is DERIVED from these steps, so the cut length the BOM reports
        and the geometry can no longer disagree (retro R28). Each step carries
        provenance back to the design intent that produced it."""
        from ..core.process_graph import ProcessRecord, ProcessStep, StockRef

        stock = StockRef(
            profile=("PT " if self.treated else "") + self.nominal,
            form="linear_stick",
            section=(self.thickness, self.depth),
            material_key=self.material_key,
        )
        length_provenance = (
            "long_point_to_long_point" if self._end_cuts else "finished-length"
        )
        steps = [ProcessStep.crosscut(self.length, provenance=length_provenance)]
        if self.ease_radius > 0:
            steps.append(ProcessStep.ease(self.ease_radius, provenance="ease_radius"))
        for end, miter_angle, long_face in self._end_cuts:
            steps.append(
                ProcessStep.miter_crosscut_from_square(
                    end,
                    miter_angle_degrees=miter_angle,
                    long_face=long_face,
                    provenance=f"end_cuts:{end}",
                )
            )
        for (hx, hz, hd) in self.holes:
            steps.append(ProcessStep.drill(
                hx, hz, hd, provenance=f"holes[({hx}, {hz}, {hd})]"))
        return ProcessRecord(stock, tuple(steps), part_id=part_id or self.name)

    def _build(self) -> cq.Workplane:
        # Delegate to fold(stock, steps): the ProcessRecord is the single
        # authoritative source of this member's installed geometry. The steps
        # reproduce exactly the box -> ease -> end-cut -> drill sequence above;
        # without end cuts, the fold remains byte-identical to the former path.
        return self.fabrication_record().installed_geometry()

    def _datums(self) -> dict[str, Frame]:
        # Local frame: length +X [0..L], thickness +Y [0..t], depth +Z [0..d],
        # corner origin (see module docstring). Each datum's +Z is its
        # assembly-up axis (the outward normal of a face, or +Z into the member
        # for the seating ``base``).
        L, t, d = self.length, self.thickness, self.depth
        datums = {
            "base": Frame.from_origin_axes((L / 2, t / 2, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((L / 2, t / 2, d), (1, 0, 0), (0, 0, 1)),
            "end_near": Frame.from_origin_axes((0, t / 2, d / 2), (0, 0, 1), (-1, 0, 0)),
            "end_far": Frame.from_origin_axes((L, t / 2, d / 2), (0, 0, 1), (1, 0, 0)),
            "face_near": Frame.from_origin_axes((L / 2, 0, d / 2), (1, 0, 0), (0, -1, 0)),
            "face_far": Frame.from_origin_axes((L / 2, t, d / 2), (1, 0, 0), (0, 1, 0)),
        }
        for end, miter_angle, long_face in self._end_cuts:
            angle = math.radians(miter_angle)
            end_sign = -1.0 if end == "near" else 1.0
            z_sign = -1.0 if long_face == "top" else 1.0
            setback = d * math.tan(angle)
            origin_x = setback / 2 if end == "near" else L - setback / 2
            normal = (end_sign * math.cos(angle), 0.0, z_sign * math.sin(angle))
            tangent = (
                math.sin(angle),
                0.0,
                -z_sign * end_sign * math.cos(angle),
            )
            datums[f"cut_{end}"] = Frame.from_origin_axes(
                (origin_x, t / 2, d / 2), tangent, normal
            )
        return datums

    def describe(self) -> str:
        description = f'{self.nominal} x {fmt_in(self.length, 1)}'
        if self._end_cuts:
            description += " (long-point to long-point)"
        return description

    def assumptions(self) -> str:
        note = "Actual dressed dimensions (PS 20)."
        if self._end_cuts:
            if self.ease_radius:
                note += f" Long edges eased r={fmt_in(self.ease_radius)}."
            cuts = ", ".join(
                f"{end} {angle:g}° off-square miter, {long_face} face long"
                for end, angle, long_face in self._end_cuts
            )
            note += (
                f" End cuts: {cuts}; authored length is long-point to "
                "long-point on the retained face."
            )
        elif self.ease_radius:
            note += (
                f" Long edges eased r={fmt_in(self.ease_radius)}; "
                "end grain square."
            )
        return note

    def bom_group(self) -> str:
        base = f"Lumber|{self.nominal}|{round(self.length,1)}|{self.treated}"
        if not self._end_cuts:
            return base
        return f"{base}|{self._end_cuts!r}|{self._length_semantics!r}"

    def bom_label(self) -> str:
        return ("PT " if self.treated else "") + self.nominal + " lumber"

    def bom_length_mm(self) -> float | None:
        # Single-source (retro R28): the authoritative cut length is the
        # crosscut step's to_length_mm in this member's ProcessRecord — the SAME
        # record its installed geometry is folded from — read here, never an
        # independent declaration of self.length. Collapsing the two paths (the
        # geometry's and the BOM's) to one reader of one record is what makes the
        # cut list and the solid unable to disagree.
        return self.fabrication_record().crosscut_length()

    def stub_of(self) -> dict | None:
        """See ``Component.stub_of``. Set only when constructed with
        ``full_length`` — this instance is a stub of a longer continuous run
        modeled in full elsewhere (currently: the platform detail)."""
        if self._full_length is None:
            return None
        if self.length <= self._full_length:
            note = (f'shown: {fmt_in(self.length, 1)} modeled portion '
                    '— full run in the platform detail')
        else:
            # This stub MODELS MORE stock than the finished run (SM4 item 6,
            # rev-sm3b minor): the trolley launch post models 68" for the 63.5"
            # finished leg. "modeled portion" would misread as a fraction of the
            # whole when modeled > full, so state it honestly instead.
            note = (f'models {fmt_in(self.length, 1)} of stock for the '
                    f'{fmt_in(self._full_length, 1)} finished run '
                    '— full run in the platform detail')
        return {
            "full_dims": f'{self.nominal} x {fmt_in(self._full_length, 1)} '
                         '(continuous run)',
            "modeled_dims": self.describe(),
            "note": note,
        }

    def check(self) -> list[str]:
        problems = super().check()
        if self.length <= 0:
            problems.append(f"{self.name}: non-positive length")
        elif self.length > max(STOCK_LENGTHS):
            problems.append(
                f"{self.name}: {fmt_in(self.length)} exceeds longest stock "
                f"({fmt_in(max(STOCK_LENGTHS))}) — needs a splice or engineered lumber"
            )
        return problems
