#!/usr/bin/env python3
"""Generate the linked five-file DV72 vanity package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from detailgen.packs import compile_project_file  # noqa: E402
from detailgen.packs.cabinetry.double_vanity_documents import (  # noqa: E402
    build_double_vanity_document_set,
)


DEFAULT_PROJECT = (
    ROOT / "tests/fixtures/cabinetry"
    / "floating_double_sink_four_drawer.project.yaml"
)
DEFAULT_OUT = ROOT / "outputs/floating_double_sink_four_drawer"


def generate_double_vanity_documents(
    project_path: str | Path = DEFAULT_PROJECT,
    out_dir: str | Path = DEFAULT_OUT,
) -> dict:
    project = compile_project_file(Path(project_path))
    documents = build_double_vanity_document_set(project)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sha256: dict[str, str] = {}
    for name, html in documents.items():
        path = out_dir / name
        path.write_text(html, encoding="utf-8")
        sha256[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"files": tuple(documents), "sha256": sha256}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    print(json.dumps(generate_double_vanity_documents(
        args.project, args.out_dir,
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
