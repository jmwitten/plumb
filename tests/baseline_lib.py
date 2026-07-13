"""ARCH0 — compiled-baseline mechanism (kill the hand-re-baseline tax).

Goldens are no longer hand-maintained Python literals. Each golden *surface*
emits its current model truth to a committed JSON file under
``tests/baselines/``; the migrated tests read that file and assert live output
== baseline, EXACTLY as they asserted the literal before. Changing behaviour
means REGENERATING the baseline (``python scripts/regen_baselines.py``) and
REVIEWING THE DIFF in git — never hand-editing a set or a count. A normal
``pytest`` run never rewrites a baseline.

Honesty properties preserved:
- Exact-set discipline: tests still assert ``got == baseline`` exactly.
- Deliberate re-baseline: regeneration is a separate command, never a side
  effect of running the suite.
- Justifications survive: the annotated site-divergence surface carries a
  per-finding ``note`` (the deferred-design justification); regeneration
  PRESERVES notes for unchanged findings and flags new/removed ones (see
  ``scripts/regen_baselines.py``).

This module is the single source of truth for the fingerprint hashing that the
migrated tests share, and for the per-surface ``compute_*`` functions the regen
command calls. The values a ``compute_*`` returns are the same values the
corresponding test computes live, so a committed baseline is provably current
(the round-trip test in ``tests/test_baselines.py``).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DETAILS = REPO / "details"
BASELINE_DIR = Path(__file__).resolve().parent / "baselines"

#: The one thing every "baseline missing / changed" message points a human at.
REGEN_HINT = "run `python scripts/regen_baselines.py` and review the git diff"


# --------------------------------------------------------------------------- #
# Canonical (deterministic) serialization + load/store
# --------------------------------------------------------------------------- #
def dumps(data) -> str:
    """The one canonical text form of a baseline: sorted keys, 2-space indent,
    trailing newline, non-ASCII preserved. Byte-stable across processes so the
    round-trip test can compare files verbatim."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_baseline(name: str) -> dict:
    path = BASELINE_DIR / f"{name}.json"
    if not path.exists():
        raise AssertionError(
            f"baseline {name!r} is missing at {path} — {REGEN_HINT}")
    return json.loads(path.read_text())


def write_baseline(name: str, data: dict, target_dir: Path = BASELINE_DIR) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{name}.json"
    path.write_text(dumps(data))
    return path


# --------------------------------------------------------------------------- #
# Model loaders (all four details compiled from their spec.yaml — the imperative
# .py mirrors were retired at milestone 4B-4b).
# --------------------------------------------------------------------------- #
# These are memoized: only the regen command (and its self-tests) call them,
# never the migrated detail tests, and a built+validated model is read-only —
# so reusing one instance across the several compute functions in a single regen
# is safe and spares the heavy 156-part site four rebuilds. Regeneration stays
# deterministic (the same model in, the same bytes out).
@lru_cache(maxsize=None)
def build_platform():
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    return compile_spec(load_spec_file(DETAILS / "platform.spec.yaml"))


@lru_cache(maxsize=None)
def build_rock_anchor():
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    return compile_spec(load_spec_file(DETAILS / "rock_anchor.spec.yaml"))


@lru_cache(maxsize=None)
def build_tree_spec():
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    return compile_spec(load_spec_file(DETAILS / "tree_attachment.spec.yaml"))


@lru_cache(maxsize=None)
def build_trolley_spec():
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    return compile_spec(load_spec_file(DETAILS / "trolley_launch.spec.yaml"))


@lru_cache(maxsize=None)
def build_site():
    from detailgen.spec.site import compile_site_file
    return compile_site_file(DETAILS / "site.spec.yaml")


# --------------------------------------------------------------------------- #
# Fingerprint helpers — the shared hashing the migrated tests import
# --------------------------------------------------------------------------- #
def _fmt(v: float) -> str:
    """Round a transform component to 1e-6 mm (a nanometre — far above the
    ≤2e-13 mm inch↔mm float residual, far below any real feature) and fold
    ``-0.0`` to ``0.0`` so a signed zero can't split the hash."""
    return f"{round(float(v), 6) + 0.0:.6f}"


def _vec(t) -> str:
    return ",".join(_fmt(c) for c in t)


def content_lines(detail) -> list[str]:
    """Full, sorted content of a validated detail: one line per finding,
    derivation fact, BOM row, and part transform. Sorted so it is invariant to
    the process-varying derivation-log order — it tracks WHAT the detail proved
    and built, not the order emitted."""
    lines: list[str] = []
    for f in detail.report.findings:
        lines.append(f"F|{f.check}|{f.subject}|{int(bool(f.passed))}|{f.detail}")
    for d in detail.derivation_log:
        lines.append("D|{}|{}|{}|{}|{}|{}|{}".format(
            d.fact, d.connection, d.rule, d.confidence, d.source_type,
            ";".join(sorted(d.assumptions)), ";".join(sorted(d.subjects))))
    for r in detail.assembly.bom_table():
        lines.append("B|{}|{}|{}|{}|{}|{}|{}|{}|{}".format(
            r["item"], r["qty"], r["material"], r["dimensions"], r["source"],
            ";".join(sorted(r["assumptions"])), r["length_mm"], r["stub_of"],
            ";".join(sorted(r["ids"]))))
    for p in detail.assembly.parts:
        fr = p.world_frame
        lines.append("T|{}|{}|{}|{}|{}".format(
            p.id, _vec(fr.origin), _vec(fr.x_axis),
            _vec(fr.y_axis), _vec(fr.z_axis)))
    return sorted(lines)


def content_fingerprint(detail) -> str:
    return hashlib.sha256("\n".join(content_lines(detail)).encode()).hexdigest()


def findings_fingerprint(report) -> str:
    """The EVIDENCE-guard fingerprint: a byte-level hash over the full findings
    set (check / subject / passed / detail), order-independent."""
    rows = sorted((f.check, f.subject, bool(f.passed), f.detail)
                  for f in report.findings)
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


#: Check kinds that POSTDATE the frozen corpus. EMPTY since the STRUCT task #19 /
#: A2 RE-FREEZE: the corpus was regenerated from the current SPEC path
#: (scripts/refreeze_from_spec.py), so it now CONTAINS the support family (and
#: every other current finding) directly — the spec matches the corpus exactly,
#: with no kind to set aside. (It held ``{"support"}`` while the corpus was the
#: pre-support imperative testimony; the re-freeze folded support into the
#: baseline, so the exclusion is no longer needed. Kept as a named seam for any
#: FUTURE family added after a freeze.)
FROZEN_POSTDATING_KINDS = frozenset()


def by_kind(report) -> dict:
    return dict(Counter(f.check for f in report.findings))


def site_divergence_pairs(site=None) -> list[dict]:
    """The pinned site divergence set — sorted (check, subject) of every site
    FAILURE, WITHOUT notes (notes are the human annotation channel, merged in by
    the regen command)."""
    if site is None:
        site = build_site()
    rep = site.validate()
    pairs = sorted((f.check, f.subject) for f in rep.failures)
    return [{"check": c, "subject": s} for c, s in pairs]


# --------------------------------------------------------------------------- #
# Per-surface compute functions — each returns the FULL baseline dict (incl.
# the ``_doc`` narrative). These are what ``scripts/regen_baselines.py`` writes,
# and every value equals what the migrated test computes live.
# --------------------------------------------------------------------------- #
def compute_detail_counts() -> dict:
    """Whole-model counts of the five shipped details — the R11 churn target
    (one part-count change used to ripple ~10 hand-edited fixtures). Every test
    that pins a whole-model part / BOM-row / derivation-log count now reads it
    from here."""
    plat = build_platform(); plat.validate()
    ra = build_rock_anchor(); ra.validate()
    tree = build_tree_spec(); tree.validate()
    trolley = build_trolley_spec(); trolley.validate()
    site = build_site(); site.validate()
    trolley_formalized = sum(
        1 for r in trolley.bom_table() if r.get("stub_of") is not None)
    return {
        "_doc": ("Whole-model counts of the shipped details. Regenerated from "
                 "the live model; " + REGEN_HINT + "."),
        "site": {"parts": len(site.assembly.parts)},
        "platform": {"parts": len(plat.assembly.parts),
                     "derivation_log": len(plat.derivation_log)},
        "rock_anchor": {"parts": len(ra.assembly.parts),
                        "derivation_log": len(ra.derivation_log)},
        "tree_attachment": {"parts": len(tree.assembly.parts),
                            "bom_rows": len(tree.bom_table())},
        "trolley_launch": {"parts": len(trolley.assembly.parts),
                           "bom_rows": len(trolley.bom_table()),
                           "formalized_stubs": trolley_formalized},
    }


def compute_slice_accounting() -> dict:
    """Slice-completeness accounting over the site views (test_site_views):
    how many site failures are scoped by a view, name no part, or name a part no
    current view scopes."""
    from detailgen.spec.views import _name_to_id, _subject_part_ids
    site = build_site(); site.validate()
    n2i = _name_to_id(site.assembly)
    in_scope: set = set()
    for v in site.views():
        in_scope |= {p.id for p in v.parts()}
    scoped = no_part = named_unscoped = 0
    for f in site.report.failures:
        ids = _subject_part_ids(f.subject, n2i)
        if any(i in in_scope for i in ids):
            scoped += 1
        elif not ids:
            no_part += 1
        else:
            named_unscoped += 1
    return {
        "_doc": ("Site view slice-completeness accounting. " + REGEN_HINT + "."),
        "scoped": scoped,
        "no_part": no_part,
        "named_unscoped": named_unscoped,
        "total_failures": len(site.report.failures),
    }


# NOTE: ``compute_site_report`` (and its ``site_report`` baseline of grab-bar
# actual/expected numbers) was RETIRED by STRUCT task #19. It read those numbers
# off the site's single grab-bar *dimension FAILURE*; the STRUCT branch resolved
# that divergence by design (the trolley grab-bar re-derives against the real
# end-joist top and now reads its honest height with no drawn-vs-derived gap), so
# there is no dimension failure to extract, and the site report section surfaces
# no grab-bar divergence. The baseline file was deleted with this surface.


#: Non-annotated surfaces: name -> zero-arg compute function. The annotated
#: site-divergence surface is handled separately (it merges human notes) in
#: ``scripts/regen_baselines.py``.
SIMPLE_SURFACES = {
    "detail_counts": compute_detail_counts,
    "slice_accounting": compute_slice_accounting,
}
