"""Centralized geometric tolerances for `detailgen.validation.checks`.

These thresholds used to be module-level globals in `checks.py`
(`NOISE_VOLUME`, `CONTACT_EPS`, `NEAR_MISS`, `PUSH`) plus a couple of stray
default arguments (`tolerance=0.5`) and an inline bearing-area fudge
(`max(min_area * 0.5, 1.0)`). Gathering them into one immutable object lets a
detail tighten or loosen checks — e.g. a rough-sawn timber joint vs. a
precision-machined bracket — without editing shared module state.

    from dataclasses import replace
    loose = replace(DEFAULT, base=1.0)
    validate_assembly(detail, tol=loose, ...)

Mesh/tessellation tolerances (``MESH_TOL_LINEAR`` / ``MESH_TOL_ANGULAR`` in
``detailgen.core.buildinfo``) are a deliberately separate pair of fixed
constants, not fields here: they set the tessellation resolution that
``geometry_hash`` hashes, so if they varied per-detail (like the thresholds
in this module do), the same geometry would hash differently depending on
which detail built it, breaking the "diff two manifests to catch a
regression" guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tolerances:
    """Geometric acceptance thresholds. All values in mm unless noted.

    `base` is the fundamental geometric precision floor: the smallest gap
    OpenCascade can reliably resolve as "actually touching" rather than
    floating-point boolean noise. `contact_eps`, `push`, and `near_miss` are
    derived multiples of it, so their relative scale stays explicit and
    tightening/loosening `base` moves all three together. Everything else
    below doesn't derive naturally from a linear precision (different units,
    or a genuinely independent design choice) and is kept as its own field.
    """

    #: Fundamental geometric precision floor (mm). See class docstring.
    base: float = 2.5e-4

    #: Overlap volume at/under this (mm^3) is boolean noise, not real
    #: interference. Independent of `base` (volume vs. length units).
    noise_volume: float = 1.0

    #: `check_contact` bbox-gap tolerance (mm) — coarse/legacy contact check.
    contact_bbox_tolerance: float = 0.5

    #: `check_dimension` design-intent tolerance (mm).
    dimension_tolerance: float = 0.5

    #: Multiplier on `min_area` in the bearing-area acceptance test.
    bearing_area_ratio: float = 0.5

    #: Floor (mm^2) under the bearing-area acceptance test, so a tiny/zero
    #: `min_area` still rejects a near-zero (edge/point) contact.
    bearing_area_floor: float = 1.0

    @property
    def contact_eps(self) -> float:
        """Gap at/under this (mm) counts as true face contact. Equal to `base`."""
        return self.base

    @property
    def push(self) -> float:
        """Depth of the face-contact proof push (mm). 120x `base`."""
        return self.base * 120

    @property
    def near_miss(self) -> float:
        """Gap above `contact_eps` but under this (mm) is a suspicious
        near-miss. 600x `base`."""
        return self.base * 600

    def bearing_area_threshold(self, min_area: float) -> float:
        """Minimum accepted bearing area (mm^2) for a given `min_area` ask."""
        return max(min_area * self.bearing_area_ratio, self.bearing_area_floor)

    @property
    def bbox_prefilter_gap(self) -> float:
        """Minimum true AABB separation (mm) required to skip a pair's exact
        boolean interference test (`check_interference`) in the O(n^2)
        pairwise sweep.

        `check_interference` only ever acts on the *volume* of an exact
        boolean intersection, compared against `noise_volume` — it has no
        surface-distance tolerance of its own (`near_miss`/`contact_eps`/
        `push` belong to `check_bearing`/`check_no_floaters`, not it). Two
        solids are each contained in their own axis-aligned bounding box, so
        ANY true positive gap between disjoint boxes already proves the exact
        intersection volume is 0 (<= `noise_volume`, trivially) — the correct
        skip threshold is mathematically 0. The only reason to pad above 0 is
        that shapes carry OCCT's own confusion tolerance (not `Bnd_Box`'s
        `SetGap`, which this codebase never touches and which defaults to
        0.0), so a computed gap of a few `base`-scale units could be noise
        rather than real separation. `near_miss` is already the codebase's
        answer to "how big a gap might still be geometrically ambiguous", so
        it's reused here rather than adding a new constant.
        """
        return self.near_miss


#: Default tolerances — values match the legacy hardcoded constants exactly.
DEFAULT = Tolerances()
