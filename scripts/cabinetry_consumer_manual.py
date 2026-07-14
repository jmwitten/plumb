#!/usr/bin/env python3
"""Generate the DB40 consumer assembly manual (separate review surface).

Writes ``frameless_three_drawer_40_consumer_manual.html`` next to — never
instead of — the accepted four-document DB40 set.
"""

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
from detailgen.packs.cabinetry.consumer_manual import (  # noqa: E402
    build_cabinetry_consumer_manual,
    consumer_action_frames,
    consumer_diagrams,
    consumer_hardware_letters,
    consumer_panels_manual,
    consumer_part_rows,
)
from detailgen.rendering.consumer_manual_html import (  # noqa: E402
    render_consumer_manual_html,
)
from detailgen.rendering.consumer_pages import (  # noqa: E402
    visible_instructional_words,
)
from detailgen.rendering.instruction_panels import (  # noqa: E402
    RelatedDocumentLink,
)
from detailgen.rendering.instruction_render import (  # noqa: E402
    DEFAULT_SIZE,
    render_cover_image,
    render_frame_images,
)

DEFAULT_PROJECT = (
    _REPO / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"
)
DEFAULT_OUT_DIR = _REPO / "outputs" / "frameless_three_drawer_40"
CONSUMER_BASENAME = "frameless_three_drawer_40_consumer_manual.html"
TECHNICAL_BASENAME = "frameless_three_drawer_40_build_document.html"
MANUAL_BASENAME = "frameless_three_drawer_40_assembly_manual.html"
FABRICATION_BASENAME = "frameless_three_drawer_40_fabrication_packet.html"
AUDIT_BASENAME = "frameless_three_drawer_40_review_trace.html"


def build_cabinetry_consumer_document(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    project_path: str | Path = DEFAULT_PROJECT,
    image_size: tuple[int, int] = DEFAULT_SIZE,
) -> dict:
    """Compile once and render the standalone DB40 consumer manual."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / CONSUMER_BASENAME

    project = compile_project_file(Path(project_path))
    project.require_fabrication_release()

    panels_manual = consumer_panels_manual(project)
    letters = consumer_hardware_letters(project.artifacts.hardware_schedule)
    frames = consumer_action_frames(panels_manual, project, letters=letters)
    consumer = build_cabinetry_consumer_manual(
        project,
        basename=CONSUMER_BASENAME,
        related_documents=(
            RelatedDocumentLink("Review & installation sheet",
                                TECHNICAL_BASENAME),
            RelatedDocumentLink("Illustrated assembly manual",
                                MANUAL_BASENAME),
            RelatedDocumentLink("Fabrication packet", FABRICATION_BASENAME),
            RelatedDocumentLink("Review trace", AUDIT_BASENAME),
        ),
    )

    image_dir = out_dir / "consumer_panels"
    image_paths = render_frame_images(
        project.detail, panels_manual, frames, image_dir,
        size=image_size, style="high_contrast")
    cover_image = render_cover_image(
        project.detail, panels_manual, image_dir,
        size=image_size, style="high_contrast")

    viewer_assets = CPR.render_shared_product_assets(
        project, out_dir / "consumer_viewer",
        instruction_manual=panels_manual)
    viewer = {
        "payload": viewer_assets.viewer_payload,
        "glb_b64": CPR._glb_b64(viewer_assets.glb_bytes),
        "isometric": viewer_assets.images["isometric"],
    }

    output_path.write_text(
        render_consumer_manual_html(
            project.detail, consumer, image_paths,
            cover_image=cover_image,
            inventory_rows=consumer_part_rows(project),
            parts_heading="Parts — cut sizes in mm",
            diagrams=consumer_diagrams(panels_manual),
            viewer=viewer,
        ),
        encoding="utf-8",
    )

    return {
        "consumer_path": str(output_path),
        "consumer_sha256": hashlib.sha256(
            output_path.read_bytes()).hexdigest(),
        "page_count": len(consumer.pages),
        "frame_count": sum(len(page.frames) for page in consumer.pages),
        "visible_instructional_words": visible_instructional_words(consumer),
        "hardware_letters": [
            f"{lt.letter}:{lt.quantity_total} {lt.quantity_unit}"
            for lt in consumer.letters
        ],
        "frame_images": sorted(str(path) for path in image_paths.values()),
        "cover_image": str(cover_image),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    args = parser.parse_args(argv)
    result = build_cabinetry_consumer_document(
        args.out_dir,
        project_path=args.project,
        image_size=(args.width, args.height),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
