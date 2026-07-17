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
from .component_extension import build_component_extension_guide


_AUTHORING_GRAMMAR: dict[str, object] = {
    "schema": "detailgen/authoring-grammar/v1",
    "scaffold_command": {
        "grammar_argv": ["python", "-m", "detailgen.authoring", "grammar"],
        "argv": [
            "python", "-m", "detailgen.authoring", "scaffold",
            "--slug", "{slug}", "--out", "details",
        ],
        "example": [
            "python", "-m", "detailgen.authoring", "scaffold",
            "--slug", "example_detail", "--out", "details",
            "--component", "base:slab",
            "--set", "base.width=12 in",
            "--set", "base.length=18 in",
            "--place", "base={raw: {at: [0, 0, 0]}}",
        ],
        "repeatable": {
            "--component": "ID:REGISTERED_TYPE",
            "--set": "ID.PARAM=YAML_VALUE",
            "--place": (
                "ID=YAML_MAPPING. Mate fields are direct (no mate wrapper), "
                "for example ID={datum: LOCAL_DATUM, to: TARGET_ID, "
                "to_datum: TARGET_DATUM, flip: true}. The raw wrapper is "
                "required for raw transforms, for example "
                "ID={raw: {at: [0, 0, 0]}}."
            ),
            "--connection": "REGISTERED_TYPE:PART_ID[,PART_ID...]",
            "--connection-set": "ZERO_BASED_INDEX.PARAM=YAML_VALUE",
            "--connection-hardware": "ZERO_BASED_INDEX=PART_ID[,PART_ID...]",
        },
        "length_values": {
            "bare_numbers": "millimeters",
            "generated_document_units": "mm",
            "other_units": "use a unit-suffixed YAML string, such as '42 in'",
        },
        "policy": (
            "Values and placements are explicit; the scaffolder fails closed "
            "instead of inferring geometry. Bare numeric component and "
            "placement lengths are millimeters."
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
        "form_selection": (
            "Choose exactly one form below. Mate fields are authored directly "
            "in the placement mapping; raw and mount fields require their "
            "named YAML wrappers."
        ),
        "exactly_one": {
            "mate": {
                "required": ["datum", "to"],
                "optional": ["to_datum", "offset", "rotate", "flip"],
                "example": {
                    "datum": "cut_near",
                    "to": "previous_member",
                    "to_datum": "cut_far",
                    "flip": True,
                },
                "shape_note": (
                    "Use these keys directly in the placement mapping; do not "
                    "wrap them in a nested mate key."
                ),
                "physical_cut_face_rule": (
                    "For cut_near/cut_far mates, use flip: true so face normals "
                    "oppose. If an omitted or false flip produces interference, "
                    "scaffold reports the exact corrected --place assignment."
                ),
            },
            "raw": {
                "wrapper": "raw",
                "required": ["at"],
                "optional": ["rotate"],
                "shape": {"at": "[x, y, z]", "rotate": "[[axis, degrees], ...]"},
                "example": {"raw": {"at": [0, 0, 0]}},
                "shape_note": (
                    "The raw wrapper is required; author raw fields inside a "
                    "single raw mapping."
                ),
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
        "hardware": "ordered list of declared component ids",
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
            "symmetric_planar_miter": (
                "off_square_degrees = 90 - included_corner_degrees / 2"
            ),
            "length_semantics": "long_point_to_long_point",
            "rule": (
                "Any end_cuts require length_semantics to be authored as "
                "long_point_to_long_point. For equal symmetric planar miters, "
                "derive the conventional off-square angle from the included "
                "corner angle before authoring the cuts."
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
    component_guide = build_component_extension_guide()
    return {
        "schema": "detailgen/authoring-manifest/v2",
        "components": _rows(components),
        "connections": _rows(connection_types),
        "views": sorted(VIEWS),
        "detail_spec_keys": sorted(DETAIL_SPEC_KEYS),
        "authoring_grammar": build_authoring_grammar(),
        "workflow": build_workflow_contract(),
        "component_extensions": {
            "guide_argv": [
                "python", "-m", "detailgen.authoring", "component-guide",
            ],
            "check_argv": [
                "python", "-m", "detailgen.authoring", "component-check",
                "{contract.yaml}",
            ],
            "guide": component_guide,
        },
    }


def authoring_manifest_json() -> str:
    """Serialize the authoring manifest deterministically."""
    return json.dumps(build_authoring_manifest(), indent=2, sort_keys=True) + "\n"
