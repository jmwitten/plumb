"""Compact public vocabulary manifest for low-context DetailSpec authoring."""

import json

from detailgen.authoring import authoring_manifest_json, build_authoring_manifest


def test_authoring_manifest_is_deterministic_and_project_agnostic():
    first = build_authoring_manifest()
    second = json.loads(authoring_manifest_json())

    assert first == second
    assert first["schema"] == "detailgen/authoring-manifest/v1"
    assert first["components"] == sorted(
        first["components"], key=lambda row: row["key"]
    )
    assert first["connections"] == sorted(
        first["connections"], key=lambda row: row["key"]
    )
    assert all(
        set(row) == {"key", "constructor", "summary"}
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
