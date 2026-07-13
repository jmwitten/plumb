"""PhaseTimer: nested self-time bookkeeping must add up to the wall clock,
with no dependency on cadquery — this is pure bookkeeping, tested in
isolation from the (slow) geometry pipeline."""

from __future__ import annotations

import time

from detailgen.core.timing import PhaseTimer


def test_flat_phase_self_time_matches_elapsed():
    t = PhaseTimer()
    with t.phase("a"):
        time.sleep(0.02)
    assert t.totals["a"] > 0.015
    assert t.counts["a"] == 1


def test_nested_phase_excluded_from_parent_self_time():
    t = PhaseTimer()
    with t.phase("outer"):
        time.sleep(0.02)
        with t.phase("inner"):
            time.sleep(0.15)
        time.sleep(0.02)
    # outer's SELF time should be ~0.04 (its own sleeps), not ~0.19 (incl.
    # inner) — generous margins since sleep() has OS-scheduling jitter under
    # load; this asserts an ordering, not a tight bound.
    assert t.totals["outer"] < t.totals["inner"]
    assert t.totals["outer"] < 0.1
    assert t.totals["inner"] > 0.1


def test_repeated_calls_accumulate_and_count():
    t = PhaseTimer()
    for _ in range(3):
        with t.phase("build:Washer"):
            time.sleep(0.005)
    assert t.counts["build:Washer"] == 3
    assert t.totals["build:Washer"] > 0.01


def test_wall_total_sums_every_phase_no_double_count():
    # 0.05s (not 0.01s) sleeps: the bound below needs to separate "no double
    # count" (~0.15s: 3 leaf sleeps, none counted twice) from the exact bug
    # this test is named for (self_time = elapsed instead of
    # elapsed - entry[2], which double-counts the nested phase's own 0.05s
    # into "validate" too -> ~0.20s) by a margin wider than sleep()'s
    # scheduling jitter. At 0.01s per sleep the gap between the two
    # (0.03s vs 0.04s) was too close to jitter to bound tightly; the original
    # 0.025-0.06 range comfortably contained both, so it never caught this.
    t = PhaseTimer()
    start = time.perf_counter()
    with t.phase("assemble"):
        time.sleep(0.05)
    with t.phase("validate"):
        time.sleep(0.05)
        with t.phase("validate:interference"):
            time.sleep(0.05)
    elapsed = time.perf_counter() - start
    # Compare against MEASURED elapsed, not fixed constants: under -n auto
    # load, sleep() overshoot pushed wall_total past a fixed 0.18 ceiling
    # (observed 0.18012) on a correct implementation. Overshoot moves
    # elapsed and wall_total together, so the measured bound is
    # load-insensitive AND a tighter discriminator: the double-count bug
    # this test is named for adds a full extra 0.05s leaf sleep
    # (wall_total ~= elapsed + 0.05), far outside the +0.025 margin.
    assert elapsed - 0.025 < t.wall_total() < elapsed + 0.025


def test_as_dict_schema():
    t = PhaseTimer()
    with t.phase("x"):
        pass
    d = t.as_dict()
    assert d == {"x": {"seconds": d["x"]["seconds"], "count": 1}}
    assert isinstance(d["x"]["seconds"], float)


def test_reset_clears_state():
    t = PhaseTimer()
    with t.phase("x"):
        pass
    t.reset()
    assert t.totals == {}
    assert t.counts == {}
    assert t._stack == []
