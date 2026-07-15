from __future__ import annotations

import json
from pathlib import Path

import pytest

from detailgen.certification import (
    CertificationFinding,
    CertificationResult,
    FindingState,
)
from detailgen.certification import __main__ as cli


ROOT = Path(__file__).resolve().parents[1]
TOY = ROOT / "tests/fixtures/certification/toy_panel.cert.yaml"


def _result(state: FindingState) -> CertificationResult:
    return CertificationResult(
        slug="toy",
        findings=(
            CertificationFinding(
                rule_id="toy.rule",
                state=state,
                subject="toy",
                detail="evidence result",
                evidence_fingerprint="abc" if state is FindingState.NEEDS_DECISION else "",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("state", "exit_code"),
    [
        (FindingState.PASS, 0),
        (FindingState.WARN, 0),
        (FindingState.FAIL, 1),
        (FindingState.NEEDS_DECISION, 2),
    ],
)
def test_cli_exit_codes(monkeypatch, capsys, state, exit_code):
    monkeypatch.setattr(cli, "_load_and_certify", lambda _path: _result(state))

    assert cli.main(["details/toy.cert.yaml", "--json"]) == exit_code

    payload = json.loads(capsys.readouterr().out)
    assert payload["slug"] == "toy"
    assert payload["findings"][0]["state"] == state.value


def test_cli_usage_error_is_exit_four(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "_load_and_certify",
        lambda _path: (_ for _ in ()).throw(cli.ContractError("bad contract")),
    )

    assert cli.main(["bad.cert.yaml"]) == 4

    assert capsys.readouterr().err == "ERROR: bad contract\n"


def test_real_toy_contract_certifies_as_json(capsys):
    assert cli.main([str(TOY), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["slug"] == "toy_panel"
    assert payload["releasable"] is True
    assert len(payload["findings"]) == 9
    assert {row["state"] for row in payload["findings"]} == {"PASS"}


def test_human_output_names_every_rule(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "_load_and_certify",
        lambda _path: _result(FindingState.PASS),
    )

    assert cli.main(["toy.cert.yaml"]) == 0

    assert capsys.readouterr().out == (
        "[PASS] toy.rule: toy — evidence result\n"
        "Certification: RELEASABLE\n"
    )

