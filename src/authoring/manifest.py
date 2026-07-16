"""Derive a small, deterministic authoring surface from live registries."""

from __future__ import annotations

import inspect
import json

from .. import components as _load_components  # noqa: F401
from ..assemblies.connection import connection_types
from ..core.registry import components
from ..rendering.export import VIEWS
from ..spec.loader import DETAIL_SPEC_KEYS


def _summary(obj: object) -> str:
    text = inspect.getdoc(obj) or ""
    return text.split("\n\n", 1)[0].replace("\n", " ").strip()


def _rows(registry: object) -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "constructor": str(inspect.signature(registry.get(key))),
            "summary": _summary(registry.get(key)),
        }
        for key in sorted(registry.names())
    ]


def build_authoring_manifest() -> dict[str, object]:
    """Return the live, project-agnostic vocabulary needed to author a spec."""
    return {
        "schema": "detailgen/authoring-manifest/v1",
        "components": _rows(components),
        "connections": _rows(connection_types),
        "views": sorted(VIEWS),
        "detail_spec_keys": sorted(DETAIL_SPEC_KEYS),
    }


def authoring_manifest_json() -> str:
    """Serialize the authoring manifest deterministically."""
    return json.dumps(build_authoring_manifest(), indent=2, sort_keys=True) + "\n"
