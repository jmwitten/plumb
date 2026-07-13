"""The durable findings store: load / dump the repo-tracked visual-review file.

The store is a human-editable YAML file (``reviews/visual/*.yaml``) — the surface
a reviewer writes suspicions to and the pipeline reads. Loading is STRICT and
teaching, mirroring the spec loaders (:mod:`detailgen.spec.loader`): an unknown
key is a hard error with a did-you-mean, a missing required key names the field,
and every value flows into the always-valid :class:`VisualReviewFinding` model
(which enforces the vocabulary and the resolution-evidence rule). A safe YAML
loader only — no arbitrary object construction from the document.

``load`` and :func:`dump_findings_text` round-trip: a store loaded, dumped, and
reloaded yields equal findings, so the file stays the single source of truth and
a programmatic edit is reviewable as a clean diff.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

import yaml

from .finding import (
    RenderRef,
    Resolution,
    ReviewSchemaError,
    VisualReviewFinding,
)

#: The only store-schema version this loader understands. A file with a
#: different version is a teaching error (not a silent best-effort parse), so a
#: future schema change is an explicit, reviewed migration.
STORE_VERSION = 1


def _take(mapping, known: dict, context: str) -> dict:
    """Validate ``mapping``'s keys against ``known`` (name -> required?) and
    return ``{name: value_or_MISSING}``. Unknown key -> teaching error with
    did-you-mean; missing required -> teaching error naming the field. Mirrors
    :func:`detailgen.spec.schema._take` in style; kept local so VISREV owns its
    own loader and never edits the spec package."""
    if not isinstance(mapping, dict):
        raise ReviewSchemaError(
            f"{context}: expected a mapping with keys {sorted(known)}, got "
            f"{type(mapping).__name__}"
        )
    for key in mapping:
        if key not in known:
            hint = difflib.get_close_matches(str(key), sorted(known), n=3)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise ReviewSchemaError(
                f"{context}: unknown key {key!r}; allowed keys: {sorted(known)}{tip}"
            )
    out = {}
    for name, required in known.items():
        if name in mapping:
            out[name] = mapping[name]
        elif required:
            raise ReviewSchemaError(
                f"{context}: missing required key {name!r}; required keys: "
                f"{sorted(k for k, r in known.items() if r)}"
            )
        else:
            out[name] = _MISSING
    return out


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


def _default(value, fallback):
    return fallback if value is _MISSING else value


@dataclass(frozen=True)
class FindingStore:
    """A loaded findings file: a version plus an ordered, id-unique tuple of
    findings. Query helpers keep the reporting surface (and a reviewer's triage)
    from re-deriving the same slices."""

    version: int
    findings: tuple[VisualReviewFinding, ...]

    def open_findings(self) -> tuple[VisualReviewFinding, ...]:
        """Unresolved findings — the open work that never silently expires."""
        return tuple(f for f in self.findings if f.is_open)

    def by_severity(self) -> dict[str, list[VisualReviewFinding]]:
        """Findings grouped by severity, in :data:`SEVERITIES` order (missing
        severities present as empty lists so the report has a stable shape)."""
        from .finding import SEVERITIES

        groups: dict[str, list[VisualReviewFinding]] = {s: [] for s in SEVERITIES}
        for f in self.findings:
            groups[f.severity].append(f)
        return groups

    def by_id(self) -> dict[str, VisualReviewFinding]:
        return {f.id: f for f in self.findings}


def load_findings_text(text: str, *, source: str = "<text>") -> FindingStore:
    """Parse findings-store ``text`` (YAML/JSON) into a :class:`FindingStore`."""
    raw = yaml.safe_load(text)
    if raw is None:
        raise ReviewSchemaError(
            f"{source}: the findings store is empty; a valid store is a mapping "
            "with 'version' and a 'findings' list (which may be empty: [])."
        )
    if not isinstance(raw, dict):
        raise ReviewSchemaError(
            f"{source}: the findings store must be a mapping at top level "
            f"(keys 'version', 'findings'), got {type(raw).__name__}"
        )
    f = _take(raw, {"version": True, "findings": False}, source)
    version = f["version"]
    if version != STORE_VERSION:
        raise ReviewSchemaError(
            f"{source}: unsupported store version {version!r}; this loader "
            f"understands version {STORE_VERSION}. Migrate the file (a version "
            "bump is an explicit, reviewed schema change), don't downgrade the "
            "loader."
        )
    raw_findings = _default(f["findings"], [])
    if not isinstance(raw_findings, list):
        raise ReviewSchemaError(
            f"{source}: 'findings' must be a list (use [] for none), got "
            f"{type(raw_findings).__name__}"
        )
    findings = tuple(_build_finding(rf, f"{source} findings[{i}]")
                     for i, rf in enumerate(raw_findings))
    seen: dict[str, int] = {}
    for i, fd in enumerate(findings):
        if fd.id in seen:
            raise ReviewSchemaError(
                f"{source}: duplicate finding id {fd.id!r} at findings[{i}] "
                f"(first seen at findings[{seen[fd.id]}]); ids must be unique so a "
                "finding can be referenced and resolved unambiguously."
            )
        seen[fd.id] = i
    return FindingStore(version=version, findings=findings)


def load_findings_file(path: str | Path) -> FindingStore:
    """Load a findings store from a file."""
    path = Path(path)
    return load_findings_text(path.read_text(), source=str(path))


def _build_finding(raw, ctx: str) -> VisualReviewFinding:
    f = _take(raw, {
        "id": True, "subject": True, "suspected_issue": True, "severity": True,
        "visual_evidence": True, "renders": True, "invariant_family": True,
        "recommended_action": True, "resolution": False, "notes": False,
    }, ctx)
    renders = _build_renders(f["renders"], f"{ctx} renders")
    resolution = (Resolution() if f["resolution"] is _MISSING
                  else _build_resolution(f["resolution"], f"{ctx} resolution"))
    return VisualReviewFinding(
        id=str(f["id"]),
        subject=str(f["subject"]),
        suspected_issue=str(f["suspected_issue"]),
        severity=str(f["severity"]),
        visual_evidence=str(f["visual_evidence"]),
        renders=renders,
        invariant_family=str(f["invariant_family"]),
        recommended_action=str(f["recommended_action"]),
        resolution=resolution,
        notes=str(_default(f["notes"], "")),
    )


def _build_renders(raw, ctx: str) -> tuple[RenderRef, ...]:
    if not isinstance(raw, list) or not raw:
        raise ReviewSchemaError(
            f"{ctx}: expected a non-empty list of render refs (each a mapping with "
            "'path' and optional 'content_hash'), got "
            f"{type(raw).__name__ if not isinstance(raw, list) else 'empty list'}"
        )
    out = []
    for i, rr in enumerate(raw):
        rf = _take(rr, {"path": True, "content_hash": False}, f"{ctx}[{i}]")
        out.append(RenderRef(
            path=str(rf["path"]),
            content_hash=(None if rf["content_hash"] is _MISSING
                          else str(rf["content_hash"])),
        ))
    return tuple(out)


def _build_resolution(raw, ctx: str) -> Resolution:
    rf = _take(raw, {"status": True, "note": False}, ctx)
    return Resolution(status=str(rf["status"]), note=str(_default(rf["note"], "")))


# -- serialize ---------------------------------------------------------------


def _finding_to_dict(fd: VisualReviewFinding) -> dict:
    d = {
        "id": fd.id,
        "subject": fd.subject,
        "suspected_issue": fd.suspected_issue,
        "severity": fd.severity,
        "visual_evidence": fd.visual_evidence,
        "renders": [
            ({"path": r.path} if r.content_hash is None
             else {"path": r.path, "content_hash": r.content_hash})
            for r in fd.renders
        ],
        "invariant_family": fd.invariant_family,
        "recommended_action": fd.recommended_action,
        "resolution": (
            {"status": fd.resolution.status} if not fd.resolution.note
            else {"status": fd.resolution.status, "note": fd.resolution.note}
        ),
    }
    if fd.notes:
        d["notes"] = fd.notes
    return d


def dump_findings_text(store: FindingStore) -> str:
    """Serialize a :class:`FindingStore` back to YAML text. Round-trips with
    :func:`load_findings_text` (load → dump → load yields equal findings)."""
    payload = {
        "version": store.version,
        "findings": [_finding_to_dict(fd) for fd in store.findings],
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100)
