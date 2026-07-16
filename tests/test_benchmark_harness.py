"""Fast smoke tests for scripts/benchmark.py.

Deliberately does NOT run the full benchmark against a real zipline detail
(rock_anchor alone is 15-90s) — it loads benchmark.py's functions and drives
them against a tiny 2-part stub Detail, which is enough to prove the harness
actually instruments the pipeline and emits schema-valid data. The slow,
full-fidelity run against the four real details is a manual/CI-optional
invocation of the script itself, not a pytest test.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_benchmark_module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_under_test", ROOT / "scripts" / "benchmark.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bench = _load_benchmark_module()


def test_family_birdhouse_is_a_normal_compiled_detail_benchmark_target():
    assert bench.DETAIL_SPECS["family_birdhouse"] == (
        "family_birdhouse.spec.yaml"
    )

    detail_module, factory = bench.load_detail("family_birdhouse")
    detail = factory()

    assert detail_module is None
    assert detail.name == "family birdhouse"


def _stub_detail_cls():
    """A minimal 2-part Detail — cheap enough to build/validate/render in a
    fraction of a second, so this test stays fast.

    The two parts sit 0.05mm apart (under Tolerances.bbox_prefilter_gap,
    0.15mm) rather than the 1.5in gap an earlier version used: the pairwise
    sweep's bbox prefilter (checks.py) would otherwise skip this pair's
    boolean check entirely as trivially disjoint, so ``validate:interference``
    would never fire and this test's instrumentation assertions below would
    fail — not because instrumentation broke, but because there'd be nothing
    for it to time. Staying inside the prefilter's margin forces the real
    check to run while the parts remain genuinely non-overlapping (validation
    stays clean)."""
    from detailgen.components import Lumber
    from detailgen.core import IN
    from detailgen.details import Detail

    class StubDetail(Detail):
        name = "bench_stub"

        @dataclass(frozen=True)
        class Params:
            length: float = 6 * IN

        def assemble(self, d):
            d.add(Lumber("2x4", length=self.params.length, name="a"))
            d.add(Lumber("2x4", length=self.params.length, name="b"),
                  at=(0.0, 1.5 * IN + 0.05, 0.0))

    return StubDetail


def test_run_detail_once_emits_schema_valid_record(tmp_path):
    record = bench.run_detail_once("bench_stub", _stub_detail_cls(), tmp_path / "out")

    assert record["validation_ok"] is True
    assert record["n_parts"] == 2
    assert record["pairwise_sweep_pairs"] == 1

    phases = record["phases"]
    assert isinstance(phases, dict) and phases
    for name, data in phases.items():
        assert isinstance(name, str)
        assert set(data) == {"seconds", "count"}
        assert isinstance(data["seconds"], float) and data["seconds"] >= 0.0
        assert isinstance(data["count"], int) and data["count"] >= 1

    # The pipeline was actually instrumented, not just called untouched:
    # both a component build and a validation check-type phase must appear.
    assert any(k.startswith("build:") for k in phases)
    assert "validate:interference" in phases
    assert "assemble" in phases
    assert "validate" in phases
    assert "render" in phases

    assert isinstance(record["wall_total_s"], float) and record["wall_total_s"] > 0.0

    dedup = record["dedup_estimate"]
    assert set(dedup) == {
        "distinct_param_groups", "total_components",
        "redundant_instances_by_type", "estimated_savings_s",
    }
    assert dedup["total_components"] == 2

    bbox = record["bbox_prefilter_estimate"]
    assert set(bbox) == {"pairs", "bbox_non_overlapping_pairs", "skippable_fraction"}
    assert bbox["pairs"] == 1


def test_run_detail_once_uses_ungated_documentation_surface(monkeypatch, tmp_path):
    detail_cls = _stub_detail_cls()
    monkeypatch.setattr(
        detail_cls,
        "render",
        lambda *_args, **_kwargs: pytest.fail(
            "benchmark attempted a certified delivery render"
        ),
    )

    record = bench.run_detail_once(
        "bench_stub", detail_cls, tmp_path / "documentation"
    )

    assert record["validation_ok"] is True


def test_run_package_once_reports_public_builder_timings(monkeypatch, tmp_path):
    import detailgen.package.builder as builder_module

    seen = {}

    class _Result:
        artifacts = (object(), object())

        def manifest(self):
            return {"timings_seconds": {"compile_validate": 0.25, "documents": 0.5}}

    def fake_build(request):
        seen["request"] = request
        return _Result()

    monkeypatch.setattr(builder_module, "build_package", fake_build)

    record = bench.run_package_once(
        tmp_path / "generic.spec.yaml",
        tmp_path / "package",
    )

    assert seen["request"].views == ("iso",)
    assert record == {
        "timings_seconds": {"compile_validate": 0.25, "documents": 0.5},
        "total_s": 0.75,
        "artifact_count": 2,
    }


def test_instrumentation_restores_originals_after_use():
    from detailgen.core import base as base_mod
    from detailgen.core.timing import PhaseTimer
    from detailgen.validation import checks as checks_mod

    original_solid = base_mod.Component.solid
    original_check = checks_mod.check_interference
    original_dimension = checks_mod.check_dimension

    timer = PhaseTimer()
    with bench._instrument(timer):
        assert base_mod.Component.solid is not original_solid
        assert checks_mod.check_interference is not original_check
        assert checks_mod.check_dimension is not original_dimension

    assert base_mod.Component.solid is original_solid
    assert checks_mod.check_interference is original_check
    assert checks_mod.check_dimension is original_dimension


def _write_real_style_detail_module(tmp_path) -> Path:
    """A detail file written to disk (not just a class defined inline in
    this test file) that reproduces EXACTLY the pattern every real detail
    uses: a module-top ``from detailgen.validation import check_dimension``,
    called directly from ``extra_checks()`` rather than through
    ``validate_assembly``'s kwargs. This is the pattern that silently
    defeated a naive ``wrap_fn(checks_mod, "check_dimension", ...)`` — that
    module-level name is bound once, at this file's own import time, to
    whatever ``check_dimension`` was *then*; patching ``checks_mod`` later
    (as ``_instrument`` does for every OTHER check type, which are all
    called from inside ``validate_assembly`` in the SAME module and so see
    the patch fine) has no effect on this already-bound reference unless
    ``_instrument`` is also told to patch this module directly."""
    src = '''
from dataclasses import dataclass

from detailgen.components import Lumber
from detailgen.core import IN
from detailgen.details import Detail
from detailgen.validation import check_dimension


class RealStyleStubDetail(Detail):
    name = "bench_real_style_stub"

    @dataclass(frozen=True)
    class Params:
        length: float = 6 * IN

    def assemble(self, d):
        d.add(Lumber("2x4", length=self.params.length, name="a"))
        d.add(Lumber("2x4", length=self.params.length, name="b"),
              at=(0.0, 3 * IN, 0.0))

    def extra_checks(self):
        a = self["a"].world_solid().val().BoundingBox()
        return [check_dimension("a length", actual=a.xlen, expected=self.params.length)]
'''
    path = tmp_path / "real_style_stub_detail.py"
    path.write_text(src)
    return path


def test_direct_module_top_check_dimension_import_is_captured(tmp_path):
    """Regression test for the bug this test was added to catch: a detail
    that imports check_dimension by value (every real detail does) must
    still show up under validate:dimension, not silently vanish into the
    bare "validate" bucket."""
    path = _write_real_style_detail_module(tmp_path)
    # Load the synthetic module-style detail directly. benchmark.py no longer
    # ships a detail-module loader (its own four details are compiled from spec
    # now), but run_detail_once/_instrument still SUPPORT a module-style detail
    # via ``detail_module`` — the capability this regression test exercises.
    spec = importlib.util.spec_from_file_location("real_style_stub_for_test", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    detail_cls = mod.RealStyleStubDetail

    record = bench.run_detail_once(
        "bench_real_style_stub", detail_cls, tmp_path / "out", detail_module=mod
    )

    assert "validate:dimension" in record["phases"]
    assert record["phases"]["validate:dimension"]["count"] == 1


def test_median_phases_aggregates_across_runs():
    fake_runs = [
        {"phases": {"assemble": {"seconds": 1.0, "count": 1},
                    "validate": {"seconds": 2.0, "count": 1}}},
        {"phases": {"assemble": {"seconds": 3.0, "count": 1},
                    "validate": {"seconds": 4.0, "count": 1}}},
    ]
    med = bench._median_phases(fake_runs)
    assert med["assemble"]["seconds"] == 2.0
    assert med["validate"]["seconds"] == 3.0


def test_cli_help_is_fast_and_does_not_require_cadquery_at_module_scope():
    """--help must exit via argparse before `import cadquery` in main() runs,
    so it stays cheap even on a machine where the geometry stack is slow to
    import — this is also the harness's `--help` acceptance check."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "benchmark.py"), "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0
    assert "--details" in proc.stdout
    assert "--runs" in proc.stdout


def test_unknown_detail_name_is_a_clean_cli_error():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "benchmark.py"),
         "--details", "not_a_real_detail", "--no-doc"],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode != 0
    assert "not_a_real_detail" in proc.stderr
