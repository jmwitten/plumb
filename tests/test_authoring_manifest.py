"""Compact public vocabulary manifest for low-context DetailSpec authoring."""

import json

from detailgen.authoring import (
    authoring_manifest_json,
    build_authoring_grammar,
    build_authoring_manifest,
)


def test_authoring_manifest_is_deterministic_and_project_agnostic():
    first = build_authoring_manifest()
    second = json.loads(authoring_manifest_json())

    assert first == second
    assert first["schema"] == "detailgen/authoring-manifest/v2"
    assert first["components"] == sorted(
        first["components"], key=lambda row: row["key"]
    )
    assert first["connections"] == sorted(
        first["connections"], key=lambda row: row["key"]
    )
    assert all(
        set(row) == {"key", "constructor", "summary", "parameters"}
        for row in (*first["components"], *first["connections"])
    )
    assert first["views"] == sorted(first["views"])
    assert first["detail_spec_keys"] == sorted(first["detail_spec_keys"])
    assert "built_up_2x4" not in authoring_manifest_json().lower()


def test_authoring_manifest_covers_live_registries_and_schema():
    from detailgen.assemblies import connection_types
    from detailgen.core.registry import components
    from detailgen.rendering.export import VIEWS
    from detailgen.spec.loader import DETAIL_SPEC_KEYS

    payload = build_authoring_manifest()

    assert [row["key"] for row in payload["components"]] == sorted(
        components.names()
    )
    assert [row["key"] for row in payload["connections"]] == sorted(
        connection_types.names()
    )
    assert payload["views"] == sorted(VIEWS)
    assert payload["detail_spec_keys"] == sorted(DETAIL_SPEC_KEYS)


def test_authoring_manifest_publishes_parameters_and_workflow_contract():
    payload = build_authoring_manifest()

    lumber = next(row for row in payload["components"] if row["key"] == "lumber")
    lumber_parameters = {parameter["name"] for parameter in lumber["parameters"]}

    assert payload["schema"] == "detailgen/authoring-manifest/v2"
    assert {"end_cuts", "length_semantics"} <= lumber_parameters
    assert "miter_angle_degrees" in lumber["summary"]
    assert "long_point_to_long_point" in lumber["summary"]
    assert all(
        set(row) == {"key", "constructor", "summary", "parameters"}
        for row in (*payload["components"], *payload["connections"])
    )
    assert all(
        set(parameter) == {"name", "required", "kind"}
        for row in (*payload["components"], *payload["connections"])
        for parameter in row["parameters"]
    )
    assert payload["workflow"] == {
        "schema": "detailgen/workflow-contract/v1",
        "tests": {
            "product_inner": {
                "argv": [
                    "pytest",
                    "--detail-gate",
                    "{slug}",
                    "--detail-cadence",
                    "inner",
                    "-q",
                ],
                "normal_product_gate": True,
            },
            "product_release": {
                "argv": [
                    "pytest",
                    "--detail-gate",
                    "{slug}",
                    "--detail-cadence",
                    "release",
                    "-q",
                ],
                "normal_product_gate": True,
            },
            "platform_integration": {
                "argv": ["pytest", "--platform-tier", "integration", "-q"],
                "normal_product_gate": False,
            },
            "platform_audit": {
                "argv": ["pytest", "--platform-tier", "audit", "-q"],
                "normal_product_gate": False,
            },
            "repository_verification": {
                "argv": ["pytest", "-q", "-n", "4"],
                "normal_product_gate": False,
            },
        },
    }


def test_authoring_manifest_publishes_compact_nested_grammar():
    grammar = build_authoring_manifest()["authoring_grammar"]

    assert grammar["schema"] == "detailgen/authoring-grammar/v1"
    assert grammar["detail_spec"]["required"] == ["name", "components"]
    assert grammar["component"]["required"] == ["id", "type"]
    assert set(grammar["placement"]["exactly_one"]) == {"mate", "raw", "mount"}
    assert grammar["connection"]["required"] == ["type", "parts"]
    assert grammar["certification_contract"]["minimal"]["subject"]["kind"] \
        == "standalone_detail"
    assert grammar["scaffold_command"]["argv"][:3] == [
        "python", "-m", "detailgen.authoring",
    ]
    assert grammar["scaffold_command"]["grammar_argv"] == [
        "python", "-m", "detailgen.authoring", "grammar",
    ]
    assert "--component" in grammar["scaffold_command"]["example"]
    assert "--set" in grammar["scaffold_command"]["example"]
    assert "--connection-hardware" in grammar["scaffold_command"]["repeatable"]
    assert grammar["scaffold_command"]["length_values"] == {
        "bare_numbers": "millimeters",
        "generated_document_units": "mm",
        "other_units": "use a unit-suffixed YAML string, such as '42 in'",
    }

    grammar["component"]["required"].append("mutation")
    assert "mutation" not in build_authoring_grammar()["component"]["required"]


def test_authoring_grammar_is_explicit_about_dimension_and_lumber_conventions():
    grammar = build_authoring_manifest()["authoring_grammar"]
    dimensions = grammar["validation"]["dimensions"]
    lumber = grammar["component_conventions"]["lumber"]

    assert set(dimensions["measures"]) == {
        "xmin", "xmax", "xmid", "xlen",
        "ymin", "ymax", "ymid", "ylen",
        "zmin", "zmax", "zmid", "zlen",
    }
    assert "world-axis bounding box" in dimensions["semantics"]
    assert dimensions["rotation_invariant_member_length"] is None
    assert "do not use xlen" in dimensions["intrinsic_length_guidance"]

    assert lumber["miter_angle_degrees"] == "degrees off square"
    assert lumber["symmetric_planar_miter"] == (
        "off_square_degrees = 90 - included_corner_degrees / 2"
    )
    assert lumber["end_cut_required"] == [
        "end", "miter_angle_degrees", "long_face",
    ]
    assert lumber["length_semantics"] == "long_point_to_long_point"
    place_help = grammar["scaffold_command"]["repeatable"]["--place"]
    assert "Mate fields are direct" in place_help
    assert "raw wrapper is required" in place_help
    form_selection = grammar["placement"]["form_selection"]
    assert "Mate fields are authored directly" in form_selection
    assert "raw and mount fields require their named YAML wrappers" in form_selection
    mate = grammar["placement"]["exactly_one"]["mate"]
    raw = grammar["placement"]["exactly_one"]["raw"]
    assert mate["example"] == {
        "datum": "cut_near",
        "to": "previous_member",
        "to_datum": "cut_far",
        "flip": True,
    }
    assert "do not wrap" in mate["shape_note"]
    assert raw["wrapper"] == "raw"
    assert raw["example"] == {"raw": {"at": [0, 0, 0]}}
    assert "raw wrapper is required" in raw["shape_note"]
    cut_face_rule = mate["physical_cut_face_rule"]
    assert "flip: true" in cut_face_rule
    assert "normals oppose" in cut_face_rule
    assert "exact corrected --place assignment" in cut_face_rule
