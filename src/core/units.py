"""Unit helpers.

Internal geometry is always modeled in **millimeters** (CadQuery's native STEP
unit). Construction inputs are almost always imperial, so every public API in
this package accepts dimensions built with these helpers:

    from detailgen.core import IN, FT

    Lumber("2x8", length=8 * FT)
    LagScrew(diameter=0.5 * IN, length=6 * IN)

Plain floats are treated as millimeters.
"""

MM: float = 1.0
IN: float = 25.4
FT: float = 12 * IN


def inches(mm_value: float) -> float:
    """Convert an internal mm value back to inches (for reports/labels)."""
    return mm_value / IN


def feet(mm_value: float) -> float:
    """Convert an internal mm value back to feet (for reports/labels)."""
    return mm_value / FT


def fmt_in(mm_value: float, precision: int = 2) -> str:
    """Format an internal mm value as an inch string, e.g. '7.25\"'.

    The inch value is snapped to 1e-6" before the display rounding. Internal mm
    lengths carry a ≤2e-13 mm inch↔mm float-ordering residual (the SAME length
    computed in a different order — spec vs imperative — differs at the
    picometre), which is far below any real dimension but enough to tip a value
    sitting exactly on a display-rounding boundary (e.g. 42.25" at one-decimal
    precision) to a different string. Snapping at 1e-6" (≈2.5e-5 mm — orders of
    magnitude above the residual, orders below any feature) sheds that dust so
    the string is stable. Display layer only: geometry is never touched."""
    return f'{round(inches(mm_value), 6):.{precision}f}"'
