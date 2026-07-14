#!/usr/bin/env python3
"""Generate the linked DB40 technical document and illustrated manual."""

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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_cabinetry_document_pair(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    project_path: str | Path = DEFAULT_PROJECT,
    image_size: tuple[int, int] = DEFAULT_SIZE,
) -> dict:
    """Compile once, then project both reciprocal reader surfaces."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    technical_path = out_dir / TECHNICAL_BASENAME
    manual_path = out_dir / MANUAL_BASENAME

    project = compile_project_file(Path(project_path))
    project.require_fabrication_release()
    manual = build_cabinetry_instruction_manual(
        project,
        technical_href=TECHNICAL_BASENAME,
        basename=MANUAL_BASENAME,
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
    CPR.generate_released_build_document(
        project,
        technical_path,
        companion_href=MANUAL_BASENAME,
        instruction_manual=manual,
    )

    ordered_images = tuple(image_paths[index] for index in sorted(image_paths))
    return {
        "technical_path": str(technical_path),
        "manual_path": str(manual_path),
        "technical_sha256": _sha256(technical_path),
        "manual_sha256": _sha256(manual_path),
        "panel_count": len(manual.panels),
        "asset_keys": tuple(path.stem for path in ordered_images),
        "panel_images": tuple(str(path) for path in ordered_images),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    args = parser.parse_args(argv)
    result = build_cabinetry_document_pair(
        args.out_dir,
        project_path=args.project,
        image_size=(args.width, args.height),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
