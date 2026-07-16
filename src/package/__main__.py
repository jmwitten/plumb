"""Command line entry point for complete generic package generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import PackageRequest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a complete Plumb construction package"
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    release = parser.add_mutually_exclusive_group()
    release.add_argument("--preview", action="store_true")
    release.add_argument("--delivery", action="store_true")
    parser.add_argument("--tests-skipped", metavar="REASON")
    args = parser.parse_args(argv)

    request = PackageRequest(
        args.spec,
        args.out,
        release="delivery" if args.delivery else "preview",
        tests_status="skipped" if args.tests_skipped else "not-run",
        tests_reason=(
            args.tests_skipped
            or "package generation does not execute tests"
        ),
    )
    from .builder import build_package

    result = build_package(request)
    print(json.dumps(result.manifest(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
