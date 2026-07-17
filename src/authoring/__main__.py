"""Print the authoring manifest or generate a verified DetailSpec starter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

from .manifest import authoring_manifest_json, build_authoring_grammar
from .component_extension import (
    ComponentExtensionError,
    build_component_extension_guide,
    load_component_extension_contract,
    verify_component_extension,
)
from .scaffold import (
    ScaffoldComponent,
    ScaffoldConnection,
    ScaffoldError,
    ScaffoldRequest,
    write_scaffold,
)


def _split(value: str, delimiter: str, *, shape: str) -> tuple[str, str]:
    if delimiter not in value:
        raise ScaffoldError(f"expected {shape}, got {value!r}")
    left, right = value.split(delimiter, 1)
    if not left or not right:
        raise ScaffoldError(f"expected {shape}, got {value!r}")
    return left, right


def _yaml_value(text: str, *, owner: str):
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        problem = getattr(error, "problem", None) or str(error).splitlines()[0]
        raise ScaffoldError(
            f"{owner}: invalid YAML value {text!r}: {problem}"
        ) from None


def _assign(
    target: dict,
    owner: object,
    field: str,
    value: object,
    *,
    flag: str,
) -> None:
    values = target.setdefault(owner, {})
    if field in values:
        raise ScaffoldError(f"duplicate {flag} for {owner}.{field}")
    values[field] = value


def _request(args) -> ScaffoldRequest:
    declarations: list[tuple[str, str]] = []
    ids: set[str] = set()
    for value in args.component:
        component_id, component_type = _split(
            value, ":", shape="--component ID:TYPE"
        )
        if component_id in ids:
            raise ScaffoldError(f"duplicate component id {component_id!r}")
        ids.add(component_id)
        declarations.append((component_id, component_type))

    component_params: dict[str, dict[str, object]] = {}
    for value in args.component_set:
        target, raw = _split(value, "=", shape="--set ID.PARAM=YAML_VALUE")
        component_id, field = _split(
            target, ".", shape="--set ID.PARAM=YAML_VALUE"
        )
        if component_id not in ids:
            raise ScaffoldError(
                f"--set names undeclared component {component_id!r}; declared: "
                f"{sorted(ids)}"
            )
        _assign(
            component_params,
            component_id,
            field,
            _yaml_value(raw, owner=f"--set {component_id}.{field}"),
            flag="--set",
        )

    placements: dict[str, object] = {}
    for value in args.place:
        component_id, raw = _split(
            value, "=", shape="--place ID=YAML_PLACEMENT_MAPPING"
        )
        if component_id not in ids:
            raise ScaffoldError(
                f"--place names undeclared component {component_id!r}; declared: "
                f"{sorted(ids)}"
            )
        if component_id in placements:
            raise ScaffoldError(f"duplicate --place for {component_id}")
        placements[component_id] = _yaml_value(
            raw, owner=f"--place {component_id}"
        )

    connection_declarations: list[tuple[str, tuple[str, ...]]] = []
    for value in args.connection:
        connection_type, raw_parts = _split(
            value, ":", shape="--connection TYPE:PART[,PART...]"
        )
        parts = tuple(part for part in raw_parts.split(",") if part)
        connection_declarations.append((connection_type, parts))

    connection_params: dict[int, dict[str, object]] = {}
    for value in args.connection_set:
        target, raw = _split(
            value,
            "=",
            shape="--connection-set INDEX.PARAM=YAML_VALUE",
        )
        raw_index, field = _split(
            target,
            ".",
            shape="--connection-set INDEX.PARAM=YAML_VALUE",
        )
        try:
            index = int(raw_index)
        except ValueError:
            raise ScaffoldError(
                f"--connection-set index must be a non-negative integer, got "
                f"{raw_index!r}"
            ) from None
        if index < 0 or index >= len(connection_declarations):
            raise ScaffoldError(
                f"--connection-set index {index} is out of range for "
                f"{len(connection_declarations)} declared connections"
            )
        _assign(
            connection_params,
            index,
            field,
            _yaml_value(raw, owner=f"--connection-set {index}.{field}"),
            flag="--connection-set",
        )

    connection_hardware: dict[int, tuple[str, ...]] = {}
    for value in args.connection_hardware:
        raw_index, raw_parts = _split(
            value,
            "=",
            shape="--connection-hardware INDEX=PART[,PART...]",
        )
        try:
            index = int(raw_index)
        except ValueError:
            raise ScaffoldError(
                f"--connection-hardware index must be a non-negative integer, "
                f"got {raw_index!r}"
            ) from None
        if index < 0 or index >= len(connection_declarations):
            raise ScaffoldError(
                f"--connection-hardware index {index} is out of range for "
                f"{len(connection_declarations)} declared connections"
            )
        if index in connection_hardware:
            raise ScaffoldError(
                f"duplicate --connection-hardware for connection {index}"
            )
        hardware = tuple(part for part in raw_parts.split(",") if part)
        if not hardware:
            raise ScaffoldError(
                f"--connection-hardware {index} must name at least one part id"
            )
        connection_hardware[index] = hardware

    return ScaffoldRequest(
        slug=args.slug,
        output_dir=args.out,
        components=tuple(
            ScaffoldComponent(
                id=component_id,
                type=component_type,
                params=component_params.get(component_id, {}),
                place=placements.get(component_id),
            )
            for component_id, component_type in declarations
        ),
        connections=tuple(
            ScaffoldConnection(
                type=connection_type,
                parts=parts,
                params=connection_params.get(index, {}),
                hardware=connection_hardware.get(index, ()),
            )
            for index, (connection_type, parts)
            in enumerate(connection_declarations)
        ),
        force=args.force,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detailgen.authoring",
        description=(
            "Print the compact authoring manifest, or emit a verified "
            "DetailSpec and certification starter."
        ),
    )
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser(
        "grammar",
        help="print only the bounded nested-field grammar",
    )
    subcommands.add_parser(
        "component-guide",
        help="print physical families and risk-classified component checks",
    )
    component_check = subcommands.add_parser(
        "component-check",
        help="verify one component-extension YAML contract",
    )
    component_check.add_argument(
        "contract",
        type=Path,
        metavar="CONTRACT",
        help="Path to a detailgen/component-extension/v1 YAML contract.",
    )
    scaffold = subcommands.add_parser(
        "scaffold",
        help="write a registry-checked DetailSpec and certification stub",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=110),
    )
    scaffold.add_argument(
        "--slug",
        required=True,
        help=(
            "Use lowercase letters, digits, and underscores; start with a "
            "lowercase letter or digit."
        ),
    )
    scaffold.add_argument(
        "--out",
        required=True,
        type=Path,
        metavar="DIRECTORY",
        help=(
            "Directory that receives SLUG.spec.yaml and SLUG.cert.yaml; "
            "created if missing."
        ),
    )
    scaffold.add_argument(
        "--component",
        action="append",
        required=True,
        metavar="ID:TYPE",
        help="Declare a component id and registered type; repeat as needed.",
    )
    scaffold.add_argument(
        "--set",
        dest="component_set",
        action="append",
        default=[],
        metavar="ID.PARAM=YAML_VALUE",
        help="Set one component parameter; repeat as needed.",
    )
    scaffold.add_argument(
        "--place",
        action="append",
        default=[],
        metavar="ID=YAML_MAPPING",
        help=(
            "Mate fields are direct; raw requires a raw wrapper. Repeat for "
            "each explicitly placed component."
        ),
    )
    scaffold.add_argument(
        "--connection",
        action="append",
        default=[],
        metavar="TYPE:PART[,PART...]",
        help="Declare a registered connection and its participants; repeat as needed.",
    )
    scaffold.add_argument(
        "--connection-set",
        action="append",
        default=[],
        metavar="INDEX.PARAM=YAML_VALUE",
        help="Set one parameter on a zero-based declared connection index.",
    )
    scaffold.add_argument(
        "--connection-hardware",
        action="append",
        default=[],
        metavar="INDEX=PART[,PART...]",
        help="Assign hardware component ids to a zero-based declared connection index.",
    )
    scaffold.add_argument(
        "--force",
        action="store_true",
        help="Replace both output files if either already exists.",
    )
    return parser


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        print(authoring_manifest_json(), end="")
        return 0
    if args.command == "grammar":
        print(json.dumps(build_authoring_grammar(), indent=2, sort_keys=True))
        return 0
    if args.command == "component-guide":
        print(json.dumps(
            build_component_extension_guide(), indent=2, sort_keys=True
        ))
        return 0
    if args.command == "component-check":
        try:
            contract = load_component_extension_contract(args.contract)
            result = verify_component_extension(contract)
        except ComponentExtensionError as error:
            print(json.dumps({
                "schema": "detailgen/component-extension-error/v1",
                "status": "FAIL",
                "error": str(error),
            }, indent=2, sort_keys=True), file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 3 if result["status"] == "ESCALATE" else 0

    try:
        result = write_scaffold(_request(args))
    except (ScaffoldError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({
        "schema": "detailgen/scaffold-result/v1",
        "spec": str(result.spec_path),
        "certification": str(result.contract_path),
        "implicit_identity_placements": list(
            result.implicit_identity_placements
        ),
        "geometry_inferred": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
