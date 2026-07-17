"""Registry-backed, fail-closed starter documents for simple DetailSpecs."""

from __future__ import annotations

import inspect
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import yaml

from .. import components as _load_components  # noqa: F401
from ..assemblies.connection import connection_types
from ..certification import load_contract
from ..core.registry import components
from ..spec import compile_spec, load_spec_text


_SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_+-]*$")


class ScaffoldError(ValueError):
    """An actionable, pre-compilation scaffolding input error."""


@dataclass(frozen=True)
class ScaffoldComponent:
    id: str
    type: str
    params: Mapping[str, object] = field(default_factory=dict)
    place: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ScaffoldConnection:
    type: str
    parts: tuple[str, ...]
    params: Mapping[str, object] = field(default_factory=dict)
    hardware: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScaffoldRequest:
    slug: str
    output_dir: Path
    components: tuple[ScaffoldComponent, ...]
    connections: tuple[ScaffoldConnection, ...] = ()
    force: bool = False


@dataclass(frozen=True)
class ScaffoldDocuments:
    spec_text: str
    contract_text: str
    implicit_identity_placements: tuple[str, ...]


@dataclass(frozen=True)
class ScaffoldResult:
    spec_path: Path
    contract_path: Path
    implicit_identity_placements: tuple[str, ...]


def _entry(registry, key: str, *, owner: str):
    try:
        return registry.get(key)
    except KeyError as error:
        raise ScaffoldError(f"{owner}: {error.args[0]}") from None


def _validate_constructor_params(
    constructor,
    supplied: Mapping[str, object],
    *,
    owner: str,
    reserved: frozenset[str] = frozenset(),
    argument: str = "--set",
) -> dict[str, object]:
    if not isinstance(supplied, Mapping):
        raise ScaffoldError(f"{owner}: params must be a mapping")
    signature = inspect.signature(constructor)
    parameters = {
        name: parameter
        for name, parameter in signature.parameters.items()
        if name not in {"self", "cls"} | set(reserved)
        and parameter.kind not in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }
    }
    unknown = sorted(set(supplied) - set(parameters))
    if unknown:
        raise ScaffoldError(
            f"{owner}: unknown params {unknown}; valid params: "
            f"{sorted(parameters)}"
        )
    missing = sorted(
        name for name, parameter in parameters.items()
        if parameter.default is inspect.Parameter.empty and name not in supplied
    )
    if missing:
        fixes = ", ".join(f"{argument} {owner}.{name}=VALUE" for name in missing)
        raise ScaffoldError(
            f"{owner}: missing required params {missing}; supply {fixes}"
        )
    return dict(supplied)


def _validate_request(request: ScaffoldRequest) -> None:
    if not _SLUG.fullmatch(request.slug):
        raise ScaffoldError(
            f"invalid slug {request.slug!r}; use lowercase letters, digits, and "
            "underscores, starting with a letter"
        )
    if not request.components:
        raise ScaffoldError("at least one --component ID:TYPE is required")
    ids: set[str] = set()
    for component in request.components:
        if not _ID.fullmatch(component.id):
            raise ScaffoldError(
                f"invalid component id {component.id!r}; use a letter followed "
                "by letters, digits, _, +, or -"
            )
        if component.id in ids:
            raise ScaffoldError(f"duplicate component id {component.id!r}")
        ids.add(component.id)
        constructor = _entry(
            components, component.type, owner=f"component {component.id}"
        )
        _validate_constructor_params(
            constructor,
            component.params,
            owner=component.id,
            reserved=frozenset({"name"}),
        )
        if component.place is not None and not isinstance(component.place, Mapping):
            raise ScaffoldError(
                f"component {component.id}: placement must be a mapping"
            )

    for index, connection in enumerate(request.connections):
        owner = f"connection {index}"
        constructor = _entry(connection_types, connection.type, owner=owner)
        _validate_constructor_params(
            constructor,
            connection.params,
            owner=str(index),
            argument="--connection-set",
        )
        if not connection.parts:
            raise ScaffoldError(f"{owner}: at least one part id is required")
        undeclared = sorted(set(connection.parts) - ids)
        if undeclared:
            raise ScaffoldError(
                f"{owner}: undeclared parts {undeclared}; declared component ids: "
                f"{sorted(ids)}"
            )
        undeclared_hardware = sorted(set(connection.hardware) - ids)
        if undeclared_hardware:
            raise ScaffoldError(
                f"{owner}: undeclared hardware {undeclared_hardware}; declared "
                f"component ids: {sorted(ids)}"
            )


def build_scaffold(request: ScaffoldRequest) -> ScaffoldDocuments:
    """Build text and prove loader, compiler, and validation can execute."""
    _validate_request(request)
    component_rows = []
    implicit = []
    for component in request.components:
        row: dict[str, object] = {
            "id": component.id,
            "type": component.type,
            "name": component.id,
        }
        if component.params:
            row["params"] = dict(component.params)
        if component.place is None:
            implicit.append(component.id)
        else:
            row["place"] = dict(component.place)
        component_rows.append(row)

    spec: dict[str, object] = {
        "name": request.slug,
        "type": "detail",
        "units": "in",
        "components": component_rows,
    }
    if request.connections:
        spec["connections"] = [
            {
                "type": connection.type,
                **({"params": dict(connection.params)} if connection.params else {}),
                "parts": list(connection.parts),
                **({"hardware": list(connection.hardware)}
                   if connection.hardware else {}),
            }
            for connection in request.connections
        ]
    spec_text = yaml.safe_dump(spec, sort_keys=False, default_flow_style=False)
    detail = compile_spec(load_spec_text(spec_text))
    detail.build()
    detail.connections()
    detail.validate()

    contract = {
        "schema_version": 1,
        "subject": {
            "kind": "standalone_detail",
            "source": f"{request.slug}.spec.yaml",
        },
    }
    return ScaffoldDocuments(
        spec_text=spec_text,
        contract_text=yaml.safe_dump(contract, sort_keys=False),
        implicit_identity_placements=tuple(implicit),
    )


def write_scaffold(request: ScaffoldRequest) -> ScaffoldResult:
    """Write both verified documents without leaving a partial pair."""
    _validate_request(request)
    output_dir = Path(request.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    spec_path = output_dir / f"{request.slug}.spec.yaml"
    contract_path = output_dir / f"{request.slug}.cert.yaml"
    collisions = [path for path in (spec_path, contract_path) if path.exists()]
    if collisions and not request.force:
        raise ScaffoldError(
            "refusing to overwrite existing outputs: "
            + ", ".join(str(path) for path in collisions)
            + "; pass --force to replace both"
        )
    documents = build_scaffold(request)

    with tempfile.TemporaryDirectory(dir=output_dir) as temporary:
        staging = Path(temporary)
        staged_spec = staging / spec_path.name
        staged_contract = staging / contract_path.name
        staged_spec.write_text(documents.spec_text, encoding="utf-8")
        staged_contract.write_text(documents.contract_text, encoding="utf-8")
        load_contract(staged_contract, repo_root=output_dir)
        backup_dir = staging / "prior"
        backups: dict[Path, Path] = {}
        for target in (spec_path, contract_path):
            if target.exists():
                backup_dir.mkdir(exist_ok=True)
                backup = backup_dir / target.name
                shutil.copy2(target, backup)
                backups[target] = backup

        installed: list[Path] = []
        try:
            staged_spec.replace(spec_path)
            installed.append(spec_path)
            staged_contract.replace(contract_path)
            installed.append(contract_path)
        except BaseException:
            for target in installed:
                target.unlink(missing_ok=True)
            for target, backup in backups.items():
                backup.replace(target)
            raise

    return ScaffoldResult(
        spec_path=spec_path,
        contract_path=contract_path,
        implicit_identity_placements=documents.implicit_identity_placements,
    )
