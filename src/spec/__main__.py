"""``python -m detailgen.spec <spec.yaml>`` — compile a DetailSpec, validate it,
print the north-star metrics, and write the derivation/diagnostic report (P4).

    python -m detailgen.spec details/rock_anchor.spec.yaml
    python -m detailgen.spec details/rock_anchor.spec.yaml --report out.md
    python -m detailgen.spec details/rock_anchor.spec.yaml --render outputs/rock_anchor_spec

Exit status is non-zero if validation is not clean, so the command doubles as a
CI gate on a spec. ``--render`` goes through the gated ``Detail.render`` (a
single STEP by default — the spec's minimal honest subset; rich GLB/manifest
rendering stays with the imperative detail and is a documented seam)."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ..validation.coverage import coverage_matrix, render_headline_line
from .compiler import compile_spec
from .loader import load_spec_file
from .metrics import compute_metrics, format_metrics


def _imperative_sibling(spec_path: Path) -> Path:
    """The imperative detail this spec re-authors (for the LOC baseline):
    ``rock_anchor.spec.yaml`` -> ``rock_anchor.py`` beside it."""
    stem = spec_path.name.split(".")[0]
    return spec_path.with_name(f"{stem}.py")


def _write_report(detail, doc, spec_path: Path, out_path: Path, metrics: dict) -> None:
    report = detail.report
    log = detail.derivation_report()
    by_conf = Counter(f.confidence for f in log)
    lines = [
        f"# DetailSpec derivation report — {doc.name}",
        "",
        f"Compiled from `{spec_path}` by `detailgen.spec`. The spec declares only "
        "author-intended facts; every line below the authored dimensions was "
        "DERIVED by the compiler (placements from mates, bearings/overlaps/bonds/"
        "install-order from the declared Connections) and is recorded here with "
        "its provenance (P1/P4).",
        "",
        "## Result",
        # Reader-facing result leads with the per-family breakdown (owner directive
        # §3), derived from the coverage matrix; CLEAN is a demoted internal verdict.
        f"- **{render_headline_line(coverage_matrix(report))}**",
        f"- Internal verdict: "
        f"{'CLEAN — all checks pass' if report.ok else str(len(report.failures)) + ' FAILURES'}.",
        f"- {len(detail.assembly.parts)} parts placed; "
        f"{metrics['connections']} connections declared.",
        "",
        "## Specification compression",
        format_metrics(metrics),
        "",
        "## Derivation log",
        f"{len(log)} facts total — "
        + ", ".join(f"{n} {c}" for c, n in sorted(by_conf.items())) + ".",
        "",
        "| Confidence | Rule | Fact |",
        "|------------|------|------|",
    ]
    for f in log:
        fact = f.fact.replace("|", "\\|")
        lines.append(f"| {f.confidence} | `{f.rule}` | {fact} |")
    lines += [
        "",
        "## Bill of materials",
        "",
        "| Qty | Item | Material | Dimensions |",
        "|----:|------|----------|------------|",
    ]
    for r in detail.bom_table():
        lines.append(f"| {r['qty']} | {r['item']} | {r['material']} | {r['dimensions']} |")
    lines.append("")
    out_path.write_text("\n".join(lines))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="detailgen.spec", description=__doc__)
    ap.add_argument("spec", type=Path, help="path to a DetailSpec .yaml/.json")
    ap.add_argument("--report", type=Path, default=None,
                    help="write the derivation report here (default: alongside the spec)")
    ap.add_argument("--render", type=Path, default=None,
                    help="also export CAD artifacts (gated on a clean report)")
    args = ap.parse_args(argv)

    doc = load_spec_file(args.spec)
    detail = compile_spec(doc)
    report = detail.validate()

    print(f"DetailSpec: {doc.name}  ({args.spec})")
    print(f"  parts placed: {len(detail.assembly.parts)}")
    print(f"  validation:   {'CLEAN' if report.ok else str(len(report.failures)) + ' FAILURES'}")
    if not report.ok:
        for f in report.failures:
            print(f"    FAIL [{f.check}] {f.subject} — {f.detail}")

    metrics = compute_metrics(doc, detail, spec_path=args.spec,
                              imperative_path=_imperative_sibling(args.spec))
    print()
    print(format_metrics(metrics))

    report_path = args.report or args.spec.with_suffix(".derivation.md")
    _write_report(detail, doc, args.spec, report_path, metrics)
    print(f"\nderivation report -> {report_path}")

    if args.render is not None:
        out = detail.render(args.render)
        print(f"exported (gated) -> {out}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
