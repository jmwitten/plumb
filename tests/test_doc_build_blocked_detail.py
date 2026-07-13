"""The build-doc pipeline renders an honestly-BLOCKED detail (FAB-3 fix round).

FAB-3 (retire R29) makes the platform block on three foundation-capacity UNKNOWNs.
The real build-doc path — ``scripts/consolidated_report.py`` ``main() ->
process_detail() -> Detail.render()`` — hard-gated on ``require_clean()`` and so
CRASHED the moment the platform went blocked. The review caught this because the
doc GOLDEN test exercises ``build_html`` DIRECTLY, bypassing the gated render.

This test closes that blind spot: it drives the REAL ``process_detail`` path on the
blocked platform and proves (a) it builds without crashing (now via the ungated
``render_documentation``) and (b) the rendered documentation SURFACES the honest
verdict — "Structural capacity: UNKNOWN — UNRESOLVED" — rather than refusing to
render or hiding the block. The certified export gate (``Detail.render`` ->
``require_clean``) is unchanged and still exclusive to ``outputs/``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cr():
    return _load("consolidated_report_docbuild",
                 REPO_ROOT / "scripts" / "consolidated_report.py")


def test_process_detail_renders_blocked_platform_without_gating(cr, tmp_path, monkeypatch):
    # Renders land in a throwaway dir (never the repo's committed renders), and a
    # fresh dir forces a real render — the hash-reuse path would otherwise skip it.
    monkeypatch.setattr(cr, "RENDERS", tmp_path / "renders")

    d = cr.load_details()["platform"]
    report = d.validate()
    # Precondition: the platform is honestly BLOCKED by FAB-3's capacity UNKNOWNs
    # (no FAIL) — the exact state that used to crash the gated render.
    assert not report.ok
    assert [f.check for f in report.failures] == []
    # capacity UNKNOWNs (FAB-3); the INSTALL toe-screw UNKNOWNs were
    # resolved on merit by task CPGCORE's authored sequence.
    assert {f.check for f in report.blocking} == {"foundation_capacity"}

    # THE fix: the real doc-build entry point renders the blocked detail instead
    # of dying at require_clean. (Pre-fix this raised AssertionError from the gate.)
    manifest, images, reused = cr.process_detail("platform", d)
    assert reused is False                       # a real render happened, not a cache hit
    assert len(manifest["parts"]) == 148         # the geometry (incl. 3 post bases) was drawn
    assert images                                # panel PNGs were produced

    # ...and the documentation SURFACES the honest verdict, loud — the coverage
    # matrix render_documentation wrote carries the blocking UNRESOLVED capacity row.
    outd = cr.RENDERS / "platform"
    cov = outd / "validation_report.md"
    if not cov.exists():
        cov = outd / "coverage_matrix.md"
    text = cov.read_text(encoding="utf-8")
    assert "Structural capacity" in text
    assert "UNKNOWN — UNRESOLVED" in text


def test_render_documentation_is_ungated_but_render_still_gates(cr, tmp_path):
    # The gate distinction is exactly one method: render_documentation draws the
    # blocked detail; render() still refuses it. Same detail, opposite verbs.
    from detailgen.details.base import Detail  # noqa: F401  (type anchor)

    d = cr.load_details()["platform"]
    d.validate()
    doc_out = d.render_documentation(tmp_path / "doc")   # does NOT raise
    assert (doc_out / "validation_report.md").exists() or \
        (doc_out / "coverage_matrix.md").exists()
    with pytest.raises(AssertionError):
        d.render(tmp_path / "certified")                 # gated: still refuses the blocked model
