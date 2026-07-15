from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.certification import (
    ContractError,
    discover_contracts,
    load_contract,
)


def _minimal_contract(
    directory: Path,
    *,
    slug: str = "toy",
    source: str | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source_name = source or f"{slug}.spec.yaml"
    if not source_name.startswith(".."):
        (directory / source_name).write_text("name: toy\n")
    path = directory / f"{slug}.cert.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "subject": {
                    "kind": "standalone_detail",
                    "source": source_name,
                },
                "intent": {},
                "deliverables": [],
                "decisions": [],
            },
            sort_keys=False,
        )
    )
    return path


def test_loads_minimal_closed_contract(tmp_path):
    path = _minimal_contract(tmp_path)

    contract = load_contract(path, repo_root=tmp_path)

    assert contract.slug == "toy"
    assert contract.subject.kind == "standalone_detail"
    assert contract.subject.source == (tmp_path / "toy.spec.yaml").resolve()
    assert contract.source_path == path.resolve()
    assert contract.intent.counts == ()
    assert contract.deliverables == ()


@pytest.mark.parametrize("unknown", ["mystery", "python", "expression"])
def test_unknown_top_level_key_fails_closed(tmp_path, unknown):
    path = _minimal_contract(tmp_path)
    raw = yaml.safe_load(path.read_text())
    raw[unknown] = "ignored if loader is lax"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))

    with pytest.raises(ContractError, match=rf"unknown field.*{unknown}"):
        load_contract(path, repo_root=tmp_path)


def test_missing_required_field_fails_with_yaml_path(tmp_path):
    path = _minimal_contract(tmp_path)
    raw = yaml.safe_load(path.read_text())
    del raw["subject"]["kind"]
    path.write_text(yaml.safe_dump(raw, sort_keys=False))

    with pytest.raises(ContractError, match=r"subject.*missing field.*kind"):
        load_contract(path, repo_root=tmp_path)


def test_source_cannot_escape_repository_root(tmp_path):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside.spec.yaml"
    outside.write_text("name: outside\n")
    path = _minimal_contract(repo, source="../outside.spec.yaml")

    with pytest.raises(ContractError, match="escapes repository root"):
        load_contract(path, repo_root=repo)


def test_discovery_rejects_duplicate_slug(tmp_path):
    _minimal_contract(tmp_path / "a", slug="toy")
    _minimal_contract(tmp_path / "b", slug="toy")

    with pytest.raises(ContractError, match="duplicate certification slug 'toy'"):
        discover_contracts(tmp_path, repo_root=tmp_path)


def test_invalid_slug_fails_closed(tmp_path):
    path = _minimal_contract(tmp_path, slug="Bad-Slug")

    with pytest.raises(ContractError, match="invalid certification slug"):
        load_contract(path, repo_root=tmp_path)


def test_typed_intent_and_decision_are_loaded(tmp_path):
    path = _minimal_contract(tmp_path)
    raw = yaml.safe_load(path.read_text())
    raw["intent"] = {
        "counts": [
            {
                "selector": {"component": "HardwoodPanel"},
                "exactly": 3,
            }
        ],
        "forbidden": [{"selector": {"name_contains": "screw"}}],
        "connections": [
            {"selector": {"kind": "bonded_to"}, "exactly": 2}
        ],
        "validation": [
            {
                "selector": {
                    "check": "bearing",
                    "verdict": "PASS",
                    "subject_contains": "sofa arm",
                },
                "exactly": 1,
            }
        ],
        "fabrication": [
            {
                "selector": {"name": "top panel"},
                "steps": ["crosscut", "bore"],
            }
        ],
        "bom": [
            {
                "item": "3/4 in hardwood panel",
                "quantity": 3,
                "length_mm": {"minimum": 190.0, "maximum": 205.0},
            }
        ],
        "governance": {
            "selected_concept": "reinforced_miter",
            "modeling_ready": True,
            "delivery_ready": True,
        },
    }
    raw["decisions"] = [
        {
            "rule": "capacity.known",
            "outcome": "unknown_allowed",
            "rationale": "non-occupied accessory",
            "evidence_fingerprint": "abc123",
        }
    ]
    path.write_text(yaml.safe_dump(raw, sort_keys=False))

    contract = load_contract(path, repo_root=tmp_path)

    assert contract.intent.counts[0].selector.component == "HardwoodPanel"
    assert contract.intent.counts[0].exactly == 3
    assert contract.intent.validation[0].selector.check == "bearing"
    assert contract.intent.validation[0].selector.subject_contains == "sofa arm"
    assert contract.intent.fabrication[0].steps == ("crosscut", "bore")
    assert contract.intent.bom[0].length_mm.minimum == 190.0
    assert contract.intent.governance.delivery_ready is True
    assert contract.decisions[0].rule_id == "capacity.known"


def test_unknown_selector_field_fails_closed(tmp_path):
    path = _minimal_contract(tmp_path)
    raw = yaml.safe_load(path.read_text())
    raw["intent"] = {
        "counts": [
            {"selector": {"regex": ".*"}, "exactly": 1},
        ]
    }
    path.write_text(yaml.safe_dump(raw, sort_keys=False))

    with pytest.raises(ContractError, match=r"selector.*unknown field.*regex"):
        load_contract(path, repo_root=tmp_path)
