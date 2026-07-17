"""Strict node-level ownership and cadence for the Plumb pytest suite."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence


Category = Literal["platform", "document_build_accuracy"]
Cadence = Literal["unit", "integration", "audit", "inner", "release"]

PLATFORM_OWNER = "plumb-platform"
PLATFORM_CADENCES = frozenset({"unit", "integration", "audit"})
BUILD_CADENCES = frozenset({"inner", "release"})
MANIFEST_COLUMNS = ("nodeid", "category", "owner", "cadence", "rationale")
CERTIFIED_BUILD_NODE = (
    "tests/test_certified_builds.py::test_certified_build[{slug}]"
)


class ScopeManifestError(ValueError):
    """The runtime test-scope manifest is incomplete or internally invalid."""


@dataclass(frozen=True)
class ScopeRecord:
    nodeid: str
    category: Category
    owner: str
    cadence: Cadence
    rationale: str


def _record_from_row(row: dict[str, str], row_number: int) -> ScopeRecord:
    values = {name: (row.get(name) or "").strip() for name in MANIFEST_COLUMNS}
    nodeid = values["nodeid"]
    category = values["category"]
    owner = values["owner"]
    cadence = values["cadence"]
    rationale = values["rationale"]
    prefix = f"scope manifest row {row_number}"

    if not nodeid.startswith("tests/") or ".py::" not in nodeid:
        raise ScopeManifestError(f"{prefix}: invalid normalized nodeid {nodeid!r}")
    if category not in {"platform", "document_build_accuracy"}:
        raise ScopeManifestError(f"{prefix}: unknown category {category!r}")
    if not rationale:
        raise ScopeManifestError(f"{prefix}: rationale must be non-empty")

    if category == "platform":
        if owner != PLATFORM_OWNER:
            raise ScopeManifestError(
                f"{prefix}: platform owner must be {PLATFORM_OWNER!r}"
            )
        if cadence not in PLATFORM_CADENCES:
            raise ScopeManifestError(
                f"{prefix}: unknown platform cadence {cadence!r}"
            )
    else:
        if not owner or owner == PLATFORM_OWNER:
            raise ScopeManifestError(
                f"{prefix}: build owner must be named and non-platform"
            )
        if cadence not in BUILD_CADENCES:
            raise ScopeManifestError(f"{prefix}: unknown build cadence {cadence!r}")

    return ScopeRecord(
        nodeid=nodeid,
        category=category,
        owner=owner,
        cadence=cadence,
        rationale=rationale,
    )


def load_scope_manifest(path: str | Path) -> tuple[ScopeRecord, ...]:
    """Load and validate a timing-free runtime scope manifest."""
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != MANIFEST_COLUMNS:
            raise ScopeManifestError(
                "scope manifest columns must be exactly "
                f"{', '.join(MANIFEST_COLUMNS)}"
            )
        records = tuple(
            _record_from_row(row, row_number)
            for row_number, row in enumerate(reader, start=2)
        )

    nodeids = [record.nodeid for record in records]
    if len(nodeids) != len(set(nodeids)):
        duplicates = sorted(
            nodeid for nodeid in set(nodeids) if nodeids.count(nodeid) > 1
        )
        raise ScopeManifestError(
            f"duplicate nodeid in test scope manifest: {duplicates}"
        )
    return records


def reconcile_scope_manifest(
    records: Sequence[ScopeRecord], collected_nodeids: Iterable[str]
) -> None:
    """Fail when collection and manifest differ in either direction."""
    nodeids = [record.nodeid for record in records]
    if len(nodeids) != len(set(nodeids)):
        raise ScopeManifestError("duplicate nodeid in test scope manifest")
    manifested = set(nodeids)
    collected = set(collected_nodeids)
    unclassified = sorted(collected - manifested)
    retired = sorted(manifested - collected)
    if unclassified or retired:
        raise ScopeManifestError(
            "scope manifest drift: "
            f"unclassified={unclassified}; retired={retired}"
        )


def augment_certification_nodes(
    records: Iterable[ScopeRecord],
    contract_slugs: Iterable[str],
) -> tuple[ScopeRecord, ...]:
    """Classify discovered generic certification nodes not already explicit."""
    augmented = list(records)
    existing = {record.nodeid for record in augmented}
    for slug in sorted(set(contract_slugs)):
        nodeid = CERTIFIED_BUILD_NODE.format(slug=slug)
        if nodeid in existing:
            continue
        augmented.append(ScopeRecord(
            nodeid=nodeid,
            category="document_build_accuracy",
            owner=slug,
            cadence="inner",
            rationale=(
                "Generic certification node discovered from "
                f"details/{slug}.cert.yaml."
            ),
        ))
        existing.add(nodeid)
    return tuple(augmented)


def build_nodes(
    records: Iterable[ScopeRecord],
    owner: str,
    *,
    include_release: bool = False,
) -> tuple[ScopeRecord, ...]:
    """Return one build owner's inner nodes, optionally including release."""
    cadences = BUILD_CADENCES if include_release else {"inner"}
    return tuple(
        record
        for record in records
        if record.category == "document_build_accuracy"
        and record.owner == owner
        and record.cadence in cadences
    )


def platform_nodes(
    records: Iterable[ScopeRecord], tier: str
) -> tuple[ScopeRecord, ...]:
    """Return exactly one explicit shared-platform cadence."""
    if tier not in PLATFORM_CADENCES:
        raise ScopeManifestError(f"unknown platform tier {tier!r}")
    return tuple(
        record
        for record in records
        if record.category == "platform" and record.cadence == tier
    )


def module_paths(records: Iterable[ScopeRecord]) -> tuple[str, ...]:
    """Return normalized test-module paths represented by ``records``."""
    return tuple(sorted({record.nodeid.split("::", 1)[0] for record in records}))
