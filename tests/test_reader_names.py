"""Presentation-only reader names for authored and placed components."""

from __future__ import annotations

import pytest

from detailgen.rendering.part_labels import part_labels
from detailgen.spec import SpecSchemaError, compile_spec, dump_yaml, load_spec_text


ONE_RAIL_YAML = """
name: reader-name-one-rail
components:
  - id: rail
    type: lumber
    name: rail machine name
    reader_name: READER_VALUE
    params: {nominal: "2x6", length: "6 in"}
"""


TWO_RAILS_YAML = """
name: reader-name-two-rails
components:
  - id: rail_pos
    type: lumber
    name: rail +X
    reader_name: Registration rail
    params: {nominal: "2x6", length: "6 in"}
  - id: rail_neg
    type: lumber
    name: rail -X
    reader_name: Registration rail
    params: {nominal: "2x6", length: "6 in"}
"""


REPEATED_RAILS_YAML = """
name: reader-name-repeated-rails
components:
  - repeat: {var: i, count: 1}
    body:
      - id: rail_pos_{i}
        type: lumber
        name: rail +X
        reader_name: Registration rail
        params: {nominal: "2x6", length: "6 in"}
      - id: rail_neg_{i}
        type: lumber
        name: rail -X
        reader_name: Registration rail
        params: {nominal: "2x6", length: "6 in"}
"""


INTERPOLATED_READER_NAMES_YAML = """
name: interpolated-reader-names
components:
  - repeat: {var: i, count: 2}
    body:
      - id: rail_{i}
        type: lumber
        name: machine rail {i}
        reader_name: Reader rail {i}
        params: {nominal: "2x6", length: "6 in"}
"""


LEGACY_RAIL_YAML = """
name: reader-name-legacy-rail
components:
  - id: legacy_rail
    type: lumber
    name: legacy machine name
    params: {nominal: "2x6", length: "6 in"}
"""


def build_text(text: str):
    detail = compile_spec(load_spec_text(text))
    detail.build()
    return detail


def test_reader_name_loads_and_duplicate_values_are_allowed():
    doc = load_spec_text(TWO_RAILS_YAML)
    assert [c.reader_name for c in doc.components] == [
        "Registration rail", "Registration rail"]


@pytest.mark.parametrize("bad", ['""', '"   "', "3", "null"])
def test_reader_name_rejects_empty_or_non_string_values(bad):
    text = ONE_RAIL_YAML.replace("READER_VALUE", bad)
    with pytest.raises(SpecSchemaError, match="reader_name.*non-empty"):
        load_spec_text(text)


def test_compiler_interpolates_reader_name_without_changing_machine_name():
    detail = build_text(REPEATED_RAILS_YAML)
    rails = [p for p in detail.assembly.parts if p.name.startswith("rail ")]
    assert [p.name for p in rails] == ["rail +X", "rail -X"]
    assert [p.reader_name for p in rails] == [
        "Registration rail", "Registration rail"]


def test_reader_name_repeat_template_interpolates_each_instance():
    detail = build_text(INTERPOLATED_READER_NAMES_YAML)
    assert [p.reader_name for p in detail.assembly.parts] == [
        "Reader rail 0", "Reader rail 1"]


def test_reader_name_round_trip_and_omission_fallback():
    authored = load_spec_text(ONE_RAIL_YAML.replace(
        "READER_VALUE", '"Registration rail"'))
    assert load_spec_text(dump_yaml(authored)) == authored
    legacy = build_text(LEGACY_RAIL_YAML)
    part = legacy.assembly.parts[0]
    assert part.reader_name == ""
    assert part.name == "legacy machine name"


def test_part_labels_number_duplicate_reader_names_once():
    detail = build_text(TWO_RAILS_YAML)
    labels = part_labels(detail.assembly.parts)
    rails = [
        labels[p.id]
        for p in detail.assembly.parts
        if p.reader_name == "Registration rail"
    ]
    assert [(x.reader_name, x.index, x.count) for x in rails] == [
        ("Registration rail", 1, 2),
        ("Registration rail", 2, 2),
    ]


def test_part_labels_fall_back_to_machine_name():
    detail = build_text(LEGACY_RAIL_YAML)
    part = detail.assembly.parts[0]
    label = part_labels(detail.assembly.parts)[part.id]
    assert label.machine_name == "legacy machine name"
    assert label.reader_name == "legacy machine name"
    assert (label.index, label.count) == (1, 1)
