#!/usr/bin/env python
"""Re-freeze the CURRENT-DESIGN determinism baseline from the SPEC path (task A2).

``capture_frozen_truth.py`` froze the imperative details' LAST TESTIMONY at base
SHA 8088624. Milestone 4B deleted the imperative ``details/*.py``, so that script
can no longer run (it raises a teaching error). Task STRUCT (task #19) then
EVOLVED three fragments BY DESIGN, so their frozen corpus is now stale:

- ``platform``       — tree-end legs + pier blocks + per-post ground elevations,
  the DECLARED tree-apron cantilever, the real screened deck-notch clearance
  (2"), and the SUPPORT / EXISTING role declarations (deck walking_surface,
  boulder + piers ground, trunk self-grounded).
- ``tree_attachment``— trunk extended to the cable-anchor height (demonstration).
- ``trolley_launch`` — launch-hardware re-registration onto the real legs, the
  grab-bar re-derivation, and the zipline hardware declared ``existing``
  demonstration context (self-grounded).

A2 RE-FREEZE. This regenerates ``tests/baselines/frozen_truth/{platform,
tree_attachment,trolley_launch}.json`` from the SPEC path — the ONLY surviving
path. The corpus's MEANING SHIFTS from "imperative last testimony" to the
CURRENT-DESIGN determinism baseline: the compiled spec must reproduce it
byte-for-byte on every future build (that is what the *_spec / promote / evidence
oracles now lock). The imperative-era corpus stays retrievable at ``b52626b``.

``rock_anchor.json`` is NOT re-frozen (STRUCT did not evolve it) — it keeps its
imperative framing and its ``captured_at_sha`` from ``capture_frozen_truth.py``.
Because there is no imperative path to diverge from, ``content_fp`` equals
``content_fp_spec`` and ``content_fp_divergence`` is ``{}``.

``capture_frozen_truth.py`` is left UNTOUCHED (A2 condition 4): it is the
imperative-era record's generator; this is a distinct, spec-only generator.

Usage: ``python scripts/refreeze_from_spec.py`` (writes the 3 files + a summary).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"
OUT_DIR = ROOT / "tests" / "baselines" / "frozen_truth"

sys.path.insert(0, str(ROOT / "tests"))
import baseline_lib as bl  # noqa: E402
# Reuse the EXACT geom-fingerprint shape the imperative capture wrote, so a
# re-frozen file is byte-comparable field-for-field with the record it replaces.
from capture_frozen_truth import geom_fingerprint  # noqa: E402

#: The fragments STRUCT evolved — the ONLY ones re-frozen at A2. rock_anchor
#: was deliberately excluded then (unchanged; kept its imperative-era record)
#: — until task INSTALL v1 (schema arc), which grows EVERY Connection-bearing
#: detail's derivation log by one install-contract fact per fastener
#: role-group, so from that re-freeze on, the rock anchor's record is also
#: a current-design determinism baseline. The INSTALL axes arc re-froze
#: platform + rock_anchor again with a justified findings-set change: the
#: axis-1/axis-2 checks add install_termination/install_access findings per
#: contracted fastener (platform +164 incl. the two honest toe-screw
#: install-order UNKNOWNs; rock_anchor +8, all PASS), and
#: FaceMountHanger.edges() now declares the header-screws-before-hung-member
#: sequence (+4 derivation facts per hanger connection on the platform).
#: tree_attachment / trolley_launch declare no fastener contracts and are
#: unchanged by that arc. The imperative-era testimony stays retrievable at
#: b52626b.
EVOLVED = ("platform", "tree_attachment", "trolley_launch", "rock_anchor")


def _base_sha() -> str:
    """The re-freeze base commit — the merge-base with master, so the stamp names
    the master SHA this corpus was re-frozen against (not a liveness commit)."""
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "HEAD", "master"],
            check=True, capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError:
        return subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()


def _build_spec(slug: str):
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    detail = compile_spec(load_spec_file(DETAILS / f"{slug}.spec.yaml"))
    detail.validate()
    return detail


def capture(slug: str, sha: str) -> dict:
    detail = _build_spec(slug)
    report = detail.report
    bom = detail.bom_table()
    fp = bl.content_fingerprint(detail)
    return {
        "_doc": (
            f"CURRENT-DESIGN determinism baseline for details/{slug}.spec.yaml, "
            f"re-frozen from the SPEC path at base SHA {sha} by "
            f"scripts/refreeze_from_spec.py (task STRUCT #19 / addendum A2). The "
            f"imperative path is gone (milestone 4B); this corpus IS the canonical "
            f"record the compiled spec must reproduce byte-for-byte. The "
            f"imperative-era testimony is retrievable at b52626b. Regenerate only "
            f"with a justified, reviewed diff: python scripts/refreeze_from_spec.py."),
        "captured_at_sha": sha,
        "name": detail.name,
        "ok": bool(report.ok),
        "counts": {
            "parts": len(detail.assembly.parts),
            "bom_rows": len(bom),
            "derivation_log": len(detail.derivation_log),
            "formalized_stubs": sum(
                1 for r in bom if r.get("stub_of") is not None),
        },
        "geom_fingerprint": geom_fingerprint(detail),
        "findings": sorted(
            [f.check, f.subject, bool(f.passed)] for f in report.findings),
        "by_kind": bl.by_kind(report),
        "bom": bom,
        # No imperative path to diverge from: content_fp == content_fp_spec, and
        # the divergence record is empty by construction (spec vs itself).
        "content_fp": fp,
        "content_fp_spec": fp,
        "content_fp_divergence": {},
        "findings_fp": bl.findings_fingerprint(report),
        "connection_kind_types": sorted(
            {type(c.kind).__name__ for c in detail.connections()}),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sha = _base_sha()
    for slug in EVOLVED:
        record = capture(slug, sha)
        (OUT_DIR / f"{slug}.json").write_text(bl.dumps(record))
        c = record["counts"]
        print(f"{slug:16s} parts={c['parts']:3d} bom={c['bom_rows']:2d} "
              f"deriv={c['derivation_log']:3d} findings={len(record['findings']):3d} "
              f"ok={record['ok']} content_fp={record['content_fp'][:12]} -> {slug}.json")
    print(f"\nre-frozen from the SPEC path at base SHA {sha} "
          f"(capture_frozen_truth.py untouched)")


if __name__ == "__main__":
    main()
