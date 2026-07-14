from pathlib import Path

from detailgen.design_review import (
    governance_for_review,
    load_design_review_file,
    render_design_review_html,
    validate_design_review,
)
from detailgen.design_review.__main__ import main


FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_review/valid.design-review.yaml"
)


def test_report_is_deterministic_and_contains_provenance_and_decision():
    doc = load_design_review_file(FIXTURE)
    result = validate_design_review(doc)
    governance = governance_for_review(doc, selected_concept="concept_b")

    first = render_design_review_html(doc, result, governance)
    second = render_design_review_html(doc, result, governance)

    assert first == second
    assert first.startswith("<!doctype html>")
    assert "https://example.com/products/three-panel-saddle" in first
    for concept in ("concept_a", "concept_b", "concept_c"):
        assert concept in first
    for criterion in (
        "strength", "part_count", "fasteners", "operations", "tooling",
        "tolerances", "material", "appearance", "builder_skill",
        "instruction_complexity",
    ):
        assert criterion in first
    assert "recommendation_only" in first
    assert "BLOCKED" in first
    assert governance.selection_digest in first


def test_report_surfaces_blocking_findings_for_incomplete_draft():
    doc = load_design_review_file(FIXTURE)
    incomplete = doc.__class__(
        **{
            **doc.__dict__,
            "concepts": doc.concepts[:2],
        }
    )
    result = validate_design_review(incomplete)

    rendered = render_design_review_html(incomplete, result)

    assert "concept.too_few" in rendered
    assert "BLOCKED" in rendered


def test_cli_validates_reports_and_blocks_unapproved_gate(tmp_path, capsys):
    out = tmp_path / "review.html"

    assert main(["validate", str(FIXTURE)]) == 0
    assert main(["report", str(FIXTURE), "--output", str(out)]) == 0
    assert out.read_text().startswith("<!doctype html>")
    assert main([
        "gate", str(FIXTURE), "--stage", "modeling",
        "--selected-concept", "concept_b",
    ]) == 2
    assert "modeling approval" in capsys.readouterr().err
