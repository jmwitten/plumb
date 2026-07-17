"""Compact public vocabulary manifest for low-context DetailSpec authoring."""

import json

from detailgen.authoring import authoring_manifest_json, build_authoring_manifest


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
