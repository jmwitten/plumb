"""Slug-independent accuracy rules for normalized build evidence."""

from __future__ import annotations

import dataclasses
import json
import math
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from .model import (
    CertificationContext,
    CertificationFinding,
    CountIntent,
    FindingState,
    IntentSelector,
)


class CertificationRule(Protocol):
    id: str

    def evaluate(self, context: CertificationContext) -> CertificationFinding:
        """Evaluate one stable rule against two fresh evidence snapshots."""


def _canonical(value):
    if dataclasses.is_dataclass(value):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def canonical_json(value) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"))


def _fingerprint(rule_id: str, payload) -> str:
    raw = canonical_json({"rule": rule_id, "evidence": payload})
    return sha256(raw.encode()).hexdigest()


def _finding(
    rule_id: str,
    state: FindingState,
    subject: str,
    detail: str,
    *,
    fingerprint_payload=None,
) -> CertificationFinding:
    return CertificationFinding(
        rule_id=rule_id,
        state=state,
        subject=subject,
        detail=detail,
        evidence_fingerprint=(
            ""
            if fingerprint_payload is None
            else _fingerprint(rule_id, fingerprint_payload)
        ),
    )


class CompileSuccessRule:
    id = "compile.success"

    def evaluate(self, context):
        snapshot = context.primary
        error = snapshot.compile_error or snapshot.collector_error
        if error:
            return _finding(self.id, FindingState.FAIL, snapshot.slug, error)
        return _finding(
            self.id, FindingState.PASS, snapshot.slug,
            "subject compiled and evidence collection completed",
        )


class ValidationCleanRule:
    id = "validation.clean"

    def evaluate(self, context):
        snapshot = context.primary
        failures = [row for row in snapshot.validation.blocking if row.verdict == "FAIL"]
        unknown = [row for row in snapshot.validation.blocking if row.verdict == "UNKNOWN"]
        if failures:
            detail = "; ".join(
                f"{row.check}: {row.subject} — {row.detail}" for row in failures
            )
            return _finding(self.id, FindingState.FAIL, snapshot.slug, detail)
        if unknown:
            detail = "UNKNOWN: " + "; ".join(
                f"{row.check}: {row.subject} — {row.detail}" for row in unknown
            )
            return _finding(
                self.id,
                FindingState.NEEDS_DECISION,
                snapshot.slug,
                detail,
                fingerprint_payload=unknown,
            )
        if not snapshot.validation.ok:
            return _finding(
                self.id, FindingState.FAIL, snapshot.slug,
                "validation is not clean but supplied no blocking evidence",
            )
        return _finding(
            self.id, FindingState.PASS, snapshot.slug,
            "production validation report is clean",
        )


class GeometryPartsValidRule:
    id = "geometry.parts_valid"

    def evaluate(self, context):
        parts = context.primary.parts
        problems = []
        if not parts:
            problems.append("assembly contains no parts")
        ids = [part.id for part in parts]
        duplicates = sorted({part_id for part_id in ids if ids.count(part_id) > 1})
        if duplicates:
            problems.append(f"duplicate part ids {duplicates}")
        for part in parts:
            if part.solid_count <= 0:
                problems.append(f"{part.id} has no solid")
            if not math.isfinite(part.volume_mm3) or part.volume_mm3 <= 0:
                problems.append(f"{part.id} has invalid volume {part.volume_mm3}")
            if len(part.bounds_mm) != 6 or not all(
                math.isfinite(value) for value in part.bounds_mm
            ):
                problems.append(f"{part.id} has invalid bounds")
        if problems:
            return _finding(
                self.id, FindingState.FAIL, context.primary.slug,
                "; ".join(problems),
            )
        return _finding(
            self.id, FindingState.PASS, context.primary.slug,
            f"{len(parts)} parts have unique ids and valid non-empty solids",
        )


class ConnectionReferencesRule:
    id = "connections.resolved"

    def evaluate(self, context):
        known = {part.id for part in context.primary.parts}
        missing = sorted({
            endpoint
            for edge in context.primary.connections
            for endpoint in (edge.a, edge.b)
            if endpoint not in known
        })
        if missing:
            return _finding(
                self.id, FindingState.FAIL, context.primary.slug,
                f"connection endpoints do not resolve: {missing}",
            )
        return _finding(
            self.id, FindingState.PASS, context.primary.slug,
            f"{len(context.primary.connections)} connection edges resolve",
        )


class FabricationFoldRule:
    id = "fabrication.fold"

    def evaluate(self, context):
        snapshot = context.primary
        if snapshot.fabrication_error:
            return _finding(
                self.id, FindingState.FAIL, snapshot.slug,
                snapshot.fabrication_error,
            )
        known = {part.id for part in snapshot.parts}
        missing = sorted(
            row.part_id for row in snapshot.fabrication if row.part_id not in known
        )
        if missing:
            return _finding(
                self.id, FindingState.FAIL, snapshot.slug,
                f"fabrication records reference unknown parts: {missing}",
            )
        return _finding(
            self.id, FindingState.PASS, snapshot.slug,
            f"fabrication fold verified for {len(snapshot.fabrication)} made parts",
        )


class BomSourceIdsRule:
    id = "bom.source_ids"

    def evaluate(self, context):
        snapshot = context.primary
        known = {part.id for part in snapshot.parts}
        occurrences: dict[str, int] = {}
        for row in snapshot.bom:
            if row.quantity != len(row.source_ids):
                return _finding(
                    self.id, FindingState.FAIL, snapshot.slug,
                    f"{row.item!r} quantity {row.quantity} does not match "
                    f"{len(row.source_ids)} source ids",
                )
            for part_id in row.source_ids:
                occurrences[part_id] = occurrences.get(part_id, 0) + 1
        duplicate = sorted(part_id for part_id, count in occurrences.items() if count > 1)
        unknown = sorted(set(occurrences) - known)
        absent = sorted(known - set(occurrences))
        if duplicate:
            detail = f"part ids appear in more than one BOM row: {duplicate}"
        elif unknown:
            detail = f"BOM rows reference unknown part ids: {unknown}"
        elif absent:
            detail = f"modeled part ids are absent from the BOM: {absent}"
        else:
            return _finding(
                self.id, FindingState.PASS, snapshot.slug,
                f"{len(known)} modeled part ids partition the BOM",
            )
        return _finding(self.id, FindingState.FAIL, snapshot.slug, detail)


class GovernanceReadyRule:
    id = "governance.ready"

    def evaluate(self, context):
        governance = context.primary.governance
        if not governance.present:
            return _finding(
                self.id, FindingState.PASS, context.primary.slug,
                "subject does not declare design governance",
            )
        if not governance.modeling_ready or not governance.delivery_ready:
            return _finding(
                self.id, FindingState.FAIL, context.primary.slug,
                "governed subject is not modeling- and delivery-ready",
            )
        return _finding(
            self.id, FindingState.PASS, context.primary.slug,
            f"governed selection {governance.selected_concept!r} is ready",
        )


def _matches(row, selector: IntentSelector) -> bool:
    for field in ("component", "material", "role", "name", "kind"):
        expected = getattr(selector, field)
        if expected is None:
            continue
        actual = getattr(row, field, None)
        if field == "role":
            if expected not in getattr(row, "roles", ()):
                return False
        elif actual != expected:
            return False
    if selector.name_contains is not None:
        name = getattr(row, "name", "")
        if selector.name_contains.casefold() not in name.casefold():
            return False
    return True


def _count_error(rows, intent: CountIntent, label: str) -> str | None:
    count = sum(1 for row in rows if _matches(row, intent.selector))
    if intent.exactly is not None and count != intent.exactly:
        return f"{label} expected exactly {intent.exactly}, observed {count}"
    if intent.minimum is not None and count < intent.minimum:
        return f"{label} expected at least {intent.minimum}, observed {count}"
    if intent.maximum is not None and count > intent.maximum:
        return f"{label} expected at most {intent.maximum}, observed {count}"
    return None


class IntentRule:
    id = "intent.matches"

    def evaluate(self, context):
        snapshot = context.primary
        intent = context.contract.intent
        problems = []
        for index, row in enumerate(intent.counts):
            error = _count_error(snapshot.parts, row, f"counts[{index}]")
            if error:
                problems.append(error)
        for index, selector in enumerate(intent.forbidden):
            matched = [part.id for part in snapshot.parts if _matches(part, selector)]
            if matched:
                problems.append(
                    f"forbidden selector matched part ids {matched} at forbidden[{index}]"
                )
        for index, row in enumerate(intent.connections):
            error = _count_error(snapshot.connections, row, f"connections[{index}]")
            if error:
                problems.append(error)
        fabrication_by_id = {row.part_id: row.steps for row in snapshot.fabrication}
        for index, row in enumerate(intent.fabrication):
            matched = [part for part in snapshot.parts if _matches(part, row.selector)]
            if not matched:
                problems.append(f"fabrication[{index}] selector matched no parts")
                continue
            for part in matched:
                observed = fabrication_by_id.get(part.id)
                if observed != row.steps:
                    problems.append(
                        f"fabrication[{index}] {part.id} expected steps "
                        f"{row.steps}, observed {observed}"
                    )
        for index, row in enumerate(intent.bom):
            matched = [item for item in snapshot.bom if item.item == row.item]
            quantity = sum(item.quantity for item in matched)
            if quantity != row.quantity:
                problems.append(
                    f"bom[{index}] {row.item!r} expected quantity "
                    f"{row.quantity}, observed {quantity}"
                )
            if row.length_mm is not None:
                for item in matched:
                    length = item.length_mm
                    if length is None:
                        problems.append(f"bom[{index}] {row.item!r} has no length_mm")
                    elif (
                        row.length_mm.minimum is not None
                        and length < row.length_mm.minimum
                    ):
                        problems.append(
                            f"bom[{index}] {row.item!r} length {length} below "
                            f"{row.length_mm.minimum}"
                        )
                    elif (
                        row.length_mm.maximum is not None
                        and length > row.length_mm.maximum
                    ):
                        problems.append(
                            f"bom[{index}] {row.item!r} length {length} above "
                            f"{row.length_mm.maximum}"
                        )
        expected_governance = intent.governance
        if any(
            value is not None
            for value in (
                expected_governance.selected_concept,
                expected_governance.modeling_ready,
                expected_governance.delivery_ready,
            )
        ):
            observed = snapshot.governance
            if not observed.present:
                problems.append("declared governance intent but governance is absent")
            else:
                for field in (
                    "selected_concept", "modeling_ready", "delivery_ready",
                ):
                    expected = getattr(expected_governance, field)
                    if expected is not None and getattr(observed, field) != expected:
                        problems.append(
                            f"governance {field} expected {expected!r}, "
                            f"observed {getattr(observed, field)!r}"
                        )
        if problems:
            return _finding(
                self.id, FindingState.FAIL, snapshot.slug,
                "; ".join(problems),
            )
        return _finding(
            self.id, FindingState.PASS, snapshot.slug,
            "all declared acceptance intent matches evidence",
        )


class DeterministicEvidenceRule:
    id = "determinism.evidence"

    def evaluate(self, context):
        primary = canonical_json(context.primary)
        repeat = canonical_json(context.repeat)
        if primary != repeat:
            return _finding(
                self.id, FindingState.FAIL, context.primary.slug,
                "two fresh collections produced different normalized evidence",
            )
        return _finding(
            self.id, FindingState.PASS, context.primary.slug,
            "two fresh collections produced identical normalized evidence",
        )


DEFAULT_RULES: tuple[CertificationRule, ...] = (
    CompileSuccessRule(),
    ValidationCleanRule(),
    GeometryPartsValidRule(),
    ConnectionReferencesRule(),
    FabricationFoldRule(),
    BomSourceIdsRule(),
    GovernanceReadyRule(),
    IntentRule(),
    DeterministicEvidenceRule(),
)

