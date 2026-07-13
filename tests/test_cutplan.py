"""Tests for the 1D cut-stock packer (src/core/cutplan.py)."""

import random

import pytest

from detailgen.core import FT, IN
from detailgen.core.cutplan import CutItem, CutPlanError, pack


def test_user_example_3ft_plus_5ft_is_one_8ft_stick():
    """The exact example from the user request: 3 ft + 5 ft of 2x4 should
    become ONE 8 ft stick, not two separate purchases."""
    items = [
        CutItem("2x4 PT", 3 * FT, "test: piece a"),
        CutItem("2x4 PT", 5 * FT, "test: piece b"),
    ]
    plans = pack(items)
    plan = plans["2x4 PT"]
    assert plan.stick_count == 1
    assert plan.sticks[0].stock_length_mm == 8 * FT
    assert {c.length_mm for c in plan.sticks[0].cuts} == {3 * FT, 5 * FT}
    # The stick is fully consumed (exact-fit exemption) — waste is ~0, not
    # negative and not inflated by kerf/end-trim.
    assert plan.total_waste_mm == pytest.approx(0.0, abs=1e-6)


def test_kerf_tips_into_two_sticks():
    """Two cuts that fit an 8 ft stick without kerf (positive raw slack) but
    not once the saw kerf is charged must land on two separate sticks — the
    catalog is restricted to 8 ft only, so there's no bigger stock to escape
    to."""
    stock_8ft_only = (8 * FT,)
    a = 47.9 * IN
    b = 48.0 * IN
    assert a + b < 8 * FT  # positive slack before kerf/end-trim
    items = [CutItem("2x4 PT", a, "test: a"), CutItem("2x4 PT", b, "test: b")]
    plan = pack(items, stock_lengths_mm=stock_8ft_only)["2x4 PT"]
    assert plan.stick_count == 2
    assert all(s.stock_length_mm == 8 * FT for s in plan.sticks)


def test_prefers_one_10ft_over_two_8ft():
    """Two 4.5 ft cuts don't fit together on an 8 ft stick (with kerf/
    end-trim) but do fit on a 10 ft stick — one 10 ft stick (10 ft
    purchased, 1 stick) must beat two 8 ft sticks (16 ft purchased, 2
    sticks) on the 'minimize total purchased length' objective."""
    items = [
        CutItem("2x4 PT", 4.5 * FT, "test: a"),
        CutItem("2x4 PT", 4.5 * FT, "test: b"),
    ]
    plan = pack(items)["2x4 PT"]
    assert plan.stick_count == 1
    assert plan.sticks[0].stock_length_mm == 10 * FT
    assert plan.total_purchased_mm == 10 * FT


def test_determinism_same_order():
    items = [
        CutItem("2x6 PT", 45 * IN, "platform: joist 1"),
        CutItem("2x6 PT", 45 * IN, "platform: joist 2"),
        CutItem("2x6 PT", 33 * IN, "platform: rail"),
        CutItem("2x4 PT", 3 * FT, "platform: brace"),
    ]
    first = pack(items)
    second = pack(items)
    assert first == second


def test_determinism_independent_of_input_order():
    items = [
        CutItem("2x6 PT", 45 * IN, "platform: joist 1"),
        CutItem("2x6 PT", 45 * IN, "platform: joist 2"),
        CutItem("2x6 PT", 33 * IN, "platform: rail"),
        CutItem("2x4 PT", 3 * FT, "platform: brace"),
        CutItem("2x4 PT", 5 * FT, "platform: step"),
    ]
    shuffled = list(items)
    random.Random(42).shuffle(shuffled)
    assert pack(items) == pack(shuffled)


def test_over_length_item_is_a_hard_error():
    items = [CutItem("2x8 PT", 20 * FT, "test: too long")]
    with pytest.raises(CutPlanError, match="exceeds the longest stock length"):
        pack(items)


def test_separate_profiles_never_combine():
    """A 2x4 and a 2x6 cut must never end up packed on the same stick, even
    though both would physically fit length-wise."""
    items = [
        CutItem("2x4 PT", 3 * FT, "test: a"),
        CutItem("2x6 PT", 3 * FT, "test: b"),
    ]
    plans = pack(items)
    assert set(plans) == {"2x4 PT", "2x6 PT"}
    assert plans["2x4 PT"].stick_count == 1
    assert plans["2x6 PT"].stick_count == 1


def test_custom_stock_catalog_and_allowances_are_honored():
    items = [CutItem("2x4", 5 * FT, "test: a")]
    plan = pack(items, stock_lengths_mm=(6 * FT,), kerf_mm=0.0, end_trim_mm=0.0)["2x4"]
    assert plan.stick_count == 1
    assert plan.sticks[0].stock_length_mm == 6 * FT


def test_machine_source_keys_survive_packing_and_stabilize_equal_display_labels():
    """Packing preserves the machine identity independently of visible source text."""
    items = [
        CutItem("1x6", 24 * IN, "fixture: Registration rail", ("fixture", "rail-b")),
        CutItem("1x6", 24 * IN, "fixture: Registration rail", ("fixture", "rail-a")),
    ]

    cuts = pack(items, stock_lengths_mm=(8 * FT,))["1x6"].sticks[0].cuts

    assert [cut.source for cut in cuts] == [
        "fixture: Registration rail",
        "fixture: Registration rail",
    ]
    assert [cut.source_key for cut in cuts] == [
        ("fixture", "rail-a"),
        ("fixture", "rail-b"),
    ]
