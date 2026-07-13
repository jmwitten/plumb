#!/usr/bin/env python3
"""Armchair-caddy PROGRESSION harness — run the same novel detail from scratch at
different eras and print one compact, deterministic block per era.

The controller runs this inside throwaway worktrees checked out at different
master SHAs (past and future). The point is to watch ONE unchanging design gain
machinery over time: pre-FAB-1 it has no fabrication records, pre-FAB-2 no
process-record-derived cut list, pre-FAB-4 no ``produced_by`` evidence edges.
Every era-gated field is PROBED (import-try / hasattr / behavioural check) and
prints an honest ``N/A (not built yet)`` when the checked-out code lacks it —
that N/A -> populated transition IS the deliverable. No field is ever faked.

Usage:
    python scripts/smoke_progression.py [--worktree DIR] [--spec PATH]

``--worktree`` (default: cwd) is the detailgen checkout to probe; the harness
imports detailgen from THAT tree (via its ``.shim``), so it always exercises the
checked-out era's code, not whatever is installed. ``--spec`` defaults to
``<worktree>/details/armchair_caddy.spec.yaml``.

Constraints honoured: no test-code imports; output is deterministic except the
single measured wall-time line; nothing is written to the project's real
``outputs/`` (the harness only reads the compiled model). One documented
carve-out from "detailgen only": FAB-2's cut-note surface lives in the REPORT
layer (``scripts/consolidated_report.py``), so the FAB-2 probe imports from
``scripts`` — still first-party detailgen code, just the report tier, and still
import-tried so an era without it degrades to an honest N/A.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

NA = "N/A (not built yet)"
_BAR = "=" * 64


# --------------------------------------------------------------------------- #
# Import wiring: make `import detailgen` resolve to the TARGET worktree.
# --------------------------------------------------------------------------- #
def _wire_imports(worktree: Path) -> None:
    """Prepend the worktree's shim so ``import detailgen`` binds to its ``src``.
    Idempotent and harmless if detailgen already imports (our own suite runs
    with the shim already on PYTHONPATH)."""
    for cand in (worktree / ".shim", worktree, worktree / "scripts"):
        s = str(cand)
        if cand.exists() and s not in sys.path:
            sys.path.insert(0, s)


def _short_sha(worktree: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10)
        sha = out.stdout.strip()
        return sha or "unknown"
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- #
# Era-gated capability probes. Each returns structured data or None (=> N/A).
# --------------------------------------------------------------------------- #
def _probe_process_records(parts):
    """FAB-1: per fabricated part, its ProcessRecord steps. None pre-FAB-1."""
    try:
        from detailgen.core.process_graph import _fabrication_record_of
    except Exception:
        return None
    records = {}
    purchased = []
    for p in parts:
        try:
            rec = _fabrication_record_of(p.component)
        except Exception:
            rec = None
        if rec is None:
            purchased.append(p.name)
            continue
        steps = []
        for s in rec.steps:
            steps.append(s.kind)
        try:
            length_in = rec.crosscut_length() / 25.4
        except Exception:
            length_in = None
        records[p.name] = (steps, length_in)
    if not records:
        return None
    return {"records": records, "purchased": purchased}


def _fab2_note_fn():
    """FAB-2's cut-note surface: ``_cutlist_fab_note(record)`` in the report layer
    (``scripts/consolidated_report.py``), which renders a fabrication note from a
    ProcessRecord (only ``notch`` steps produce a note in FAB-2 v1). Returns the
    callable, or None when the checked-out tree has no such surface — the honest
    'not built yet' signal. We do NOT synthesise the note ourselves; we call
    detailgen's OWN renderer, so the field can never claim a cut list the code
    can't actually produce."""
    import importlib
    for modname in ("scripts.consolidated_report", "consolidated_report"):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        fn = getattr(mod, "_cutlist_fab_note", None)
        if callable(fn):
            return fn
    return None


def _probe_derived_cutlist(parts):
    """FAB-2: per fabricated part, the report layer's process-record-derived
    cut-list note. Returns None when the FAB-2 surface is ABSENT (honest N/A), or
    a {part: note} dict when it is BUILT — where an empty note string means the
    surface exists but this part has no cut-note (no ``notch`` step). That
    absent-vs-built-but-empty distinction is the point: a built FAB-2 must never
    print 'N/A (not built yet)'."""
    fn = _fab2_note_fn()
    if fn is None:
        return None
    try:
        from detailgen.core.process_graph import _fabrication_record_of
    except Exception:
        return None
    out: dict = {}
    for p in parts:
        rec = _fabrication_record_of(p.component)
        if rec is None:
            continue
        try:
            note = fn(rec)
        except Exception:
            note = ""
        out[p.name] = note if isinstance(note, str) else ""
    return out


def _probe_evidence_walkback(detail):
    """FAB-4: the evidence graph projects fabrication as ``process_step`` nodes
    linked by ``produced_by`` edges, so a part is walkable back to the operation
    that produced it. None until those node/edge kinds are populated."""
    try:
        eg = detail.evidence_graph
    except Exception:
        return None
    try:
        steps = eg.nodes_of_kind("process_step")
        edges = eg.edges_of_kind("produced_by")
    except Exception:
        return None
    if not steps and not edges:
        return None
    return {"process_step_nodes": len(steps), "produced_by_edges": len(edges)}


def _coverage_rows(report):
    """Per-family verdicts, or None if the checked-out era predates the matrix."""
    try:
        matrix = report.coverage_matrix()
    except Exception:
        return None
    rows = []
    for fc in matrix:
        kinds = ", ".join(f"{k}x{n}" for k, n in fc.ran_kinds) or "-"
        rows.append((fc.family, fc.verdict, kinds))
    return rows


def _probe_doc_build(detail):
    """Exercise the FULL pipeline INCLUDING the reader-facing HTML build document,
    through the REAL entry path. Preference order, most-to-least capable:

    1. the single-detail HTML build document (task 10) — reuses the consolidated
       report's panel/coverage/BOM/cut-plan/findings/3D-viewer machinery; reports
       the real HTML's size + headline;
    2. FAB-3's ungated ``render_documentation`` (draws + surfaces the honest
       verdict; the machine layer — report.md + coverage, no HTML);
    3. the gated ``render`` (pre-FAB-3: only the certifying verb).

    Each degradation is an honest era signal, not a failure to hide. Everything
    writes to a throwaway temp dir — NEVER the real ``outputs/``."""
    import tempfile
    # 1) the real HTML build document.
    try:
        import single_detail_report as SDR
        with tempfile.TemporaryDirectory() as td:
            binfo = SDR.build_document(Path(td) / "doc.html", preview=False)
        return {"mode": "html", "kb": binfo["size_bytes"] / 1024.0,
                "panels": binfo.get("panels"), "headline": binfo["headline"],
                "gated": False, "error": None}
    except Exception as e:  # pre-FAB-3 render_documentation, or any HTML fault
        html_err = f"{type(e).__name__}: {e}"

    # 2/3) fall back to the machine-layer render (report.md), era-tolerant.
    info = {"mode": "report", "headline": None, "gated": None, "error": None,
            "report_written": False, "html_err": html_err}
    fn = getattr(detail, "render_documentation", None)
    gated = False
    if not callable(fn):
        fn = getattr(detail, "render", None)   # pre-FAB-3: only the gated verb
        gated = True
    info["gated"] = gated
    if not callable(fn):
        info["error"] = "no render entry point"
        return info
    try:
        with tempfile.TemporaryDirectory() as td:
            out = fn(td)
            info["path"] = "render_documentation" if not gated else "render (gated)"
            rep_md = Path(out) / "validation_report.md"
            if rep_md.exists():
                info["report_written"] = True
                for ln in rep_md.read_text().splitlines():
                    if ln.startswith("## Result:"):
                        info["headline"] = ln.split("Result:", 1)[1].strip(" *")
                        break
    except Exception as e:  # gated render on a blocked model, or any render fault
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def _probe_visual_findings(worktree: Path):
    """Read the caddy's visual-review store (reviews/visual/caddy-findings.yaml)
    through the REAL loader (detailgen.review). Era-tolerant: pre-VISREV the
    package does not import (-> None -> honest N/A); a missing store file is also
    None. Returns {open, resolved, total} when present."""
    try:
        from detailgen.review import load_findings_file
    except Exception:
        return None
    store_path = worktree / "reviews" / "visual" / "caddy-findings.yaml"
    if not store_path.exists():
        return None
    try:
        store = load_findings_file(store_path)
    except Exception:
        return None
    total = len(store.findings)
    openn = len(store.open_findings())
    try:
        rel = store_path.relative_to(worktree)
    except ValueError:
        rel = store_path
    return {"open": openn, "resolved": total - openn, "total": total,
            "store": str(rel)}


def _probe_view_coverage(worktree: Path):
    """Read the caddy's auditable view-coverage decision table
    (reviews/visual/caddy-view-coverage.json). Counts primary views and ZOOM
    decisions (+ recorded why-nots). None (honest N/A) when the artifact is
    absent. Deterministic; no rendering happens here."""
    import json
    path = worktree / "reviews" / "visual" / "caddy-view-coverage.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    primary = len(data.get("primary_views", []))
    areas = data.get("candidate_areas", [])
    zoom = sum(1 for a in areas if a.get("decision") == "ZOOM")
    whynot = sum(1 for a in areas if a.get("decision") == "WHY-NOT")
    return {"primary": primary, "zoom": zoom, "why_not": whynot,
            "areas": len(areas)}


# --------------------------------------------------------------------------- #
# Probe + render.
# --------------------------------------------------------------------------- #
def probe(worktree: Path, spec: Path) -> dict:
    """Run the from-scratch pipeline once and gather every field. Import-time
    failures (an era too old to compile the spec at all) are captured, not
    raised, so the harness still prints an honest block."""
    _wire_imports(worktree)
    data: dict = {"sha": _short_sha(worktree), "spec": str(spec)}

    t0 = time.perf_counter()
    try:
        from detailgen.spec.compiler import compile_spec_file
        detail = compile_spec_file(spec)
        report = detail.validate()
    except Exception as e:  # noqa: BLE001 — report, don't crash the harness
        data["wall_s"] = time.perf_counter() - t0
        data["error"] = f"{type(e).__name__}: {e}"
        return data
    data["wall_s"] = time.perf_counter() - t0

    parts = list(detail.assembly.parts)
    data["n_parts"] = len(parts)
    data["failures"] = len(report.failures)
    data["blocking"] = len(report.blocking)
    data["coverage"] = _coverage_rows(report)

    try:
        bom = []
        for r in detail.bom_table():
            L = r.get("length_mm")
            bom.append((r["qty"], r["item"], (L / 25.4) if L else None))
        # deterministic order: item then length
        bom.sort(key=lambda t: (t[1], t[2] if t[2] is not None else -1.0))
        data["bom"] = bom
    except Exception:
        data["bom"] = None

    proc = _probe_process_records(parts)
    data["process_records"] = proc
    board_names = set(proc["records"]) if proc else set()
    data["cutlist"] = _probe_derived_cutlist(parts)
    data["evidence"] = _probe_evidence_walkback(detail)
    data["n_fabricated"] = len(board_names) if proc else None
    # task-8 fields
    data["doc_build"] = _probe_doc_build(detail)
    data["visual"] = _probe_visual_findings(worktree)
    data["views"] = _probe_view_coverage(worktree)
    return data


def render(data: dict) -> str:
    L = [_BAR, "armchair-caddy progression probe", _BAR]

    if "error" in data:
        L.append(f"milestone : {data['sha']}")
        L.append(f"wall time : {data['wall_s']:.2f}s  (non-deterministic)")
        L.append(f"ERROR     : {data['error']}")
        L.append("  (this era cannot compile/validate the caddy spec — "
                 "everything below is N/A)")
        L.append(_BAR)
        return "\n".join(L)

    caps = (f"FAB-1={'yes' if data['process_records'] else 'no'} "
            f"FAB-2={'yes' if data['cutlist'] is not None else 'no'} "
            f"FAB-4={'yes' if data['evidence'] else 'no'}")
    L.append(f"milestone : {data['sha']}  [caps: {caps}]")
    L.append(f"wall time : {data['wall_s']:.2f}s  "
             f"(compile+validate+records; NON-deterministic)")
    fab = data["n_fabricated"]
    fab_txt = f", {fab} fabricated" if fab is not None else ""
    L.append(f"parts     : {data['n_parts']}{fab_txt}")

    L.append("--- validation verdicts (per invariant family) ---")
    if data["coverage"] is None:
        L.append(f"  {NA}")
    else:
        for family, verdict, kinds in data["coverage"]:
            L.append(f"  {family:34s} {verdict:22s} ({kinds})")
    L.append(f"  => failures: {data['failures']}   blocking: {data['blocking']}")

    L.append("--- bill of materials ---")
    if not data["bom"]:
        L.append(f"  {NA}")
    else:
        for qty, item, length_in in data["bom"]:
            ln = f'{length_in:.2f}"' if length_in is not None else "—"
            L.append(f"  {qty}x  {item:24s} {ln}")

    L.append("--- process records: steps per part (FAB-1) ---")
    proc = data["process_records"]
    if proc is None:
        L.append(f"  {NA}")
    else:
        for name in sorted(proc["records"]):
            steps, length_in = proc["records"][name]
            # collapse repeated kinds: e.g. drill,drill,drill,drill -> drill x4
            parts_txt = []
            i = 0
            while i < len(steps):
                j = i
                while j < len(steps) and steps[j] == steps[i]:
                    j += 1
                n = j - i
                parts_txt.append(steps[i] if n == 1 else f"{steps[i]} x{n}")
                i = j
            head = f'crosscut {length_in:.2f}"' if length_in is not None else "crosscut"
            # replace the leading 'crosscut' token with the measured head
            if parts_txt and parts_txt[0].startswith("crosscut"):
                parts_txt[0] = head
            L.append(f"  {name:16s} : " + " · ".join(parts_txt))
        if proc["purchased"]:
            L.append(f"  (purchased-as-is, no record: "
                     f"{', '.join(sorted(proc['purchased']))})")

    L.append("--- derived cut list from process records (FAB-2) ---")
    cut = data["cutlist"]
    if cut is None:
        L.append(f"  {NA}")
    elif not cut:
        L.append("  built, no fabricated parts to note")
    else:
        for name in sorted(cut):
            note = cut[name]
            if note:
                L.append(f"  {name:16s} : {note}")
            else:
                L.append(f"  {name:16s} : built, no cut-note for this part "
                         f"(no notch step)")

    L.append("--- evidence walkback: produced_by edges (FAB-4) ---")
    ev = data["evidence"]
    if ev is None:
        L.append(f"  {NA}")
    else:
        L.append(f"  process_step nodes: {ev['process_step_nodes']}   "
                 f"produced_by edges: {ev['produced_by_edges']}")

    L.append("--- doc build: full pipeline incl. reader-facing HTML (task 10 / FAB-3) ---")
    db = data.get("doc_build")
    if db is None:
        L.append(f"  {NA}")
    elif db.get("mode") == "html":
        # the real reader-facing HTML build document (reused site machinery).
        pnl = db.get("panels")
        pnl_txt = f", {pnl} panel(s)" if pnl is not None else ""
        L.append(f"  single-detail HTML build document: OK — {db['kb']:.0f} KB{pnl_txt}")
        L.append(f"    headline: {db.get('headline') or '(no result line)'}")
    elif db.get("error") and not db.get("report_written"):
        # honest crash/gate: the gated verb refusing a blocked model, or a fault
        verb = "gated render()" if db.get("gated") else "render_documentation()"
        L.append(f"  HTML doc unavailable this era; {verb}: NO doc — {db['error']}  "
                 f"(honest gate/crash)")
    else:
        verb = db.get("path") or "render"
        L.append(f"  HTML doc unavailable this era ({db.get('html_err','')}); "
                 f"machine layer via {verb}: OK")
        L.append(f"    headline: {db.get('headline') or '(no result line)'}")

    L.append("--- visual review findings (VISREV store) ---")
    vf = data.get("visual")
    if vf is None:
        L.append(f"  {NA}")
    else:
        # name the store read (per-detail sibling store, loaded by the real
        # detailgen.review loader) so the field is auditable, not anonymous.
        L.append(f"  {vf['open']} open / {vf['resolved']} resolved "
                 f"({vf['total']} total)  [store: {vf['store']}]")

    L.append("--- view coverage (auditable decision table) ---")
    vc = data.get("views")
    if vc is None:
        L.append(f"  {NA}")
    else:
        L.append(f"  {vc['primary']} primary + {vc['zoom']} zoom "
                 f"({vc['why_not']} recorded why-not, {vc['areas']} areas audited)")

    L.append(_BAR)
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worktree", default=".",
                    help="detailgen checkout to probe (default: cwd)")
    ap.add_argument("--spec", default=None,
                    help="spec path (default: <worktree>/details/armchair_caddy.spec.yaml)")
    args = ap.parse_args(argv)

    worktree = Path(args.worktree).resolve()
    spec = (Path(args.spec).resolve() if args.spec
            else worktree / "details" / "armchair_caddy.spec.yaml")

    print(render(probe(worktree, spec)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
