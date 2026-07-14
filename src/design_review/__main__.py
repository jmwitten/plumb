"""Validate, report, and gate precedent-first design reviews."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .gate import DesignReviewGateError, governance_for_review
from .loader import load_design_review_file
from .report import render_design_review_html
from .schema import DesignReviewSchemaError
from .validation import validate_design_review


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="detailgen.design_review")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("review", type=Path)
    report = commands.add_parser("report")
    report.add_argument("review", type=Path)
    report.add_argument("--output", type=Path, required=True)
    gate = commands.add_parser("gate")
    gate.add_argument("review", type=Path)
    gate.add_argument("--stage", choices=("modeling", "delivery"), required=True)
    gate.add_argument("--selected-concept")
    gate.add_argument("--spec-json", type=Path)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        doc = load_design_review_file(args.review)
        result = validate_design_review(doc)
        if args.command == "validate":
            for finding in result.blocking:
                print(
                    f"[{finding.code}] {finding.path}: {finding.message}",
                    file=sys.stderr,
                )
            return 0 if result.ok else 1
        selected = (
            getattr(args, "selected_concept", None)
            or doc.decision.selected_concept
        )
        spec_payload = None
        spec_json = getattr(args, "spec_json", None)
        if spec_json is not None:
            spec_payload = json.loads(spec_json.read_text())
        governance = governance_for_review(
            doc,
            selected_concept=selected,
            spec_payload=spec_payload,
        )
        if args.command == "report":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                render_design_review_html(doc, result, governance),
                encoding="utf-8",
            )
            return 0
        if args.stage == "modeling":
            governance.require_modeling_approval()
        else:
            governance.require_delivery_confirmation()
        return 0
    except (DesignReviewSchemaError, DesignReviewGateError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
