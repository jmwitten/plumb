from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from detailgen.design_review import (
    DesignReviewGateError,
    load_design_review_file,
    model_fingerprint,
    selection_fingerprint,
)
from detailgen.design_review.__main__ import main as design_review_main
from detailgen.spec import (
    SpecCompileError,
    SpecSchemaError,
    compile_spec_file,
    load_spec_file,
    load_spec_text,
    spec_to_dict,
)


ROOT = Path(__file__).resolve().parents[1]
VALID_REVIEW = (
    ROOT / "tests/fixtures/design_review/valid.design-review.yaml"
)
BASE_SPEC = ROOT / "tests/fixtures/cl1/mount_bearing.spec.yaml"


def write_governed_fixture(tmp_path, *, approved=False, confirmed=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    review_path = tmp_path / "example.design-review.yaml"
    review_raw = yaml.safe_load(VALID_REVIEW.read_text())
    if confirmed:
        review_raw["decision"]["application"] = "implemented"
    review_path.write_text(yaml.safe_dump(review_raw, sort_keys=False))

    spec_path = tmp_path / "mount_bearing.spec.yaml"
    spec_raw = yaml.safe_load(BASE_SPEC.read_text())
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


def test_ungoverned_spec_round_trips_and_uses_existing_delivery_gate():
    doc = load_spec_file(BASE_SPEC)
    detail = compile_spec_file(BASE_SPEC)

    assert "design_review" not in spec_to_dict(doc)
    assert detail.design_governance is None
    assert detail.require_modeling_approval() is detail
    assert detail.require_delivery_ready().ok


def test_loader_path_context_does_not_change_legacy_dataclass_projection():
    doc = load_spec_file(BASE_SPEC)

    assert "source_path" not in asdict(doc)


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

    with pytest.raises(DesignReviewGateError, match="recommendation_only"):
        detail.render(out)

    assert not out.exists()


def test_current_delivery_confirmation_allows_certified_render(tmp_path):
    spec_path = write_governed_fixture(tmp_path, confirmed=True)
    detail = compile_spec_file(spec_path)
    out = tmp_path / "delivery"

    assert detail.render(out) == out
    assert out.exists()
    assert list(out.glob("*.step"))


def test_relative_review_path_resolves_from_spec_directory(tmp_path):
    spec_path = write_governed_fixture(tmp_path, approved=True)
    detail = compile_spec_file(spec_path)

    assert detail.design_governance.review.source_path.parent == spec_path.parent


def test_binding_round_trips_without_source_path(tmp_path):
    spec_path = write_governed_fixture(tmp_path)
    doc = load_spec_file(spec_path)
    payload = spec_to_dict(doc)

    assert payload["design_review"] == {
        "record": "example.design-review.yaml",
        "selected_concept": "concept_b",
    }
    assert "source_path" not in payload
    assert load_spec_text(yaml.safe_dump(payload)) == doc


def test_unknown_binding_key_is_a_teaching_error(tmp_path):
    spec_path = write_governed_fixture(tmp_path)
    text = spec_path.read_text().replace(
        "selected_concept: concept_b",
        "selected_concept: concept_b\n  selected_conceptt: concept_a",
    )

    with pytest.raises(SpecSchemaError, match="selected_conceptt"):
        load_spec_text(text)


def test_in_memory_governed_doc_requires_file_context(tmp_path):
    spec_path = write_governed_fixture(tmp_path)
    doc = load_spec_text(spec_path.read_text())

    with pytest.raises(SpecCompileError, match="file path"):
        from detailgen.spec import compile_spec
        compile_spec(doc)


def test_gate_cli_resolves_detail_spec_binding(tmp_path, capsys):
    pending = write_governed_fixture(tmp_path / "pending")
    approved = write_governed_fixture(tmp_path / "approved", approved=True)

    assert design_review_main([
        "gate", str(pending), "--stage", "modeling",
    ]) == 2
    assert "modeling approval" in capsys.readouterr().err
    assert design_review_main([
        "gate", str(approved), "--stage", "modeling",
    ]) == 0
