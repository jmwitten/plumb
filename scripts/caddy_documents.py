#!/usr/bin/env python3
"""Generate the linked armchair-caddy technical document + assembly manual."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

import single_detail_report as SDR

from detailgen.rendering.caddy_stations import attach_caddy_stations
from detailgen.rendering.instruction_manual import render_instruction_manual_html
from detailgen.rendering.instruction_panels import build_instruction_manual
from detailgen.rendering.instruction_render import DEFAULT_SIZE, render_instruction_images
from detailgen.spec.compiler import compile_spec_file


DEFAULT_OUT_DIR = _REPO / "outputs" / "armchair_caddy"
TECHNICAL_BASENAME = "armchair_caddy_build_document.html"
MANUAL_BASENAME = "armchair_caddy_assembly_manual.html"
PREVIEW_NOTICE = "PREVIEW — NOT APPROVED FOR DELIVERY"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_caddy_document_pair(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    image_size: tuple[int, int] = DEFAULT_SIZE,
    spec_path: str | Path = SDR.CADDY_SPEC,
    preview: bool = False,
) -> dict:
    """Build both reciprocal documents and their content-keyed panel images."""
    spec_path = Path(spec_path)
    detail = compile_spec_file(spec_path)
    detail.validate()
    if preview:
        detail.require_modeling_approval()
    else:
        detail.require_delivery_ready()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    technical_path = out_dir / TECHNICAL_BASENAME
    manual_path = out_dir / MANUAL_BASENAME

    manual = build_instruction_manual(detail, TECHNICAL_BASENAME)
    if preview:
        manual = replace(
            manual,
            title=f"{PREVIEW_NOTICE} · {manual.title}",
            lede=f"{PREVIEW_NOTICE}. {manual.lede}",
        )
    manual = attach_caddy_stations(detail, manual)
    image_paths = render_instruction_images(
        detail, manual, out_dir / "instruction_panels", size=image_size)
    manual_path.write_text(
        render_instruction_manual_html(detail, manual, image_paths),
        encoding="utf-8")
    SDR.build_document(
        technical_path, spec_path=spec_path, preview=False,
        companion_href=MANUAL_BASENAME, compiled_detail=detail,
        instruction_manual=manual,
        document_notice=PREVIEW_NOTICE if preview else None)

    ordered_images = tuple(image_paths[index] for index in sorted(image_paths))
    return {
        "technical_path": str(technical_path),
        "manual_path": str(manual_path),
        "technical_sha256": _sha256(technical_path),
        "manual_sha256": _sha256(manual_path),
        "panel_count": len(manual.panels),
        "asset_keys": tuple(path.stem for path in ordered_images),
        "panel_images": tuple(str(path) for path in ordered_images),
        "preview": preview,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    parser.add_argument(
        "--preview", action="store_true",
        help="build an unmistakably marked review pair before delivery confirmation",
    )
    args = parser.parse_args(argv)
    result = build_caddy_document_pair(
        args.out_dir, image_size=(args.width, args.height), preview=args.preview)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
