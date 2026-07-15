"""One generic certification node for every declarative build contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.certification import discover_contracts, load_contract
from detailgen.certification.engine import certify_contract


ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"
CORE_CONTRACTS = (
    "compile",
    "geometry",
    "validation",
    "connections",
    "fabrication",
    "bom",
    "governance",
    "intent",
    "determinism",
)


def certification_params(details_dir: Path = DETAILS, repo_root: Path = ROOT):
    return [
        pytest.param(
            contract.source_path,
            id=contract.slug,
            marks=pytest.mark.detail_gate(
                contract.slug,
                contracts=CORE_CONTRACTS,
            ),
        )
        for contract in discover_contracts(details_dir, repo_root=repo_root)
    ]


@pytest.mark.parametrize("contract_path", certification_params())
def test_certified_build(contract_path):
    contract = load_contract(contract_path, repo_root=ROOT)
    result = certify_contract(contract)
    details = "\n".join(
        f"[{row.state.value}] {row.rule_id}: {row.detail}"
        for row in result.findings
    )
    assert result.releasable, details


def test_unrelated_contract_becomes_a_parameter_without_registry_edit(tmp_path):
    details = tmp_path / "details"
    details.mkdir()
    (details / "garden_shelf.spec.yaml").write_text("name: garden shelf\n")
    (details / "garden_shelf.cert.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "subject": {
                    "kind": "standalone_detail",
                    "source": "garden_shelf.spec.yaml",
                },
                "intent": {},
                "deliverables": [],
                "decisions": [],
            },
            sort_keys=False,
        )
    )

    params = certification_params(details, repo_root=tmp_path)

    assert [param.id for param in params] == ["garden_shelf"]
    marks = [mark for mark in params[0].marks if mark.name == "detail_gate"]
    assert marks[0].args == ("garden_shelf",)
    assert marks[0].kwargs["contracts"] == CORE_CONTRACTS
