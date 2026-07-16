"""Pure self-tests for baseline comparison and annotation merging."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import regen_baselines as regen  # noqa: E402


def _write_json(directory: Path, name: str, data: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        json.dumps(data, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def test_tampered_plain_baseline_is_named_without_regeneration(tmp_path):
    committed = tmp_path / "committed"
    generated = tmp_path / "generated"
    _write_json(committed, "detail_counts.json", {"count": 4})
    _write_json(generated, "detail_counts.json", {"count": 5})

    assert regen.stale_baseline_names(generated, committed) == (
        "detail_counts.json",
    )


def test_missing_and_extra_baselines_are_both_named(tmp_path):
    committed = tmp_path / "committed"
    generated = tmp_path / "generated"
    _write_json(committed, "missing.json", {"value": 1})
    _write_json(generated, "extra.json", {"value": 1})

    assert regen.stale_baseline_names(generated, committed) == (
        "extra.json",
        "missing.json",
    )


def test_annotated_merge_preserves_notes_and_flags_new_and_removed(tmp_path):
    _write_json(
        tmp_path,
        "site_divergence.json",
        {
            "findings": [
                {"check": "old", "subject": "gone", "note": "retired note"},
                {"check": "keep", "subject": "same", "note": "real reason"},
            ]
        },
    )

    data, new, removed = regen.merge_site_divergence(
        [
            {"check": "keep", "subject": "same"},
            {"check": "new", "subject": "appeared"},
        ],
        tmp_path,
    )

    assert data["findings"][0]["note"] == "real reason"
    assert data["findings"][1]["note"] == regen.TODO_NOTE
    assert new == [("new", "appeared")]
    assert removed == [("old", "gone")]


def test_pure_annotated_merge_never_loads_live_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        regen.bl,
        "site_divergence_pairs",
        lambda: pytest.fail("pure merge must not compile or validate a model"),
    )

    data, new, removed = regen.merge_site_divergence([], tmp_path)

    assert data["findings"] == []
    assert new == []
    assert removed == []


@pytest.mark.parametrize(("generated_value", "expected"), ((1, 0), (2, 1)))
def test_check_mode_compares_tiny_generated_files_without_cad(
    tmp_path, monkeypatch, generated_value, expected
):
    committed = tmp_path / "committed"
    _write_json(committed, "probe.json", {"value": 1})
    monkeypatch.setattr(regen.bl, "BASELINE_DIR", committed)

    def fake_regenerate(target_dir, source_dir):
        _write_json(target_dir, "probe.json", {"value": generated_value})
        return {"new": [], "removed": []}

    monkeypatch.setattr(regen, "regenerate", fake_regenerate)

    assert regen.main(["--check"]) == expected
