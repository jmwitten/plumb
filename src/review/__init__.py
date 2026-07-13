"""Visual-review subsystem (task VISREV) — the machinery around an adversarial
visual smell test of rendered output.

This subsystem does NOT call an LLM and does NOT decide correctness. The reviewer
stays an agent/human process; this package is the durable spine around it:

    finding   — :class:`VisualReviewFinding`, a first-class model of ONE visual
                suspicion with the owner directive's required fields and an
                enforced resolution workflow (four outcomes + a legal, persistent
                ``unresolved`` state).
    store     — a strict, teaching-error loader for the repo-tracked findings
                file (``reviews/visual/*.yaml``) the reviewer edits and the
                pipeline reads, plus a round-trippable serializer.
    stores    — the per-detail naming convention as a first-class enumeration
                (``<name>-findings.yaml`` / ``<name>-design-findings.yaml``), so a
                detail's stores are DISCOVERED, not hand-pointed, with a cross-store
                id-namespace check.
    manifest  — enumerate the renders a build produced (paths + content hashes +
                what detail/view each shows) so a reviewer is pointed at a
                content-addressed set and a stale review is DETECTABLE.
    report    — an honest visual-review status block (findings by severity,
                resolution state, unresolved count, never-reviewed renders,
                staleness) derived from the store + manifest.

BINDING GUARDRAIL (owner directive, visual-review-directive.md): compiler
invariants are the SOURCE OF TRUTH. A visual finding is a SUSPICION, never
proof; a visual PASS proves nothing. Nothing in this package may relax, gate, or
substitute for an invariant verdict — its value is DISCOVERING MISSING
INVARIANTS, not certifying safety. Every surface here says so.
"""

from __future__ import annotations

from .finding import (
    FIXED_BY_REVISION,
    RESOLUTION_STATES,
    SEVERITIES,
    UNRESOLVED,
    RenderRef,
    Resolution,
    ReviewSchemaError,
    VisualReviewFinding,
    known_invariant_families,
)
from .manifest import RenderEntry, ReviewManifest, build_review_manifest
from .report import (
    RefState,
    reconcile,
    render_visual_review_block_html,
    render_visual_review_block_md,
)
from .store import FindingStore, dump_findings_text, load_findings_file, load_findings_text
from .stores import (
    DetailStores,
    LoadedDetailStores,
    enumerate_detail_stores,
    find_detail_store,
    load_detail_stores,
)

__all__ = [
    "FIXED_BY_REVISION",
    "RESOLUTION_STATES",
    "SEVERITIES",
    "UNRESOLVED",
    "RenderRef",
    "Resolution",
    "ReviewSchemaError",
    "VisualReviewFinding",
    "known_invariant_families",
    "RenderEntry",
    "ReviewManifest",
    "build_review_manifest",
    "RefState",
    "reconcile",
    "render_visual_review_block_html",
    "render_visual_review_block_md",
    "FindingStore",
    "dump_findings_text",
    "load_findings_file",
    "load_findings_text",
    "DetailStores",
    "LoadedDetailStores",
    "enumerate_detail_stores",
    "find_detail_store",
    "load_detail_stores",
]
