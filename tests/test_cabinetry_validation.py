"""Evidence-aware cabinet validation and draft/release honesty."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.packs import load_project_file, load_project_text
from detailgen.packs.cabinetry import FramelessCabinetryPack

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "cabinetry"
    / "frameless_base_cabinet.project.yaml"
)


def _model(path=FIXTURE):
    from detailgen.packs.cabinetry.model import build_model

    doc = load_project_file(path)
    return build_model(FramelessCabinetryPack().parse(doc), project_name=doc.name)


def _mutated_model(mutator):
    from detailgen.packs.cabinetry.model import build_model

    raw = yaml.safe_load(FIXTURE.read_text())
    mutator(raw)
    doc = load_project_text(yaml.safe_dump(raw, sort_keys=False))
    return build_model(FramelessCabinetryPack().parse(doc), project_name=doc.name)


def test_release_fixture_passes_required_checks_without_claiming_certification():
    from detailgen.packs.cabinetry.validation import validate_model

    report = validate_model(_model())

    assert report.mode == "release"
    assert report.release_ready
    assert report.blocking == ()
    assert "certified" not in report.summary.lower()
    assert report.by_rule("cabinetry.shelf.deflection").verdict == "PASS"
    assert report.by_rule("cabinetry.hardware.hinge_fit").verdict == "PASS"
    assert report.by_rule("cabinetry.material.design_properties").verdict == "PASS"
    assert report.by_rule("cabinetry.install.studs").verdict == "PASS"

    hinge_quantity = report.by_rule("cabinetry.hardware.hinge_quantity")
    assert hinge_quantity.verdict == "PASS"
    assert "600 mm" in hinge_quantity.message
    assert "1000 mm" in hinge_quantity.message
    assert "6 kg" in hinge_quantity.message


def test_physical_kcma_tests_remain_explicitly_unperformed_and_nonblocking():
    from detailgen.packs.cabinetry.validation import validate_model

    report = validate_model(_model())
    finding = report.by_rule("cabinetry.performance.physical_tests")

    assert finding.verdict == "UNKNOWN"
    assert finding.severity == "advisory"
    assert not finding.blocking
    assert "not performed" in finding.message.lower()
    evidence = report.evidence_by_id(finding.evidence_ids[0])
    assert evidence.level == "unknown"
    assert evidence.standard_ref == "ANSI/KCMA A161.1-2022"


def test_unverified_stud_is_required_unknown_and_blocks_release():
    from detailgen.packs.cabinetry.validation import validate_model

    model = _mutated_model(
        lambda raw: raw["site"]["wall"]["studs"][0].update(verified=False)
    )
    report = validate_model(model)
    finding = report.by_rule("cabinetry.install.studs")

    assert finding.verdict == "UNKNOWN"
    assert finding.blocking
    assert not report.release_ready
    assert "stud_32" in finding.message


def test_missing_tsca_record_is_required_unknown_not_a_silent_material_pass():
    from detailgen.packs.cabinetry.validation import validate_model

    model = _mutated_model(
        lambda raw: raw["cabinetry"]["material_evidence"].update(
            tsca_title_vi="required", reference="verify at procurement"
        )
    )
    report = validate_model(model)
    finding = report.by_rule("cabinetry.material.tsca_title_vi")

    assert finding.verdict == "UNKNOWN"
    assert finding.blocking
    assert finding.evidence_level == "unknown"


def test_wide_cabinet_fails_shelf_deflection_and_two_hinge_limits():
    from detailgen.packs.cabinetry.validation import validate_model

    model = _mutated_model(
        lambda raw: raw["cabinetry"]["cabinets"][0].update(width=60)
    )
    report = validate_model(model)

    assert report.by_rule("cabinetry.shelf.deflection").verdict == "FAIL"
    assert report.by_rule("cabinetry.hardware.hinge_quantity").verdict == "FAIL"
    assert not report.release_ready


def test_site_environment_and_acclimation_are_release_gates():
    from detailgen.packs.cabinetry.validation import validate_model

    model = _mutated_model(
        lambda raw: raw["site"]["environment"].update(
            hvac_operating=False, acclimation_hours=24
        )
    )
    report = validate_model(model)
    finding = report.by_rule("cabinetry.install.site_readiness")

    assert finding.verdict == "FAIL"
    assert finding.blocking
    assert "HVAC" in finding.message
    assert "72" in finding.message


def test_anchor_geometry_uses_real_cabinet_screw_and_checks_stud_embedment():
    from detailgen.packs.cabinetry.catalogs import get_wall_anchor_product
    from detailgen.packs.cabinetry.validation import validate_model

    product = get_wall_anchor_product("grk_low_profile_cabinet_8x3_1_8@2026.1")
    report = validate_model(_model())

    assert product.manufacturer == "GRK Fasteners"
    assert product.sku == "110083"
    assert product.length_mm == pytest.approx(3.125 * 25.4)
    assert product.source_url.startswith("https://www.grkfasteners.com/")
    assert report.by_rule("cabinetry.install.anchor_embedment").verdict == "PASS"


def test_report_order_and_summary_are_deterministic():
    from detailgen.packs.cabinetry.validation import validate_model

    a = validate_model(_model())
    b = validate_model(_model())

    assert a == b
    assert a.summary == b.summary
    assert [finding.rule for finding in a.findings] == sorted(
        finding.rule for finding in a.findings
    )
