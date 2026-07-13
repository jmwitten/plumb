"""Task CLEANUP item 5 — ``fmt_in`` must be stable across the ≤2e-13 mm inch↔mm
float-ordering residual.

The same real length computed in a different order (the spec compiler vs the
imperative detail) can differ by ≤2e-13 mm. That is far below any real feature,
but a value sitting exactly on a display-rounding boundary (a 3/8"=0.375 bolt at
2 decimals, a 42.25" mesh at 1 decimal) would be tipped to a different STRING by
that dust. ``fmt_in`` now snaps the inch value to 1e-6" before the display
rounding, so the boundary can't be tipped — display layer only, geometry
untouched (there is no geometry mutation here to test; this is pure formatting).
"""

from __future__ import annotations

import pytest

from detailgen.core import IN
from detailgen.core.units import fmt_in

RESIDUAL = 2e-13  # mm — the worst inch↔mm ordering drift observed on the platform


@pytest.mark.parametrize("inch_value,precision", [
    (0.375, 2),    # 3/8" bolt/washer/nut — the .2f knife-edge (was 0.37 vs 0.38)
    (42.25, 1),    # welded-wire mesh length — the .1f knife-edge (42.2 vs 42.3)
    (16.75, 1),    # boulder chunk dimension
    (7.25, 2),     # an ordinary non-boundary value stays put
    (24.0, 1),     # an exact inch stays "24.0"
])
def test_fmt_in_is_stable_across_the_float_residual(inch_value, precision):
    """A boundary value formats to ONE string no matter which side of the
    picometre residual the internal mm lands on."""
    exact_mm = inch_value * IN
    strings = {
        fmt_in(exact_mm, precision),
        fmt_in(exact_mm + RESIDUAL, precision),
        fmt_in(exact_mm - RESIDUAL, precision),
    }
    assert len(strings) == 1, (
        f"{inch_value}\" at {precision}dp tipped across the residual: {strings}")


def test_fmt_in_snaps_to_the_canonical_rounding_of_the_exact_fraction():
    """The single string is the canonical rounding of the EXACT fraction, so a
    value the raw float nudged just under the boundary is no longer shown one
    tick low."""
    assert fmt_in((0.375 - 1e-15) * IN, 2) == '0.38"'   # not 0.37"
    assert fmt_in(42.25 * IN, 1) == '42.2"'             # round-half-even, stable
