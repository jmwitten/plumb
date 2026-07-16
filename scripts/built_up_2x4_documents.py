#!/usr/bin/env python3
"""Generate the linked built-up-2x4 technical document and assembly manual."""

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

from detailgen.rendering.instruction_manual import render_instruction_manual_html
from detailgen.rendering.instruction_panels import build_instruction_manual
from detailgen.rendering.instruction_render import DEFAULT_SIZE, render_instruction_images
from detailgen.spec.compiler import compile_spec_file


DEFAULT_OUT_DIR = _REPO / "outputs" / "built_up_2x4"
TECHNICAL_BASENAME = "built_up_2x4_build_document.html"
MANUAL_BASENAME = "built_up_2x4_assembly_manual.html"
COMMISSIONING_BASENAME = "built_up_2x4_installation_and_commissioning.md"
PREVIEW_NOTICE = "PREVIEW — NOT APPROVED FOR DELIVERY"
MANUAL_TITLE = "Built-Up 2×4 — Illustrated Assembly Manual"
MANUAL_LEDE = (
    "This is one machine-checked build order from the validated construction "
    "process graph. Its phase boundary includes {declared_constraints} authored "
    "process-order constraints. Colored parts are current work, pale gray parts "
    "are already present, and numbered callouts identify the compiled parts. Use "
    "the linked technical document and commissioning sheet for the exact station "
    "chain. Structural capacity, composite action, use suitability, and code "
    "compliance remain UNKNOWN — NOT ANALYZED."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _commissioning_markdown(detail, *, preview: bool) -> str:
    ns = detail.namespace
    hardware_count = sum(
        1 for part in detail.assembly.parts if part.name.startswith("screw at ")
    )
    notice = f"> **{PREVIEW_NOTICE}**\n\n" if preview else ""
    stations = [
        float(ns["first_station"]) + index * float(ns["station_spacing"])
        for index in range(int(ns["station_count"]))
    ]
    station_text = ", ".join(f"{value:g}" for value in stations)
    return f"""# Built-Up 2×4 — Installation and Commissioning Sheet

{notice}Use this sheet with [{TECHNICAL_BASENAME}]({TECHNICAL_BASENAME}) and
[{MANUAL_BASENAME}]({MANUAL_BASENAME}). Dimensions govern over rendered scale.

## Live model facts

- Finished member length: **{float(ns['member_length']):g} in**
- Actual assembled section: **{float(ns['assembly_width']):g} × {float(ns['stud_depth']):g} in**
- Hardware count: **{hardware_count} screws**
- Representative screw envelope: **Ø {float(ns['screw_diameter']):g} × {float(ns['screw_length']):g} in**
- Modeled receiving-ply bite: **{float(ns['modeled_embedment']):g} in**
- Station rule: **{float(ns['first_station']):g} in first center, {float(ns['station_spacing']):g} in on center, {float(ns['final_station']):g} in final center**
- Centers from the reference end: **{station_text} in**

## Before driving

- [ ] Both nominal 2×4s are at least {float(ns['member_length']):g} inches long, straight, and free of unacceptable splits, decay, twist, or damage.
- [ ] Broad faces are paired together; one common reference end and faces A/B are marked.
- [ ] Ends and long edges are flush, and clamps hold the mating faces fully closed.
- [ ] All {hardware_count} centers are marked from the same datum; consecutive stations alternate face A / face B.
- [ ] Purchased screw, drive bit, coating, lumber-treatment compatibility, edge distances, and use conform to current manufacturer instructions.

## After driving

- [ ] Exactly {hardware_count} screw heads are present at the modeled centers.
- [ ] Heads are fully seated without crushing the lumber; no tip protrudes from the opposite face.
- [ ] Ends and long edges remain flush; the seam remains fully closed.
- [ ] No new split, tear-out, stripped head, or damaged fastener is present.
- [ ] The completed member remains acceptably straight and untwisted for its intended fit.
- [ ] Final actual section is verified where fit matters; this member is {float(ns['assembly_width']):g} × {float(ns['stud_depth']):g} inches, not a true 4×4.

## Mandatory hold

This commissioning sheet verifies conformance to the modeled geometry and owner-selected screw layout only. It is **not structural approval**. Species, grade, moisture, loads, supports, end connections, withdrawal, shear, composite action, capacity, use suitability, and code compliance are **UNKNOWN — NOT ANALYZED**. Obtain appropriate engineering and authority approval before any load-bearing or code-regulated use.

Installer: ____________________  Date: ____________________

Reviewed by: ____________________  Date: ____________________
"""


def build_built_up_2x4_document_pair(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    image_size: tuple[int, int] = DEFAULT_SIZE,
    spec_path: str | Path = SDR.BUILT_SPEC,
    preview: bool = False,
) -> dict:
    """Compile once and build the reciprocal technical/manual document pair."""
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
    commissioning_path = out_dir / COMMISSIONING_BASENAME

    manual = build_instruction_manual(
        detail,
        TECHNICAL_BASENAME,
        title=MANUAL_TITLE,
        basename=MANUAL_BASENAME,
        lede=MANUAL_LEDE,
    )
    manual = replace(
        manual,
        panels=tuple(
            replace(
                panel,
                instructions=tuple(
                    instruction.replace(
                        "with each proud.",
                        "with each head seated on the surface (proud, not countersunk).",
                    )
                    for instruction in panel.instructions
                ),
            )
            for panel in manual.panels
        ),
    )
    if preview:
        manual = replace(
            manual,
            title=f"{PREVIEW_NOTICE} · {manual.title}",
            lede=f"{PREVIEW_NOTICE}. {manual.lede}",
        )
    image_paths = render_instruction_images(
        detail, manual, out_dir / "instruction_panels", size=image_size
    )
    manual_path.write_text(
        render_instruction_manual_html(detail, manual, image_paths),
        encoding="utf-8",
    )
    SDR.build_document(
        technical_path,
        spec_path=spec_path,
        preview=False,
        companion_href=MANUAL_BASENAME,
        compiled_detail=detail,
        instruction_manual=manual,
        document_notice=PREVIEW_NOTICE if preview else None,
    )
    commissioning_path.write_text(
        _commissioning_markdown(detail, preview=preview), encoding="utf-8"
    )

    ordered_images = tuple(image_paths[index] for index in sorted(image_paths))
    return {
        "technical_path": str(technical_path),
        "manual_path": str(manual_path),
        "commissioning_path": str(commissioning_path),
        "technical_sha256": _sha256(technical_path),
        "manual_sha256": _sha256(manual_path),
        "commissioning_sha256": _sha256(commissioning_path),
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
        "--preview",
        action="store_true",
        help="build an unmistakably marked review pair before delivery confirmation",
    )
    args = parser.parse_args(argv)
    result = build_built_up_2x4_document_pair(
        args.out_dir,
        image_size=(args.width, args.height),
        preview=args.preview,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
