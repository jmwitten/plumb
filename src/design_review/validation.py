"""Aggregate semantic validation for precedent-first design reviews."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from urllib.parse import urlparse

from .schema import (
    CRITERIA,
    SIGNATURE_FIELDS,
    SOURCE_KINDS,
    DesignReviewDoc,
)


_PLACEHOLDER = re.compile(
    r"\b(?:tbd|todo|n/?a|lorem ipsum|placeholder)\b", re.IGNORECASE
)
_WORDS = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")


@dataclass(frozen=True)
class DesignReviewFinding:
    code: str
    path: str
    message: str
    blocking: bool = True


class DesignReviewValidationError(ValueError):
    """A structurally loaded review is not complete enough for approval."""


@dataclass(frozen=True)
class DesignReviewResult:
    findings: tuple[DesignReviewFinding, ...]

    @property
    def blocking(self) -> tuple[DesignReviewFinding, ...]:
        return tuple(finding for finding in self.findings if finding.blocking)

    @property
    def ok(self) -> bool:
        return not self.blocking

    def require_valid(self) -> "DesignReviewResult":
        if not self.ok:
            lines = "\n".join(
                f"[{finding.code}] {finding.path}: {finding.message}"
                for finding in self.blocking
            )
            raise DesignReviewValidationError(
                "design review is incomplete:\n" + lines
            )
        return self


def _finding(findings, code: str, path: str, message: str) -> None:
    findings.append(DesignReviewFinding(code, path, message))


def _duplicates(values: list[tuple[str, str]], findings, code: str) -> None:
    seen: dict[str, str] = {}
    for path, value in values:
        if value in seen:
            _finding(
                findings,
                code,
                path,
                f"duplicates substantive prose at {seen[value]}",
            )
        else:
            seen[value] = path


def _normalized(text: str) -> str:
    return " ".join(_WORDS.findall(text.lower()))


def _check_prose(
    findings,
    path: str,
    text: str,
    duplicate_groups: dict[str, list[tuple[str, str]]],
    group: str | None = None,
) -> None:
    normalized = _normalized(text or "")
    if not normalized:
        _finding(findings, "prose.empty", path, "substantive prose is required")
        return
    if _PLACEHOLDER.search(text):
        _finding(
            findings,
            "prose.placeholder",
            path,
            "placeholder language cannot satisfy a design gate",
        )
    if len(_WORDS.findall(text)) < 6:
        _finding(
            findings,
            "prose.too_short",
            path,
            "substantive prose requires at least six word tokens",
        )
    if group is not None:
        duplicate_groups.setdefault(group, []).append((path, normalized))


def _validate_prose(doc, findings) -> None:
    groups: dict[str, list[tuple[str, str]]] = {}
    for name in ("use", "loads", "fit_range", "appearance", "builder_skill"):
        _check_prose(findings, f"brief.{name}", getattr(doc.brief, name), groups)
    for index, item in enumerate(doc.brief.required_features):
        _check_prose(
            findings, f"brief.required_features[{index}].text", item.text, groups
        )
    for index, item in enumerate(doc.brief.constraints):
        _check_prose(
            findings, f"brief.constraints[{index}].text", item.text, groups
        )
    for index, source in enumerate(doc.precedents):
        _check_prose(
            findings,
            f"precedents[{index}].construction_pattern",
            source.construction_pattern,
            groups,
        )
        for lesson_index, lesson in enumerate(source.lessons):
            _check_prose(
                findings,
                f"precedents[{index}].lessons[{lesson_index}]",
                lesson,
                groups,
            )
    for index, concept in enumerate(doc.concepts):
        _check_prose(
            findings,
            f"concepts[{index}].summary",
            concept.summary,
            groups,
            "concept.summary",
        )
        for feature_index, feature in enumerate(concept.features):
            _check_prose(
                findings,
                f"concepts[{index}].features[{feature_index}].description",
                feature.description,
                groups,
            )
        for part_index, part in enumerate(concept.parts):
            _check_prose(
                findings,
                f"concepts[{index}].parts[{part_index}].purpose",
                part.purpose,
                groups,
            )
            _check_prose(
                findings,
                f"concepts[{index}].parts[{part_index}].joinery_replacement",
                part.joinery_replacement,
                groups,
            )
    for index, cell in enumerate(doc.comparison):
        _check_prose(
            findings,
            f"comparison[{index}].explanation",
            cell.explanation,
            groups,
            f"comparison.{cell.criterion}",
        )
    for index, deviation in enumerate(doc.deviations):
        if deviation.exception is None:
            continue
        for name in ("rationale", "cost_or_risk", "alternatives_rejected"):
            _check_prose(
                findings,
                f"deviations[{index}].exception.{name}",
                getattr(deviation.exception, name),
                groups,
            )
    _check_prose(findings, "decision.rationale", doc.decision.rationale, groups)
    for index, tradeoff in enumerate(doc.decision.tradeoffs):
        _check_prose(
            findings, f"decision.tradeoffs[{index}]", tradeoff, groups
        )
    for group, values in groups.items():
        _duplicates(values, findings, "prose.duplicate")


def _validate_brief(doc, findings) -> tuple[set[str], set[str]]:
    requirement_ids = [item.id for item in doc.brief.required_features]
    constraint_ids = [item.id for item in doc.brief.constraints]
    if not doc.brief.tools:
        _finding(findings, "brief.missing_tools", "brief.tools", "list tools")
    if not requirement_ids:
        _finding(
            findings,
            "brief.missing_required_features",
            "brief.required_features",
            "list at least one required feature",
        )
    if not constraint_ids:
        _finding(
            findings,
            "brief.missing_constraints",
            "brief.constraints",
            "list at least one prioritized constraint",
        )
    all_ids = requirement_ids + constraint_ids
    for value in sorted(set(all_ids)):
        if all_ids.count(value) > 1:
            _finding(
                findings,
                "id.duplicate",
                "brief",
                f"brief id {value!r} is duplicated",
            )
    priorities = [item.priority for item in doc.brief.constraints]
    if any(priority < 1 for priority in priorities) or len(set(priorities)) != len(priorities):
        _finding(
            findings,
            "brief.invalid_priorities",
            "brief.constraints",
            "constraint priorities must be unique positive integers",
        )
    return set(requirement_ids), set(constraint_ids)


def _validate_precedents(doc, findings) -> set[str]:
    ids = [item.id for item in doc.precedents]
    for value in sorted(set(ids)):
        if ids.count(value) > 1:
            _finding(
                findings, "id.duplicate", "precedents", f"duplicate id {value!r}"
            )
    kinds = {item.kind for item in doc.precedents}
    if "commercial_product" not in kinds:
        _finding(
            findings,
            "precedent.missing_commercial_product",
            "precedents",
            "include at least one comparable commercial product",
        )
    if "build_instruction" not in kinds:
        _finding(
            findings,
            "precedent.missing_build_instruction",
            "precedents",
            "include at least one real build instruction",
        )
    for index, item in enumerate(doc.precedents):
        parsed = urlparse(item.url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            _finding(
                findings,
                "precedent.invalid_url",
                f"precedents[{index}].url",
                "use an absolute http or https source URL",
            )
        try:
            date.fromisoformat(item.accessed_on)
        except ValueError:
            _finding(
                findings,
                "precedent.invalid_access_date",
                f"precedents[{index}].accessed_on",
                "use an ISO date in YYYY-MM-DD form",
            )
        if not item.lessons:
            _finding(
                findings,
                "precedent.missing_lessons",
                f"precedents[{index}].lessons",
                "retain at least one design lesson",
            )
    return set(ids)


def _signature_distance(left, right) -> int:
    return sum(
        getattr(left, field) != getattr(right, field)
        for field in SIGNATURE_FIELDS
    )


def _validate_concepts(doc, findings, precedent_ids) -> tuple[set[str], set[str]]:
    if len(doc.concepts) < 3:
        _finding(
            findings,
            "concept.too_few",
            "concepts",
            "at least three materially distinct concepts are required",
        )
    ids = [concept.id for concept in doc.concepts]
    for value in sorted(set(ids)):
        if ids.count(value) > 1:
            _finding(
                findings, "id.duplicate", "concepts", f"duplicate id {value!r}"
            )
    for left, right in combinations(doc.concepts, 2):
        if _signature_distance(left.signature, right.signature) < 2:
            _finding(
                findings,
                "concept.insufficient_signature_distance",
                f"concepts.{left.id}|{right.id}",
                "concept pair differs in fewer than two architecture fields",
            )
    feature_ids: set[str] = set()
    for concept_index, concept in enumerate(doc.concepts):
        if not concept.features:
            _finding(
                findings,
                "concept.missing_features",
                f"concepts[{concept_index}].features",
                "inventory at least one meaningful feature",
            )
        if not concept.parts:
            _finding(
                findings,
                "concept.missing_parts",
                f"concepts[{concept_index}].parts",
                "inventory conceptual part families",
            )
        local_ids = [feature.id for feature in concept.features]
        for value in sorted(set(local_ids)):
            if local_ids.count(value) > 1:
                _finding(
                    findings,
                    "id.duplicate",
                    f"concepts[{concept_index}].features",
                    f"duplicate feature id {value!r}",
                )
        for feature_index, feature in enumerate(concept.features):
            qualified = f"{concept.id}.{feature.id}"
            feature_ids.add(qualified)
            for ref in feature.precedent_refs:
                if ref not in precedent_ids:
                    _finding(
                        findings,
                        "reference.unknown",
                        f"concepts[{concept_index}].features[{feature_index}].precedent_refs",
                        f"unknown precedent id {ref!r}",
                    )
    return set(ids), feature_ids


def _validate_comparison(
    doc, findings, concept_ids, precedent_ids, brief_ids,
) -> set[str]:
    cell_ids = [cell.id for cell in doc.comparison]
    for value in sorted(set(cell_ids)):
        if cell_ids.count(value) > 1:
            _finding(
                findings, "id.duplicate", "comparison", f"duplicate id {value!r}"
            )
    by_key: dict[tuple[str, str], list[int]] = {}
    evidence_ids = precedent_ids | brief_ids
    for index, cell in enumerate(doc.comparison):
        by_key.setdefault((cell.concept, cell.criterion), []).append(index)
        if cell.concept not in concept_ids:
            _finding(
                findings,
                "reference.unknown",
                f"comparison[{index}].concept",
                f"unknown concept id {cell.concept!r}",
            )
        if not cell.evidence_refs:
            _finding(
                findings,
                "comparison.missing_evidence",
                f"comparison[{index}].evidence_refs",
                "cite precedent or brief evidence",
            )
        for ref in cell.evidence_refs:
            if ref not in evidence_ids:
                _finding(
                    findings,
                    "reference.unknown",
                    f"comparison[{index}].evidence_refs",
                    f"unknown evidence id {ref!r}",
                )
    for concept_id in concept_ids:
        for criterion in CRITERIA:
            matches = by_key.get((concept_id, criterion), [])
            if not matches:
                _finding(
                    findings,
                    "comparison.missing_cell",
                    f"comparison.{concept_id}.{criterion}",
                    "every concept requires every comparison criterion",
                )
            elif len(matches) > 1:
                _finding(
                    findings,
                    "comparison.duplicate_cell",
                    f"comparison.{concept_id}.{criterion}",
                    "a concept may have only one cell per criterion",
                )
    return set(cell_ids)


def _validate_novelty(doc, findings, feature_ids, requirement_ids) -> None:
    deviations: dict[str, list[tuple[int, object]]] = {}
    for index, deviation in enumerate(doc.deviations):
        deviations.setdefault(deviation.feature_ref, []).append((index, deviation))
        if deviation.feature_ref not in feature_ids:
            _finding(
                findings,
                "reference.unknown",
                f"deviations[{index}].feature_ref",
                f"unknown feature ref {deviation.feature_ref!r}",
            )
        if deviation.forcing_requirement:
            if deviation.forcing_requirement not in requirement_ids:
                _finding(
                    findings,
                    "reference.unknown",
                    f"deviations[{index}].forcing_requirement",
                    f"unknown requirement id {deviation.forcing_requirement!r}",
                )
        elif deviation.exception is None:
            _finding(
                findings,
                "novelty.unsupported",
                f"deviations[{index}]",
                "deviation needs a forcing requirement or approved exception",
            )
        if deviation.exception is not None:
            approval_valid = bool(deviation.exception.approved_by.strip())
            try:
                date.fromisoformat(deviation.exception.approved_on)
            except ValueError:
                approval_valid = False
            if not approval_valid:
                _finding(
                    findings,
                    "novelty.invalid_exception_approval",
                    f"deviations[{index}].exception",
                    "an exception requires a named approver and ISO approval date",
                )
    for feature_ref, values in deviations.items():
        if len(values) > 1:
            _finding(
                findings,
                "novelty.duplicate_deviation",
                f"deviations.{feature_ref}",
                "a feature may have only one deviation record",
            )
    for concept in doc.concepts:
        for feature in concept.features:
            if feature.precedent_refs:
                continue
            qualified = f"{concept.id}.{feature.id}"
            values = deviations.get(qualified, [])
            if not values or (
                not values[0][1].forcing_requirement
                and values[0][1].exception is None
            ):
                _finding(
                    findings,
                    "novelty.unsupported",
                    f"concepts.{qualified}",
                    "feature has no precedent and no justified deviation",
                )


def _validate_simplification(
    doc, findings, requirement_ids, feature_ids,
) -> None:
    for concept_index, concept in enumerate(doc.concepts):
        families = [part.part_family for part in concept.parts]
        for value in sorted(set(families)):
            if families.count(value) > 1:
                _finding(
                    findings,
                    "simplification.duplicate_part_family",
                    f"concepts[{concept_index}].parts",
                    f"part family {value!r} is duplicated",
                )
        for part_index, part in enumerate(concept.parts):
            path = f"concepts[{concept_index}].parts[{part_index}]"
            if not part.purpose.strip():
                _finding(
                    findings,
                    "simplification.missing_purpose",
                    f"{path}.purpose",
                    "every part family needs an indispensable purpose",
                )
            if not part.joinery_replacement.strip():
                _finding(
                    findings,
                    "simplification.missing_joinery_review",
                    f"{path}.joinery_replacement",
                    "state whether joinery or an existing part can absorb it",
                )
            if not part.requirement_refs and not part.feature_refs:
                _finding(
                    findings,
                    "simplification.unlinked_purpose",
                    path,
                    "link the purpose to a requirement or concept feature",
                )
            for ref in part.requirement_refs:
                if ref not in requirement_ids:
                    _finding(
                        findings,
                        "reference.unknown",
                        f"{path}.requirement_refs",
                        f"unknown requirement id {ref!r}",
                    )
            for ref in part.feature_refs:
                if ref not in feature_ids:
                    _finding(
                        findings,
                        "reference.unknown",
                        f"{path}.feature_refs",
                        f"unknown feature ref {ref!r}",
                    )


def _validate_decision(doc, findings, concept_ids, cell_ids) -> None:
    if doc.decision.selected_concept not in concept_ids:
        _finding(
            findings,
            "reference.unknown",
            "decision.selected_concept",
            f"unknown concept id {doc.decision.selected_concept!r}",
        )
    if not doc.decision.decisive_cells:
        _finding(
            findings,
            "decision.missing_decisive_cells",
            "decision.decisive_cells",
            "cite the comparison cells that drove selection",
        )
    by_id = {cell.id: cell for cell in doc.comparison}
    for ref in doc.decision.decisive_cells:
        if ref not in cell_ids:
            _finding(
                findings,
                "reference.unknown",
                "decision.decisive_cells",
                f"unknown comparison cell {ref!r}",
            )
        elif by_id[ref].concept != doc.decision.selected_concept:
            _finding(
                findings,
                "decision.foreign_decisive_cell",
                "decision.decisive_cells",
                f"decisive cell {ref!r} belongs to another concept",
            )
    if not doc.decision.tradeoffs:
        _finding(
            findings,
            "decision.missing_tradeoffs",
            "decision.tradeoffs",
            "record at least one accepted tradeoff",
        )


def validate_design_review(doc: DesignReviewDoc) -> DesignReviewResult:
    findings: list[DesignReviewFinding] = []
    requirement_ids, constraint_ids = _validate_brief(doc, findings)
    precedent_ids = _validate_precedents(doc, findings)
    concept_ids, feature_ids = _validate_concepts(doc, findings, precedent_ids)
    cell_ids = _validate_comparison(
        doc,
        findings,
        concept_ids,
        precedent_ids,
        requirement_ids | constraint_ids,
    )
    _validate_novelty(doc, findings, feature_ids, requirement_ids)
    _validate_simplification(doc, findings, requirement_ids, feature_ids)
    _validate_decision(doc, findings, concept_ids, cell_ids)
    _validate_prose(doc, findings)
    return DesignReviewResult(tuple(findings))
