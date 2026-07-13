"""SM3b — the ValidationSpec surface added to close the tree/trolley residual:
``expected_overlaps:`` / ``contacts:`` allowlist/touch blocks and the DimensionSpec
generalizations (cross-part ``minus_part``/``minus_measure`` difference, and a
``ge``/``gt`` threshold ``op``). Same strict-loading + did-you-mean + serialize
round-trip culture as every existing block (schema.py / loader.py / serialize.py).
"""

from __future__ import annotations

import pytest

from detailgen.spec.loader import load_spec_text
from detailgen.spec.serialize import dump_json, dump_yaml
from detailgen.spec.schema import SpecSchemaError

_HEAD = """
name: t
units: in
params: {r: 5.0, gap: 0.25}
components:
  - {id: a, type: lumber, name: A, params: {nominal: "2x6", length: "10 in"}}
  - {id: b, type: lumber, name: B, params: {nominal: "2x6", length: "10 in"}}
"""


def _load(validation: str):
    return load_spec_text(_HEAD + "validation:\n" + validation)


# -- expected_overlaps / contacts -------------------------------------------- #
def test_expected_overlaps_and_contacts_load():
    doc = _load("  expected_overlaps:\n    - {a: a, b: b}\n"
                "  contacts:\n    - {a: a, b: b}\n")
    assert len(doc.validation.expected_overlaps) == 1
    assert len(doc.validation.contacts) == 1
    assert doc.validation.expected_overlaps[0].a == "a"


def test_expected_overlaps_unknown_key_is_teaching_error():
    with pytest.raises(SpecSchemaError) as e:
        _load("  expected_overlaps:\n    - {a: a, bb: b}\n")
    assert "unknown key 'bb'" in str(e.value)


def test_contacts_missing_key_is_teaching_error():
    with pytest.raises(SpecSchemaError) as e:
        _load("  contacts:\n    - {a: a}\n")
    assert "missing required key 'b'" in str(e.value)


# -- DimensionSpec: cross-part + threshold ----------------------------------- #
def test_cross_part_dimension_loads():
    doc = _load("  dimensions:\n"
                "    - {name: d, part: a, measure: zmid, minus_part: b, "
                "minus_measure: zmax, expected: '$gap'}\n")
    d = doc.validation.dimensions[0]
    assert d.minus_part == "b" and d.minus_measure == "zmax" and d.op == "eq"


def test_threshold_op_loads():
    doc = _load("  dimensions:\n"
                "    - {name: d, part: a, measure: ymin, op: gt, expected: '$r'}\n")
    assert doc.validation.dimensions[0].op == "gt"


def test_bad_op_is_teaching_error():
    with pytest.raises(SpecSchemaError) as e:
        _load("  dimensions:\n"
              "    - {name: d, part: a, measure: ymin, op: lt, expected: '$r'}\n")
    assert "'op'" in str(e.value) and "ge" in str(e.value)


def test_half_a_cross_part_pair_is_teaching_error():
    """A cross-part difference needs BOTH minus_part and minus_measure."""
    with pytest.raises(SpecSchemaError) as e:
        _load("  dimensions:\n"
              "    - {name: d, part: a, measure: zmid, minus_part: b, "
              "expected: '$gap'}\n")
    assert "minus_part" in str(e.value) and "minus_measure" in str(e.value)


# -- serialize round-trip ---------------------------------------------------- #
def test_new_surface_round_trips_yaml_and_json():
    doc = _load(
        "  expected_overlaps:\n    - {a: a, b: b}\n"
        "  contacts:\n    - {a: b, b: a}\n"
        "  dimensions:\n"
        "    - {name: cross, part: a, measure: zmid, minus_part: b, "
        "minus_measure: zmax, expected: '$gap'}\n"
        "    - {name: thresh, part: a, measure: ymin, negate: true, op: gt, "
        "expected: '$r'}\n")
    assert load_spec_text(dump_yaml(doc)) == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc


def test_eq_default_dimension_omits_op_on_dump():
    """An ordinary (eq, single-part) dimension serializes exactly as before —
    no op/minus_* keys — so every pre-SM3b spec round-trips unchanged."""
    doc = _load("  dimensions:\n"
                "    - {name: d, part: a, measure: zmax, expected: '$r'}\n")
    dumped = dump_yaml(doc)
    assert "op:" not in dumped and "minus_part" not in dumped
    assert load_spec_text(dumped) == doc
