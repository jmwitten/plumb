"""Single-pass compiler for complete, generic construction packages."""

from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import json
from pathlib import Path

from ..core.buildinfo import build_manifest
from ..core.timing import PhaseTimer
from ..design_review import render_design_review_html
from ..rendering import (
    build_instruction_manual,
    export_glb,
    render_instruction_images,
    render_instruction_manual_html,
)
from ..rendering.web_viewer import build_viewer_payload
from ..review.manifest import build_review_manifest
from ..spec.compiler import compile_spec_file
from .documents import write_package_documents
from .html import page
from .model import PackageArtifact, PackageRequest, PackageResult
from .projections import (
    fabrication_projection,
    technical_projection,
)
from .views import render_standard_views


_ASSEMBLY_HOLD = (
    "No modeled assembly sequence is available; assembly order remains "
    "UNKNOWN — NOT ANALYZED."
)


def _write_csv(path: Path, rows: tuple[dict[str, object], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not columns:
            return
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _cut_rows(fabrication) -> tuple[dict[str, object], ...]:
    rows = []
    for part in fabrication:
        steps = part["steps"] or ({"kind": "none", "params": {}},)
        for number, step in enumerate(steps, start=1):
            rows.append(
                {
                    "part_id": part["part_id"],
                    "part_name": part["part_name"],
                    "stock_profile": part["stock_profile"],
                    "step": number,
                    "kind": step["kind"],
                    "params": json.dumps(step["params"], sort_keys=True),
                    "note": part["note"],
                }
            )
    return tuple(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _media_type(path: Path) -> str:
    return {
        ".csv": "text/csv",
        ".glb": "model/gltf-binary",
        ".html": "text/html",
        ".json": "application/json",
        ".md": "text/markdown",
        ".png": "image/png",
        ".step": "model/step",
    }.get(path.suffix.lower(), "application/octet-stream")


def _kind(relative_path: str) -> str:
    path = Path(relative_path)
    if relative_path == "assembly.html":
        return "assembly"
    if relative_path == "design-review.html":
        return "design-review"
    if relative_path == "review-manifest.json":
        return "review-manifest"
    if path.parts[0] == "views":
        return "standard-view"
    if path.parts[0] == "assembly-images":
        return "instruction-image"
    if path.parts[0] == "model":
        return "model"
    return path.stem


def _source(relative_path: str) -> str:
    if relative_path == "design-review.html":
        return "design-governance"
    if relative_path == "review-manifest.json":
        return "rendered-artifacts"
    return "compiled-detail"


def _instruction_viewer(detail, manual, out: Path, view_paths: tuple[Path, ...]):
    """Build the existing offline viewer bundle for the assembly document."""
    if not view_paths:
        return None
    glb_path = out / "model" / "detail.glb"
    if not glb_path.is_file():
        glb_path = export_glb(detail.assembly, out / "model" / "detail.web.glb")
    compressed = gzip.compress(glb_path.read_bytes(), compresslevel=9, mtime=0)
    preferred = next(
        (path for path in view_paths if path.stem == "iso"),
        view_paths[0],
    )
    return {
        "payload": build_viewer_payload(detail, instruction_manual=manual),
        "glb_b64": base64.b64encode(compressed).decode("ascii"),
        "isometric_href": preferred.relative_to(out).as_posix(),
    }


def _artifacts(out_dir: Path) -> tuple[PackageArtifact, ...]:
    artifacts = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.name == "package-manifest.json":
            continue
        relative = path.relative_to(out_dir).as_posix()
        artifacts.append(
            PackageArtifact(
                kind=_kind(relative),
                relative_path=relative,
                sha256=_sha256(path),
                media_type=_media_type(path),
                source=_source(relative),
            )
        )
    return tuple(artifacts)


def build_package(request: PackageRequest) -> PackageResult:
    """Generate a full package from one compiled and validated detail."""
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
        technical = technical_projection(
            detail,
            tuple(path.relative_to(out) for path in view_paths),
        )
        fabrication = fabrication_projection(detail)
        write_package_documents(
            out,
            technical=technical,
            fabrication=fabrication,
        )
        _write_csv(out / "bom.csv", tuple(detail.bom_table()))
        _write_csv(out / "cuts.csv", _cut_rows(fabrication))

        graph = detail.construction_event_graph
        assembly_path = out / "assembly.html"
        if graph is None:
            assembly_path.write_text(
                page("Assembly", f'<p class="unknown">{_ASSEMBLY_HOLD}</p>'),
                encoding="utf-8",
            )
        else:
            manual = build_instruction_manual(
                detail,
                technical_href="technical.html",
                title=f"{detail.name} — Illustrated Assembly Manual",
                basename="assembly.html",
                lede=(
                    "Model-derived sequence from the compiled construction "
                    "graph."
                ),
            )
            image_paths = render_instruction_images(
                detail,
                manual,
                out / "assembly-images",
            )
            assembly_path.write_text(
                render_instruction_manual_html(
                    detail,
                    manual,
                    image_paths,
                    generated_at="from the compiled package model",
                    viewer=_instruction_viewer(detail, manual, out, view_paths),
                ),
                encoding="utf-8",
            )

        governance = getattr(detail, "design_governance", None)
        if governance is not None:
            (out / "design-review.html").write_text(
                render_design_review_html(
                    governance.review,
                    governance.result,
                    governance,
                ),
                encoding="utf-8",
            )

    with timer.phase("review_trace"):
        review_manifest = build_review_manifest(out, repo_root=out)
        (out / "review-manifest.json").write_text(
            json.dumps(review_manifest.to_dict(), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        model = build_manifest(detail.assembly)
        artifacts = _artifacts(out)

    governance = getattr(detail, "design_governance", None)
    matrix = detail.coverage_matrix()
    result = PackageResult(
        request=request,
        assembly_hash=model["assembly_hash"],
        selection_fingerprint=(
            governance.selection_digest if governance is not None else None
        ),
        model_fingerprint=(
            governance.model_digest if governance is not None else None
        ),
        validation_ok=report.ok,
        blocking_count=len(report.blocking),
        holds=tuple(
            f"{row.family} — {row.verdict_display}"
            for row in matrix
            if row.verdict != "PASS"
        ),
        artifacts=artifacts,
        timings=tuple(sorted(timer.totals.items())),
    )
    (out / "package-manifest.json").write_text(
        json.dumps(result.manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
