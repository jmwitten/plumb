#!/usr/bin/env python3
"""Generate the self-contained DV72 floating double-vanity coordination study."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from detailgen.packs import compile_project_file  # noqa: E402
from detailgen.packs.cabinetry.double_vanity_document import (  # noqa: E402
    build_double_vanity_study_html,
)


DEFAULT_PROJECT = (
    ROOT / "tests/fixtures/cabinetry"
    / "floating_double_sink_four_drawer.project.yaml"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs/floating_double_sink_four_drawer"
    / "floating_double_sink_four_drawer_coordination_study.html"
)


def generate_double_vanity_study(
    project_path: str | Path = DEFAULT_PROJECT,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    project = compile_project_file(Path(project_path))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_double_vanity_study_html(project), encoding="utf-8"
    )
    return output_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    print(generate_double_vanity_study(args.project, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
