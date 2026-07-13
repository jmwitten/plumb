"""Deterministic 1D cut-stock packing for linear lumber stock.

Given the required cut lengths for a lumber profile (e.g. every "2x4 PT"
member across a build), pack them into purchasable stock sticks — 8/10/12/16
ft by default — so a buy list can read "buy 2x 2x4 PT @ 8 ft" with a per-stick
cut map, instead of listing each cut length as its own purchase line.

Algorithm — Best-Fit-Decreasing over a variable-length stock catalog, one
profile at a time
------------------------------------------------------------------------
1. Sort a profile's cut instances by ``(-length_mm, source)``, an explicit,
   stable key — never a set/dict iteration order — so two runs over the same
   input always produce identical output (see ``test_determinism``).
2. Repeatedly take the longest still-unplaced instance. For every stock
   length that can hold it alone, simulate greedily filling that stock with
   the remaining instances (longest-first, same fit rule as step 3) and
   measure the resulting waste. Commit the stock length with the LEAST waste
   (ties: shorter stock, then more instances packed, then input order) as one
   purchased stick, and remove its packed instances from the pool.

   Considering every catalog length for each new stick (rather than always
   grabbing the smallest stock that fits the current piece alone) is what
   lets the packer prefer one 10 ft stick over two 8 ft sticks when that
   wins on total purchased length: an 8 ft stick holding only the anchor
   piece reports its true (large) waste, so a 10 ft stick that also
   swallows the next piece can win on waste even though it's the bigger
   single purchase.
3. A set of ``n`` instances (raw lengths summing to ``raw_sum``) fits a stock
   length ``L`` if ``raw_sum + KERF*(n-1) + END_TRIM <= L`` — the ``n-1``
   kerfs are the interior saw cuts needed to separate ``n`` pieces from one
   stick, and END_TRIM is the allowance for squaring one end before the
   first measured cut. EXCEPTION: if the raw lengths sum to *exactly* ``L``
   (the stick is fully consumed — there is no leftover to spare), kerf and
   end-trim are not charged. Buying a longer, pricier stick purely to
   protect the last piece from an unavoidable sub-1/8" saw-kerf shortfall
   isn't a real choice a contractor makes; that shortfall comes out of
   ordinary cutting tolerance. This is the only exemption from the strict
   rule and it only ever HELPS a fit — any ``raw_sum`` strictly less than
   ``L`` still pays the full kerf + end-trim, which is what lets a genuine
   "fits without kerf, doesn't with kerf" case still force a second stick
   (see ``test_kerf_tips_into_two_sticks``).
4. A cut longer than the longest stock length in the catalog is a hard
   ``CutPlanError`` — never silently spliced.

Determinism
-----------
Every grouping and comparison is a sorted list keyed on plain
``(float, str, int)`` tuples; nothing iterates a ``dict`` or ``set`` for
ordering. ``pack()`` is a pure function of its arguments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .units import FT

#: One saw cut's width (1/8"), charged once per interior cut on a stick.
KERF_MM: float = 3.175

#: Allowance for squaring one end of a stick before the first measured cut
#: (1/4"). Charged once per stick — see the exact-fit exemption above.
END_TRIM_MM: float = 6.35

#: Standard purchasable lumber lengths: 8/10/12/16 ft. Overridable per call.
DEFAULT_STOCK_LENGTHS_MM: tuple[float, ...] = tuple(n * FT for n in (8, 10, 12, 16))

_ISCLOSE_ABS_TOL = 1e-6
_FIT_EPS = 1e-9


class CutPlanError(ValueError):
    """A cut item cannot be produced from any stock length in the catalog."""


@dataclass(frozen=True)
class CutItem:
    """One required cut: ``qty`` is expanded by the caller — each ``CutItem``
    here is a single physical piece."""

    profile: str
    length_mm: float
    source: str


@dataclass(frozen=True)
class PlacedCut:
    """One cut as packed onto a stick."""

    length_mm: float
    source: str


@dataclass(frozen=True)
class Stick:
    """One purchased stick and the cuts taken from it, in packed order."""

    stock_length_mm: float
    cuts: tuple[PlacedCut, ...]
    waste_mm: float


@dataclass(frozen=True)
class ProfilePlan:
    """The full cut plan for one lumber profile (e.g. "2x4 PT")."""

    profile: str
    sticks: tuple[Stick, ...]

    @property
    def stick_count(self) -> int:
        return len(self.sticks)

    @property
    def total_purchased_mm(self) -> float:
        return sum(s.stock_length_mm for s in self.sticks)

    @property
    def total_waste_mm(self) -> float:
        return sum(s.waste_mm for s in self.sticks)


def _fits(raw_sum: float, n: int, stock_length: float, kerf_mm: float, end_trim_mm: float) -> bool:
    if math.isclose(raw_sum, stock_length, rel_tol=0.0, abs_tol=_ISCLOSE_ABS_TOL):
        return True
    required = raw_sum + kerf_mm * max(0, n - 1) + end_trim_mm
    return required <= stock_length + _FIT_EPS


def _waste(raw_sum: float, n: int, stock_length: float, kerf_mm: float, end_trim_mm: float) -> float:
    if math.isclose(raw_sum, stock_length, rel_tol=0.0, abs_tol=_ISCLOSE_ABS_TOL):
        return max(0.0, stock_length - raw_sum)
    return max(0.0, stock_length - raw_sum - kerf_mm * max(0, n - 1) - end_trim_mm)


def _pack_profile(
    items: list[CutItem],
    stock_lengths_mm: tuple[float, ...],
    kerf_mm: float,
    end_trim_mm: float,
) -> ProfilePlan:
    profile = items[0].profile
    longest_stock = max(stock_lengths_mm)
    for it in items:
        if not _fits(it.length_mm, 1, longest_stock, kerf_mm, end_trim_mm):
            raise CutPlanError(
                f"{profile}: cut {it.length_mm:.1f}mm ({it.source}) exceeds "
                f"the longest stock length {longest_stock:.1f}mm — needs a "
                f"splice or engineered lumber, not a bigger stick"
            )

    # Explicit, stable order — sort key never touches dict/set iteration.
    ordered = sorted(items, key=lambda it: (-it.length_mm, it.source))
    remaining: list[tuple[int, CutItem]] = list(enumerate(ordered))
    stocks_sorted = sorted(stock_lengths_mm)

    sticks: list[Stick] = []
    while remaining:
        anchor_idx, anchor = remaining[0]
        best_key = None
        best_L = None
        best_packed: list[tuple[int, CutItem]] = []

        for L in stocks_sorted:
            if not _fits(anchor.length_mm, 1, L, kerf_mm, end_trim_mm):
                continue
            packed = [(anchor_idx, anchor)]
            raw_sum = anchor.length_mm
            for idx, it in remaining[1:]:
                trial_sum = raw_sum + it.length_mm
                if _fits(trial_sum, len(packed) + 1, L, kerf_mm, end_trim_mm):
                    packed.append((idx, it))
                    raw_sum = trial_sum
            waste = _waste(raw_sum, len(packed), L, kerf_mm, end_trim_mm)
            key = (waste, L, -len(packed))
            if best_key is None or key < best_key:
                best_key, best_L, best_packed = key, L, packed

        packed_ids = {idx for idx, _ in best_packed}
        remaining = [(idx, it) for idx, it in remaining if idx not in packed_ids]
        raw_sum = sum(it.length_mm for _, it in best_packed)
        waste = _waste(raw_sum, len(best_packed), best_L, kerf_mm, end_trim_mm)
        cuts = tuple(PlacedCut(it.length_mm, it.source) for _, it in best_packed)
        sticks.append(Stick(best_L, cuts, waste))

    return ProfilePlan(profile, tuple(sticks))


def pack(
    items: list[CutItem],
    stock_lengths_mm: tuple[float, ...] = DEFAULT_STOCK_LENGTHS_MM,
    kerf_mm: float = KERF_MM,
    end_trim_mm: float = END_TRIM_MM,
) -> dict[str, ProfilePlan]:
    """Pack every ``CutItem`` into purchased sticks, grouped by profile.

    Returns ``{profile: ProfilePlan}``; iterate the result in ``sorted()``
    order if the caller needs a deterministic profile order (dict insertion
    order here already follows ``sorted(profiles)``, but don't rely on that
    without saying so — sort explicitly at the call site too).
    """
    by_profile: dict[str, list[CutItem]] = {}
    for it in items:
        by_profile.setdefault(it.profile, []).append(it)
    return {
        profile: _pack_profile(by_profile[profile], stock_lengths_mm, kerf_mm, end_trim_mm)
        for profile in sorted(by_profile)
    }
