"""Strict, non-executable certification-contract loading and discovery."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .model import (
    BomIntent,
    CertificationContract,
    CountIntent,
    DecisionRecord,
    FabricationIntent,
    GovernanceIntent,
    IntentContract,
    IntentSelector,
    NumericRange,
    SubjectContract,
)


_SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
_SELECTOR_FIELDS = {
    "component", "material", "role", "name", "name_contains", "kind",
    "check", "verdict", "subject_contains",
}


class ContractError(ValueError):
    """A structural, vocabulary, or path error in a certification contract."""


def _mapping(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{path}: expected a mapping")
    return value


def _list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise ContractError(f"{path}: expected a list")
    return value


def _keys(
    value: dict,
    *,
    required: set[str] | frozenset[str] = frozenset(),
    optional: set[str] | frozenset[str] = frozenset(),
    path: str,
) -> None:
    missing = required - set(value)
    if missing:
        raise ContractError(f"{path}: missing field {sorted(missing)[0]!r}")
    unknown = set(value) - required - optional
    if unknown:
        raise ContractError(f"{path}: unknown field {sorted(unknown)[0]!r}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{path}: expected a non-empty string")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{path}: expected true or false")
    return value


def _integer(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractError(f"{path}: expected a non-negative integer")
    return value


def _number(value: Any, path: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ContractError(f"{path}: expected a number")
    return float(value)


def _selector(value: Any, path: str) -> IntentSelector:
    raw = _mapping(value, path)
    _keys(raw, optional=_SELECTOR_FIELDS, path=path)
    if not raw:
        raise ContractError(f"{path}: selector must declare at least one field")
    parsed = {key: _string(item, f"{path}.{key}") for key, item in raw.items()}
    return IntentSelector(**parsed)


def _count_intent(value: Any, path: str) -> CountIntent:
    raw = _mapping(value, path)
    _keys(
        raw,
        required={"selector"},
        optional={"exactly", "minimum", "maximum"},
        path=path,
    )
    bounds = [key for key in ("exactly", "minimum", "maximum") if key in raw]
    if not bounds:
        raise ContractError(f"{path}: one count bound is required")
    if "exactly" in raw and len(bounds) != 1:
        raise ContractError(f"{path}: exactly cannot be combined with a range")
    parsed = {
        key: _integer(raw[key], f"{path}.{key}")
        for key in bounds
    }
    if (
        "minimum" in parsed
        and "maximum" in parsed
        and parsed["minimum"] > parsed["maximum"]
    ):
        raise ContractError(f"{path}: minimum exceeds maximum")
    return CountIntent(selector=_selector(raw["selector"], f"{path}.selector"), **parsed)


def _numeric_range(value: Any, path: str) -> NumericRange:
    raw = _mapping(value, path)
    _keys(raw, optional={"minimum", "maximum"}, path=path)
    if not raw:
        raise ContractError(f"{path}: range must declare minimum or maximum")
    minimum = _number(raw["minimum"], f"{path}.minimum") if "minimum" in raw else None
    maximum = _number(raw["maximum"], f"{path}.maximum") if "maximum" in raw else None
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ContractError(f"{path}: minimum exceeds maximum")
    return NumericRange(minimum=minimum, maximum=maximum)


def _intent(value: Any, path: str) -> IntentContract:
    raw = _mapping(value, path)
    allowed = {
        "counts", "forbidden", "connections", "validation",
        "fabrication", "bom", "governance",
    }
    _keys(raw, optional=allowed, path=path)

    counts = tuple(
        _count_intent(item, f"{path}.counts[{index}]")
        for index, item in enumerate(_list(raw.get("counts", []), f"{path}.counts"))
    )
    forbidden = tuple(
        _selector(
            _required_selector(item, f"{path}.forbidden[{index}]"),
            f"{path}.forbidden[{index}].selector",
        )
        for index, item in enumerate(
            _list(raw.get("forbidden", []), f"{path}.forbidden")
        )
    )
    connections = tuple(
        _count_intent(item, f"{path}.connections[{index}]")
        for index, item in enumerate(
            _list(raw.get("connections", []), f"{path}.connections")
        )
    )
    validation = tuple(
        _count_intent(item, f"{path}.validation[{index}]")
        for index, item in enumerate(
            _list(raw.get("validation", []), f"{path}.validation")
        )
    )
    fabrication = tuple(
        _fabrication_intent(item, f"{path}.fabrication[{index}]")
        for index, item in enumerate(
            _list(raw.get("fabrication", []), f"{path}.fabrication")
        )
    )
    bom = tuple(
        _bom_intent(item, f"{path}.bom[{index}]")
        for index, item in enumerate(_list(raw.get("bom", []), f"{path}.bom"))
    )
    governance = _governance_intent(raw.get("governance", {}), f"{path}.governance")
    return IntentContract(
        counts=counts,
        forbidden=forbidden,
        connections=connections,
        validation=validation,
        fabrication=fabrication,
        bom=bom,
        governance=governance,
    )


def _required_selector(value: Any, path: str) -> Any:
    raw = _mapping(value, path)
    _keys(raw, required={"selector"}, path=path)
    return raw["selector"]


def _fabrication_intent(value: Any, path: str) -> FabricationIntent:
    raw = _mapping(value, path)
    _keys(raw, required={"selector", "steps"}, path=path)
    steps = tuple(
        _string(item, f"{path}.steps[{index}]")
        for index, item in enumerate(_list(raw["steps"], f"{path}.steps"))
    )
    if not steps:
        raise ContractError(f"{path}.steps: expected at least one step")
    return FabricationIntent(
        selector=_selector(raw["selector"], f"{path}.selector"),
        steps=steps,
    )


def _bom_intent(value: Any, path: str) -> BomIntent:
    raw = _mapping(value, path)
    _keys(raw, required={"item", "quantity"}, optional={"length_mm"}, path=path)
    return BomIntent(
        item=_string(raw["item"], f"{path}.item"),
        quantity=_integer(raw["quantity"], f"{path}.quantity"),
        length_mm=(
            _numeric_range(raw["length_mm"], f"{path}.length_mm")
            if "length_mm" in raw
            else None
        ),
    )


def _governance_intent(value: Any, path: str) -> GovernanceIntent:
    raw = _mapping(value, path)
    allowed = {"selected_concept", "modeling_ready", "delivery_ready"}
    _keys(raw, optional=allowed, path=path)
    return GovernanceIntent(
        selected_concept=(
            _string(raw["selected_concept"], f"{path}.selected_concept")
            if "selected_concept" in raw
            else None
        ),
        modeling_ready=(
            _boolean(raw["modeling_ready"], f"{path}.modeling_ready")
            if "modeling_ready" in raw
            else None
        ),
        delivery_ready=(
            _boolean(raw["delivery_ready"], f"{path}.delivery_ready")
            if "delivery_ready" in raw
            else None
        ),
    )


def _decisions(value: Any, path: str) -> tuple[DecisionRecord, ...]:
    records = []
    for index, item in enumerate(_list(value, path)):
        item_path = f"{path}[{index}]"
        raw = _mapping(item, item_path)
        required = {"rule", "outcome", "rationale", "evidence_fingerprint"}
        _keys(raw, required=required, path=item_path)
        records.append(DecisionRecord(
            rule_id=_string(raw["rule"], f"{item_path}.rule"),
            outcome=_string(raw["outcome"], f"{item_path}.outcome"),
            rationale=_string(raw["rationale"], f"{item_path}.rationale"),
            evidence_fingerprint=_string(
                raw["evidence_fingerprint"],
                f"{item_path}.evidence_fingerprint",
            ),
        ))
    return tuple(records)


def load_contract(path: Path, *, repo_root: Path) -> CertificationContract:
    source_path = Path(path).resolve()
    try:
        raw = yaml.safe_load(source_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"{source_path}: {exc}") from None
    root = _mapping(raw, str(source_path))
    _keys(
        root,
        required={"schema_version", "subject"},
        optional={"intent", "deliverables", "decisions"},
        path=str(source_path),
    )
    if root["schema_version"] != 1:
        raise ContractError(
            f"{source_path}.schema_version: expected 1, got {root['schema_version']!r}"
        )

    suffix = ".cert.yaml"
    slug = source_path.name.removesuffix(suffix)
    if not source_path.name.endswith(suffix) or not _SLUG.fullmatch(slug):
        raise ContractError(f"{source_path}: invalid certification slug {slug!r}")

    subject_raw = _mapping(root["subject"], f"{source_path}.subject")
    _keys(
        subject_raw,
        required={"kind", "source"},
        path=f"{source_path}.subject",
    )
    kind = _string(subject_raw["kind"], f"{source_path}.subject.kind")
    source_value = _string(subject_raw["source"], f"{source_path}.subject.source")
    subject_source = (source_path.parent / source_value).resolve()
    repo = Path(repo_root).resolve()
    if not subject_source.is_relative_to(repo):
        raise ContractError(
            f"{source_path}.subject.source: {subject_source} escapes repository root {repo}"
        )
    if not subject_source.is_file():
        raise ContractError(
            f"{source_path}.subject.source: source file does not exist: {subject_source}"
        )

    deliverables = tuple(
        _string(item, f"{source_path}.deliverables[{index}]")
        for index, item in enumerate(
            _list(root.get("deliverables", []), f"{source_path}.deliverables")
        )
    )
    if len(set(deliverables)) != len(deliverables):
        raise ContractError(f"{source_path}.deliverables: duplicate value")

    return CertificationContract(
        schema_version=1,
        slug=slug,
        subject=SubjectContract(kind=kind, source=subject_source),
        intent=_intent(root.get("intent", {}), f"{source_path}.intent"),
        deliverables=deliverables,
        decisions=_decisions(root.get("decisions", []), f"{source_path}.decisions"),
        source_path=source_path,
    )


def discover_contracts(
    details_dir: Path,
    *,
    repo_root: Path,
) -> tuple[CertificationContract, ...]:
    contracts = tuple(
        load_contract(path, repo_root=repo_root)
        for path in sorted(Path(details_dir).rglob("*.cert.yaml"))
    )
    by_slug: dict[str, Path] = {}
    for contract in contracts:
        prior = by_slug.get(contract.slug)
        if prior is not None:
            raise ContractError(
                f"duplicate certification slug {contract.slug!r}: "
                f"{prior} and {contract.source_path}"
            )
        by_slug[contract.slug] = contract.source_path
    return tuple(sorted(contracts, key=lambda item: item.slug))
