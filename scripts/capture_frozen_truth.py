#!/usr/bin/env python
"""Freeze the imperative details' LAST TESTIMONY into tests/baselines/frozen_truth/.

Milestone 4B step 4a. Today the five equivalence oracles prove
``spec == imperative`` by building BOTH paths live. Step 4B-4b will DELETE the
four imperative ``details/*.py`` files, which removes the oracles' reference
side. Before that can happen, the imperative truth must be captured into
committed baselines so the oracles can be converted to assert
``spec == frozen corpus`` instead.

This script imports each of the four imperative details by file path (the same
``importlib`` machinery the oracle tests use), builds and validates each, and
writes one deterministic JSON per detail into ``tests/baselines/frozen_truth/``.
Each file captures EVERYTHING the five oracles compare between the two paths:

- ``geom_fingerprint``  — per placed part: world origin, solid volume, bbox
  (the ``_fingerprint`` shape the ``*_spec`` oracles share; transforms/geometry).
- ``findings``          — every validation finding as (check, subject, passed),
  sorted; ``by_kind`` and ``ok`` alongside. (The oracles diff this multiset;
  finding DETAIL text is frozen through ``content_fp``/``findings_fp`` below, so
  it is not duplicated here.)
- ``bom``               — the full ``bom_table()`` (every field the oracles diff,
  including the documented inch->mm ``length_mm`` residual, compared to 1e-6).
- ``content_fp``        — ``baseline_lib.content_fingerprint`` of the IMPERATIVE
  path (the PROMOTE full-content hash: findings + derivation facts + BOM + part
  transforms). This is the imperative testimony.
- ``content_fp_spec``   — the SAME hash of the compiled SPEC path. This is the
  fingerprint the PROMOTE oracle locks going forward, because after 4B-4b the
  spec is the only surviving path. For three of the four details it EQUALS
  ``content_fp``; for the platform it differs, and ``content_fp_divergence``
  enumerates exactly why (no divergence is hidden — see below).
- ``content_fp_divergence`` — a full accounting of every ``content_lines``
  difference between the imperative and the spec at freeze time: reworded
  derivation-fact ``assumptions`` prose (semantically equal, byte-different) and
  the sub-1e-6 mm inch->mm ``length_mm`` residual that ``content_fingerprint``
  does not round. Empty ``{}`` when the two paths hash identically.
- ``findings_fp``       — ``baseline_lib.findings_fingerprint`` (the EVIDENCE
  byte-level validation-outcome hash).
- ``connection_kind_types`` — the connection ``kind`` class names the detail
  resolves to (the PROMOTE library-types identity check).
- ``counts``            — parts / bom_rows / derivation_log / formalized_stubs.

This corpus is the imperative path's LAST TESTIMONY, captured at the base SHA
stamped in each file (``captured_at_sha``). Regenerate it ONLY while the
imperative ``.py`` still exist and ONLY with a justified, reviewed diff. After
4B-4b removes them, this script cannot re-run: it raises a teaching error naming
the reason rather than silently producing an empty or partial corpus.

Usage: ``python scripts/capture_frozen_truth.py`` (writes the corpus, prints a
per-detail summary).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"
OUT_DIR = ROOT / "tests" / "baselines" / "frozen_truth"

# baseline_lib is the single source of truth for the fingerprint hashing the
# migrated oracles share; reuse it so the frozen values are byte-identical to
# what the tests compute live.
sys.path.insert(0, str(ROOT / "tests"))
import baseline_lib as bl  # noqa: E402

#: slug -> (class name, imperative .py filename). Order fixed for deterministic
#: output. rock_anchor has no *_spec oracle but the evidence oracle freezes it.
IMPERATIVE = {
    "platform": ("Platform", "platform.py"),
    "rock_anchor": ("RockAnchor", "rock_anchor.py"),
    "tree_attachment": ("TreeAttachment", "tree_attachment.py"),
    "trolley_launch": ("TrolleyLaunch", "trolley_launch.py"),
}

#: slug -> compiled spec filename (all four ship a spec fragment).
SPEC = {slug: f"{slug}.spec.yaml" for slug in IMPERATIVE}


def _base_sha() -> str:
    """The base commit the corpus is captured at — the merge-base with master,
    so it names 8088624 (the post-TREEDOC + post-4B-3 base) regardless of any
    liveness/incremental commits on the capture branch."""
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "HEAD", "master"],
            check=True, capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError:
        return subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()


def _load_imperative(slug: str):
    cls_name, rel = IMPERATIVE[slug]
    path = DETAILS / rel
    if not path.exists():
        raise SystemExit(
            f"capture_frozen_truth: the imperative detail {path.name!r} is gone "
            f"({path} does not exist). This script freezes the imperative path's "
            f"testimony and can ONLY run while the details/*.py still exist. "
            f"After milestone 4B-4b removed them, the frozen corpus in "
            f"{OUT_DIR.relative_to(ROOT)} IS the canonical record — do not "
            f"regenerate it; the spec path is now the only path.")
    spec = importlib.util.spec_from_file_location(f"{slug}_frozen_capture", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{slug}_frozen_capture"] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, cls_name)()


def _build_spec(slug):
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    detail = compile_spec(load_spec_file(DETAILS / SPEC[slug]))
    detail.validate()
    return detail


def content_fp_divergence(imp, spec) -> dict:
    """Full, honest accounting of every ``content_lines`` difference between the
    imperative and the compiled spec at freeze time — the reason a detail's
    ``content_fp`` and ``content_fp_spec`` differ. Categorized so nothing is
    hidden behind the hash: reworded derivation-fact ``assumptions`` prose
    (semantically equal, byte-different), the sub-1e-6 mm inch->mm ``length_mm``
    residual ``content_fingerprint`` leaves unrounded, and any OTHER line the two
    paths disagree on (which would be a real, unexplained divergence to escalate).
    Returns ``{}`` when the two paths hash identically."""
    li, ls = bl.content_lines(imp), bl.content_lines(spec)
    if li == ls:
        return {}
    only_i = sorted(set(li) - set(ls))
    only_s = sorted(set(ls) - set(li))

    # content_lines D format, after split("|"): [0]=D [1]=fact [2]=connection
    # [3]=rule [4]=confidence [5]=source_type [6]=assumptions [7]=subjects.
    def _parse_d(line):
        return line.split("|")

    di = {tuple(_parse_d(l)[1:4]): _parse_d(l) for l in only_i if l[0] == "D"}
    ds = {tuple(_parse_d(l)[1:4]): _parse_d(l) for l in only_s if l[0] == "D"}
    assumption_prose = other_d = 0
    # A fact key present on only ONE side is an ADDED/REMOVED derivation fact, not
    # a reword — count it as unexplained so a future key drift can never hide as a
    # silently-uncounted line (the zero-unexplained guard in the promote oracle
    # then fails loudly). Currently 0 on both sides (prose-only reword).
    other_d += len(set(di) ^ set(ds))
    for k in set(di) & set(ds):
        a, b = di[k], ds[k]
        # only the assumptions field (6) moved; confidence/source_type/subjects hold
        if (a[4] == b[4] and a[5] == b[5] and a[7] == b[7] and a[6] != b[6]):
            assumption_prose += 1
        else:
            other_d += 1

    def _parse_b(line):  # B|item|qty|material|dims|source|assumptions|length_mm|stub_of|ids
        return line.split("|")
    bi = sorted(l for l in only_i if l[0] == "B")
    bs = sorted(l for l in only_s if l[0] == "B")
    length_residual = []
    other_b = 0
    for a, b in zip(bi, bs):
        fa, fb = _parse_b(a), _parse_b(b)
        diff = [i for i, (x, y) in enumerate(zip(fa, fb)) if x != y]
        if diff == [7]:   # only length_mm
            try:
                if abs(float(fa[7]) - float(fb[7])) <= 1e-6:
                    length_residual.append([fa[1], fa[7], fb[7]])
                    continue
            except ValueError:
                pass
        other_b += 1

    other_kinds = [l[0] for l in only_i if l[0] not in ("D", "B")]
    note = (
        "content_fp (imperative) and content_fp_spec differ ONLY by: "
        f"({assumption_prose}) derivation facts whose `assumptions` prose the spec "
        "reworded — semantically identical, byte-different; the imperative wording "
        "references \"module constants' docstring\", a pointer into the .py that "
        "4B-4b deletes, so the spec wording is the correct one for the surviving "
        f"world. Plus ({len(length_residual)}) BOM rows differing only in the "
        "sub-1e-6 mm inch->mm length_mm float residual that content_fingerprint "
        "does not round (baseline_lib is out of 4B-4a's ownership; logged as a "
        "known hazard). Fact keys, confidence, source_type, subjects, geometry, "
        "findings and by_kind all match. The PROMOTE oracle locks content_fp_spec "
        "(the canonical path post-4B-4b); this field keeps the imperative value "
        "and the exact gap permanently visible. See task-4b4a-report.md.")
    return {
        "_note": note,
        "assumption_prose_facts": assumption_prose,
        "length_mm_residual_rows": length_residual,
        "unexplained_d_lines": other_d,
        "unexplained_b_lines": other_b,
        "unexplained_other_lines": sorted(set(other_kinds)),
    }


def geom_fingerprint(detail) -> dict:
    """Per placed part, by name: world origin + volume + bbox — the API-agnostic,
    orientation-sensitive ``_fingerprint`` the ``*_spec`` oracles share. Floats
    kept at full repr precision (JSON round-trips doubles exactly); the converted
    oracle compares to this with the oracle's own transform tolerance."""
    out = {}
    for p in detail.assembly.parts:
        wp = p.world_solid()
        solids = wp.vals()
        vol = sum(s.Volume() for s in solids)
        bb = (wp.combine().objects[0].BoundingBox() if len(solids) > 1
              else solids[0].BoundingBox())
        out[p.name] = [
            list(p.world_frame.origin),
            vol,
            [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
        ]
    return out


def capture(slug: str, sha: str) -> dict:
    detail = _load_imperative(slug)
    report = detail.validate()
    bom = detail.bom_table()
    spec_detail = _build_spec(slug)
    record = {
        "_doc": (
            f"LAST TESTIMONY of the imperative details/{IMPERATIVE[slug][1]}, "
            f"frozen at base SHA {sha}. The compiled details/{slug}.spec.yaml "
            f"must reproduce every field here to the oracle's tolerances. "
            f"Regenerate only while the .py exists, only with a justified diff: "
            f"`python scripts/capture_frozen_truth.py`."),
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
            [f.check, f.subject, bool(f.passed)]
            for f in report.findings),
        "by_kind": bl.by_kind(report),
        "bom": bom,
        "content_fp": bl.content_fingerprint(detail),
        "content_fp_spec": bl.content_fingerprint(spec_detail),
        "content_fp_divergence": content_fp_divergence(detail, spec_detail),
        "findings_fp": bl.findings_fingerprint(report),
        "connection_kind_types": sorted(
            {type(c.kind).__name__ for c in detail.connections()}),
    }
    return record


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sha = _base_sha()
    for slug in IMPERATIVE:
        record = capture(slug, sha)
        path = OUT_DIR / f"{slug}.json"
        path.write_text(bl.dumps(record))
        c = record["counts"]
        div = record["content_fp_divergence"]
        div_note = "spec==imp" if not div else (
            f"spec!=imp ({div['assumption_prose_facts']} prose facts, "
            f"{len(div['length_mm_residual_rows'])} len residual rows)")
        print(f"{slug:16s} parts={c['parts']:3d} bom={c['bom_rows']:2d} "
              f"deriv={c['derivation_log']:3d} findings={len(record['findings']):3d} "
              f"content_fp={record['content_fp'][:12]} [{div_note}] -> {path.name}")
    print(f"\nfrozen at base SHA {sha}")


if __name__ == "__main__":
    main()
