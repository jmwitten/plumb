"""Stack-based phase timer for the generation-speed benchmark (directive #8).

This module is a standalone leaf: nothing in ``detailgen`` imports it, so it
adds zero overhead to a normal build/validate/render — it only does anything
when ``scripts/benchmark.py`` explicitly imports it and monkeypatches a
handful of pipeline entry points (``Component.solid``, the ``validation``
check_* functions, ``buildinfo.geometry_hash``, the ``rendering.export``
exporters) with wrappers built on :class:`PhaseTimer`. Those wrappers call
straight through to the original function/property — they add timing, never
change behavior, output, or hashes — and every patch is unwound after the
benchmark run, restoring the exact original callable.
"""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager


class PhaseTimer:
    """Accumulates SELF time (wall clock minus time spent in nested phases)
    per named phase, plus a call count.

    "Self time" is the point: if phase B runs nested inside phase A (e.g. a
    component solid build happening lazily inside the interference sweep),
    A's total excludes B's time. That makes a table of every phase's total
    sum to the measured wall clock instead of double-counting nested work —
    the property this benchmark's baseline report leans on to make "where
    does the time go" numbers add up unambiguously.
    """

    def __init__(self) -> None:
        self.totals: dict[str, float] = defaultdict(float)
        self.counts: dict[str, int] = defaultdict(int)
        self._stack: list[list] = []  # each entry: [name, start_time, child_time]

    @contextmanager
    def phase(self, name: str):
        entry = [name, time.perf_counter(), 0.0]
        self._stack.append(entry)
        try:
            yield
        finally:
            self._stack.pop()
            elapsed = time.perf_counter() - entry[1]
            self_time = elapsed - entry[2]
            self.totals[name] += self_time
            self.counts[name] += 1
            if self._stack:
                self._stack[-1][2] += elapsed

    def reset(self) -> None:
        self.totals.clear()
        self.counts.clear()
        self._stack.clear()

    def as_dict(self) -> dict[str, dict[str, float | int]]:
        """``{phase: {"seconds": self_time_total, "count": calls}}``, sorted
        by name for stable JSON diffs."""
        return {
            name: {"seconds": self.totals[name], "count": self.counts[name]}
            for name in sorted(self.totals)
        }

    def wall_total(self) -> float:
        """Sum of every phase's self time — equals the wall clock of the
        outermost measured region, provided every timed span nests cleanly
        under it (no untimed gaps at the root)."""
        return sum(self.totals.values())
