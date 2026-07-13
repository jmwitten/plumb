"""Presentation-only reader names for authored and placed components."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

from detailgen.core.buildinfo import geometry_hash
from detailgen.rendering.inspector import build_inspector_payload
from detailgen.rendering.part_labels import part_labels
from detailgen.rendering.web_viewer import build_viewer_payload
from detailgen.spec import (
    SpecSchemaError,
    compile_spec,
    compile_spec_file,
    dump_yaml,
    load_spec_file,
    load_spec_text,
)


ROOT = Path(__file__).resolve().parents[1]
CADDY = ROOT / "details" / "armchair_caddy.spec.yaml"


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


def compile_caddy():
    detail = compile_spec_file(CADDY)
    detail.validate()
    return detail


@pytest.fixture(scope="module")
def caddy_html(tmp_path_factory):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import single_detail_report as SDR

    out = tmp_path_factory.mktemp("reader-names") / "caddy.html"
    SDR.build_document(out, spec_path=CADDY, preview=False)
    return out.read_text()


def finding_signature(detail):
    return tuple(
        (finding.verdict, finding.check, finding.subject, finding.detail)
        for finding in detail.validate().findings
    )


def solid_hashes(detail):
    return tuple(
        (part.name, geometry_hash(part.world_solid()))
        for part in detail.assembly.parts
    )


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
    assert [x.display_name for x in rails] == [
        "Registration rail (1 of 2)",
        "Registration rail (2 of 2)",
    ]


def test_part_labels_fall_back_to_machine_name():
    detail = build_text(LEGACY_RAIL_YAML)
    part = detail.assembly.parts[0]
    label = part_labels(detail.assembly.parts)[part.id]
    assert label.machine_name == "legacy machine name"
    assert label.reader_name == "legacy machine name"
    assert (label.index, label.count) == (1, 1)
    assert label.display_name == "legacy machine name"


def test_caddy_ordinals_match_projection_viewer_and_inspector():
    detail = compile_caddy()
    labels = part_labels(detail.assembly.parts)
    viewer = build_viewer_payload(detail)["parts"]
    inspector = build_inspector_payload(detail)["parts"]
    repeated = [
        part
        for part in detail.assembly.parts
        if part.reader_name in {"Registration rail", "Rail-to-side screw"}
    ]

    assert [labels[part.id].display_name for part in repeated] == [
        "Registration rail (1 of 2)",
        "Registration rail (2 of 2)",
        "Rail-to-side screw (1 of 8)",
        "Rail-to-side screw (2 of 8)",
        "Rail-to-side screw (3 of 8)",
        "Rail-to-side screw (4 of 8)",
        "Rail-to-side screw (5 of 8)",
        "Rail-to-side screw (6 of 8)",
        "Rail-to-side screw (7 of 8)",
        "Rail-to-side screw (8 of 8)",
    ]
    for part in repeated:
        label = labels[part.id]
        assert (
            viewer[part.name]["reader_name"],
            viewer[part.name]["instance_index"],
            viewer[part.name]["instance_count"],
        ) == (label.reader_name, label.index, label.count)
        assert inspector[part.name]["reader_name"] == label.reader_name
        assert inspector[part.name]["instance_index"] == label.index
        assert inspector[part.name]["instance_count"] == label.count
        assert inspector[part.name]["display_name"] == label.display_name


def test_caddy_authors_the_closed_reader_vocabulary():
    expected = {
        "arm": ("sofa arm", "Sofa arm"),
        "side_pos": ("side board +X", "Side board"),
        "side_neg": ("side board -X", "Side board"),
        "top": ("top board", "Top board"),
        "cleat_pos": ("registration rail +X", "Registration rail"),
        "cleat_neg": ("registration rail -X", "Registration rail"),
        "hscrew_p0": ("rail-side screw +X upper 0", "Rail-to-side screw"),
        "hscrew_p1": ("rail-side screw +X upper 1", "Rail-to-side screw"),
        "hscrew_p2": ("rail-side screw +X lower 0", "Rail-to-side screw"),
        "hscrew_p3": ("rail-side screw +X lower 1", "Rail-to-side screw"),
        "hscrew_m0": ("rail-side screw -X upper 0", "Rail-to-side screw"),
        "hscrew_m1": ("rail-side screw -X upper 1", "Rail-to-side screw"),
        "hscrew_m2": ("rail-side screw -X lower 0", "Rail-to-side screw"),
        "hscrew_m3": ("rail-side screw -X lower 1", "Rail-to-side screw"),
    }

    doc = load_spec_file(CADDY)
    assert {
        component.id: (component.name, component.reader_name)
        for component in doc.components
    } == expected
    detail = compile_spec(doc)
    detail.validate()
    expected_by_machine = {
        machine_name: reader_name
        for machine_name, reader_name in expected.values()
    }
    assert {
        part.name: part.reader_name
        for part in detail.assembly.parts
    } == expected_by_machine
    assert {part.reader_name for part in detail.assembly.parts} == {
        "Sofa arm",
        "Side board",
        "Top board",
        "Registration rail",
        "Rail-to-side screw",
    }


def test_reader_name_only_edit_is_geometry_and_truth_inert():
    original = compile_caddy()
    doc = load_spec_file(CADDY)
    components = tuple(
        replace(component, reader_name="Registration cleat")
        if getattr(component, "id", None) == "cleat_pos"
        else component
        for component in doc.components
    )
    renamed = compile_spec(replace(doc, components=components))

    assert solid_hashes(original) == solid_hashes(renamed)
    assert finding_signature(original) == finding_signature(renamed)
    assert [part.name for part in original.assembly.parts] == [
        part.name for part in renamed.assembly.parts
    ]


def test_caddy_reader_surfaces_share_the_same_rail_label(caddy_html):
    from detailgen.validation.build_sequence import build_sequence_model

    detail = compile_caddy()
    sequence, _loose = build_sequence_model(detail)
    placed_names = [
        name
        for step in sequence
        for name, _bom, _fab in step["places"]
    ]
    assert [name for name in placed_names if name.startswith("Registration rail")] == [
        "Registration rail (1 of 2)",
        "Registration rail (2 of 2)",
    ]

    cut_plan = caddy_html.split(
        '<section class="notes cutplan">', 1)[1].split("</section>", 1)[0]
    assert cut_plan.count("Registration rail (1 of 2)") == 1
    assert cut_plan.count("Registration rail (2 of 2)") == 1
    assert "registration rail +X" not in cut_plan
    assert "registration rail -X" not in cut_plan

    payload = build_inspector_payload(detail)
    assert [
        part["display_name"]
        for part in payload["parts"].values()
        if part["reader_name"] == "Registration rail"
    ] == ["Registration rail (1 of 2)", "Registration rail (2 of 2)"]


def test_caddy_existing_context_uses_reader_name_in_bom_and_hover(caddy_html):
    existing = caddy_html.split(
        '<div class="existing">', 1)[1].split("</div>", 1)[0]
    assert "Sofa arm (existing)" in existing
    assert "sofa arm (existing)" not in existing

    payload_json = caddy_html.split(
        '<script type="application/json" id="detail-data-', 1
    )[1].split(">", 1)[1].split("</script>", 1)[0]
    payload = json.loads(payload_json)
    assert "sofa arm" in payload["parts"]
    assert payload["parts"]["sofa arm"]["item"] == "Sofa arm (existing)"


def test_machine_connection_labels_remain_in_raw_contract_appendix(caddy_html):
    appendix = caddy_html.split(
        "<section class='notes install-disclosure'>", 1
    )[1].split("</section>", 1)[0]
    assert "rail +X" in appendix

    sequence = caddy_html.split(
        "<section class='notes build-sequence'>", 1
    )[1].split("</section>", 1)[0]
    assert "place Registration rail (1 of 2)" in sequence
    assert "place Registration rail (2 of 2)" in sequence
    assert "place registration rail +X" not in sequence
