# Precedent-First Design Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, precedent-first design-selection artifact whose approved concept gates production promotion and whose model fingerprint gates delivery, then prove it with an evidence-backed armchair-caddy report without changing caddy geometry.

**Architecture:** A new `detailgen.design_review` package owns strict YAML loading, immutable review values, validation, fingerprints, lifecycle gates, CLI commands, and a standalone HTML report. DetailSpec gains only a small optional sidecar binding; compiled governed details carry governance state, while ungoverned details follow the existing lifecycle exactly. The caddy opts in with a pending, recommendation-only review, so its design report is available but its default customer-document delivery path fails closed until owner approval and a later conformance confirmation.

**Tech Stack:** Python 3.12, frozen dataclasses, PyYAML, stdlib `argparse`/`hashlib`/`json`/`html`, pytest 9, existing DetailSpec compiler and `Detail` lifecycle.

## Global Constraints

- Work only in `/Users/joelwitten/Code/construction-detail-generator/.worktrees/precedent-first-design-selection` on `codex/precedent-first-design-selection`.
- Preserve the dirty primary checkout and all concurrent worktrees.
- Design governance is opt-in; a DetailSpec with no `design_review` field must retain existing load, compile, validate, render, serialization, and document behavior.
- Do not add a product-specific rule about rails, miters, dowels, brackets, or any other technique.
- Keep design-review output out of the customer build manual.
- Do not change armchair-caddy production geometry in this increment.
- Unknown comparison outcomes remain `unknown`; validation and reporting must not imply safety or adequacy.
- Official caddy delivery must write no customer artifact when governance is incomplete or stale.
- Use TDD for every behavior change and commit after each independently reviewable task.
- Run tests through `.venv/bin/python` so imports resolve to the isolated worktree.
- Do not merge the feature branch.

---

## File Structure

- `src/design_review/schema.py` — frozen domain values, closed vocabularies, and review/gate exceptions.
- `src/design_review/loader.py` — strict YAML/JSON loader with path-aware teaching errors.
- `src/design_review/validation.py` — aggregate structural/semantic findings and adversarial prose checks.
- `src/design_review/fingerprint.py` — canonical JSON payloads and SHA-256 fingerprints.
- `src/design_review/gate.py` — immutable governance state and modeling/delivery gate decisions.
- `src/design_review/report.py` — deterministic standalone developer HTML.
- `src/design_review/__main__.py` — `validate`, `report`, and `gate` CLI subcommands.
- `src/design_review/__init__.py` — public API.
- `src/spec/schema.py` / `src/spec/loader.py` / `src/spec/serialize.py` — optional DetailSpec binding.
- `src/spec/compiler.py` — resolve sidecar and attach governance to `SpecDetail`.
- `src/details/base.py` — default delivery-ready hook used by certified render.
- `scripts/caddy_documents.py` — fail before output creation for the governed caddy.
- `details/armchair_caddy.design-review.yaml` — pilot evidence and recommendation.
- `details/armchair_caddy.spec.yaml` — opt-in binding only; no geometry edit.
- `tests/fixtures/design_review/valid.design-review.yaml` — minimal reusable valid draft.
- `tests/test_design_review_schema.py` — loading and strict-schema tests.
- `tests/test_design_review_validation.py` — completeness, distinctness, novelty, exception, purpose, and superficial-prose tests.
- `tests/test_design_review_gate.py` — fingerprint and lifecycle tests.
- `tests/test_design_review_report.py` — deterministic HTML/CLI tests.
- `tests/test_design_review_integration.py` — DetailSpec opt-in and legacy behavior.
- `tests/test_caddy_design_review.py` — real pilot content, report, gate, and geometry-equivalence tests.

---

### Task 1: Strict Design-Review Domain and Loader

**Files:**
- Create: `src/design_review/schema.py`
- Create: `src/design_review/loader.py`
- Create: `src/design_review/__init__.py`
- Create: `tests/fixtures/design_review/valid.design-review.yaml`
- Create: `tests/test_design_review_schema.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `DesignReviewDoc`, `DesignBrief`, `Precedent`, `Concept`, `ArchitectureSignature`, `ConceptFeature`, `PartPurpose`, `ComparisonCell`, `Deviation`, `Decision`, `Approval`, `DeliveryConfirmation`, `DesignReviewSchemaError`.
- Produces: `load_design_review_file(path: str | Path) -> DesignReviewDoc` and `load_design_review_text(text: str, *, fmt: str = "yaml") -> DesignReviewDoc`.
- Consumes: PyYAML and stdlib dataclasses only; no DetailSpec or CadQuery import.

- [ ] **Step 1: Write a complete valid fixture**

Create `tests/fixtures/design_review/valid.design-review.yaml` with schema
`detailgen/design-review/v1`, all eight brief fields, one commercial source,
one instruction source, three concepts whose six-field signatures differ by at
least two fields, ten comparison cells per concept, complete part purposes, a
decision selecting `concept_b`, and absent approvals. Use substantive unique
sentences so the same fixture later passes prose validation.

- [ ] **Step 2: Write failing loader tests**

```python
from pathlib import Path
import pytest

from detailgen.design_review import (
    DesignReviewSchemaError,
    load_design_review_file,
    load_design_review_text,
)

FIXTURE = Path(__file__).parent / "fixtures/design_review/valid.design-review.yaml"


def test_loads_complete_design_review_document():
    doc = load_design_review_file(FIXTURE)
    assert doc.schema == "detailgen/design-review/v1"
    assert doc.project_id == "example_project"
    assert [concept.id for concept in doc.concepts] == [
        "concept_a", "concept_b", "concept_c"
    ]
    assert doc.decision.selected_concept == "concept_b"
    assert doc.source_path == FIXTURE.resolve()


def test_unknown_top_level_key_is_a_teaching_error():
    text = FIXTURE.read_text().replace(
        "project_id: example_project",
        "project_id: example_project\nconceptz: []",
    )
    with pytest.raises(DesignReviewSchemaError, match="unknown key 'conceptz'"):
        load_design_review_text(text)


def test_closed_source_kind_rejects_typo():
    text = FIXTURE.read_text().replace(
        "kind: commercial_product", "kind: commercial"
    )
    with pytest.raises(DesignReviewSchemaError, match="commercial_product"):
        load_design_review_text(text)
```

- [ ] **Step 3: Run loader tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_design_review_schema.py -q`

Expected: collection fails because `detailgen.design_review` does not exist.

- [ ] **Step 4: Implement frozen schema values and vocabularies**

In `src/design_review/schema.py`, define frozen dataclasses and these closed
vocabularies exactly:

```python
SCHEMA_ID = "detailgen/design-review/v1"
SOURCE_KINDS = ("commercial_product", "build_instruction")
ASSESSMENTS = ("advantage", "neutral", "disadvantage", "unknown")
APPLICATION_STATES = ("recommendation_only", "implemented")
CRITERIA = (
    "strength", "part_count", "fasteners", "operations", "tooling",
    "tolerances", "material", "appearance", "builder_skill",
    "instruction_complexity",
)
SIGNATURE_FIELDS = (
    "load_path", "joint_family", "part_topology", "fastening_strategy",
    "visible_seam_strategy", "fit_strategy",
)
```

Use these exact immutable shapes:

```python
Requirement(id: str, text: str)
Constraint(id: str, text: str, priority: int)
DesignBrief(
    use: str, loads: str, fit_range: str, appearance: str,
    builder_skill: str, tools: tuple[str, ...],
    required_features: tuple[Requirement, ...],
    constraints: tuple[Constraint, ...],
)
Precedent(
    id: str, kind: str, title: str, publisher: str, url: str,
    accessed_on: str, construction_pattern: str, lessons: tuple[str, ...],
)
ArchitectureSignature(
    load_path: str, joint_family: str, part_topology: str,
    fastening_strategy: str, visible_seam_strategy: str, fit_strategy: str,
)
NoveltyException(
    rationale: str, cost_or_risk: str, alternatives_rejected: str,
    approved_by: str, approved_on: str,
)
ConceptFeature(
    id: str, description: str, precedent_refs: tuple[str, ...],
)
PartPurpose(
    part_family: str, purpose: str, requirement_refs: tuple[str, ...],
    feature_refs: tuple[str, ...], joinery_replacement: str,
)
Concept(
    id: str, title: str, summary: str,
    signature: ArchitectureSignature,
    features: tuple[ConceptFeature, ...], parts: tuple[PartPurpose, ...],
)
ComparisonCell(
    id: str, concept: str, criterion: str, assessment: str,
    explanation: str, evidence_refs: tuple[str, ...],
)
Deviation(
    feature_ref: str, forcing_requirement: str,
    exception: NoveltyException | None,
)
Decision(
    selected_concept: str, rationale: str,
    decisive_cells: tuple[str, ...], tradeoffs: tuple[str, ...],
    application: str,
)
Approval(approved_by: str, approved_on: str, selection_fingerprint: str)
DeliveryConfirmation(
    approved_by: str, approved_on: str,
    selection_fingerprint: str, model_fingerprint: str,
)
DesignReviewDoc(
    schema: str, project_id: str, title: str, status: str,
    brief: DesignBrief, precedents: tuple[Precedent, ...],
    concepts: tuple[Concept, ...], comparison: tuple[ComparisonCell, ...],
    deviations: tuple[Deviation, ...], decision: Decision,
    modeling_approval: Approval | None,
    delivery_confirmation: DeliveryConfirmation | None,
    source_path: Path | None,
)
```

`DesignReviewDoc.source_path` must be `field(default=None, compare=False,
repr=False)` so filesystem location never affects value equality or canonical
fingerprints.

- [ ] **Step 5: Implement strict recursive loading**

In `src/design_review/loader.py`, implement one `_take(raw, fields, context)`
helper matching the teaching-error style in `src/spec/schema.py`. Every mapping
rejects unknown keys; every required list must be a list; ids and prose load as
strings without semantic judgment. `load_design_review_file()` must use
`dataclasses.replace(doc, source_path=path.resolve())`.

- [ ] **Step 6: Export the public API and package it**

Add `detailgen.design_review` to the setuptools `packages` list. Export schema
types and loader functions from `src/design_review/__init__.py`; do not import
the package from top-level `src/__init__.py` because no registry side effect is
required.

- [ ] **Step 7: Run loader tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_design_review_schema.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit the schema slice**

```bash
git add pyproject.toml src/design_review tests/fixtures/design_review tests/test_design_review_schema.py
git commit -m "feat: add structured design review schema"
```

---

### Task 2: Validation, Adversarial Prose Checks, and Fingerprints

**Files:**
- Create: `src/design_review/validation.py`
- Create: `src/design_review/fingerprint.py`
- Create: `tests/test_design_review_validation.py`
- Modify: `src/design_review/__init__.py`

**Interfaces:**
- Consumes: `DesignReviewDoc` from Task 1.
- Produces: `DesignReviewFinding(code: str, path: str, message: str, blocking: bool = True)`.
- Produces: `DesignReviewResult(findings: tuple[DesignReviewFinding, ...])` with `ok`, `blocking`, and `require_valid()`.
- Produces: `validate_design_review(doc: DesignReviewDoc) -> DesignReviewResult`.
- Produces: `selection_payload(doc) -> dict`, `selection_fingerprint(doc) -> str`, `model_fingerprint(spec_payload: dict, selected_concept: str) -> str`.

- [ ] **Step 1: Write failing requirement tests**

Use `dataclasses.replace()` against the loaded valid fixture. Define this
fixture and helper at the top of the test module:

```python
@pytest.fixture
def valid_doc():
    return load_design_review_file(FIXTURE)


def codes(result):
    return {finding.code for finding in result.blocking}
```

Add one focused test for each required failure code:

```python
def test_precedent_requires_both_source_kinds(valid_doc):
    only_products = tuple(
        source for source in valid_doc.precedents
        if source.kind == "commercial_product"
    )
    result = validate_design_review(replace(valid_doc, precedents=only_products))
    assert "precedent.missing_build_instruction" in codes(result)


def test_three_renamed_copies_are_not_distinct(valid_doc):
    first = valid_doc.concepts[0]
    copies = tuple(replace(first, id=f"copy_{index}") for index in range(3))
    result = validate_design_review(replace(valid_doc, concepts=copies))
    assert "concept.insufficient_signature_distance" in codes(result)


def test_unsupported_novelty_blocks(valid_doc):
    concept = valid_doc.concepts[0]
    feature = replace(
        concept.features[0], precedent_refs=(),
    )
    concept = replace(concept, features=(feature,) + concept.features[1:])
    result = validate_design_review(
        replace(valid_doc, concepts=(concept,) + valid_doc.concepts[1:])
    )
    assert "novelty.unsupported" in codes(result)


def test_approved_exception_justifies_novelty(valid_doc):
    concept = valid_doc.concepts[0]
    feature = replace(concept.features[0], precedent_refs=())
    concept = replace(concept, features=(feature,) + concept.features[1:])
    deviation = Deviation(
        feature_ref=f"{concept.id}.{feature.id}", forcing_requirement="",
        exception=NoveltyException(
            rationale="The removable liner requires a locating lip not shown in the reviewed precedents.",
            cost_or_risk="The lip adds one routing setup and can trap debris if left unfinished.",
            alternatives_rejected="A loose liner could shift into the cup opening during use.",
            approved_by="Joel Witten", approved_on="2026-07-14",
        ),
    )
    doc = replace(
        valid_doc,
        concepts=(concept,) + valid_doc.concepts[1:],
        deviations=valid_doc.deviations + (deviation,),
    )
    assert "novelty.unsupported" not in codes(validate_design_review(doc))


def test_missing_part_purpose_and_joinery_answer_block(valid_doc):
    concept = valid_doc.concepts[0]
    part = concept.parts[0]
    no_purpose = replace(part, purpose="")
    no_joinery = replace(part, joinery_replacement="")
    purpose_doc = replace(
        valid_doc,
        concepts=(replace(concept, parts=(no_purpose,) + concept.parts[1:]),)
        + valid_doc.concepts[1:],
    )
    joinery_doc = replace(
        valid_doc,
        concepts=(replace(concept, parts=(no_joinery,) + concept.parts[1:]),)
        + valid_doc.concepts[1:],
    )
    assert "simplification.missing_purpose" in codes(validate_design_review(purpose_doc))
    assert "simplification.missing_joinery_review" in codes(validate_design_review(joinery_doc))


@pytest.mark.parametrize("bad_text", ["", "TBD", "good", "same words repeated"])
def test_empty_placeholder_and_superficial_prose_block(valid_doc, bad_text):
    repeated = tuple(
        replace(cell, explanation=bad_text)
        if cell.criterion == "strength" else cell
        for cell in valid_doc.comparison
    )
    result = validate_design_review(replace(valid_doc, comparison=repeated))
    assert codes(result) & {
        "prose.empty", "prose.placeholder", "prose.too_short",
        "prose.duplicate",
    }
```

Also test missing comparison criteria, broken refs, duplicate ids, invalid URL
schemes, missing access dates, and a decision whose rationale cites no decisive
cell.

- [ ] **Step 2: Write failing fingerprint tests**

```python
def test_selection_fingerprint_is_deterministic_and_ignores_approvals(valid_doc):
    first = selection_fingerprint(valid_doc)
    approved = replace(valid_doc, modeling_approval=Approval(
        approved_by="Joel Witten", approved_on="2026-07-14",
        selection_fingerprint=first,
    ))
    assert selection_fingerprint(approved) == first


def test_selection_edit_changes_fingerprint(valid_doc):
    changed = replace(valid_doc, title=valid_doc.title + " revised")
    assert selection_fingerprint(changed) != selection_fingerprint(valid_doc)


def test_model_fingerprint_uses_selected_concept_and_spec_payload():
    payload = {"name": "example", "components": []}
    base = model_fingerprint(payload, "concept_a")
    assert model_fingerprint(payload, "concept_b") != base
    assert model_fingerprint({**payload, "type": "changed"}, "concept_a") != base
```

- [ ] **Step 3: Run validation tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_design_review_validation.py -q`

Expected: imports fail for missing validation/fingerprint modules.

- [ ] **Step 4: Implement deterministic aggregate validation**

Implement validators as small functions called in a fixed order by
`validate_design_review()`: `_validate_brief`, `_validate_precedents`,
`_validate_concepts`, `_validate_comparison`, `_validate_novelty`,
`_validate_simplification`, `_validate_decision`, `_validate_approvals`, and
`_validate_prose`. Never stop at the first semantic error.

Signature distance is:

```python
def signature_distance(left, right) -> int:
    return sum(
        getattr(left, field) != getattr(right, field)
        for field in SIGNATURE_FIELDS
    )
```

Reject pairs below distance 2. Prose normalization must lowercase, collapse
whitespace, strip punctuation, reject `tbd|todo|n/a|lorem ipsum|placeholder`,
require at least six word tokens for substantive narrative fields, and reject
normalized duplicates within concept summaries and within each comparison
criterion. These checks supplement rather than replace human approval.

- [ ] **Step 5: Implement canonical payloads and hashes**

Convert dataclasses recursively to JSON-native values while excluding
`source_path`, `modeling_approval`, and `delivery_confirmation` from the
selection payload. Hash `json.dumps(payload, sort_keys=True,
separators=(",", ":"), ensure_ascii=False).encode("utf-8")` with SHA-256.

- [ ] **Step 6: Run validation tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_design_review_validation.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit validation and fingerprints**

```bash
git add src/design_review tests/test_design_review_validation.py
git commit -m "feat: validate design selection evidence"
```

---

### Task 3: Lifecycle Gates, Standalone Report, and CLI

**Files:**
- Create: `src/design_review/gate.py`
- Create: `src/design_review/report.py`
- Create: `src/design_review/__main__.py`
- Create: `tests/test_design_review_gate.py`
- Create: `tests/test_design_review_report.py`
- Modify: `src/design_review/__init__.py`

**Interfaces:**
- Consumes: Task 1 document and Task 2 validation/fingerprint functions.
- Produces: `DesignReviewGateError`, `DesignGovernance`, `governance_for_review(doc, *, selected_concept, spec_payload=None)`.
- Produces: `DesignGovernance.require_modeling_approval() -> DesignGovernance` and `.require_delivery_confirmation() -> DesignGovernance`.
- Produces: `render_design_review_html(doc, result, governance=None) -> str`.
- CLI: `python -m detailgen.design_review {validate,report,gate}`.

- [ ] **Step 1: Write failing gate tests**

Define exact approval helpers in `tests/test_design_review_gate.py`:

```python
def approve(doc):
    digest = selection_fingerprint(doc)
    return replace(doc, modeling_approval=Approval(
        approved_by="Joel Witten", approved_on="2026-07-14",
        selection_fingerprint=digest,
    ))


def approve_and_confirm(doc, spec_payload, selected_concept):
    applied = replace(
        doc,
        decision=replace(doc.decision, application="implemented"),
    )
    digest = selection_fingerprint(applied)
    return replace(
        applied,
        modeling_approval=Approval(
            approved_by="Joel Witten", approved_on="2026-07-14",
            selection_fingerprint=digest,
        ),
        delivery_confirmation=DeliveryConfirmation(
            approved_by="Joel Witten", approved_on="2026-07-14",
            selection_fingerprint=digest,
            model_fingerprint=model_fingerprint(spec_payload, selected_concept),
        ),
    )
```

```python
def test_valid_but_unapproved_review_cannot_be_promoted(valid_doc):
    governance = governance_for_review(valid_doc, selected_concept="concept_b")
    with pytest.raises(DesignReviewGateError, match="modeling approval"):
        governance.require_modeling_approval()


def test_current_selection_approval_opens_modeling_gate(valid_doc):
    digest = selection_fingerprint(valid_doc)
    approved = replace(valid_doc, modeling_approval=Approval(
        approved_by="Joel Witten", approved_on="2026-07-14",
        selection_fingerprint=digest,
    ))
    assert governance_for_review(
        approved, selected_concept="concept_b"
    ).require_modeling_approval().modeling_ready


def test_stale_modeling_approval_fails(valid_doc):
    approved = approve(valid_doc)
    changed = replace(approved, title=approved.title + " changed")
    with pytest.raises(DesignReviewGateError, match="stale selection"):
        governance_for_review(changed, selected_concept="concept_b").require_modeling_approval()


def test_delivery_requires_current_selection_and_model_hash(valid_doc):
    spec_payload = {"name": "example", "components": []}
    confirmed = approve_and_confirm(valid_doc, spec_payload, "concept_b")
    governance = governance_for_review(
        confirmed, selected_concept="concept_b", spec_payload=spec_payload,
    )
    assert governance.require_delivery_confirmation().delivery_ready
    changed = {**spec_payload, "type": "changed"}
    with pytest.raises(DesignReviewGateError, match="stale model"):
        governance_for_review(
            confirmed, selected_concept="concept_b", spec_payload=changed,
        ).require_delivery_confirmation()
```

- [ ] **Step 2: Write failing report and CLI tests**

Assert two calls to `render_design_review_html()` are byte-identical and the
HTML includes every concept id, source URL, criterion, deviation status,
selection fingerprint, and blocking finding. Invoke `main([...])` directly to
assert `validate` returns 0 for the valid fixture, `report` writes HTML for a
valid-but-unapproved draft, and `gate --stage modeling` returns nonzero.

- [ ] **Step 3: Run gate/report tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_design_review_gate.py tests/test_design_review_report.py -q`

Expected: missing module imports.

- [ ] **Step 4: Implement lifecycle governance**

`DesignGovernance` stores the document, validation result, selected concept,
selection fingerprint, optional model fingerprint, and computed readiness
properties. Modeling approval requires a valid document, matching selected
concept, nonempty approver/date, and exact selection hash. Delivery additionally
requires `decision.application == "implemented"` and a confirmation matching
both current hashes.

- [ ] **Step 5: Implement escaped deterministic HTML**

Build one self-contained HTML string with `html.escape()` for all authored
content. Use stable document order, no timestamps, no network assets, and no
JavaScript requirement. Render explicit `BLOCKED`, `UNKNOWN`,
`recommendation_only`, and stale states; never infer a pass from absence.

- [ ] **Step 6: Implement CLI subcommands**

Use `argparse` subparsers:

```python
validate REVIEW
report REVIEW --output PATH
gate REVIEW --stage {modeling,delivery} [--spec-json PATH] [--selected-concept ID]
```

The `gate` command accepts a review directly in this task; Task 4 extends it to
accept a DetailSpec and resolve its binding. Catch only known schema/gate
exceptions, print the teaching message to stderr, and return 2.

- [ ] **Step 7: Run gate/report tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_design_review_gate.py tests/test_design_review_report.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit gates and report**

```bash
git add src/design_review tests/test_design_review_gate.py tests/test_design_review_report.py
git commit -m "feat: gate and report design reviews"
```

---

### Task 4: Opt-In DetailSpec and Delivery Integration

**Files:**
- Modify: `src/spec/schema.py`
- Modify: `src/spec/loader.py`
- Modify: `src/spec/serialize.py`
- Modify: `src/spec/compiler.py`
- Modify: `src/details/base.py`
- Modify: `src/design_review/__main__.py`
- Create: `tests/test_design_review_integration.py`

**Interfaces:**
- Produces: `DesignReviewSpec(record: str, selected_concept: str)` on `DetailSpecDoc.design_review`.
- Produces: `DetailSpecDoc.source_path: Path | None`, excluded from equality/serialization.
- Produces: `SpecDetail.design_governance: DesignGovernance | None`.
- Produces: `SpecDetail.require_modeling_approval()` and override of `require_delivery_ready()`.
- Produces: `Detail.require_delivery_ready()` defaulting to existing physical `require_clean()`.

- [ ] **Step 1: Write failing opt-in and legacy tests**

Define this fixture writer in `tests/test_design_review_integration.py`; it
builds a governed copy of the real step-stool spec without changing repository
fixtures:

```python
def write_governed_fixture(tmp_path, *, approved=False, confirmed=False):
    review_path = tmp_path / "example.design-review.yaml"
    review_raw = yaml.safe_load(VALID_REVIEW.read_text())
    if confirmed:
        review_raw["decision"]["application"] = "implemented"
    review_path.write_text(yaml.safe_dump(review_raw, sort_keys=False))

    spec_path = tmp_path / "step_stool.spec.yaml"
    spec_raw = yaml.safe_load(STEP_STOOL_SPEC.read_text())
    spec_raw["design_review"] = {
        "record": review_path.name,
        "selected_concept": "concept_b",
    }
    spec_path.write_text(yaml.safe_dump(spec_raw, sort_keys=False))

    if approved or confirmed:
        doc = load_design_review_file(review_path)
        digest = selection_fingerprint(doc)
        review_raw["modeling_approval"] = {
            "approved_by": "Joel Witten",
            "approved_on": "2026-07-14",
            "selection_fingerprint": digest,
        }
        if confirmed:
            spec_payload = spec_to_dict(load_spec_file(spec_path))
            review_raw["delivery_confirmation"] = {
                "approved_by": "Joel Witten",
                "approved_on": "2026-07-14",
                "selection_fingerprint": digest,
                "model_fingerprint": model_fingerprint(
                    spec_payload, "concept_b"
                ),
            }
        review_path.write_text(yaml.safe_dump(review_raw, sort_keys=False))
    return spec_path
```

```python
def test_ungoverned_spec_round_trips_and_renders_unchanged(tmp_path):
    detail = compile_spec_file(ROOT / "details/step_stool.spec.yaml")
    assert detail.design_governance is None
    assert detail.require_modeling_approval() is detail
    assert detail.require_delivery_ready().ok


def test_governed_draft_compiles_but_cannot_be_promoted(tmp_path):
    spec_path = write_governed_fixture(tmp_path, approved=False)
    detail = compile_spec_file(spec_path)
    assert detail.design_governance is not None
    assert detail.validate().ok
    with pytest.raises(DesignReviewGateError, match="modeling approval"):
        detail.require_modeling_approval()


def test_governed_render_writes_nothing_without_delivery_confirmation(tmp_path):
    spec_path = write_governed_fixture(tmp_path, approved=True, confirmed=False)
    detail = compile_spec_file(spec_path)
    out = tmp_path / "delivery"
    with pytest.raises(DesignReviewGateError, match="delivery confirmation"):
        detail.render(out)
    assert not out.exists()


def test_relative_review_path_resolves_from_spec_directory(tmp_path):
    spec_path = write_governed_fixture(tmp_path, approved=True)
    detail = compile_spec_file(spec_path)
    assert detail.design_governance.review.source_path.parent == spec_path.parent
```

Also pin that `spec_to_dict()` emits only `record` and `selected_concept`, never
`source_path`, and that unknown binding keys receive a teaching error.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_design_review_integration.py -q`

Expected: DetailSpec rejects the unknown `design_review` key.

- [ ] **Step 3: Add the optional binding and source context**

Add frozen `DesignReviewSpec` to `src/spec/schema.py`; add
`design_review: DesignReviewSpec | None = None` and
`source_path: Path | None = field(default=None, compare=False, repr=False)` to
`DetailSpecDoc`. Extend the loader’s top-level `_take`, parse exactly `record`
and `selected_concept`, and set `source_path` only in `load_spec_file()` using
`replace()`.

- [ ] **Step 4: Preserve serialization identity**

Extend `spec_to_dict()` to emit `design_review` only when non-null. Do not emit
`source_path`. Run existing round-trip tests after the new focused test.

- [ ] **Step 5: Attach governance during file compilation**

In `SpecDetail.__init__`, set `self.design_governance = None` for ungoverned
docs. For a binding, require `doc.source_path`, resolve
`doc.source_path.parent / binding.record`, load the review, build the canonical
spec payload with `spec_to_dict(doc)`, and call `governance_for_review()`.

Implement:

```python
def require_modeling_approval(self):
    if self.design_governance is not None:
        self.design_governance.require_modeling_approval()
    return self

def require_delivery_ready(self):
    report = super().require_delivery_ready()
    if self.design_governance is not None:
        self.design_governance.require_delivery_confirmation()
    return report
```

In `Detail`, add `require_delivery_ready()` returning `require_clean()` and
change certified `render()` to call it before `_render_into()`. Do not gate
`render_documentation()`; project-specific delivery scripts must call the
delivery hook explicitly before writing.

- [ ] **Step 6: Extend CLI gate to DetailSpec bindings**

When the `gate` positional path loads as a DetailSpec, compile it without
geometry, then call `require_modeling_approval()` or
`design_governance.require_delivery_confirmation()`. Keep direct-review mode
for isolated review development.

- [ ] **Step 7: Run focused and legacy tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_design_review_integration.py tests/test_spec.py tests/test_detail_base.py tests/test_packaging.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit DetailSpec integration**

```bash
git add src/spec src/details/base.py src/design_review/__main__.py tests/test_design_review_integration.py
git commit -m "feat: gate governed detail lifecycle"
```

---

### Task 5: Armchair-Caddy Evidence, Recommendation, and Governed Delivery

**Files:**
- Create: `details/armchair_caddy.design-review.yaml`
- Modify: `details/armchair_caddy.spec.yaml`
- Modify: `scripts/caddy_documents.py`
- Create: `tests/test_caddy_design_review.py`
- Modify: `tests/test_caddy_instruction_manual.py`

**Interfaces:**
- Consumes: Task 4 governed DetailSpec lifecycle.
- Produces: real caddy review with four concepts and pending approvals.
- Produces: `build_caddy_document_pair(..., spec_path=SDR.CADDY_SPEC)` so legacy manual presentation tests can use an explicitly ungoverned temporary copy while the default governed production path remains blocked.

- [ ] **Step 1: Verify primary precedent pages**

Re-open each candidate source and retain only pages that visibly support the
recorded construction claim. At minimum include one commercial product and two
real build instructions. Record title, publisher, URL, access date
`2026-07-14`, observed joint/part pattern, and the claim used in the comparison.
Do not treat search-result snippets as evidence.

- [ ] **Step 2: Write failing pilot-content tests**

Define the ungoverned comparison helper exactly once in
`tests/test_caddy_design_review.py`:

```python
def strip_design_review(path):
    raw = yaml.safe_load(Path(path).read_text())
    raw.pop("design_review", None)
    return yaml.safe_dump(raw, sort_keys=False)
```

```python
def test_caddy_review_has_required_concepts_and_complete_matrix():
    doc = load_design_review_file(REVIEW)
    assert {concept.id for concept in doc.concepts} == {
        "current_double_wall", "reinforced_miter", "rabbet_and_dowel",
        "concealed_pocket_screw_or_bracket",
    }
    assert len(doc.comparison) == 4 * len(CRITERIA)
    assert {source.kind for source in doc.precedents} == {
        "commercial_product", "build_instruction"
    }
    assert validate_design_review(doc).ok


def test_caddy_recommendation_is_evidence_linked_and_not_applied():
    doc = load_design_review_file(REVIEW)
    assert doc.decision.selected_concept in {concept.id for concept in doc.concepts}
    assert len(doc.decision.decisive_cells) >= 3
    assert doc.decision.application == "recommendation_only"
    assert doc.delivery_confirmation is None


def test_caddy_geometry_is_unchanged_by_governance_binding():
    from detailgen.core.buildinfo import build_manifest

    governed = compile_spec_file(CADDY_SPEC)
    ungoverned = compile_spec(load_spec_text(strip_design_review(CADDY_SPEC)))
    assert (build_manifest(governed.assembly)["assembly_hash"]
            == build_manifest(ungoverned.assembly)["assembly_hash"])
    assert governed.bom_table() == ungoverned.bom_table()


def test_default_caddy_delivery_fails_before_writing(tmp_path):
    with pytest.raises(DesignReviewGateError):
        build_caddy_document_pair(tmp_path)
    assert not tmp_path.exists()
```

Use the repository’s existing assembly-identity helper if `assembly_hash()` is
not a public method; do not invent a second geometry digest.

- [ ] **Step 3: Run caddy pilot tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_caddy_design_review.py -q`

Expected: missing review file and binding.

- [ ] **Step 4: Author the caddy review**

Capture the prioritized brief, verified sources, four architecture signatures,
feature inventories, conceptual part purposes, full 40-cell comparison,
deviation ledger, and evidence-linked recommendation. The current two rails
must appear only as ordinary parts/features whose part count, fasteners,
operations, tolerance cost, and precedent support are compared by general
rules. Do not encode “rails are bad.”

- [ ] **Step 5: Opt in without changing geometry**

Add only this top-level binding to `details/armchair_caddy.spec.yaml`:

```yaml
design_review:
  record: armchair_caddy.design-review.yaml
  selected_concept: reinforced_miter
```

The existing handoff research supports `reinforced_miter` as the working
recommendation because it removes the extra wall parts while retaining a
concealed, precedent-backed furniture joint. Re-open the primary sources and
complete the matrix before authoring the decision; if that evidence contradicts
the working recommendation, amend this approved plan and design record together
before changing the binding.

- [ ] **Step 6: Gate the default document pair before filesystem mutation**

Add `spec_path: str | Path = SDR.CADDY_SPEC` to
`build_caddy_document_pair()`. Compile `spec_path`, call
`detail.require_delivery_ready()`, then create `out_dir`. Pass `spec_path` into
`SDR.build_document()` so a test copy and its compiled detail remain one source.

Adapt existing manual presentation tests through a module-scoped fixture that
writes an otherwise identical temporary caddy spec with `design_review`
removed and calls `build_caddy_document_pair(..., spec_path=legacy_copy)`.
These remain tests of the manual renderer, not a production delivery bypass.

- [ ] **Step 7: Run caddy and legacy behavior tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_caddy_design_review.py tests/test_caddy_instruction_manual.py tests/test_armchair_caddy_e2e.py -q
```

Expected: all pass; real caddy delivery is blocked, legacy-copy manual tests
still prove the unchanged presentation pipeline, and geometry identity holds.

- [ ] **Step 8: Generate the standalone report**

Run:

```bash
.venv/bin/python -m detailgen.design_review report \
  details/armchair_caddy.design-review.yaml \
  --output outputs/design-reviews/armchair_caddy.html
```

Expected: exit 0 and a standalone developer report containing four concepts,
source URLs, all ten criteria, deviations, recommendation, and blocked approval
status. Confirm no customer manual file is created.

- [ ] **Step 9: Commit the governed pilot**

```bash
git add details/armchair_caddy.design-review.yaml details/armchair_caddy.spec.yaml scripts/caddy_documents.py tests/test_caddy_design_review.py tests/test_caddy_instruction_manual.py
git commit -m "feat: govern armchair caddy design selection"
```

---

### Task 6: Adversarial Review, Documentation, and Release Verification

**Files:**
- Modify if findings require: `src/design_review/*.py`, relevant tests, or caddy review.
- Modify: `README.md`
- Verify: `outputs/design-reviews/armchair_caddy.html` (generated, gitignored).

**Interfaces:**
- Consumes every earlier task.
- Produces a documented command surface, adversarial evidence, clean targeted/full test runs, and a pushed review branch.

- [ ] **Step 1: Add README usage and lifecycle wording**

Document the sidecar, opt-in binding, `validate`/`report`/`gate` commands,
modeling-versus-delivery gates, explicit low-level non-production escape hatch,
and the fact that legacy details remain ungoverned.

- [ ] **Step 2: Run an adversarial fixture mutation matrix**

Run the focused validation tests plus a small inline script that mutates the
valid fixture into: empty prose, six-word repeated prose, three identical
signatures, URL-only precedents with no observation, all-neutral comparison
cells with copied explanations, circular deviation references, and an
exception with no approver. Convert every uncovered bypass into a named pytest
regression before changing implementation.

- [ ] **Step 3: Inspect the generated caddy report**

Open `outputs/design-reviews/armchair_caddy.html` and verify the selected
concept rationale follows the actual matrix, the two rails are not singled out
by code or canned report language, source URLs are visible, unknowns remain
unknown, and approval/delivery are visibly blocked.

- [ ] **Step 4: Run all targeted tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_design_review_schema.py \
  tests/test_design_review_validation.py \
  tests/test_design_review_gate.py \
  tests/test_design_review_report.py \
  tests/test_design_review_integration.py \
  tests/test_caddy_design_review.py \
  tests/test_caddy_instruction_manual.py \
  tests/test_armchair_caddy_e2e.py -q
```

Expected: all pass.

- [ ] **Step 5: Run packaging and legacy smoke tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_packaging.py tests/test_spec.py tests/test_detail_base.py tests/test_step_stool_e2e.py -q
```

Expected: all pass.

- [ ] **Step 6: Run the complete suite**

Run: `.venv/bin/python -m pytest -n auto`

Expected: no failures; compare totals with the clean baseline of 1,742 passed,
3 skipped, and 1 xfailed plus the newly added tests.

- [ ] **Step 7: Verify worktree and commits**

Run:

```bash
git diff --check
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected: no uncommitted tracked changes, only intentional feature commits,
and no production caddy geometry edits beyond the two-line governance binding.

- [ ] **Step 8: Commit final documentation or review fixes**

```bash
git add README.md src/design_review tests details scripts/caddy_documents.py
git commit -m "docs: document precedent-first design gates"
```

Skip this commit only if every listed path is already clean after prior commits.

- [ ] **Step 9: Push without merging**

Run: `git push -u origin codex/precedent-first-design-selection`

Expected: push succeeds. Do not merge and do not create an auto-merge rule.

- [ ] **Step 10: Hand off the owner review surface**

Report the branch, worktree, exact targeted/full test results, commit list, and
absolute path to `outputs/design-reviews/armchair_caddy.html`. State plainly
that caddy delivery remains blocked until the owner approves the recommendation
and a later geometry implementation receives current delivery confirmation.
