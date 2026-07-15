from __future__ import annotations

from pathlib import Path

from detailgen.certification import load_contract
from detailgen.certification.adapters import StandaloneSpecAdapter


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/certification"


def _contract():
    return load_contract(
        FIXTURES / "toy_panel.cert.yaml",
        repo_root=ROOT,
    )


def test_standalone_adapter_collects_authoritative_evidence():
    snapshot = StandaloneSpecAdapter().collect(_contract())

    assert snapshot.slug == "toy_panel"
    assert snapshot.compile_error == ""
    assert snapshot.validation.ok
    assert snapshot.validation.blocking == ()
    assert len(snapshot.parts) == 1
    part = snapshot.parts[0]
    assert part.id == "lumber-0"
    assert part.name == "shelf board"
    assert part.component == "Lumber"
    assert part.material
    assert part.solid_count == 1
    assert part.volume_mm3 > 0
    assert len(part.bounds_mm) == 6
    assert snapshot.bom[0].source_ids == (part.id,)
    assert snapshot.bom[0].quantity == 1


def test_adapter_collects_fabrication_steps_for_made_parts():
    snapshot = StandaloneSpecAdapter().collect(_contract())

    assert snapshot.fabrication_error == ""
    assert len(snapshot.fabrication) == 1
    assert snapshot.fabrication[0].part_id == "lumber-0"
    assert snapshot.fabrication[0].steps == ("crosscut",)


def test_adapter_calls_authoritative_fabrication_verifier(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "detailgen.certification.adapters.verify_assembly_fabrication",
        lambda assembly: calls.append(assembly.name),
    )

    StandaloneSpecAdapter().collect(_contract())

    assert calls == ["toy panel"]


def test_compile_exception_becomes_structured_failure(monkeypatch):
    def fail(_path):
        raise ValueError("bad spec")

    monkeypatch.setattr(
        "detailgen.certification.adapters.compile_spec_file",
        fail,
    )

    snapshot = StandaloneSpecAdapter().collect(_contract())

    assert snapshot.compile_error == "ValueError: bad spec"
    assert snapshot.parts == ()
    assert snapshot.connections == ()
    assert snapshot.bom == ()


def test_fabrication_exception_is_not_misreported_as_compile_failure(monkeypatch):
    monkeypatch.setattr(
        "detailgen.certification.adapters.verify_assembly_fabrication",
        lambda _assembly: (_ for _ in ()).throw(ValueError("fold drift")),
    )

    snapshot = StandaloneSpecAdapter().collect(_contract())

    assert snapshot.compile_error == ""
    assert snapshot.fabrication_error == "ValueError: fold drift"
    assert snapshot.parts


def test_governance_evidence_is_absent_for_ungoverned_subject():
    governance = StandaloneSpecAdapter().collect(_contract()).governance

    assert governance.present is False
    assert governance.selected_concept == ""
    assert governance.modeling_ready is False
    assert governance.delivery_ready is False
