"""Audits for declarative migrations away from per-product test suites."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / ".superpowers/sdd"
ROW = re.compile(r"^\| (\d+) \| `([^`]+)` \| \*\*([A-Z]+)\*\*")


def test_every_certification_equivalence_ledger_is_complete_and_replaces_80_percent():
    ledgers = sorted(REPORTS.glob("*-generic-certification-equivalence.md"))
    assert ledgers, "at least one certification migration ledger is required"

    for ledger in ledgers:
        text = ledger.read_text()
        baseline_match = re.search(r"- Baseline rows: (\d+)", text)
        retained_match = re.search(r"- Retained .* nodes: (\d+)", text)
        assert baseline_match and retained_match, ledger
        baseline = int(baseline_match.group(1))
        retained = int(retained_match.group(1))
        rows = [
            match.groups()
            for line in text.splitlines()
            if (match := ROW.match(line))
        ]
        assert [int(number) for number, _node, _kind in rows] == list(
            range(1, baseline + 1)
        )
        assert len({node for _number, node, _kind in rows}) == baseline
        assert {kind for _number, _node, kind in rows} <= {
            "RULE", "CONTRACT", "SHARED", "RETAIN", "POLICY",
        }
        assert sum(kind == "RETAIN" for _number, _node, kind in rows) == retained
        assert (baseline - retained) / baseline >= 0.80
