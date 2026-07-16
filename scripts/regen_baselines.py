#!/usr/bin/env python
"""Regenerate the committed test baselines from the live model (ARCH0).

This is the ONLY thing that rewrites ``tests/baselines/**``. A normal
``pytest`` run reads those files; it never regenerates them. Regenerating is a
deliberate, reviewable act: run this, then ``git diff`` the baselines and
confirm every change is exactly what you intended.

Usage:
    python scripts/regen_baselines.py            # rewrite the committed baselines
    python scripts/regen_baselines.py --check    # fail if any baseline is stale
                                                  # (no writes; for CI)

Annotated surface — ``site_divergence``: each pinned finding carries a ``note``
(its deferred-design justification). Regeneration PRESERVES the note of every
finding whose (check, subject) is unchanged, and FLAGS findings that appeared or
disappeared: a NEW finding is written with a ``TODO-JUSTIFY`` placeholder note
(which ``tests/test_baselines.py`` fails on, so you cannot commit an
un-annotated finding); a REMOVED finding's note is dropped and reported.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import baseline_lib as bl  # noqa: E402

#: Placeholder note a regen writes for a NEW pinned finding it cannot justify.
#: test_baselines.py fails while any note equals this, so an un-annotated
#: finding cannot be committed.
TODO_NOTE = "TODO-JUSTIFY"

SITE_DIVERGENCE_DOC = (
    "The pinned site divergence set: every open FAILURE the compiled site model "
    "surfaces, each with the justification for why it is expected (deferred "
    "design). Exact-set-asserted by test_site_model.py; regenerate with "
    "`python scripts/regen_baselines.py` and review the diff — never hand-edit."
)


def stale_baseline_names(
    generated_dir: Path, source_dir: Path
) -> tuple[str, ...]:
    """Name every JSON baseline missing or byte-different on either side."""
    generated = {path.name: path for path in Path(generated_dir).glob("*.json")}
    committed = {path.name: path for path in Path(source_dir).glob("*.json")}
    return tuple(
        name
        for name in sorted(set(generated) | set(committed))
        if name not in generated
        or name not in committed
        or generated[name].read_bytes() != committed[name].read_bytes()
    )


def merge_site_divergence(
    pairs: list[dict], source_dir: Path
) -> tuple[dict, list, list]:
    """Purely merge live finding rows with committed human annotations."""
    old_notes: dict = {}
    src = source_dir / "site_divergence.json"
    if src.exists():
        for f in json.loads(src.read_text()).get("findings", []):
            old_notes[(f["check"], f["subject"])] = f.get("note", "")

    live_keys = {(p["check"], p["subject"]) for p in pairs}
    findings, new_keys = [], []
    for p in pairs:
        key = (p["check"], p["subject"])
        note = old_notes.get(key)
        if not note:
            note = TODO_NOTE
            new_keys.append(key)
        findings.append({"check": p["check"], "subject": p["subject"], "note": note})
    removed_keys = [k for k in old_notes if k not in live_keys]

    data = {"_doc": SITE_DIVERGENCE_DOC, "findings": findings}
    return data, new_keys, removed_keys


def _compute_site_divergence(source_dir: Path) -> tuple[dict, list, list]:
    """Load live divergence pairs, then merge committed annotations."""
    return merge_site_divergence(bl.site_divergence_pairs(), source_dir)


def regenerate(target_dir: Path, source_dir: Path = bl.BASELINE_DIR) -> dict:
    """Write every baseline into ``target_dir``. Annotation notes are read from
    ``source_dir`` (the committed baselines), so regenerating into a temp dir
    still preserves the human notes — that is what the round-trip test relies on.
    Returns a small summary (new/removed pinned findings)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for name, fn in bl.SIMPLE_SURFACES.items():
        bl.write_baseline(name, fn(), target_dir=target_dir)
    data, new_keys, removed_keys = _compute_site_divergence(source_dir)
    bl.write_baseline("site_divergence", data, target_dir=target_dir)
    return {"new": new_keys, "removed": removed_keys}


def _print_summary(summary: dict) -> None:
    for key in summary["new"]:
        print(f"  NEW pinned finding (needs a note): {key}", file=sys.stderr)
    for key in summary["removed"]:
        print(f"  REMOVED pinned finding (note dropped): {key}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Scoped mode (INCR-5) — regenerate only the baselines an edit's affected region
# reaches, gated by the self-verify check. BEHIND A FLAG; the default path above
# is byte-for-byte unchanged (flipping the default is the owner's call, design Q3).
# --------------------------------------------------------------------------- #
#: The five golden-bearing details, in the world the consumer scopes over.
_WORLD_SLUGS = ("platform", "rock_anchor", "tree_attachment", "trolley_launch", "site")


def _world_from(base_dir: Path) -> dict:
    """Compile the whole golden-bearing world from a ``details/`` directory."""
    from detailgen.spec.compiler import compile_spec_file
    from detailgen.spec.site import compile_site_file
    world = {}
    for slug in _WORLD_SLUGS[:-1]:
        d = compile_spec_file(base_dir / f"{slug}.spec.yaml"); d.validate()
        world[slug] = d
    site = compile_site_file(base_dir / "site.spec.yaml"); site.validate()
    world["site"] = site
    return world


def _materialize_ref(ref: str, dest: Path) -> Path:
    """Extract ``<ref>:details/`` into ``dest`` and return the details directory —
    the base revision the working tree is diffed against. Read-only on git."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(bl.REPO), "archive", ref, "details"],
        check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    return dest / "details"


def _run_gate(ref: str, work_dir: Path):
    """Build the (base=ref, new=working-tree) world and run the AC2 self-verify gate.
    Returns the :class:`SelfVerify` result."""
    from detailgen.incremental.scoped_regen import self_verify
    base_dir = _materialize_ref(ref, work_dir)
    base_world = _world_from(base_dir)
    new_world = _world_from(bl.DETAILS)
    bw = {s: (base_world[s], base_world[s]) for s in base_world}
    nw = {s: (base_world[s], new_world[s]) for s in base_world}
    return self_verify(bw, nw, bl.content_lines)


def _print_scoped_report(ref: str, sv) -> None:
    scoped = sv.scoped
    churn = scoped.churn()
    print(f"Scoped regeneration vs {ref}:", file=sys.stderr)
    print(f"  self-verify: {'PASS' if sv.passed else 'FAIL'} "
          f"(byte-equal to whole-world regen, attribution sound)", file=sys.stderr)
    print(f"  regenerate : {', '.join(scoped.regenerated_slugs()) or '(none)'}",
          file=sys.stderr)
    print(f"  reuse      : {', '.join(scoped.reused_slugs()) or '(none)'}",
          file=sys.stderr)
    print(f"  churn      : {churn['scoped_regenerated']}/{churn['details']} details "
          f"regenerate ({churn['reused']} reused); "
          f"{churn['semantic_changed_lines']} semantic line(s) changed, "
          f"{churn['renumbered_lines']} positional-renumber line(s)", file=sys.stderr)
    for slug in scoped.regenerated_slugs():
        d = scoped.details[slug]
        top = d.attribution.attributed[:3]
        who = ", ".join(sorted({m for _, m in top}))
        print(f"    {slug}: {d.semantic_changed_lines} semantic line(s) attributed "
              f"(e.g. {who})", file=sys.stderr)
    if not sv.passed:
        for slug in sv.mismatched_slugs:
            print(f"  MISMATCH {slug}: scoped golden != whole-world golden",
                  file=sys.stderr)
        for slug in sv.anomaly_slugs:
            lines = scoped.details[slug].attribution.anomalies[:5]
            print(f"  ANOMALY {slug}: {len(lines)} unattributable changed line(s): "
                  f"{[l[:70] for l in lines]}", file=sys.stderr)


def _scoped_detail_counts(regenerated: set, source_dir: Path) -> dict:
    """``detail_counts`` scoped by region: recompute the entries of in-region details;
    preserve out-of-region entries verbatim from the committed baseline. Because the
    self-verify gate has passed, an out-of-region detail is byte-unchanged, so its
    preserved entry equals a whole-world recompute — the scoping is provably lossless,
    it just leaves the untouched details' lines out of the diff."""
    fresh = bl.compute_detail_counts()
    committed = json.loads((source_dir / "detail_counts.json").read_text())
    out = {"_doc": fresh["_doc"]}
    for slug in _WORLD_SLUGS:
        if slug in regenerated or slug not in committed:
            out[slug] = fresh[slug]
        else:
            out[slug] = committed[slug]      # untouched — kept out of the diff
    return out


def _scoped_regenerate(sv, source_dir: Path = bl.BASELINE_DIR) -> None:
    """Write the baselines an edit's region reaches, leaving the rest byte-stable.
    ``detail_counts`` is written per-entry (in-region details only); the site-governed
    surfaces (``slice_accounting``, ``site_divergence``) are rewritten only when the
    site is in the region — untouched otherwise."""
    regenerated = set(sv.scoped.regenerated_slugs())
    bl.write_baseline("detail_counts",
                      _scoped_detail_counts(regenerated, source_dir))
    if "site" in regenerated:
        bl.write_baseline("slice_accounting", bl.compute_slice_accounting())
        data, new_keys, removed_keys = _compute_site_divergence(source_dir)
        bl.write_baseline("site_divergence", data)
        _print_summary({"new": new_keys, "removed": removed_keys})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="fail if committed baselines are stale; write nothing")
    ap.add_argument("--scoped-from", metavar="REF",
                    help="INCR-5 scoped mode: regenerate only the baselines whose "
                         "detail has a non-empty affected region between git REF "
                         "(base) and the working tree (new). Runs the self-verify "
                         "gate first and writes NOTHING if it fails. Default (omitted) "
                         "is the unchanged whole-world regeneration.")
    args = ap.parse_args(argv)

    if args.scoped_from:
        with tempfile.TemporaryDirectory() as tmp:
            sv = _run_gate(args.scoped_from, Path(tmp))
            _print_scoped_report(args.scoped_from, sv)
            if not sv.passed:
                print("\nABORT: self-verify failed — the region or the consumer is "
                      "wrong; no baseline written. Investigate the mismatch/anomaly "
                      "above (never widen the region to pass).", file=sys.stderr)
                return 1
            if not sv.scoped.regenerated_slugs():
                print("Nothing to regenerate — every detail's region is empty.")
                return 0
            _scoped_regenerate(sv)
        print(f"Scoped-regenerated {', '.join(sv.scoped.regenerated_slugs())} "
              f"(others left byte-stable). Review the git diff.")
        return 0

    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp)
            regenerate(generated, source_dir=bl.BASELINE_DIR)
            stale = stale_baseline_names(generated, bl.BASELINE_DIR)
        if stale:
            print("STALE baselines (regenerate + commit): " + ", ".join(stale),
                  file=sys.stderr)
            return 1
        print("baselines are current.")
        return 0

    summary = regenerate(bl.BASELINE_DIR)
    _print_summary(summary)
    if any(f.get("note") == TODO_NOTE
           for f in json.loads((bl.BASELINE_DIR / "site_divergence.json").read_text())["findings"]):
        print("\nA pinned finding has a TODO-JUSTIFY placeholder note. Edit "
              "tests/baselines/site_divergence.json to justify it before "
              "committing (tests/test_baselines.py enforces this).",
              file=sys.stderr)
    print(f"Regenerated {len(bl.SIMPLE_SURFACES) + 1} baselines in {bl.BASELINE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
