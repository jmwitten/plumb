"""Strict YAML/JSON loading for design-review records."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import yaml

from .schema import (
    APPLICATION_STATES,
    ASSESSMENTS,
    CRITERIA,
    SCHEMA_ID,
    SOURCE_KINDS,
    Approval,
    ArchitectureSignature,
    ComparisonCell,
    Concept,
    ConceptFeature,
    Constraint,
    Decision,
    DeliveryConfirmation,
    DesignBrief,
    DesignReviewDoc,
    DesignReviewSchemaError,
    Deviation,
    NoveltyException,
    PartPurpose,
    Precedent,
    Requirement,
)


def _take(raw, fields: dict[str, bool], context: str) -> dict:
    if not isinstance(raw, dict):
        raise DesignReviewSchemaError(
            f"{context}: expected a mapping, got {type(raw).__name__}"
        )
    unknown = sorted(set(raw) - set(fields))
    if unknown:
        key = unknown[0]
        raise DesignReviewSchemaError(
            f"{context}: unknown key {key!r}; allowed keys: "
            f"{sorted(fields)}"
        )
    missing = [name for name, required in fields.items()
               if required and name not in raw]
    if missing:
        raise DesignReviewSchemaError(
            f"{context}: missing required key {missing[0]!r}"
        )
    return {name: raw.get(name) for name in fields}


def _list(value, context: str) -> list:
    if not isinstance(value, list):
        raise DesignReviewSchemaError(
            f"{context}: expected a list, got {type(value).__name__}"
        )
    return value


def _text(value, context: str) -> str:
    if not isinstance(value, str):
        raise DesignReviewSchemaError(
            f"{context}: expected text, got {type(value).__name__}"
        )
    return value


def _texts(value, context: str) -> tuple[str, ...]:
    return tuple(
        _text(item, f"{context}[{index}]")
        for index, item in enumerate(_list(value, context))
    )


def _date_text(value, context: str) -> str:
    """Normalize PyYAML's implicit ISO date scalar to canonical text."""
    if isinstance(value, date):
        return value.isoformat()
    return _text(value, context)


def _closed(value, allowed: tuple[str, ...], context: str) -> str:
    value = _text(value, context)
    if value not in allowed:
        raise DesignReviewSchemaError(
            f"{context}: {value!r} is not valid; expected one of {list(allowed)}"
        )
    return value


def _requirement(raw, context: str) -> Requirement:
    f = _take(raw, {"id": True, "text": True}, context)
    return Requirement(_text(f["id"], f"{context}.id"),
                       _text(f["text"], f"{context}.text"))


def _constraint(raw, context: str) -> Constraint:
    f = _take(raw, {"id": True, "text": True, "priority": True}, context)
    priority = f["priority"]
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise DesignReviewSchemaError(
            f"{context}.priority: expected an integer, got {priority!r}"
        )
    return Constraint(
        _text(f["id"], f"{context}.id"),
        _text(f["text"], f"{context}.text"),
        priority,
    )


def _brief(raw) -> DesignBrief:
    f = _take(raw, {
        "use": True,
        "loads": True,
        "fit_range": True,
        "appearance": True,
        "builder_skill": True,
        "tools": True,
        "required_features": True,
        "constraints": True,
    }, "brief")
    return DesignBrief(
        use=_text(f["use"], "brief.use"),
        loads=_text(f["loads"], "brief.loads"),
        fit_range=_text(f["fit_range"], "brief.fit_range"),
        appearance=_text(f["appearance"], "brief.appearance"),
        builder_skill=_text(f["builder_skill"], "brief.builder_skill"),
        tools=_texts(f["tools"], "brief.tools"),
        required_features=tuple(
            _requirement(item, f"brief.required_features[{index}]")
            for index, item in enumerate(
                _list(f["required_features"], "brief.required_features")
            )
        ),
        constraints=tuple(
            _constraint(item, f"brief.constraints[{index}]")
            for index, item in enumerate(
                _list(f["constraints"], "brief.constraints")
            )
        ),
    )


def _precedent(raw, index: int) -> Precedent:
    context = f"precedents[{index}]"
    f = _take(raw, {
        "id": True,
        "kind": True,
        "title": True,
        "publisher": True,
        "url": True,
        "accessed_on": True,
        "construction_pattern": True,
        "lessons": True,
    }, context)
    return Precedent(
        id=_text(f["id"], f"{context}.id"),
        kind=_closed(f["kind"], SOURCE_KINDS, f"{context}.kind"),
        title=_text(f["title"], f"{context}.title"),
        publisher=_text(f["publisher"], f"{context}.publisher"),
        url=_text(f["url"], f"{context}.url"),
        accessed_on=_date_text(f["accessed_on"], f"{context}.accessed_on"),
        construction_pattern=_text(
            f["construction_pattern"], f"{context}.construction_pattern"
        ),
        lessons=_texts(f["lessons"], f"{context}.lessons"),
    )


def _signature(raw, context: str) -> ArchitectureSignature:
    fields = {
        "load_path": True,
        "joint_family": True,
        "part_topology": True,
        "fastening_strategy": True,
        "visible_seam_strategy": True,
        "fit_strategy": True,
    }
    f = _take(raw, fields, context)
    return ArchitectureSignature(**{
        name: _text(f[name], f"{context}.{name}") for name in fields
    })


def _feature(raw, context: str) -> ConceptFeature:
    f = _take(raw, {
        "id": True, "description": True, "precedent_refs": True,
    }, context)
    return ConceptFeature(
        id=_text(f["id"], f"{context}.id"),
        description=_text(f["description"], f"{context}.description"),
        precedent_refs=_texts(f["precedent_refs"], f"{context}.precedent_refs"),
    )


def _part(raw, context: str) -> PartPurpose:
    f = _take(raw, {
        "part_family": True,
        "purpose": True,
        "requirement_refs": True,
        "feature_refs": True,
        "joinery_replacement": True,
    }, context)
    return PartPurpose(
        part_family=_text(f["part_family"], f"{context}.part_family"),
        purpose=_text(f["purpose"], f"{context}.purpose"),
        requirement_refs=_texts(
            f["requirement_refs"], f"{context}.requirement_refs"
        ),
        feature_refs=_texts(f["feature_refs"], f"{context}.feature_refs"),
        joinery_replacement=_text(
            f["joinery_replacement"], f"{context}.joinery_replacement"
        ),
    )


def _concept(raw, index: int) -> Concept:
    context = f"concepts[{index}]"
    f = _take(raw, {
        "id": True,
        "title": True,
        "summary": True,
        "signature": True,
        "features": True,
        "parts": True,
    }, context)
    return Concept(
        id=_text(f["id"], f"{context}.id"),
        title=_text(f["title"], f"{context}.title"),
        summary=_text(f["summary"], f"{context}.summary"),
        signature=_signature(f["signature"], f"{context}.signature"),
        features=tuple(
            _feature(item, f"{context}.features[{feature_index}]")
            for feature_index, item in enumerate(
                _list(f["features"], f"{context}.features")
            )
        ),
        parts=tuple(
            _part(item, f"{context}.parts[{part_index}]")
            for part_index, item in enumerate(
                _list(f["parts"], f"{context}.parts")
            )
        ),
    )


def _comparison(raw, index: int) -> ComparisonCell:
    context = f"comparison[{index}]"
    f = _take(raw, {
        "id": True,
        "concept": True,
        "criterion": True,
        "assessment": True,
        "explanation": True,
        "evidence_refs": True,
    }, context)
    return ComparisonCell(
        id=_text(f["id"], f"{context}.id"),
        concept=_text(f["concept"], f"{context}.concept"),
        criterion=_closed(f["criterion"], CRITERIA, f"{context}.criterion"),
        assessment=_closed(
            f["assessment"], ASSESSMENTS, f"{context}.assessment"
        ),
        explanation=_text(f["explanation"], f"{context}.explanation"),
        evidence_refs=_texts(f["evidence_refs"], f"{context}.evidence_refs"),
    )


def _exception(raw, context: str) -> NoveltyException:
    f = _take(raw, {
        "rationale": True,
        "cost_or_risk": True,
        "alternatives_rejected": True,
        "approved_by": True,
        "approved_on": True,
    }, context)
    return NoveltyException(
        rationale=_text(f["rationale"], f"{context}.rationale"),
        cost_or_risk=_text(f["cost_or_risk"], f"{context}.cost_or_risk"),
        alternatives_rejected=_text(
            f["alternatives_rejected"], f"{context}.alternatives_rejected"
        ),
        approved_by=_text(f["approved_by"], f"{context}.approved_by"),
        approved_on=_date_text(f["approved_on"], f"{context}.approved_on"),
    )


def _deviation(raw, index: int) -> Deviation:
    context = f"deviations[{index}]"
    f = _take(raw, {
        "feature_ref": True,
        "forcing_requirement": False,
        "exception": False,
    }, context)
    return Deviation(
        feature_ref=_text(f["feature_ref"], f"{context}.feature_ref"),
        forcing_requirement=_text(
            f["forcing_requirement"] or "", f"{context}.forcing_requirement"
        ),
        exception=(
            None if f["exception"] is None
            else _exception(f["exception"], f"{context}.exception")
        ),
    )


def _decision(raw) -> Decision:
    f = _take(raw, {
        "selected_concept": True,
        "rationale": True,
        "decisive_cells": True,
        "tradeoffs": True,
        "application": True,
    }, "decision")
    return Decision(
        selected_concept=_text(
            f["selected_concept"], "decision.selected_concept"
        ),
        rationale=_text(f["rationale"], "decision.rationale"),
        decisive_cells=_texts(f["decisive_cells"], "decision.decisive_cells"),
        tradeoffs=_texts(f["tradeoffs"], "decision.tradeoffs"),
        application=_closed(
            f["application"], APPLICATION_STATES, "decision.application"
        ),
    )


def _approval(raw, context: str) -> Approval | None:
    if raw is None:
        return None
    f = _take(raw, {
        "approved_by": True,
        "approved_on": True,
        "selection_fingerprint": True,
    }, context)
    return Approval(
        approved_by=_text(f["approved_by"], f"{context}.approved_by"),
        approved_on=_date_text(f["approved_on"], f"{context}.approved_on"),
        selection_fingerprint=_text(
            f["selection_fingerprint"], f"{context}.selection_fingerprint"
        ),
    )


def _confirmation(raw) -> DeliveryConfirmation | None:
    if raw is None:
        return None
    context = "delivery_confirmation"
    f = _take(raw, {
        "approved_by": True,
        "approved_on": True,
        "selection_fingerprint": True,
        "model_fingerprint": True,
    }, context)
    return DeliveryConfirmation(
        approved_by=_text(f["approved_by"], f"{context}.approved_by"),
        approved_on=_date_text(f["approved_on"], f"{context}.approved_on"),
        selection_fingerprint=_text(
            f["selection_fingerprint"], f"{context}.selection_fingerprint"
        ),
        model_fingerprint=_text(
            f["model_fingerprint"], f"{context}.model_fingerprint"
        ),
    )


def _build_doc(raw) -> DesignReviewDoc:
    f = _take(raw, {
        "schema": True,
        "project_id": True,
        "title": True,
        "status": True,
        "brief": True,
        "precedents": True,
        "concepts": True,
        "comparison": True,
        "deviations": True,
        "decision": True,
        "modeling_approval": False,
        "delivery_confirmation": False,
    }, "design review")
    schema = _text(f["schema"], "schema")
    if schema != SCHEMA_ID:
        raise DesignReviewSchemaError(
            f"schema: expected {SCHEMA_ID!r}, got {schema!r}"
        )
    return DesignReviewDoc(
        schema=schema,
        project_id=_text(f["project_id"], "project_id"),
        title=_text(f["title"], "title"),
        status=_text(f["status"], "status"),
        brief=_brief(f["brief"]),
        precedents=tuple(
            _precedent(item, index)
            for index, item in enumerate(
                _list(f["precedents"], "precedents")
            )
        ),
        concepts=tuple(
            _concept(item, index)
            for index, item in enumerate(_list(f["concepts"], "concepts"))
        ),
        comparison=tuple(
            _comparison(item, index)
            for index, item in enumerate(
                _list(f["comparison"], "comparison")
            )
        ),
        deviations=tuple(
            _deviation(item, index)
            for index, item in enumerate(
                _list(f["deviations"], "deviations")
            )
        ),
        decision=_decision(f["decision"]),
        modeling_approval=_approval(f["modeling_approval"], "modeling_approval"),
        delivery_confirmation=_confirmation(f["delivery_confirmation"]),
    )


def load_design_review_text(
    text: str, *, fmt: str = "yaml",
) -> DesignReviewDoc:
    raw = json.loads(text) if fmt == "json" else yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise DesignReviewSchemaError(
            "a design-review document must be a mapping at top level, got "
            f"{type(raw).__name__}"
        )
    return _build_doc(raw)


def load_design_review_file(path: str | Path) -> DesignReviewDoc:
    path = Path(path)
    fmt = "json" if path.suffix.lower() == ".json" else "yaml"
    doc = load_design_review_text(path.read_text(), fmt=fmt)
    return replace(doc, source_path=path.resolve())
