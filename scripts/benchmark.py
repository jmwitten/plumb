#!/usr/bin/env python3
"""Timing harness for directive #8 (generation-speed, TARGET: 4x faster).

    .venv/bin/python scripts/benchmark.py --help
    .venv/bin/python scripts/benchmark.py                      # full run -> outputs/bench/
    .venv/bin/python scripts/benchmark.py --details rock_anchor --runs 2 --no-doc

Measures, for each of the four shipped details (rock_anchor, tree_attachment,
trolley_launch, platform):

  - fresh-subprocess import cost (cadquery vs. detailgen+detail, decomposed)
  - fresh-subprocess ``python -m detailgen.spec details/<name>.spec.yaml`` wall
    time (compile + validate, NO render — the metric the roadmap ledger flags as what an
    agent authoring loop actually pays per iteration)
  - in-process phase breakdown: assemble (placement graph) / validate (by
    check type) / component solid builds (by concrete type, with counts) /
    geometry hashing / render (by artifact format, incl. a PNG capture) —
    see ``_instrument`` for how this is wired without editing any pipeline
    module
  - a dedup estimate for lever (a): components sharing (type, params) that a
    solid cache would only need to build once
  - a bbox-prefilter estimate for lever (c): what fraction of the pairwise
    interference sweep's pairs are trivially non-overlapping by bounding box

...and, once per whole run, ``scripts/consolidated_report.py`` cold (fresh
scratch render cache) and warm (same cache, re-run immediately) — redirected
to a scratch directory (never the real ``outputs/consolidated`` or the vault
copy) so benchmarking never disturbs the project's real hash-gated cache or
overwrites the shipped vault document.

Methodology: every in-process phase number is SELF time from
``detailgen.core.timing.PhaseTimer`` (nested phases subtract out of their
parent), so a table of phase totals sums to the measured wall clock — see
that module's docstring. Instrumentation is applied by monkeypatching
class/module attributes for the duration of one measured detail and restored
immediately after (``_instrument``); nothing in ``src/`` is edited, so this
is zero overhead when the benchmark isn't running and cannot change any
pipeline behavior, output, or hash. Repeatability: every measurement below
runs >=2 times; both runs and the median are reported. This is a single
M-series Mac under normal desktop load, not a quiet CI box — treat single-run
outliers accordingly, and re-run before trusting a small (<15%) delta.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
import time
from contextlib import ExitStack
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS_DIR = ROOT / "details"
DEFAULT_OUT = ROOT / "outputs" / "bench"

#: name -> compiled spec filename. The imperative ``.py`` details this tool used
#: to benchmark were retired at milestone 4B-4b; each detail is now compiled from
#: its ``spec.yaml`` through the shared pipeline.
DETAIL_SPECS: dict[str, str] = {
    "rock_anchor": "rock_anchor.spec.yaml",
    "tree_attachment": "tree_attachment.spec.yaml",
    "trolley_launch": "trolley_launch.spec.yaml",
    "platform": "platform.spec.yaml",
    "family_birdhouse": "family_birdhouse.spec.yaml",
}


# --------------------------------------------------------------------------- #
# Detail loading (via the spec compiler — the only path since 4B-4b).
# --------------------------------------------------------------------------- #
def load_detail(name: str):
    """Return ``(detail_module, factory)`` for a detail. A compiled ``SpecDetail``
    has no per-detail module of its own — it routes every check through the shared
    ``detailgen.validation.checks`` module, which ``_instrument`` already patches —
    so ``detail_module`` is ``None``. The factory is a zero-arg callable that
    compiles a fresh instance, matching the old ``(module, class)`` call shape."""
    from detailgen.spec.compiler import compile_spec_file

    spec_file = DETAILS_DIR / DETAIL_SPECS[name]
    return None, lambda: compile_spec_file(spec_file)


def load_detail_class(name: str):
    """Convenience wrapper over :func:`load_detail` for callers that only need
    the zero-arg factory."""
    _mod, factory = load_detail(name)
    return factory


# --------------------------------------------------------------------------- #
# Instrumentation: monkeypatch a handful of pipeline entry points so their
# calls are timed through a PhaseTimer, for the duration of one measured
# detail run only. See module docstring + timing.py docstring for why this
# is zero-overhead / behavior-preserving.
# --------------------------------------------------------------------------- #
def _instrument(timer, detail_module=None) -> ExitStack:
    """``detail_module``, if given, is the already-loaded detail module for
    the run about to happen — see :func:`load_detail` for why it needs to be
    patched too, not just ``checks_mod``."""
    from detailgen.core import base as base_mod
    from detailgen.core import buildinfo as buildinfo_mod
    from detailgen.rendering import export as export_mod
    from detailgen.validation import checks as checks_mod

    stack = ExitStack()

    # -- component solid builds, grouped by concrete component type ---------
    orig_solid_prop = base_mod.Component.solid

    def solid_fget(self):
        if self._solid is None:
            with timer.phase(f"build:{type(self).__name__}"):
                self._solid = self._build()
        return self._solid

    stack.callback(setattr, base_mod.Component, "solid", orig_solid_prop)
    base_mod.Component.solid = property(solid_fget)

    # -- generic "wrap this module function in a phase" patcher -------------
    def wrap_fn(mod, fn_name: str, phase_name: str) -> None:
        original = getattr(mod, fn_name)

        def wrapper(*a, **kw):
            with timer.phase(phase_name):
                return original(*a, **kw)

        stack.callback(setattr, mod, fn_name, original)
        setattr(mod, fn_name, wrapper)

        # A detail file that did `from detailgen.validation import fn_name`
        # at its own module top (e.g. rock_anchor's `check_dimension`,
        # trolley_launch's `check_contact`) holds its OWN reference to the
        # pre-patch original, bound once when that module was first loaded
        # (before this function ever ran) — patching checks_mod alone would
        # never be seen by those call sites. Patch the matching name in the
        # detail module too, but only if it's still pointing at the exact
        # object we just replaced (never overwrite something the detail
        # module rebound to on purpose).
        if detail_module is not None and getattr(detail_module, fn_name, None) is original:
            stack.callback(setattr, detail_module, fn_name, original)
            setattr(detail_module, fn_name, wrapper)

    # -- validation, by check type -------------------------------------------
    wrap_fn(checks_mod, "check_interference", "validate:interference")
    wrap_fn(checks_mod, "check_contact", "validate:contact")
    wrap_fn(checks_mod, "check_bearing", "validate:bearing")
    wrap_fn(checks_mod, "check_through_hole", "validate:through_hole")
    wrap_fn(checks_mod, "check_no_floaters", "validate:floating")
    wrap_fn(checks_mod, "check_dimension", "validate:dimension")

    # -- geometry hashing / buildinfo -----------------------------------------
    wrap_fn(buildinfo_mod, "geometry_hash", "hash")

    # -- export, by artifact format -------------------------------------------
    wrap_fn(export_mod, "export_step", "render:step")
    wrap_fn(export_mod, "export_stl", "render:stl")
    wrap_fn(export_mod, "export_glb", "render:glb")
    wrap_fn(export_mod, "export_manifest", "render:manifest")
    wrap_fn(export_mod, "export_png", "render:png")

    return stack


# --------------------------------------------------------------------------- #
# One in-process measured pass over a single detail.
# --------------------------------------------------------------------------- #
def run_detail_once(name: str, detail_cls, out_dir: Path, detail_module=None) -> dict:
    """Fresh detail instance -> assemble -> validate -> documentation render -> a PNG
    capture (PNG isn't part of these details' Detail.render(), so it's timed
    as its own extra step to satisfy the "PNG/VTK measured too" requirement).
    ``detail_module`` (the module ``detail_cls`` came from, if any — see
    :func:`load_detail`) is threaded through to ``_instrument`` so a direct,
    module-top ``from detailgen.validation import check_dimension``-style
    import in the detail file is captured too. Returns the raw per-run
    record (phases + derived counts)."""
    from detailgen.core.timing import PhaseTimer

    timer = PhaseTimer()
    with _instrument(timer, detail_module=detail_module):
        detail = detail_cls()
        with timer.phase("assemble"):
            detail.build()
        n_parts = len(detail.assembly.parts)
        with timer.phase("validate"):
            report = detail.validate()
        with timer.phase("render"):
            detail.render_documentation(out_dir)
        with timer.phase("export_png"):
            from detailgen.rendering.export import export_png
            export_png(detail.assembly, out_dir / f"{name}_bench.png")

    dedup = _dedup_estimate(detail, timer)
    bbox = _bbox_prefilter_estimate(detail)
    return {
        "phases": timer.as_dict(),
        "wall_total_s": timer.wall_total(),
        "validation_ok": report.ok,
        "n_parts": n_parts,
        "pairwise_sweep_pairs": n_parts * (n_parts - 1) // 2,
        "dedup_estimate": dedup,
        "bbox_prefilter_estimate": bbox,
    }


def run_package_once(spec_path: Path, out_dir: Path) -> dict:
    """Run the public one-view package builder and return its SLA surface."""
    from detailgen.package import PackageRequest
    from detailgen.package import builder as builder_module

    result = builder_module.build_package(
        PackageRequest(Path(spec_path), Path(out_dir), views=("iso",))
    )
    timings = result.manifest()["timings_seconds"]
    return {
        "timings_seconds": timings,
        "total_s": sum(timings.values()),
        "artifact_count": len(result.artifacts),
    }


def _dedup_estimate(detail, timer) -> dict:
    """Lever (a) evidence: group placed components by (type, params) — a
    solid cache keyed on that tuple would build each group once instead of
    once per instance. Savings assumes uniform per-instance cost within a
    type (avg = that type's measured total / its measured count), which is
    accurate for near-identical fasteners (same bolt built 8 times etc)."""
    groups: dict[tuple, int] = {}
    for p in detail.assembly.parts:
        c = p.component
        key = (type(c).__name__, tuple(sorted(
            (k, repr(v)) for k, v in c.params().items()
        )))
        groups[key] = groups.get(key, 0) + 1

    by_type_total: dict[str, float] = {}
    by_type_count: dict[str, int] = {}
    for phase, data in timer.as_dict().items():
        if phase.startswith("build:"):
            t = phase[len("build:"):]
            by_type_total[t] = data["seconds"]
            by_type_count[t] = data["count"]

    redundant_by_type: dict[str, int] = {}
    for (type_name, _params), count in groups.items():
        if count > 1:
            redundant_by_type[type_name] = redundant_by_type.get(type_name, 0) + (count - 1)

    savings_s = 0.0
    for type_name, redundant in redundant_by_type.items():
        total = by_type_total.get(type_name, 0.0)
        n = by_type_count.get(type_name, 0)
        if n:
            savings_s += (total / n) * redundant

    return {
        "distinct_param_groups": len(groups),
        "total_components": sum(groups.values()),
        "redundant_instances_by_type": redundant_by_type,
        "estimated_savings_s": savings_s,
    }


def _bbox_prefilter_estimate(detail) -> dict:
    """Lever (c) evidence: of the O(n^2) pairwise interference sweep, what
    fraction of pairs have non-overlapping bounding boxes (a bbox prefilter
    would skip the expensive boolean intersect for these entirely)? Computed
    directly here (cheap AABB test), NOT via the timer, so it's a diagnostic
    aside rather than a phase competing in the main "where does time go"
    table."""
    parts = detail.assembly.parts
    boxes = [p.world_solid().val().BoundingBox() for p in parts]
    total = 0
    non_overlapping = 0
    for (ba, bb) in combinations(boxes, 2):
        total += 1
        disjoint = (
            ba.xmax < bb.xmin or bb.xmax < ba.xmin or
            ba.ymax < bb.ymin or bb.ymax < ba.ymin or
            ba.zmax < bb.zmin or bb.zmax < ba.zmin
        )
        if disjoint:
            non_overlapping += 1
    return {
        "pairs": total,
        "bbox_non_overlapping_pairs": non_overlapping,
        "skippable_fraction": (non_overlapping / total) if total else 0.0,
    }


# --------------------------------------------------------------------------- #
# Fresh-subprocess measurements (import cost, no-render CLI wall time).
# --------------------------------------------------------------------------- #
def _run_subprocess_json(script: str, timeout: int) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        cwd=ROOT, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"benchmark subprocess failed (exit {proc.returncode}):\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def measure_import_cost(name: str, runs: int) -> list[dict]:
    spec_file = DETAILS_DIR / DETAIL_SPECS[name]
    script = f"""
import json, sys, time
t0 = time.perf_counter()
import cadquery  # noqa: F401
t1 = time.perf_counter()
from detailgen.spec.compiler import compile_spec_file
compile_spec_file({str(spec_file)!r})
t2 = time.perf_counter()
print(json.dumps({{"cadquery_import_s": t1 - t0, "detailgen_and_detail_import_s": t2 - t1, "total_s": t2 - t0}}))
"""
    return [_run_subprocess_json(script, timeout=120) for _ in range(runs)]


def measure_cli_no_render(name: str, runs: int) -> list[float]:
    """Wall time of ``python -m detailgen.spec details/<name>.spec.yaml`` with no
    render — compile + validate + metrics print, NO render. This is the ledger's
    flagged "what an agent authoring loop actually pays per iteration" number, now
    measured on the spec CLI (the only path since 4B-4b)."""
    spec_file = DETAILS_DIR / DETAIL_SPECS[name]
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "detailgen.spec", str(spec_file)],
            capture_output=True, text=True, cwd=ROOT, timeout=600,
        )
        elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            raise RuntimeError(
                f"detailgen.spec {name} failed (exit {proc.returncode}):\n"
                f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
            )
        times.append(elapsed)
    return times


def measure_consolidated_report(out_root: Path) -> dict:
    """Cold (fresh scratch renders dir -> every detail misses the hash gate)
    and warm (same scratch dir, re-run immediately -> every detail hits the
    hash gate) wall time of scripts/consolidated_report.py. Redirected via
    module-attribute overrides (OUT_DIR/RENDERS/HTML_OUT/VAULT_OUT) to a
    scratch directory so this NEVER touches the real outputs/consolidated
    cache or overwrites the vault copy."""
    script_path = ROOT / "scripts" / "consolidated_report.py"
    scratch = out_root / "consolidated_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)

    runner = f"""
import importlib.util, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("consolidated_report_bench", {str(script_path)!r})
mod = importlib.util.module_from_spec(spec)
sys.modules["consolidated_report_bench"] = mod
spec.loader.exec_module(mod)
scratch = Path({str(scratch)!r})
mod.OUT_DIR = scratch
mod.RENDERS = scratch / "renders"
mod.HTML_OUT = scratch / "zipline-build-document.html"
mod.VAULT_OUT = scratch / "vault_copy_DO_NOT_USE.html"
t0 = time.perf_counter()
mod.main()
t1 = time.perf_counter()
print("BENCH_ELAPSED", t1 - t0)
"""

    def _run() -> float:
        proc = subprocess.run(
            [sys.executable, "-c", runner], capture_output=True, text=True,
            cwd=ROOT, timeout=600,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"consolidated_report benchmark failed (exit {proc.returncode}):\n"
                f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
            )
        for line in reversed(proc.stdout.splitlines()):
            if line.startswith("BENCH_ELAPSED"):
                return float(line.split()[1])
        raise RuntimeError(f"no BENCH_ELAPSED marker in output:\n{proc.stdout}")

    cold_s = _run()   # scratch dir was just wiped -> every detail misses the gate
    warm_s = _run()   # same scratch dir, still warm -> every detail should hit the gate
    return {"cold_s": cold_s, "warm_s": warm_s}


# --------------------------------------------------------------------------- #
# Aggregation helpers.
# --------------------------------------------------------------------------- #
def _median_phases(run_records: list[dict]) -> dict:
    names = sorted({p for r in run_records for p in r["phases"]})
    return {
        name: {
            "seconds": statistics.median(
                r["phases"].get(name, {"seconds": 0.0})["seconds"] for r in run_records
            ),
            "count": statistics.median(
                r["phases"].get(name, {"count": 0})["count"] for r in run_records
            ),
        }
        for name in names
    }


def benchmark_details(names: list[str], runs: int, out_dir: Path) -> dict:
    results = {}
    for name in names:
        print(f"[benchmark] {name}: import cost ({runs} fresh subprocess runs)...",
              file=sys.stderr)
        import_cost = measure_import_cost(name, runs)

        print(f"[benchmark] {name}: no-render CLI wall time ({runs} fresh subprocess runs)...",
              file=sys.stderr)
        cli_no_render = measure_cli_no_render(name, runs)

        print(f"[benchmark] {name}: in-process phase breakdown ({runs} runs)...",
              file=sys.stderr)
        detail_module, detail_cls = load_detail(name)
        run_records = []
        for i in range(runs):
            rec = run_detail_once(name, detail_cls, out_dir / name / f"run{i}",
                                  detail_module=detail_module)
            run_records.append(rec)

        results[name] = {
            "import_cost_runs": import_cost,
            "cli_no_render_s_runs": cli_no_render,
            "cli_no_render_s_median": statistics.median(cli_no_render),
            "n_parts": run_records[0]["n_parts"],
            "pairwise_sweep_pairs": run_records[0]["pairwise_sweep_pairs"],
            "validation_ok": all(r["validation_ok"] for r in run_records),
            "runs": run_records,
            "median_phases": _median_phases(run_records),
            "dedup_estimate": run_records[0]["dedup_estimate"],
            "bbox_prefilter_estimate": run_records[0]["bbox_prefilter_estimate"],
        }
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--details", default=",".join(DETAIL_SPECS),
                        help="comma-separated detail names (default: all four)")
    parser.add_argument("--runs", type=int, default=2,
                        help="measurements per detail (default: 2; must be >=2 for a median)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="scratch output dir for benchmark artifacts (default: outputs/bench)")
    parser.add_argument("--no-doc", action="store_true",
                        help="skip the consolidated_report.py cold/warm timing (slowest part)")
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.details.split(",") if n.strip()]
    for n in names:
        if n not in DETAIL_SPECS:
            parser.error(f"unknown detail {n!r}; choices: {sorted(DETAIL_SPECS)}")
    if args.runs < 1:
        parser.error("--runs must be >= 1")

    args.out.mkdir(parents=True, exist_ok=True)

    import cadquery  # noqa: F401  (fail fast/loud before the long run if the env is broken)

    data: dict = {
        "meta": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "python": sys.version.split()[0],
            "cadquery": getattr(cadquery, "__version__", "unknown"),
            "runs": args.runs,
            "details": names,
            "machine_note": (
                "single M-series Mac, normal desktop load (not a quiet CI box) — "
                "treat any <15% run-to-run delta as noise, not signal"
            ),
        },
        "details": benchmark_details(names, args.runs, args.out),
    }

    if not args.no_doc:
        print("[benchmark] consolidated_report.py cold + warm...", file=sys.stderr)
        data["consolidated_report"] = measure_consolidated_report(args.out)

    out_path = args.out / "bench.json"
    out_path.write_text(json.dumps(data, indent=1))
    print(f"[benchmark] wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
