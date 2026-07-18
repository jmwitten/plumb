"""Small, risk-classified contracts for extending public component vocabulary."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import MappingProxyType
from typing import Mapping

import yaml

from .. import components as _load_components  # noqa: F401
from ..core.registry import components
from ..spec import compile_spec, load_spec_text
from ..spec.values import Resolver, SpecValueError


FAMILY_GUIDANCE: dict[str, dict[str, object]] = {
    "stock_member": {
        "examples": ["dimensional lumber", "rod", "tube", "bar", "profile"],
        "expected_evidence": ["section", "length", "end datums", "material"],
    },
    "sheet_panel": {
        "examples": ["plywood", "wood panel", "sheet metal", "glazing"],
        "expected_evidence": [
            "length", "width", "thickness", "face datums", "fabrication",
        ],
    },
    "fastener": {
        "examples": ["screws", "nails", "bolts", "nuts", "washers", "dowels"],
        "expected_evidence": [
            "axis datums", "capabilities", "envelope", "installation meaning",
        ],
    },
    "connector": {
        "examples": ["bracket", "hanger", "plate", "tie"],
        "expected_evidence": [
            "mounting datums", "holes", "compatible connection semantics",
        ],
    },
    "foundation_site": {
        "examples": ["concrete", "masonry", "anchor", "existing wall", "tree"],
        "expected_evidence": [
            "contact datums", "field facts", "honest capacity and code unknowns",
        ],
    },
    "manufactured_hardware": {
        "examples": ["hinge", "slide", "latch", "wheel", "appliance"],
        "expected_evidence": [
            "manufacturer or proxy identity", "motion", "clearance semantics",
        ],
    },
    "custom_geometry": {
        "examples": ["irregular fabrication", "imported manufacturer part"],
        "expected_evidence": [
            "source asset", "geometry invariants", "explicit review",
        ],
    },
}

COMPONENT_FAMILIES = tuple(FAMILY_GUIDANCE)


CHANGE_CLASSES: dict[str, dict[str, object]] = {
    "catalog_variant": {
        "lane": "micro",
        "budget_seconds": 60,
        "result": "PASS",
        "required_evidence": [
            "public_compile",
            "component_check",
            "geometry_dimensions",
            "declared_datums_capabilities_material",
        ],
    },
    "new_primitive": {
        "lane": "standard",
        "budget_seconds": 60,
        "result": "PASS",
        "required_evidence": [
            "micro_lane",
            "registry_manifest",
            "positive_geometry",
            "bom_identity",
            "invalid_parameter_rejection",
        ],
    },
    "semantic_component": {
        "lane": "semantic",
        "budget_seconds": 60,
        "result": "PASS",
        "required_evidence": [
            "standard_lane",
            "declared_capability_or_datum",
            "focused_consumer_test_without_cad",
        ],
    },
    "cross_layer_complex": {
        "lane": "escalated",
        "budget_seconds": None,
        "result": "ESCALATE",
        "required_evidence": [
            "owning_layer_regressions",
            "applicable_platform_tier",
            "requesting_product_gates",
        ],
    },
}


_CATALOG_CONTEXT_ALLOWED_READS = (
    "the component-extension YAML contract",
    "the exact registered component declaration",
    "the closest catalog declaration and its focused test",
)


class ComponentExtensionError(ValueError):
    """A component-extension contract or verification failed closed."""


_CONTRACT_SCHEMA = "detailgen/component-extension/v1"
_CONTRACT_FIELDS = frozenset({
    "schema",
    "id",
    "family",
    "change_class",
    "component",
    "expect",
    "reject",
    "focused_tests",
})
_REQUIRED_FIELDS = frozenset({
    "schema", "id", "family", "change_class", "component", "expect",
})
_EXPECT_FIELDS = frozenset({
    "dimensions", "datums", "capabilities", "material_key",
})
_DIMENSIONS = frozenset({"xlen", "ylen", "zlen"})
_ID = re.compile(r"^[a-z0-9][a-z0-9_]*$")
_TEST_NODE = re.compile(r"^tests/[^\s:]+\.py::[^\s]+$")


@dataclass(frozen=True)
class ComponentExtensionContract:
    """Normalized, immutable inputs for one component-extension probe."""

    source: Path
    id: str
    family: str
    change_class: str
    component_type: str
    params: Mapping[str, object]
    dimensions: Mapping[str, object]
    datums: tuple[str, ...]
    capabilities: tuple[str, ...]
    material_key: str | None
    reject_params: tuple[Mapping[str, object], ...]
    focused_tests: tuple[str, ...]


def build_component_context_route(
    contract: ComponentExtensionContract,
) -> dict[str, object]:
    """Choose bounded catalog context only for an existing component type."""
    registered = True
    try:
        components.get(contract.component_type)
    except KeyError:
        registered = False

    catalog_micro = (
        contract.change_class == "catalog_variant" and registered
    )
    if catalog_micro:
        route = "catalog_micro"
        reason = (
            "catalog_variant targets an already registered component type"
        )
        context_budget_seconds = 30
        allowed_reads = list(_CATALOG_CONTEXT_ALLOWED_READS)
        required_verification = "component-check"
    else:
        route = "full_extension"
        if contract.change_class != "catalog_variant":
            reason = (
                f"{contract.change_class} requires the full extension workflow"
            )
        else:
            reason = (
                "catalog_variant targets an unregistered component type"
            )
        context_budget_seconds = None
        allowed_reads = []
        required_verification = "full-extension-workflow"

    return {
        "schema": "detailgen/component-context-route/v1",
        "id": contract.id,
        "change_class": contract.change_class,
        "component_type": contract.component_type,
        "route": route,
        "reason": reason,
        "context_budget_seconds": context_budget_seconds,
        "allowed_reads": allowed_reads,
        "required_verification": required_verification,
    }


def _as_mapping(value, *, owner: str) -> dict:
    if not isinstance(value, Mapping):
        raise ComponentExtensionError(f"{owner} must be a mapping")
    return dict(value)


def _unknown_fields(row: Mapping, allowed: frozenset[str], *, owner: str) -> None:
    unknown = sorted(set(row) - allowed)
    if unknown:
        raise ComponentExtensionError(f"{owner} has unknown fields: {unknown}")


def _string_tuple(value, *, owner: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ComponentExtensionError(f"{owner} must be a list of strings")
    if len(set(value)) != len(value):
        raise ComponentExtensionError(f"{owner} must not contain duplicates")
    return tuple(value)


def load_component_extension_contract(path: Path) -> ComponentExtensionContract:
    """Load and fail-closed validate a component-extension YAML contract."""
    source = Path(path).resolve()
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise ComponentExtensionError(f"could not read {source}: {error}") from None
    except yaml.YAMLError as error:
        raise ComponentExtensionError(f"invalid YAML in {source}: {error}") from None

    row = _as_mapping(payload, owner="component extension")
    _unknown_fields(row, _CONTRACT_FIELDS, owner="component extension")
    missing = sorted(_REQUIRED_FIELDS - set(row))
    if missing:
        raise ComponentExtensionError(
            f"component extension is missing required fields: {missing}"
        )
    if row["schema"] != _CONTRACT_SCHEMA:
        raise ComponentExtensionError(
            f"unknown component-extension schema {row['schema']!r}; "
            f"expected {_CONTRACT_SCHEMA!r}"
        )

    extension_id = row["id"]
    if not isinstance(extension_id, str) or not _ID.fullmatch(extension_id):
        raise ComponentExtensionError(
            "id must use lowercase letters, digits, and underscores and start "
            "with a lowercase letter or digit"
        )
    family = row["family"]
    if family not in COMPONENT_FAMILIES:
        raise ComponentExtensionError(
            f"unknown family {family!r}; known families: {list(COMPONENT_FAMILIES)}"
        )
    change_class = row["change_class"]
    if not isinstance(change_class, str) or change_class not in CHANGE_CLASSES:
        raise ComponentExtensionError(
            f"unknown change class {change_class!r}; known change classes: "
            f"{list(CHANGE_CLASSES)}"
        )

    component = _as_mapping(row["component"], owner="component")
    _unknown_fields(component, frozenset({"type", "params"}), owner="component")
    if "type" not in component:
        raise ComponentExtensionError("component.type is required")
    component_type = component["type"]
    if not isinstance(component_type, str) or not component_type:
        raise ComponentExtensionError("component.type must be a non-empty string")
    params = _as_mapping(component.get("params", {}), owner="component.params")

    expect = _as_mapping(row["expect"], owner="expect")
    _unknown_fields(expect, _EXPECT_FIELDS, owner="expect")
    dimensions = _as_mapping(
        expect.get("dimensions", {}), owner="expect.dimensions"
    )
    unknown_dimensions = sorted(set(dimensions) - _DIMENSIONS)
    if unknown_dimensions:
        raise ComponentExtensionError(
            f"expect dimension keys must be xlen, ylen, or zlen; got "
            f"{unknown_dimensions}"
        )
    if change_class != "cross_layer_complex" and set(dimensions) != _DIMENSIONS:
        raise ComponentExtensionError(
            "fast component contracts require dimensions xlen, ylen, and zlen"
        )
    datums = _string_tuple(expect.get("datums", []), owner="expect.datums")
    capabilities = _string_tuple(
        expect.get("capabilities", []), owner="expect.capabilities"
    )
    material_key = expect.get("material_key")
    if material_key is not None and (
        not isinstance(material_key, str) or not material_key
    ):
        raise ComponentExtensionError(
            "expect.material_key must be a non-empty string"
        )

    raw_reject = row.get("reject", [])
    if not isinstance(raw_reject, list):
        raise ComponentExtensionError("reject must be a list")
    reject_params = []
    for index, case in enumerate(raw_reject):
        case_row = _as_mapping(case, owner=f"reject[{index}]")
        _unknown_fields(case_row, frozenset({"params"}), owner=f"reject[{index}]")
        if "params" not in case_row:
            raise ComponentExtensionError(f"reject[{index}].params is required")
        reject_params.append(MappingProxyType(_as_mapping(
            case_row["params"], owner=f"reject[{index}].params"
        )))
    if change_class in {"new_primitive", "semantic_component"} and not reject_params:
        raise ComponentExtensionError(
            f"reject with at least one invalid params mapping is required for "
            f"{change_class}"
        )

    focused_tests = _string_tuple(
        row.get("focused_tests", []), owner="focused_tests"
    )
    if len(focused_tests) > 8 or any(
        not _TEST_NODE.fullmatch(node) for node in focused_tests
    ):
        raise ComponentExtensionError(
            "focused_tests must contain at most eight explicit "
            "tests/path.py::test_name node IDs with no whitespace"
        )
    if change_class == "semantic_component":
        semantic_datums = set(datums) - {"origin"}
        if not capabilities and not semantic_datums:
            raise ComponentExtensionError(
                "semantic_component requires an expected capability or "
                "non-origin datum"
            )
        if not focused_tests:
            raise ComponentExtensionError(
                "semantic_component requires at least one focused_tests node ID"
            )

    return ComponentExtensionContract(
        source=source,
        id=extension_id,
        family=family,
        change_class=change_class,
        component_type=component_type,
        params=MappingProxyType(params),
        dimensions=MappingProxyType(dimensions),
        datums=datums,
        capabilities=capabilities,
        material_key=material_key,
        reject_params=tuple(reject_params),
        focused_tests=focused_tests,
    )


def _compile_component(contract: ComponentExtensionContract):
    """Compile one component through the public DetailSpec surface."""
    spec = {
        "name": contract.id,
        "type": "detail",
        "units": "mm",
        "components": [{
            "id": "probe",
            "type": contract.component_type,
            "name": "probe",
            "params": dict(contract.params),
        }],
    }
    try:
        detail = compile_spec(load_spec_text(yaml.safe_dump(
            spec, sort_keys=False, default_flow_style=False
        )))
        detail.build()
        return detail.assembly.parts[0].component
    except Exception as error:
        raise ComponentExtensionError(
            f"public compile failed for {contract.component_type!r}: {error}"
        ) from None


def _resolve_length(value, *, owner: str) -> float:
    try:
        return Resolver({}, 1.0).resolve_length(value)
    except (SpecValueError, TypeError, ValueError):
        raise ComponentExtensionError(
            f"{owner} must be a number of millimeters or unit-suffixed length; "
            f"got {value!r}"
        ) from None


def _verify_rejects(contract: ComponentExtensionContract) -> None:
    if not contract.reject_params:
        return
    try:
        constructor = components.get(contract.component_type)
    except KeyError as error:
        raise ComponentExtensionError(error.args[0]) from None
    resolver = Resolver({}, 1.0)
    for index, invalid in enumerate(contract.reject_params):
        params = dict(contract.params)
        params.update(invalid)
        try:
            candidate = constructor(**resolver.resolve(params))
            problems = candidate.check()
        except Exception:
            continue
        if problems:
            continue
        raise ComponentExtensionError(
            f"reject[{index}] did not reject: construction succeeded and "
            "component.check() returned no problems"
        )


def _run_focused_tests(
    contract: ComponentExtensionContract,
    *,
    repo_root: Path,
    timeout: float,
) -> None:
    env = os.environ.copy()
    source = str(repo_root / "src")
    prior = env.get("PYTHONPATH")
    env["PYTHONPATH"] = source if not prior else source + os.pathsep + prior
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", *contract.focused_tests, "-q"],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=max(timeout, 0.001),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise ComponentExtensionError(
            f"focused tests exceeded the remaining {timeout:.3f}s budget"
        ) from None
    if completed.returncode:
        output = (completed.stdout + "\n" + completed.stderr).strip()
        raise ComponentExtensionError(
            f"focused tests failed with return code {completed.returncode}:\n"
            f"{output}"
        )


def _verify_component_extension_impl(
    contract: ComponentExtensionContract,
    *,
    repo_root: Path = Path.cwd(),
    clock=time.perf_counter,
) -> dict[str, object]:
    """Verify one extension through its smallest honest, bounded surface."""
    started = clock()
    policy = CHANGE_CLASSES[contract.change_class]
    lane = policy["lane"]
    budget = policy["budget_seconds"]
    if contract.change_class == "cross_layer_complex":
        return {
            "schema": "detailgen/component-extension-result/v1",
            "id": contract.id,
            "family": contract.family,
            "change_class": contract.change_class,
            "lane": lane,
            "status": "ESCALATE",
            "elapsed_seconds": round(max(clock() - started, 0.0), 6),
            "budget_seconds": None,
            "checks": ["contract_schema"],
            "context_route": build_component_context_route(contract),
        }

    checks = ["contract_schema"]
    component = _compile_component(contract)
    checks.append("public_compile")

    problems = component.check()
    if problems:
        raise ComponentExtensionError(
            "component.check() reported problems:\n" +
            "\n".join(str(problem) for problem in problems)
        )
    checks.append("component_check")

    shapes = component.solid.vals()
    volumes = [shape.Volume() for shape in shapes]
    if (
        not shapes
        or any(not math.isfinite(volume) or volume <= 0 for volume in volumes)
        or sum(volumes) <= 0
    ):
        raise ComponentExtensionError(
            "component geometry must contain positive finite solid volume"
        )
    checks.append("positive_geometry")

    bounds = component.bounding_box()
    for axis in ("xlen", "ylen", "zlen"):
        expected_raw = contract.dimensions[axis]
        expected = _resolve_length(
            expected_raw, owner=f"expect.dimensions.{axis}"
        )
        actual = float(getattr(bounds, axis))
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6):
            raise ComponentExtensionError(
                f"{axis} expected {expected_raw!r} ({expected:.6f} mm), "
                f"got {actual:.6f} mm"
            )
    checks.append("dimensions")

    missing_datums = sorted(set(contract.datums) - set(component.datums))
    if missing_datums:
        raise ComponentExtensionError(
            f"missing expected datums {missing_datums}; actual: "
            f"{sorted(component.datums)}"
        )
    checks.append("datums")

    actual_capabilities = component.capability_tags()
    missing_capabilities = sorted(
        set(contract.capabilities) - set(actual_capabilities)
    )
    if missing_capabilities:
        raise ComponentExtensionError(
            f"missing expected capabilities {missing_capabilities}; actual: "
            f"{sorted(actual_capabilities)}"
        )
    checks.append("capabilities")

    if contract.material_key is not None:
        if component.material_key != contract.material_key:
            raise ComponentExtensionError(
                f"material expected {contract.material_key!r}, got "
                f"{component.material_key!r}"
            )
        component.material
    checks.append("material")

    if not component.bom_label().strip() or not component.describe().strip():
        raise ComponentExtensionError(
            "component must provide non-empty BOM label and description"
        )
    checks.append("bom_identity")

    if contract.change_class in {"new_primitive", "semantic_component"}:
        from .manifest import build_authoring_manifest

        manifest_keys = {
            row["key"] for row in build_authoring_manifest()["components"]
        }
        if contract.component_type not in manifest_keys:
            raise ComponentExtensionError(
                f"component {contract.component_type!r} is absent from the "
                "public authoring manifest"
            )
        checks.append("registry_manifest")
        _verify_rejects(contract)
        checks.append("invalid_parameter_rejection")

    if contract.change_class == "semantic_component":
        elapsed = max(clock() - started, 0.0)
        _run_focused_tests(
            contract,
            repo_root=Path(repo_root).resolve(),
            timeout=float(budget) - elapsed,
        )
        checks.append("focused_tests")

    elapsed = max(clock() - started, 0.0)
    if elapsed > float(budget):
        raise ComponentExtensionError(
            f"{lane} component verification exceeded its {budget}s budget: "
            f"{elapsed:.3f}s"
        )
    return {
        "schema": "detailgen/component-extension-result/v1",
        "id": contract.id,
        "family": contract.family,
        "change_class": contract.change_class,
        "lane": lane,
        "status": "PASS",
        "elapsed_seconds": round(elapsed, 6),
        "budget_seconds": budget,
        "checks": checks,
        "context_route": build_component_context_route(contract),
    }


def verify_component_extension(
    contract: ComponentExtensionContract,
    *,
    repo_root: Path = Path.cwd(),
    clock=time.perf_counter,
) -> dict[str, object]:
    """Verify a contract and turn component failures into CLI-safe evidence."""
    try:
        return _verify_component_extension_impl(
            contract, repo_root=repo_root, clock=clock
        )
    except ComponentExtensionError:
        raise
    except Exception as error:
        raise ComponentExtensionError(
            f"component verification failed: {type(error).__name__}: {error}"
        ) from None


def build_component_extension_guide() -> dict[str, object]:
    """Return bounded, mutation-isolated component-extension guidance."""
    return {
        "schema": "detailgen/component-extension-guide/v1",
        "families": deepcopy(FAMILY_GUIDANCE),
        "change_classes": deepcopy(CHANGE_CLASSES),
        "contract_required": [
            "schema",
            "id",
            "family",
            "change_class",
            "component",
            "expect",
        ],
        "example_contract": {
            "schema": "detailgen/component-extension/v1",
            "id": "nominal_2x2_lumber",
            "family": "stock_member",
            "change_class": "catalog_variant",
            "component": {
                "type": "lumber",
                "params": {"nominal": "2x2", "length": "24 in"},
            },
            "expect": {
                "dimensions": {
                    "xlen": "24 in",
                    "ylen": "1.5 in",
                    "zlen": "1.5 in",
                },
                "datums": ["end_near", "end_far"],
                "capabilities": [],
                "material_key": "lumber_spf",
            },
        },
        "commands": {
            "guide": ["python", "-m", "detailgen.authoring", "component-guide"],
            "route": [
                "python",
                "-m",
                "detailgen.authoring",
                "component-route",
                "{contract.yaml}",
            ],
            "check": [
                "python",
                "-m",
                "detailgen.authoring",
                "component-check",
                "{contract.yaml}",
            ],
        },
    }
