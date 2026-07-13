"""The visual-review status block: an honest, derived-from-the-store summary for
the doc/report surfaces.

What it reports: findings by severity, resolution state (with the unresolved
count made prominent), staleness of each finding's renders against a live
manifest, and how many rendered images have NEVER been reviewed. It reads the
store (and optionally a :class:`~detailgen.review.manifest.ReviewManifest`); it
computes NO verdict and flips NONE.

BINDING wording (owner directive + the epistemic ladder the coverage matrix
already uses): visual review is a SMELL TEST. Every rendering here says so — a
visual PASS proves nothing, findings are suspicions, and this block never
substitutes for the invariant coverage matrix that carries the actual verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .finding import FIXED_BY_REVISION, RESOLUTION_STATES, SEVERITIES, VisualReviewFinding
from .manifest import RenderEntry, ReviewManifest
from .store import FindingStore

#: The standing disclaimer rendered on every visual-review surface — the same
#: "absence of a finding is not evidence" honesty the invariant coverage matrix
#: carries, phrased for the smell test. Binding wording (directive guardrails).
STANDING_NOTE = (
    "Visual review is an adversarial SMELL TEST, not a verdict. Findings are "
    "SUSPICIONS, never proof; a clean visual pass proves nothing and NEVER "
    "relaxes, gates, or substitutes for an invariant verdict. Its value is "
    "surfacing MISSING invariants — the coverage matrix, not this block, carries "
    "correctness."
)

# -- per-render-ref staleness states -----------------------------------------
CURRENT = "current"            # ref hash matches the live manifest
STALE = "stale"               # ref hash != manifest hash — render changed since review
RENDER_MISSING = "render-missing"  # the reviewed render is not in the manifest
UNVERIFIED = "unverified"     # ref carries no hash — staleness can't be checked


@dataclass(frozen=True)
class RefState:
    """The staleness verdict for one of a finding's render refs."""

    finding_id: str
    path: str
    state: str


@dataclass(frozen=True)
class ReviewReconciliation:
    """The store cross-referenced against a live manifest.

    ``ref_states`` is every finding render-ref's staleness; ``never_reviewed`` is
    the manifest renders no finding references (candidates for a first review).
    ``stale`` / ``missing`` / ``unverified`` are the ref-state rollups. When no
    manifest is supplied, staleness is all UNVERIFIED and ``never_reviewed`` is
    empty (nothing to compare against) — reported honestly, not as "all clear"."""

    ref_states: tuple[RefState, ...]
    never_reviewed: tuple[RenderEntry, ...]
    has_manifest: bool

    def _paths_in_state(self, state: str) -> tuple[RefState, ...]:
        return tuple(r for r in self.ref_states if r.state == state)

    @property
    def stale(self) -> tuple[RefState, ...]:
        return self._paths_in_state(STALE)

    @property
    def missing(self) -> tuple[RefState, ...]:
        return self._paths_in_state(RENDER_MISSING)

    @property
    def unverified(self) -> tuple[RefState, ...]:
        return self._paths_in_state(UNVERIFIED)


def reconcile(store: FindingStore,
              manifest: ReviewManifest | None = None) -> ReviewReconciliation:
    """Cross-reference the store against a live manifest: staleness per render
    ref, and which manifest renders no finding has reviewed."""
    by_path = manifest.by_path() if manifest is not None else {}
    ref_states: list[RefState] = []
    reviewed_paths: set[str] = set()
    for f in store.findings:
        for ref in f.renders:
            reviewed_paths.add(ref.path)
            ref_states.append(RefState(f.id, ref.path, _ref_state(ref, by_path)))
    never_reviewed = tuple(
        e for e in (manifest.renders if manifest is not None else ())
        if e.path not in reviewed_paths
    )
    return ReviewReconciliation(
        ref_states=tuple(ref_states),
        never_reviewed=never_reviewed,
        has_manifest=manifest is not None,
    )


def _ref_state(ref, by_path: dict) -> str:
    if ref.content_hash is None:
        return UNVERIFIED
    entry = by_path.get(ref.path)
    if entry is None:
        # No manifest at all -> can't verify; a manifest that simply lacks this
        # path -> the reviewed render is gone.
        return UNVERIFIED if not by_path else RENDER_MISSING
    return CURRENT if entry.content_hash == ref.content_hash else STALE


# -- markdown surface --------------------------------------------------------


def _severity_counts(store: FindingStore) -> list[tuple[str, int, int]]:
    """(severity, total, open) rows in canonical severity order."""
    groups = store.by_severity()
    return [(s, len(groups[s]), sum(1 for f in groups[s] if f.is_open))
            for s in SEVERITIES]


def _resolution_counts(store: FindingStore) -> dict[str, int]:
    from collections import Counter

    return dict(Counter(f.resolution.status for f in store.findings))


def render_visual_review_block_md(store: FindingStore,
                                  manifest: ReviewManifest | None = None) -> str:
    """Markdown visual-review status block, derived entirely from the store
    (+ optional manifest for staleness / never-reviewed)."""
    rec = reconcile(store, manifest)
    n_open = len(store.open_findings())
    total = len(store.findings)
    lines = [
        "## Visual review — adversarial smell test",
        "",
        f"> {STANDING_NOTE}",
        "",
        f"**{n_open} unresolved** of {total} finding(s). Unresolved suspicions are "
        "open work items that never silently expire.",
        "",
        "### Findings by severity",
        "",
        "| Severity | Findings | Unresolved |",
        "| --- | --: | --: |",
    ]
    for sev, tot, opn in _severity_counts(store):
        lines.append(f"| {sev} | {tot} | {opn} |")
    lines += ["", "### Resolution state", ""]
    res = _resolution_counts(store)
    for status in RESOLUTION_STATES:
        if res.get(status):
            lines.append(f"- {status}: {res[status]}")
    lines += ["", "### Findings", "",
              "| ID | Severity | Subject | Possible family | Resolution | Renders |",
              "| --- | --- | --- | --- | --- | --- |"]
    for f in store.findings:
        renders = "; ".join(r.path.split("/")[-1] for r in f.renders)
        lines.append(
            f"| {f.id} | {f.severity} | {_md_cell(f.subject)} | "
            f"{_md_cell(f.invariant_family)} | {f.resolution.status} | "
            f"{_md_cell(renders)} |"
        )
    lines += ["", "### Render freshness", ""]
    if not rec.has_manifest:
        lines.append("- No render manifest supplied — staleness not evaluated.")
    else:
        lines.append(f"- {len(rec.never_reviewed)} render(s) never reviewed.")
        lines.append(f"- {len(rec.stale)} finding render-ref(s) STALE "
                     "(render changed since review).")
        lines.append(f"- {len(rec.missing)} finding render-ref(s) point at a "
                     "render no longer produced.")
        lines.append(f"- {len(rec.unverified)} finding render-ref(s) have no "
                     "captured hash (staleness unverifiable).")
    lines.append("")
    return "\n".join(lines)


def _md_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


# -- html surface (for the consolidated build document) ----------------------

_SEV_CLASS = {"CRITICAL": "vr-crit", "HIGH": "vr-high",
              "MEDIUM": "vr-med", "LOW": "vr-low"}


def _resolution_class(f: VisualReviewFinding) -> str:
    """The CSS class for a finding's resolution cell. Open work reads as open
    (``vr-open``); a defect removed by a design revision reads as fixed
    (``vr-fixed`` — distinct from a mere accepted assumption); every other
    resolved state reads as resolved (``vr-resolved``)."""
    if f.is_open:
        return "vr-open"
    if f.resolution.status == FIXED_BY_REVISION:
        return "vr-fixed"
    return "vr-resolved"


def render_visual_review_block_html(store: FindingStore,
                                    manifest: ReviewManifest | None = None,
                                    *, title: str | None = None,
                                    lede: str | None = None,
                                    section_class: str | None = None) -> str:
    """Self-contained HTML block for the consolidated document. Mirrors the
    coverage-matrix section's structure (a lede standing note + tables) so it
    reads as a sibling honesty surface, explicitly BELOW the invariant verdict.

    ``title`` / ``lede`` / ``section_class`` default to the VISUAL-review block
    (byte-identical to the prior output, so every existing caller is unchanged).
    A SIBLING findings surface with the same schema — e.g. the DESIGN-review store
    — passes its own heading + standing note to reuse this one renderer rather
    than forking a parallel block. ``title`` is raw HTML (may carry entities);
    ``lede`` is plain text and is escaped."""
    rec = reconcile(store, manifest)
    n_open = len(store.open_findings())
    total = len(store.findings)

    sev_rows = "".join(
        f'<tr><td class="{_SEV_CLASS.get(sev, "")}">{escape(sev)}</td>'
        f"<td>{tot}</td><td>{opn}</td></tr>"
        for sev, tot, opn in _severity_counts(store)
    )

    find_rows = "".join(
        f'<tr><td>{escape(f.id)}</td>'
        f'<td class="{_SEV_CLASS.get(f.severity, "")}">{escape(f.severity)}</td>'
        f"<td>{escape(f.subject)}</td>"
        f"<td>{escape(f.invariant_family)}</td>"
        f'<td class="{_resolution_class(f)}">'
        f"{escape(f.resolution.status)}</td>"
        f"<td>{escape('; '.join(r.path.split('/')[-1] for r in f.renders))}</td></tr>"
        for f in store.findings
    )

    if not rec.has_manifest:
        fresh = "<li>No render manifest supplied — staleness not evaluated.</li>"
    else:
        fresh = (
            f"<li>{len(rec.never_reviewed)} render(s) never reviewed.</li>"
            f"<li>{len(rec.stale)} finding render-ref(s) STALE — render changed "
            "since review.</li>"
            f"<li>{len(rec.missing)} finding render-ref(s) point at a render no "
            "longer produced.</li>"
            f"<li>{len(rec.unverified)} finding render-ref(s) have no captured "
            "hash (staleness unverifiable).</li>"
        )

    return f"""
  <section class="{section_class or "notes visual-review"}">
    <h2>{title or "Visual review &mdash; adversarial smell test"}</h2>
    <p class="lede">{escape(lede) if lede else escape(STANDING_NOTE)}</p>
    <p class="vr-open-count"><strong>{n_open} unresolved</strong> of {total}
    finding(s) &mdash; open work items that never silently expire.</p>
    <div class="dims">
      <div class="dims-h">By severity</div>
      <table class="coverage">
        <tr><th>Severity</th><th>Findings</th><th>Unresolved</th></tr>
        {sev_rows}
      </table>
    </div>
    <div class="dims">
      <div class="dims-h">Findings <span>(suspicions &mdash; each carries a
      POSSIBLE family and a recommended action, never a verdict)</span></div>
      <table class="coverage">
        <tr><th>ID</th><th>Severity</th><th>Subject</th><th>Possible family</th>
        <th>Resolution</th><th>Renders</th></tr>
        {find_rows}
      </table>
    </div>
    <div class="dims">
      <div class="dims-h">Render freshness</div>
      <ul class="narrative">{fresh}</ul>
    </div>
  </section>"""
