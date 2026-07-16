# Generic Full-Package Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one project-agnostic command that compiles any supported `DetailSpec` once and generates the complete model-backed contractor package with deterministic evidence and phase timings.

**Architecture:** Introduce `detailgen.authoring` as a compact read-only vocabulary manifest and `detailgen.package` as a new downstream compiler stage. `PackageBuilder` owns one compiled detail and passes it to generic view, document, review, and manifest projections; no consumer may dispatch on a project name or recompile the spec.

**Tech Stack:** Python 3.12, CadQuery/VTK, frozen dataclasses, existing `detailgen.spec`, `detailgen.rendering`, `detailgen.review`, and `pytest`.

## Global Constraints

- No production identifier, branch, template, or dispatch condition may name the July 16 simple-assembly experiment, built-up members, nominal 2x4 lumber, or its fastener schedule.
- Do not add a domain recipe or new construction vocabulary in this plan.
- Compile and validate exactly one `SpecDetail` per package run.
- Preserve `UNKNOWN — NOT ANALYZED`; document generation may not upgrade evidence.
- A skipped test status must serialize as `skipped`, never `passed`.
- Existing project-specific scripts remain backward compatible; this plan adds the generic path and does not migrate their custom reader copy.
- Run the full Plumb suite before integration because this changes shared rendering and document-generation infrastructure.

---

### Task 1: Publish a compact authoring manifest

**Files:**
- Create: `src/authoring/__init__.py`
- Create: `src/authoring/manifest.py`
- Create: `src/authoring/__main__.py`
- Modify: `src/spec/loader.py`
- Modify: `pyproject.toml`
- Test: `tests/test_authoring_manifest.py`

**Interfaces:**
- Consumes: `detailgen.core.registry.components`, `detailgen.assemblies.connection.connection_types`, `detailgen.rendering.export.VIEWS`.
- Produces: `build_authoring_manifest() -> dict`, `authoring_manifest_json() -> str`, and `python -m detailgen.authoring`.

- [ ] **Step 1: Write the failing manifest contract test**

```python
import json

from detailgen.authoring import authoring_manifest_json, build_authoring_manifest


def test_authoring_manifest_is_deterministic_and_project_agnostic():
    first = build_authoring_manifest()
    second = json.loads(authoring_manifest_json())

    assert first == second
    assert first["schema"] == "detailgen/authoring-manifest/v1"
    assert first["components"] == sorted(first["components"], key=lambda row: row["key"])
    assert first["connections"] == sorted(first["connections"], key=lambda row: row["key"])
    assert all(set(row) == {"key", "constructor", "summary"}
               for row in (*first["components"], *first["connections"]))
    assert first["views"] == sorted(first["views"])
    serialized = authoring_manifest_json().lower()
    assert "built_up" not in serialized
    assert "2x4" not in serialized
```

- [ ] **Step 2: Run the focused test and confirm the missing-module failure**

Run: `.venv/bin/python -m pytest tests/test_authoring_manifest.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'detailgen.authoring'`.

- [ ] **Step 3: Extract the public top-level schema-key contract**

In `src/spec/loader.py`, define and use one immutable key map instead of keeping the keys inside `load_spec`:

```python
DETAIL_SPEC_KEYS = {
    "name": True, "type": True, "units": False,
    "params": False, "derived": False, "components": True,
    "connections": False, "validation": False, "roles": False,
    "design_review": False, "callouts": False, "explode": False,
    "doc": False, "cross_check": False, "export": False,
    "sequence": False, "retire": False,
}
```

Replace the corresponding literal passed to `_take()` with `DETAIL_SPEC_KEYS`.

- [ ] **Step 4: Implement the deterministic manifest**

```python
# src/authoring/manifest.py
from __future__ import annotations

import inspect
import json

from .. import components as _load_components  # noqa: F401
from ..assemblies.connection import connection_types
from ..core.registry import components
from ..rendering.export import VIEWS
from ..spec.loader import DETAIL_SPEC_KEYS


def _summary(obj) -> str:
    text = inspect.getdoc(obj) or ""
    return text.split("\n\n", 1)[0].replace("\n", " ").strip()


def _rows(registry) -> list[dict]:
    return [
        {
            "key": key,
            "constructor": str(inspect.signature(registry.get(key))),
            "summary": _summary(registry.get(key)),
        }
        for key in sorted(registry.names())
    ]


def build_authoring_manifest() -> dict:
    return {
        "schema": "detailgen/authoring-manifest/v1",
        "components": _rows(components),
        "connections": _rows(connection_types),
        "views": sorted(VIEWS),
        "detail_spec_keys": sorted(DETAIL_SPEC_KEYS),
    }


def authoring_manifest_json() -> str:
    return json.dumps(build_authoring_manifest(), indent=2, sort_keys=True) + "\n"
```

Export both functions from `src/authoring/__init__.py`, print the JSON from `src/authoring/__main__.py`, and add `"detailgen.authoring"` to the setuptools package list.

- [ ] **Step 5: Run the manifest tests**

Run: `.venv/bin/python -m pytest tests/test_authoring_manifest.py tests/test_registry.py -q`

Expected: all selected tests pass and `python -m detailgen.authoring` emits one JSON object.

- [ ] **Step 6: Commit the authoring surface**

```bash
git add src/authoring src/spec/loader.py tests/test_authoring_manifest.py pyproject.toml
git commit -m "feat: publish compact Plumb authoring manifest"
```

---

### Task 2: Define the generic package protocol

**Files:**
- Create: `src/package/__init__.py`
- Create: `src/package/model.py`
- Modify: `pyproject.toml`
- Test: `tests/test_package_model.py`

**Interfaces:**
- Consumes: plain paths, hashes, validation state, and timing values.
- Produces: `PackageRequest`, `PackageArtifact`, `PackageResult`, and `PackageResult.manifest()`.

- [ ] **Step 1: Write protocol tests for release state, skipped tests, and deterministic ordering**

```python
from pathlib import Path

import pytest

from detailgen.package import PackageArtifact, PackageRequest, PackageResult


def test_package_request_rejects_unknown_release_state(tmp_path):
    with pytest.raises(ValueError, match="release must be preview or delivery"):
        PackageRequest(Path("x.spec.yaml"), tmp_path, release="draft")


def test_manifest_keeps_skipped_distinct_from_passed(tmp_path):
    request = PackageRequest(
        Path("x.spec.yaml"), tmp_path, tests_status="skipped",
        tests_reason="owner-request",
    )
    result = PackageResult(
        request=request,
        assembly_hash="a" * 64,
        selection_fingerprint=None,
        model_fingerprint=None,
        validation_ok=True,
        blocking_count=0,
        holds=("Structural capacity — UNKNOWN — NOT ANALYZED",),
        artifacts=(PackageArtifact("technical", "technical.html", "b" * 64,
                                   "text/html", "compiled-detail"),),
        timings=(("compile_validate", 0.25),),
    )

    payload = result.manifest()
    assert payload["tests"] == {"status": "skipped", "reason": "owner-request"}
    assert payload["artifacts"][0]["relative_path"] == "technical.html"
```

- [ ] **Step 2: Run the focused test and confirm the missing-module failure**

Run: `.venv/bin/python -m pytest tests/test_package_model.py -q`

Expected: collection fails because `detailgen.package` does not exist.

- [ ] **Step 3: Implement the frozen protocol types**

```python
# src/package/model.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PackageRequest:
    spec_path: Path
    output_dir: Path
    release: str = "preview"
    views: tuple[str, ...] = ("iso", "front", "right", "top")
    tests_status: str = "not-run"
    tests_reason: str = "package generation does not execute tests"

    def __post_init__(self):
        if self.release not in {"preview", "delivery"}:
            raise ValueError("release must be preview or delivery")
        if self.tests_status not in {"not-run", "skipped", "passed", "failed"}:
            raise ValueError("tests_status must be not-run, skipped, passed, or failed")
        if self.tests_status == "skipped" and not self.tests_reason.strip():
            raise ValueError("skipped tests require a reason")


@dataclass(frozen=True)
class PackageArtifact:
    kind: str
    relative_path: str
    sha256: str
    media_type: str
    source: str


@dataclass(frozen=True)
class PackageResult:
    request: PackageRequest
    assembly_hash: str
    selection_fingerprint: str | None
    model_fingerprint: str | None
    validation_ok: bool
    blocking_count: int
    holds: tuple[str, ...]
    artifacts: tuple[PackageArtifact, ...]
    timings: tuple[tuple[str, float], ...]

    def manifest(self) -> dict:
        artifacts = sorted(self.artifacts, key=lambda row: row.relative_path)
        return {
            "schema": "detailgen/package-manifest/v1",
            "spec": self.request.spec_path.name,
            "release": self.request.release,
            "assembly_hash": self.assembly_hash,
            "selection_fingerprint": self.selection_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "validation": {
                "ok": self.validation_ok,
                "blocking_count": self.blocking_count,
            },
            "holds": list(self.holds),
            "tests": {
                "status": self.request.tests_status,
                "reason": self.request.tests_reason,
            },
            "timings_seconds": dict(self.timings),
            "artifacts": [row.__dict__ for row in artifacts],
        }
```

Export these types in `src/package/__init__.py` and add `"detailgen.package"` to `pyproject.toml`.

- [ ] **Step 4: Run the package-model tests**

Run: `.venv/bin/python -m pytest tests/test_package_model.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit the package protocol**

```bash
git add src/package tests/test_package_model.py pyproject.toml
git commit -m "feat: define generic package protocol"
```

---

### Task 3: Project generic views and contractor document data

**Files:**
- Create: `src/package/projections.py`
- Create: `src/package/views.py`
- Modify: `src/details/base.py`
- Modify: `src/rendering/instruction_panels.py`
- Test: `tests/test_package_projections.py`
- Test: `tests/test_package_views.py`

**Interfaces:**
- Consumes: one built and validated `Detail`, `export_png`, fabrication records, installation contracts, coverage, BOM rows, and reader steps.
- Produces: `technical_projection(detail, view_paths)`, `fabrication_projection(detail)`, `installation_projection(detail)`, and `render_standard_views(detail, out_dir, names)`.

- [ ] **Step 1: Write tests proving projection by capability rather than project identity**

```python
from types import SimpleNamespace

from detailgen.package.projections import fabrication_projection


def test_fabrication_projection_uses_component_protocol_only():
    record = SimpleNamespace(
        stock=SimpleNamespace(profile="generic stock"),
        steps=(SimpleNamespace(kind="crosscut", params_dict=lambda: {"to_length_mm": 100.0}),),
        fab_note=lambda: "crosscut to length",
    )
    component = SimpleNamespace(fabrication_record=lambda part_id: record)
    part = SimpleNamespace(id="part-a", name="Part A", component=component)
    detail = SimpleNamespace(assembly=SimpleNamespace(parts=(part,)))

    assert fabrication_projection(detail) == ({
        "part_id": "part-a",
        "part_name": "Part A",
        "stock_profile": "generic stock",
        "steps": ({"kind": "crosscut", "params": {"to_length_mm": 100.0}},),
        "note": "crosscut to length",
    },)
```

- [ ] **Step 2: Write the view contract test**

```python
from pathlib import Path

import pytest

from detailgen.package.views import render_standard_views


def test_standard_views_reject_unknown_camera(monkeypatch, tmp_path):
    detail = object()
    with pytest.raises(ValueError, match="unknown standard view"):
        render_standard_views(detail, tmp_path, ("not-a-camera",))


def test_standard_views_use_one_existing_assembly(monkeypatch, tmp_path):
    calls = []
    detail = type("D", (), {"assembly": object()})()
    monkeypatch.setattr("detailgen.package.views.export_png",
                        lambda assembly, path, view: calls.append((assembly, Path(path), view)) or Path(path))

    paths = render_standard_views(detail, tmp_path, ("iso", "front"))

    assert [path.name for path in paths] == ["iso.png", "front.png"]
    assert all(call[0] is detail.assembly for call in calls)
```

- [ ] **Step 3: Run both test files and confirm the missing modules**

Run: `.venv/bin/python -m pytest tests/test_package_projections.py tests/test_package_views.py -q`

Expected: collection fails because the projection modules do not exist.

- [ ] **Step 4: Implement standard view rendering**

```python
# src/package/views.py
from pathlib import Path

from ..rendering.export import VIEWS, export_png


def render_standard_views(detail, out_dir, names):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    unknown = sorted(set(names) - set(VIEWS))
    if unknown:
        raise ValueError(f"unknown standard view(s) {unknown}; valid: {sorted(VIEWS)}")
    return tuple(
        export_png(detail.assembly, out_dir / f"{name}.png", view=name)
        for name in names
    )
```

- [ ] **Step 5: Expose installation/process facts as public detail properties**

Add these properties beside `Detail.connection_edges` in `src/details/base.py`:

```python
@property
def resolved_installations(self) -> tuple:
    """Resolved installation contracts from the last validation."""
    if self._connection_checks is None:
        return ()
    return tuple(self._connection_checks.installs)


@property
def construction_event_graph(self):
    """The validated construction event graph, or None when unrepresented."""
    if self._connection_checks is None:
        return None
    return self._connection_checks.event_graph
```

Change `build_instruction_manual()` to read
`detail.construction_event_graph` and `detail.resolved_installations` rather
than `_connection_checks`. Add assertions to
`tests/test_package_projections.py` that both properties are empty before
validation and populated afterward for an existing connected detail.

- [ ] **Step 6: Implement capability-driven projections**

Implement `fabrication_projection()` exactly over the public `fabrication_record(part.id)` protocol shown in the test. Add:

```python
def technical_projection(detail, view_paths):
    from ..validation.coverage import coverage_matrix, render_headline_line

    matrix = coverage_matrix(detail.report)
    return {
        "title": detail.name,
        "headline": render_headline_line(matrix),
        "views": tuple(path.name for path in view_paths),
        "coverage": tuple(row.as_dict() if hasattr(row, "as_dict") else row for row in matrix),
        "bom": tuple(detail.bom_table()),
        "callouts": tuple(detail.rendered_callouts()),
    }


def installation_projection(detail):
    return {
        "installs": detail.resolved_installations,
        "event_graph": detail.construction_event_graph,
        "connection_edges": tuple(detail.connection_edges),
        "coverage": tuple(detail.coverage_matrix()),
    }
```

Keep the projection values typed where Plumb already owns a value type; do not convert installation contracts back into guessed prose.

- [ ] **Step 7: Run focused projection and existing instruction tests**

Run: `.venv/bin/python -m pytest tests/test_package_projections.py tests/test_package_views.py tests/test_instruction_panels.py tests/test_stepdoc_process.py -q`

Expected: all selected tests pass.

- [ ] **Step 8: Commit the projections**

```bash
git add src/package/projections.py src/package/views.py src/details/base.py src/rendering/instruction_panels.py tests/test_package_projections.py tests/test_package_views.py
git commit -m "feat: project generic package views and records"
```

---

### Task 4: Render generic technical, fabrication, and installation documents

**Files:**
- Create: `src/package/html.py`
- Create: `src/package/documents.py`
- Test: `tests/test_package_documents.py`

**Interfaces:**
- Consumes: projection dictionaries from Task 3 plus the existing `InstructionManual` renderer.
- Produces: `render_technical_html`, `render_fabrication_html`, `render_installation_html`, and `write_package_documents`.

- [ ] **Step 1: Write renderer tests for standalone identity and honest unknowns**

```python
from detailgen.package.documents import (
    render_fabrication_html, render_installation_html, render_technical_html,
)


def test_generic_documents_are_standalone_and_keep_unknowns():
    technical = render_technical_html({
        "title": "Example Assembly",
        "headline": "Geometry PASS · Structural capacity UNKNOWN — NOT ANALYZED",
        "views": ("iso.png",), "coverage": (), "bom": (), "callouts": (),
    })
    fabrication = render_fabrication_html(({
        "part_id": "a", "part_name": "Part A", "stock_profile": "stock",
        "steps": (), "note": "purchased as-is",
    },))
    installation = render_installation_html({
        "installs": (), "event_graph": None,
        "connection_edges": (), "coverage": (),
    })

    assert "Example Assembly" in technical
    assert "UNKNOWN — NOT ANALYZED" in technical
    assert "Part A" in fabrication
    assert "No modeled installation contract" in installation
    combined = (technical + fabrication + installation).lower()
    assert "armchair" not in combined
    assert "birdhouse" not in combined
```

- [ ] **Step 2: Run the test and confirm the missing renderer failure**

Run: `.venv/bin/python -m pytest tests/test_package_documents.py -q`

Expected: collection fails because `detailgen.package.documents` does not exist.

- [ ] **Step 3: Implement one shared HTML shell**

```python
# src/package/html.py
from html import escape


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>body{{max-width:960px;margin:auto;padding:32px;font:15px/1.5 system-ui;color:#172033}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #cbd5e1;padding:7px;text-align:left}}img{{max-width:100%;height:auto}}.unknown{{border-left:5px solid #b45309;padding:10px;background:#fff7ed}}@media print{{body{{padding:0}}}}</style>
</head><body>{body}</body></html>"""
```

- [ ] **Step 4: Implement the three renderers without project dispatch**

Use `html.escape` for every model-derived string. `render_technical_html()` renders the headline, standard-view images, coverage, callouts, and BOM. `render_fabrication_html()` renders one row per projected part and one ordered list per process record. `render_installation_html()` renders resolved installation contracts and sequence edges; when no contract exists, it emits the exact sentence `No modeled installation contract is available; installation remains UNKNOWN — NOT ANALYZED.`

Expose this write surface:

```python
def write_package_documents(out_dir, *, technical, fabrication, installation):
    out_dir = Path(out_dir)
    paths = {
        "technical": out_dir / "technical.html",
        "fabrication": out_dir / "fabrication.html",
        "installation": out_dir / "installation.html",
    }
    paths["technical"].write_text(render_technical_html(technical), encoding="utf-8")
    paths["fabrication"].write_text(render_fabrication_html(fabrication), encoding="utf-8")
    paths["installation"].write_text(render_installation_html(installation), encoding="utf-8")
    return paths
```

- [ ] **Step 5: Run document and print-surface tests**

Run: `.venv/bin/python -m pytest tests/test_package_documents.py tests/test_instruction_render.py tests/test_instruction_panels.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit generic document rendering**

```bash
git add src/package/html.py src/package/documents.py tests/test_package_documents.py
git commit -m "feat: render generic contractor package documents"
```

---

### Task 5: Build the entire package from one prepared detail

**Files:**
- Create: `src/package/builder.py`
- Test: `tests/test_package_builder.py`

**Interfaces:**
- Consumes: `PackageRequest`, `compile_spec_file`, Task 3 projections, Task 4 renderers, existing model/manual/design-review renderers, and review manifests.
- Produces: `build_package(request: PackageRequest) -> PackageResult`.

- [ ] **Step 1: Write the one-compile regression test**

```python
from pathlib import Path

from detailgen.package import PackageRequest
from detailgen.package.builder import build_package


def test_builder_compiles_once_and_writes_content_addressed_manifest(monkeypatch, tmp_path):
    import detailgen.package.builder as builder_module

    calls = {"compile": 0}
    root = Path(__file__).resolve().parents[1]
    spec = root / "details" / "armchair_caddy.spec.yaml"
    real_compile = builder_module.compile_spec_file

    def compile_once(path):
        calls["compile"] += 1
        return real_compile(path)

    monkeypatch.setattr("detailgen.package.builder.compile_spec_file", compile_once)
    result = build_package(PackageRequest(spec, tmp_path / "out", views=("iso",)))

    assert calls["compile"] == 1
    assert result.validation_ok is True
    manifest_path = tmp_path / "out" / "package-manifest.json"
    assert manifest_path.is_file()
    assert all(len(artifact.sha256) == 64 for artifact in result.artifacts)
```

- [ ] **Step 2: Add a real-detail integration test using an existing governed spec**

```python
def test_two_existing_details_share_the_same_builder(tmp_path):
    root = Path(__file__).resolve().parents[1]
    specs = (
        root / "details" / "armchair_caddy.spec.yaml",
        root / "details" / "family_birdhouse.spec.yaml",
    )
    results = [
        build_package(PackageRequest(spec, tmp_path / spec.stem, views=("iso",)))
        for spec in specs
    ]
    assert all(result.validation_ok for result in results)
    assert all(len(result.artifacts) >= 8 for result in results)
```

- [ ] **Step 3: Run the tests and confirm the missing builder failure**

Run: `.venv/bin/python -m pytest tests/test_package_builder.py -q`

Expected: collection fails because `detailgen.package.builder` does not exist.

- [ ] **Step 4: Implement the timed single-pass builder**

The implementation must use one phase timer and one compiled detail:

```python
def build_package(request: PackageRequest) -> PackageResult:
    timer = PhaseTimer()
    with timer.phase("compile_validate"):
        detail = compile_spec_file(request.spec_path)
        report = detail.validate()
        if request.release == "delivery":
            detail.require_delivery_ready()
        else:
            approval = getattr(detail, "require_modeling_approval", None)
            if approval is not None:
                approval()

    out = request.output_dir
    out.mkdir(parents=True, exist_ok=True)
    with timer.phase("model_export"):
        detail.render_documentation(out / "model")
    with timer.phase("standard_views"):
        view_paths = render_standard_views(detail, out / "views", request.views)
    with timer.phase("documents"):
        projections = (
            technical_projection(detail, view_paths),
            fabrication_projection(detail),
            installation_projection(detail),
        )
        document_paths = write_package_documents(
            out,
            technical=projections[0], fabrication=projections[1],
            installation=projections[2],
        )
        manual = build_instruction_manual(
            detail,
            technical_href="technical.html",
            title=f"{detail.name} — Illustrated Assembly Manual",
            basename="assembly.html",
            lede="Model-derived sequence from the compiled construction graph.",
        )
        image_paths = render_instruction_images(detail, manual, out / "assembly-images")
        assembly_path = out / "assembly.html"
        assembly_path.write_text(
            render_instruction_manual_html(detail, manual, image_paths),
            encoding="utf-8",
        )
```

Before calling `build_instruction_manual`, inspect the already-validated event
graph. When it is absent, still write `assembly.html`, but make it a visible
hold using the shared HTML shell and this exact sentence:
`No modeled assembly sequence is available; assembly order remains UNKNOWN — NOT ANALYZED.`
Do not invent an order to satisfy the document checklist.

Then render the governed design review when `detail.design_governance` exists,
build the review manifest over `views/` and `assembly-images/`, write BOM/cut
CSVs from public rows, hash every file except `package-manifest.json`, build
`PackageResult`, and write its manifest last. Do not call `compile_spec_file`,
`validate`, or `render_documentation` from a helper or renderer.

- [ ] **Step 5: Run builder, review-manifest, and determinism tests**

Run: `.venv/bin/python -m pytest tests/test_package_builder.py tests/test_review_manifest.py tests/test_reproducible_builds.py -q`

Expected: all selected tests pass; the integration test exercises the same builder for both existing details.

- [ ] **Step 6: Commit the single-pass builder**

```bash
git add src/package/builder.py tests/test_package_builder.py
git commit -m "feat: generate complete package from one compiled detail"
```

---

### Task 6: Add the generic CLI and SLA evidence

**Files:**
- Create: `src/package/__main__.py`
- Modify: `src/package/__init__.py`
- Modify: `scripts/benchmark.py`
- Test: `tests/test_package_cli.py`
- Test: `tests/test_benchmark_harness.py`

**Interfaces:**
- Consumes: `build_package(PackageRequest)`.
- Produces: `python -m detailgen.package <spec> --out <dir> [--preview|--delivery] [--tests-skipped REASON]` and package timing records in the existing benchmark harness.

- [ ] **Step 1: Write CLI tests**

```python
import subprocess
import sys


def test_package_cli_help_is_fast():
    proc = subprocess.run(
        [sys.executable, "-m", "detailgen.package", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0
    assert "--tests-skipped" in proc.stdout
    assert "--delivery" in proc.stdout
```

- [ ] **Step 2: Run the CLI test and confirm the missing-entry-point failure**

Run: `.venv/bin/python -m pytest tests/test_package_cli.py -q`

Expected: the command fails because `detailgen.package.__main__` does not exist.

- [ ] **Step 3: Implement the CLI**

```python
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate a complete Plumb package")
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    release = parser.add_mutually_exclusive_group()
    release.add_argument("--preview", action="store_true")
    release.add_argument("--delivery", action="store_true")
    parser.add_argument("--tests-skipped", metavar="REASON")
    args = parser.parse_args(argv)
    request = PackageRequest(
        args.spec,
        args.out,
        release="delivery" if args.delivery else "preview",
        tests_status="skipped" if args.tests_skipped else "not-run",
        tests_reason=args.tests_skipped or "package generation does not execute tests",
    )
    result = build_package(request)
    print(json.dumps(result.manifest(), indent=2, sort_keys=True))
    return 0
```

- [ ] **Step 4: Extend the benchmark harness through the public builder**

Add `run_package_once(spec_path: Path, out_dir: Path) -> dict` to `scripts/benchmark.py`. It calls `build_package()` with a one-view preview request and returns `result.manifest()["timings_seconds"]`, `total_s`, and artifact count. Do not add any named project to `DETAIL_SPECS` for this work.

- [ ] **Step 5: Run CLI and benchmark tests**

Run: `.venv/bin/python -m pytest tests/test_package_cli.py tests/test_benchmark_harness.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the CLI and timing surface**

```bash
git add src/package scripts/benchmark.py tests/test_package_cli.py tests/test_benchmark_harness.py
git commit -m "feat: expose generic package CLI and timings"
```

---

### Task 7: Document the new path and verify the subsystem

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: the CLI and manifest contracts landed above.
- Produces: the public authoring command, context-loading boundary, and roadmap progress record.

- [ ] **Step 1: Add the public commands to README**

Document these exact commands and explain that no source-code registration is required:

```bash
.venv/bin/python -m detailgen.authoring
.venv/bin/python -m detailgen.package details/example.spec.yaml \
  --out outputs/example --preview
```

- [ ] **Step 2: Add the authoring boundary to CLAUDE.md**

Record that ordinary new projects query `detailgen.authoring`, author a spec, and invoke `detailgen.package`; roadmap/progress and implementation source are loaded only after a concrete capability gap. Keep the existing rule that actual framework work reads roadmap state.

- [ ] **Step 3: Record the generic package compiler in the progress ledger**

Add one dated section with the public interfaces, verification commands, and measured package phases. State explicitly that the external simple-project replay is not part of production code.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_authoring_manifest.py tests/test_package_model.py tests/test_package_projections.py tests/test_package_views.py tests/test_package_documents.py tests/test_package_builder.py tests/test_package_cli.py -q
.venv/bin/python -m pytest -q -n auto
```

Expected: focused tests pass, then the complete Plumb suite passes with no regression.

- [ ] **Step 5: Generate one existing package twice and compare non-timing content**

Run:

```bash
rm -rf /tmp/plumb-package-a /tmp/plumb-package-b
.venv/bin/python -m detailgen.package details/armchair_caddy.spec.yaml --out /tmp/plumb-package-a --preview
.venv/bin/python -m detailgen.package details/armchair_caddy.spec.yaml --out /tmp/plumb-package-b --preview
```

Expected: every artifact hash matches between manifests; only `timings_seconds` may differ.

- [ ] **Step 6: Commit and push the core implementation**

```bash
git add README.md CLAUDE.md .superpowers/sdd/progress.md
git commit -m "docs: publish generic full-package workflow"
git push -u origin HEAD
```

The plugin-orchestration plan may start only after this public CLI is available on the implementation branch.
