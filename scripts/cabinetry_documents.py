#!/usr/bin/env python3
"""Generate the linked four-file DB40 cabinetry document set."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))
if str(_REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO / "scripts"))

import cabinetry_project_report as CPR  # noqa: E402

from detailgen.packs import compile_project_file  # noqa: E402
from detailgen.packs.cabinetry.instruction_manual import (  # noqa: E402
    build_cabinetry_instruction_manual,
)
from detailgen.rendering.instruction_panels import (  # noqa: E402
    RelatedDocumentLink,
)
from detailgen.rendering.instruction_manual import (  # noqa: E402
    render_instruction_manual_html,
)
from detailgen.rendering.instruction_render import (  # noqa: E402
    DEFAULT_SIZE,
    render_instruction_images,
)


DEFAULT_PROJECT = (
    _REPO / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"
)
DEFAULT_OUT_DIR = _REPO / "outputs" / "frameless_three_drawer_40"
TECHNICAL_BASENAME = "frameless_three_drawer_40_build_document.html"
MANUAL_BASENAME = "frameless_three_drawer_40_assembly_manual.html"
FABRICATION_BASENAME = "frameless_three_drawer_40_fabrication_packet.html"
AUDIT_BASENAME = "frameless_three_drawer_40_review_trace.html"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_cabinetry_document_set(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    project_path: str | Path = DEFAULT_PROJECT,
    image_size: tuple[int, int] = DEFAULT_SIZE,
) -> dict:
    """Compile and render once, then project four linked reader surfaces."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    technical_path = out_dir / TECHNICAL_BASENAME
    manual_path = out_dir / MANUAL_BASENAME
    fabrication_path = out_dir / FABRICATION_BASENAME
    audit_path = out_dir / AUDIT_BASENAME

    project = compile_project_file(Path(project_path))
    project.require_fabrication_release()
    document_links = CPR.CabinetryDocumentLinks(
        review_href=TECHNICAL_BASENAME,
        manual_href=MANUAL_BASENAME,
        fabrication_href=FABRICATION_BASENAME,
        audit_href=AUDIT_BASENAME,
    )
    manual = build_cabinetry_instruction_manual(
        project,
        technical_href=TECHNICAL_BASENAME,
        basename=MANUAL_BASENAME,
        related_documents=(
            RelatedDocumentLink(
                "Review & installation sheet", TECHNICAL_BASENAME,
            ),
            RelatedDocumentLink("Fabrication packet", FABRICATION_BASENAME),
            RelatedDocumentLink("Review trace", AUDIT_BASENAME),
        ),
    )
    image_paths = render_instruction_images(
        project.detail,
        manual,
        out_dir / "instruction_panels",
        size=image_size,
    )
    manual_path.write_text(
        render_instruction_manual_html(project.detail, manual, image_paths),
        encoding="utf-8",
    )
    assets = CPR.render_shared_product_assets(
        project, out_dir, instruction_manual=manual,
    )
    technical_path.write_text(
        CPR.build_cabinetry_review_html(
            project,
            images=assets.images,
            viewer_payload=assets.viewer_payload,
            glb_b64=CPR._glb_b64(assets.glb_bytes),
            links=document_links,
        ),
        encoding="utf-8",
    )
    fabrication_path.write_text(
        CPR.build_cabinetry_fabrication_html(
            project, images=assets.images, links=document_links,
        ),
        encoding="utf-8",
    )
    audit_path.write_text(
        CPR.build_cabinetry_audit_html(project, links=document_links),
        encoding="utf-8",
    )

    ordered_images = tuple(image_paths[index] for index in sorted(image_paths))
    return {
        "technical_path": str(technical_path),
        "manual_path": str(manual_path),
        "fabrication_path": str(fabrication_path),
        "audit_path": str(audit_path),
        "technical_sha256": _sha256(technical_path),
        "manual_sha256": _sha256(manual_path),
        "fabrication_sha256": _sha256(fabrication_path),
        "audit_sha256": _sha256(audit_path),
        "panel_count": len(manual.panels),
        "asset_keys": tuple(path.stem for path in ordered_images),
        "panel_images": tuple(str(path) for path in ordered_images),
    }


def build_cabinetry_document_pair(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    project_path: str | Path = DEFAULT_PROJECT,
    image_size: tuple[int, int] = DEFAULT_SIZE,
) -> dict:
    """Compatibility alias for the four-file cabinetry document set."""

    return build_cabinetry_document_set(
        out_dir, project_path=project_path, image_size=image_size,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    args = parser.parse_args(argv)
    result = build_cabinetry_document_set(
        args.out_dir,
        project_path=args.project,
        image_size=(args.width, args.height),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
