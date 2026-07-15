"""Audits for declarative migrations away from per-product test suites."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / ".superpowers/sdd"
ROW = re.compile(r"^\| (\d+) \| `([^`]+)` \| \*\*([A-Z]+)\*\*")


def _defined_tests() -> dict[str, list[Path]]:
    definitions: dict[str, list[Path]] = {}
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    definitions.setdefault(node.name, []).append(path)
    return definitions


def test_every_certification_equivalence_ledger_is_complete_and_replaces_80_percent():
    ledgers = sorted(REPORTS.glob("*-generic-certification-equivalence.md"))
    assert ledgers, "at least one certification migration ledger is required"
    defined_tests = _defined_tests()

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
        for _number, node_id, kind in rows:
            original_path, _separator, original_test = node_id.partition("::")
            test_name = original_test.split("[", 1)[0]
            locations = defined_tests.get(test_name, [])
            if kind == "RETAIN":
                assert locations, f"{ledger}: retained test is missing: {test_name}"
            else:
                original = (ROOT / original_path).resolve()
                assert original not in (path.resolve() for path in locations), (
                    f"{ledger}: replaced baseline node still exists: {node_id}"
                )
