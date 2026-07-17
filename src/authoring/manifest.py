"""Derive a small, deterministic authoring surface from live registries."""

from __future__ import annotations

import inspect
import json
from copy import deepcopy

from .. import components as _load_components  # noqa: F401
from ..assemblies.connection import connection_types
from ..core.registry import components
from ..rendering.export import VIEWS
from ..spec.loader import DETAIL_SPEC_KEYS
from .workflow import build_workflow_contract


_AUTHORING_GRAMMAR: dict[str, object] = {
    "schema": "detailgen/authoring-grammar/v1",
    "scaffold_command": {
        "argv": [
            "python", "-m", "detailgen.authoring", "scaffold",
            "--slug", "{slug}", "--out", "details",
        ],
        "repeatable": {
            "--component": "ID:REGISTERED_TYPE",
            "--set": "ID.PARAM=YAML_VALUE",
            "--place": "ID=YAML_PLACEMENT_MAPPING",
            "--connection": "REGISTERED_TYPE:PART_ID[,PART_ID...]",
            "--connection-set": "ZERO_BASED_INDEX.PARAM=YAML_VALUE",
        },
        "policy": (
            "Values and placements are explicit; the scaffolder fails closed "
            "instead of inferring geometry."
        ),
    },
    "detail_spec": {
        "required": ["name", "components"],
        "optional": sorted(key for key, required in DETAIL_SPEC_KEYS.items()
                           if not required),
    },
    "component": {
        "required": ["id", "type"],
        "optional": ["name", "reader_name", "params", "place", "features", "was"],
        "params": "mapping passed to the selected registered component",
    },
    "placement": {
        "exactly_one": {
            "mate": {
                "required": ["datum", "to"],
                "optional": ["to_datum", "offset", "rotate", "flip"],
            },
            "raw": {
                "required": ["at"],
                "optional": ["rotate"],
                "shape": {"at": "[x, y, z]", "rotate": "[[axis, degrees], ...]"},
            },
            "mount": {
                "required": ["to", "face", "axis"],
                "standoff_exactly_one": ["flush", "clear_by", "offset"],
                "optional": ["center", "ground", "mirror"],
            },
        },
        "omitted": (
            "Identity placement at the origin; valid syntax, but multiple "
            "members may remain physically unresolved."
        ),
    },
    "connection": {
        "required": ["type", "parts"],
        "optional": [
            "hardware", "params", "surfaces", "assumptions", "label",
            "expect", "install", "process",
        ],
        "params": "mapping passed to the selected registered connection type",
    },
    "validation": {
        "dimensions": {
            "required": ["name", "part", "measure", "expected"],
            "optional": [
                "tolerance", "negate", "op", "minus_part", "minus_measure",
            ],
            "measures": [
                "xmin", "xmax", "xmid", "xlen",
                "ymin", "ymax", "ymid", "ylen",
                "zmin", "zmax", "zmid", "zlen",
            ],
            "semantics": (
                "Every measure is taken from the placed solid's world-axis "
                "bounding box; xlen/ylen/zlen are world-axis projections."
            ),
            "rotation_invariant_member_length": None,
            "intrinsic_length_guidance": (
                "No intrinsic member-length measure exists: do not use xlen "
                "for a rotated member; omit the claim or extend the platform."
            ),
        },
    },
    "component_conventions": {
        "lumber": {
            "end_cuts": "list of end-cut mappings",
            "end_cut_required": ["end", "miter_angle_degrees", "long_face"],
            "end": ["near", "far"],
            "long_face": ["top", "bottom"],
            "miter_angle_degrees": "degrees off square",
            "length_semantics": "long_point_to_long_point",
            "rule": (
                "Any end_cuts require length_semantics to be authored as "
                "long_point_to_long_point."
            ),
        },
    },
    "certification_contract": {
        "filename": "{slug}.cert.yaml",
        "minimal": {
            "schema_version": 1,
            "subject": {
                "kind": "standalone_detail",
                "source": "{slug}.spec.yaml",
            },
        },
    },
}


def build_authoring_grammar() -> dict[str, object]:
    """Return an isolated compact guide to valid nested authoring shapes."""
    return deepcopy(_AUTHORING_GRAMMAR)


def _summary(obj: object) -> str:
    text = inspect.getdoc(obj) or ""
    return text.split("\n\n", 1)[0].replace("\n", " ").strip()


def _parameters(obj: object) -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "required": parameter.default is inspect.Parameter.empty,
            "kind": parameter.kind.name.lower(),
        }
        for name, parameter in inspect.signature(obj).parameters.items()
        if name not in {"self", "cls"}
    ]


def _rows(registry: object) -> list[dict[str, object]]:
    return [
        {
            "key": key,
            "constructor": str(inspect.signature(registry.get(key))),
            "summary": _summary(registry.get(key)),
            "parameters": _parameters(registry.get(key)),
        }
        for key in sorted(registry.names())
    ]


def build_authoring_manifest() -> dict[str, object]:
    """Return the live, project-agnostic vocabulary needed to author a spec."""
    return {
        "schema": "detailgen/authoring-manifest/v3",
        "components": _rows(components),
        "connections": _rows(connection_types),
        "views": sorted(VIEWS),
        "detail_spec_keys": sorted(DETAIL_SPEC_KEYS),
        "authoring_grammar": build_authoring_grammar(),
        "workflow": build_workflow_contract(),
    }


def authoring_manifest_json() -> str:
    """Serialize the authoring manifest deterministically."""
    return json.dumps(build_authoring_manifest(), indent=2, sort_keys=True) + "\n"
