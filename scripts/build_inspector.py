#!/usr/bin/env python3
"""Emit the Inspector Mode HTML for a detail (task INSPECTOR).

ONE self-contained HTML file — the compiler-as-IDE view over a construction
detail: click a component, a panel answers the four questions (what is it / why
is it here / how do we know it's correct / what depends on it), every word read
from the payload the compiler emits (see ``src/rendering/inspector.py``). Opens
from ``file://`` with no server.

Run:  .venv/bin/python scripts/build_inspector.py
Out:  outputs/inspector/rock_anchor_inspector.html

The detail is loaded by compiling its ``details/<name>.spec.yaml`` through the
spec compiler (task 4B-3 rewire); the imperative ``details/<name>.py`` is no
longer imported. The emitted HTML is byte-identical to the ``.py``-built
document (the spec reproduces the detail at parity).
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"
OUT_DIR = ROOT / "outputs" / "inspector"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("detail", nargs="?", default="rock_anchor",
                    help="detail spec name under details/ (default rock_anchor)")
    ap.add_argument("-o", "--out", default=None, help="output HTML path")
    args = ap.parse_args()

    from detailgen.rendering.inspector import emit_inspector_html
    from detailgen.spec.compiler import compile_spec_file

    detail = compile_spec_file(DETAILS / f"{args.detail}.spec.yaml")
    out = Path(args.out) if args.out else OUT_DIR / f"{args.detail}_inspector.html"

    written = emit_inspector_html(detail, out, glb_work_dir=OUT_DIR / "_glb")
    size_kb = written.stat().st_size / 1024
    print(f"Inspector emitted: {written}  ({size_kb:.0f} KB)")
    print(f"Open it:  file://{written.resolve()}")


if __name__ == "__main__":
    main()
