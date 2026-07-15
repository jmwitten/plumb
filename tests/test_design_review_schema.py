from pathlib import Path

import pytest

from detailgen.design_review import (
    DesignReviewSchemaError,
    load_design_review_file,
    load_design_review_text,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_review/valid.design-review.yaml"
)


def test_loads_complete_design_review_document():
    doc = load_design_review_file(FIXTURE)

    assert doc.schema == "detailgen/design-review/v1"
    assert doc.project_id == "example_project"
    assert [concept.id for concept in doc.concepts] == [
        "concept_a", "concept_b", "concept_c",
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
        "kind: commercial_product", "kind: commercial",
    )

    with pytest.raises(DesignReviewSchemaError, match="commercial_product"):
        load_design_review_text(text)
