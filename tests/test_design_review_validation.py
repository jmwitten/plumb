from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.design_review import (
    Approval,
    Deviation,
    NoveltyException,
    load_design_review_file,
    model_fingerprint,
    selection_fingerprint,
    validate_design_review,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_review/valid.design-review.yaml"
)


@pytest.fixture
def valid_doc():
    return load_design_review_file(FIXTURE)


def codes(result):
    return {finding.code for finding in result.blocking}


def test_valid_structured_draft_passes_without_requiring_approval(valid_doc):
    result = validate_design_review(valid_doc)

    assert result.ok
    assert result.findings == ()


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


def test_fewer_than_three_concepts_blocks(valid_doc):
    result = validate_design_review(
        replace(valid_doc, concepts=valid_doc.concepts[:2])
    )

    assert "concept.too_few" in codes(result)


def test_unsupported_novelty_blocks(valid_doc):
    concept = valid_doc.concepts[0]
    feature = replace(concept.features[0], precedent_refs=())
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
        feature_ref=f"{concept.id}.{feature.id}",
        forcing_requirement="",
        exception=NoveltyException(
            rationale=(
                "The removable liner requires a locating lip absent from the "
                "reviewed precedents."
            ),
            cost_or_risk=(
                "The lip adds one routing setup and can trap debris if left "
                "unfinished."
            ),
            alternatives_rejected=(
                "A loose liner could shift into the cup opening during use."
            ),
            approved_by="Joel Witten",
            approved_on="2026-07-14",
        ),
    )
    doc = replace(
        valid_doc,
        concepts=(concept,) + valid_doc.concepts[1:],
        deviations=(deviation,),
    )

    assert "novelty.unsupported" not in codes(validate_design_review(doc))


def test_forcing_requirement_justifies_novelty(valid_doc):
    concept = valid_doc.concepts[0]
    feature = replace(concept.features[0], precedent_refs=())
    concept = replace(concept, features=(feature,) + concept.features[1:])
    deviation = Deviation(
        feature_ref=f"{concept.id}.{feature.id}",
        forcing_requirement="req_fit",
        exception=None,
    )
    doc = replace(
        valid_doc,
        concepts=(concept,) + valid_doc.concepts[1:],
        deviations=(deviation,),
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

    assert "simplification.missing_purpose" in codes(
        validate_design_review(purpose_doc)
    )
    assert "simplification.missing_joinery_review" in codes(
        validate_design_review(joinery_doc)
    )


@pytest.mark.parametrize(
    ("bad_text", "expected"),
    [
        ("", "prose.empty"),
        ("TBD", "prose.placeholder"),
        ("good", "prose.too_short"),
        ("same words repeated", "prose.too_short"),
    ],
)
def test_empty_placeholder_and_superficial_prose_block(
    valid_doc, bad_text, expected,
):
    repeated = tuple(
        replace(cell, explanation=bad_text)
        if cell.criterion == "strength" else cell
        for cell in valid_doc.comparison
    )

    result = validate_design_review(replace(valid_doc, comparison=repeated))

    assert expected in codes(result)


def test_repeated_boilerplate_across_concepts_blocks(valid_doc):
    repeated = tuple(
        replace(
            cell,
            explanation=(
                "This copied explanation supplies no concept-specific "
                "comparison evidence."
            ),
        )
        if cell.criterion == "strength" else cell
        for cell in valid_doc.comparison
    )

    result = validate_design_review(replace(valid_doc, comparison=repeated))

    assert "prose.duplicate" in codes(result)


def test_missing_comparison_cell_blocks(valid_doc):
    result = validate_design_review(
        replace(valid_doc, comparison=valid_doc.comparison[:-1])
    )

    assert "comparison.missing_cell" in codes(result)


def test_broken_references_and_invalid_url_block(valid_doc):
    source = replace(valid_doc.precedents[0], url="file:///tmp/source")
    cell = replace(valid_doc.comparison[0], evidence_refs=("missing",))
    doc = replace(
        valid_doc,
        precedents=(source,) + valid_doc.precedents[1:],
        comparison=(cell,) + valid_doc.comparison[1:],
    )

    result = validate_design_review(doc)

    assert "precedent.invalid_url" in codes(result)
    assert "reference.unknown" in codes(result)


def test_decision_requires_decisive_comparison_cells(valid_doc):
    decision = replace(valid_doc.decision, decisive_cells=())

    result = validate_design_review(replace(valid_doc, decision=decision))

    assert "decision.missing_decisive_cells" in codes(result)


def test_selection_fingerprint_is_deterministic_and_ignores_approvals(valid_doc):
    first = selection_fingerprint(valid_doc)
    approved = replace(
        valid_doc,
        modeling_approval=Approval(
            approved_by="Joel Witten",
            approved_on="2026-07-14",
            selection_fingerprint=first,
        ),
    )

    assert selection_fingerprint(valid_doc) == first
    assert selection_fingerprint(approved) == first


def test_selection_edit_changes_fingerprint_but_source_path_does_not(valid_doc):
    changed = replace(
        valid_doc,
        brief=replace(
            valid_doc.brief,
            use=valid_doc.brief.use + " The revised use also includes books.",
        ),
    )
    relocated = replace(valid_doc, source_path=Path("/tmp/elsewhere.yaml"))

    assert selection_fingerprint(changed) != selection_fingerprint(valid_doc)
    assert selection_fingerprint(relocated) == selection_fingerprint(valid_doc)


def test_model_fingerprint_uses_selected_concept_and_spec_payload():
    payload = {"name": "example", "components": []}
    base = model_fingerprint(payload, "concept_a")

    assert model_fingerprint(payload, "concept_b") != base
    assert model_fingerprint(
        {**payload, "type": "changed"}, "concept_a"
    ) != base
