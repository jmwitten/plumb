"""Tests for the centralized Tolerances config (src/core/config.py)."""

from dataclasses import FrozenInstanceError, replace

import pytest

from detailgen.core import Tolerances, DEFAULT, IN
from detailgen.assemblies import DetailAssembly
from detailgen.components import Lumber
from detailgen.validation import check_contact, check_no_floaters, validate_assembly


def test_default_reproduces_legacy_values():
    """DEFAULT must match the numbers that used to be hardcoded globals in
    validation/checks.py exactly — default behavior must not change."""
    assert DEFAULT.noise_volume == 1.0
    assert DEFAULT.contact_eps == 2.5e-4
    assert DEFAULT.near_miss == 0.15
    assert DEFAULT.push == 0.03
    assert DEFAULT.contact_bbox_tolerance == 0.5
    assert DEFAULT.dimension_tolerance == 0.5
    assert DEFAULT.bearing_area_ratio == 0.5
    assert DEFAULT.bearing_area_floor == 1.0


def test_tolerances_is_frozen():
    with pytest.raises(FrozenInstanceError):
        DEFAULT.base = 1.0


def _gapped_pair(gap: float):
    """Two 2x4s ``gap`` mm apart in Y, named 'a' and 'b'."""
    detail = DetailAssembly("gap-test")
    a = detail.add(Lumber("2x4", 6 * IN, name="a"))
    b = detail.add(Lumber("2x4", 6 * IN, name="b"), at=(0, 1.5 * IN + gap, 0))
    return detail, a, b


def test_overriding_contact_tolerance_changes_verdict():
    """A 0.6mm bbox gap fails DEFAULT's contact_bbox_tolerance (0.5mm) but
    passes a config that widens it to 1.0mm."""
    _, a, b = _gapped_pair(0.6)

    tight = check_contact(a, b, tol=DEFAULT)
    assert not tight.passed

    loose_tol = replace(DEFAULT, contact_bbox_tolerance=1.0)
    loose = check_contact(a, b, tol=loose_tol)
    assert loose.passed


def test_overriding_near_miss_changes_floating_part_verdict():
    """check_no_floaters links two parts only if their gap is within
    ``near_miss``. A 0.3mm gap is outside DEFAULT's near_miss (0.15mm) so 'b'
    is reported floating; widening near_miss (via base) links it instead."""
    detail, a, b = _gapped_pair(0.3)

    tight = check_no_floaters(detail, bearings=[("a", "b", "Y", 0.0)],
                              bonds=[], ground="a", tol=DEFAULT)
    assert not tight[0].passed

    loose_tol = replace(DEFAULT, base=0.5)  # near_miss becomes 300mm >> 0.3mm gap
    loose = check_no_floaters(detail, bearings=[("a", "b", "Y", 0.0)],
                              bonds=[], ground="a", tol=loose_tol)
    assert loose[0].passed


def test_validate_assembly_accepts_custom_tolerances_without_mutating_default():
    """A detail can pass its own Tolerances through validate_assembly without
    mutating any global state (DEFAULT stays untouched afterward)."""
    detail, _, _ = _gapped_pair(0.6)

    custom = replace(DEFAULT, contact_bbox_tolerance=1.0)
    report = validate_assembly(detail, contacts=[("a", "b")], tol=custom)
    assert report.ok, str(report)

    assert DEFAULT.contact_bbox_tolerance == 0.5  # global default untouched
