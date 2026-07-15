#!/usr/bin/env python3
"""Generate the DB40 homeowner cutting guide (separate review surface).

Writes ``frameless_three_drawer_40_cutting_guide.html`` next to — never
instead of — the accepted DB40 document set. The fabrication packet stays
the mm-exact shop alternate.
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

from detailgen.packs import compile_project_file  # noqa: E402
from detailgen.packs.cabinetry.cutting_guide import (  # noqa: E402
    build_cabinetry_cutting_guide,
    cutting_action_frames,
    cutting_guide_diagrams,
    cutting_kit_groups,
    cutting_panels_manual,
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
CUTTING_BASENAME = "frameless_three_drawer_40_cutting_guide.html"
CONSUMER_BASENAME = "frameless_three_drawer_40_consumer_manual.html"
TECHNICAL_BASENAME = "frameless_three_drawer_40_build_document.html"
FABRICATION_BASENAME = "frameless_three_drawer_40_fabrication_packet.html"


def build_cabinetry_cutting_document(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    project_path: str | Path = DEFAULT_PROJECT,
    image_size: tuple[int, int] = DEFAULT_SIZE,
) -> dict:
    """Compile once and render the standalone DB40 cutting guide."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / CUTTING_BASENAME

    project = compile_project_file(Path(project_path))
    project.require_fabrication_release()

    panels_manual = cutting_panels_manual(project)
    frames = cutting_action_frames(panels_manual, project)
    guide = build_cabinetry_cutting_guide(
        project,
        basename=CUTTING_BASENAME,
        related_documents=(
            RelatedDocumentLink("Assembly manual (next document)",
                                CONSUMER_BASENAME),
            RelatedDocumentLink("Fabrication packet (exact mm, shop copy)",
                                FABRICATION_BASENAME),
            RelatedDocumentLink("Review & installation sheet",
                                TECHNICAL_BASENAME),
        ),
    )

    image_dir = out_dir / "cutting_panels"
    image_paths = render_frame_images(
        project.detail, panels_manual, frames, image_dir,
        size=image_size, style="high_contrast")
    cover_image = render_cover_image(
        project.detail, panels_manual, image_dir,
        size=image_size, style="high_contrast")

    diagrams_by_id = cutting_guide_diagrams(panels_manual)
    kit_groups = cutting_kit_groups(project)

    # No embedded 3D viewer here: its explode/milestone semantics describe
    # assembly arrivals, and every cutting-guide part exists from breakdown
    # onward. The linked assembly manual carries the interactive model.
    output_path.write_text(
        render_consumer_manual_html(
            project.detail, guide, image_paths,
            cover_image=cover_image,
            inventory_groups=kit_groups,
            parts_heading="Wood list — pre-band cut sizes",
            diagrams=diagrams_by_id,
            # The dimensioned drawing is this document's payload (owner
            # directive: illustrations); it takes the primary column and
            # the 3D scene becomes the small orientation thumbnail.
            extra_style=(
                ".frame .scene-figure { flex: 0 1 30%; }"
                ".op-diagram { flex: 1 1 66%; }"
                ".op-diagram svg { max-height: 2.1in; }"
                ".frame img { max-height: 1.9in; }"
                # The two drawer-strip diagrams share one crowded sheet;
                # their content is a short strip and fits a smaller frame.
                '.op-diagram[data-diagram-id="cut-drawer-bottom-grooves"]'
                " svg,"
                '.op-diagram[data-diagram-id="cut-drawer-side-joinery"]'
                " svg { max-height: 1.7in; }"),
        ),
        encoding="utf-8",
    )

    return {
        "cutting_guide_path": str(output_path),
        "cutting_guide_sha256": hashlib.sha256(
            output_path.read_bytes()).hexdigest(),
        "page_count": len(guide.pages),
        "frame_count": sum(len(page.frames) for page in guide.pages),
        # Diagram titles and captions are reader-visible prose, so both
        # count; the dense dimension notes are layout data and do not.
        "visible_instructional_words": visible_instructional_words(
            guide,
            extra_texts=tuple(
                text
                for frame in frames for d in frame.detail_diagram_ids
                for text in (diagrams_by_id[d].title,
                             diagrams_by_id[d].caption))),
        "kit_groups": [
            f"{heading}: {len(rows)} rows" for heading, rows in kit_groups],
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
    result = build_cabinetry_cutting_document(
        args.out_dir,
        project_path=args.project,
        image_size=(args.width, args.height),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
