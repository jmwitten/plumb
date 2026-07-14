from pathlib import Path
import sys

import pytest
import yaml

from detailgen.core.buildinfo import build_manifest
from detailgen.design_review import (
    DesignReviewGateError,
    load_design_review_file,
    validate_design_review,
)
from detailgen.spec import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import caddy_documents as CD


SPEC = ROOT / "details/armchair_caddy.spec.yaml"
REVIEW = ROOT / "details/armchair_caddy.design-review.yaml"
REPORT = ROOT / "outputs/design-reviews/armchair_caddy.html"


def test_caddy_review_is_complete_and_compares_four_required_architectures():
    doc = load_design_review_file(REVIEW)

    assert validate_design_review(doc).ok
    assert {concept.id for concept in doc.concepts} == {
        "current_double_wall",
        "reinforced_miter",
        "rabbet_and_dowel",
        "concealed_pocket_screw_or_bracket",
    }
    assert len(doc.comparison) == 40
    assert {source.kind for source in doc.precedents} == {
        "commercial_product",
        "build_instruction",
    }


def test_caddy_recommendation_is_reinforced_miter_but_not_implemented():
    doc = load_design_review_file(REVIEW)

    assert doc.decision.selected_concept == "reinforced_miter"
    assert doc.decision.application == "recommendation_only"
    assert doc.modeling_approval is None
    assert doc.delivery_confirmation is None


def test_caddy_spec_opts_in_and_delivery_is_blocked():
    detail = compile_spec_file(SPEC)

    assert detail.design_governance is not None
    assert detail.design_governance.selected_concept == "reinforced_miter"
    with pytest.raises(DesignReviewGateError, match="modeling approval"):
        detail.require_delivery_ready()


def test_customer_document_pair_writes_nothing_while_review_is_pending(tmp_path):
    out = tmp_path / "customer-delivery"

    with pytest.raises(DesignReviewGateError, match="modeling approval"):
        CD.build_caddy_document_pair(out, image_size=(320, 240))

    assert not out.exists()


def test_governance_binding_does_not_change_caddy_geometry(tmp_path):
    governed = compile_spec_file(SPEC)
    raw = yaml.safe_load(SPEC.read_text())
    raw.pop("design_review")
    legacy_spec = tmp_path / SPEC.name
    legacy_spec.write_text(yaml.safe_dump(raw, sort_keys=False))
    ungoverned = compile_spec_file(legacy_spec)

    assert build_manifest(governed.assembly)["assembly_hash"] == build_manifest(
        ungoverned.assembly
    )["assembly_hash"]


def test_generated_caddy_report_is_developer_facing_and_retains_provenance():
    html = REPORT.read_text()

    assert "Production promotion: BLOCKED" in html
    assert "Delivery: BLOCKED" in html
    assert "reinforced_miter" in html
    assert "current_double_wall" in html
    assert "https://learn.kregtool.com/plans/sofa-arm-table/" in html
    assert "https://www.woodworkersjournal.com/project-sofa-armrest-table/" in html
