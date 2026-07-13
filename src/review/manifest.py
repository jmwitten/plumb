"""Post-render review manifest: enumerate the renders a build produced.

This is the pipeline's answer to "what is reviewable, and has it changed?" It
walks a renders tree (``outputs/consolidated/renders/<detail>/<detail>_<view>.png``
plus ``site_overview/site_overview_<view>.png``) and records, per PNG:

    path          — repo-root-relative, the SAME key a finding's RenderRef uses
    content_hash  — SHA-256 of the file bytes (content-addressed: a re-render with
                    changed geometry changes this, which is how a stale review is
                    detected)
    detail, view  — what the image shows, parsed from the path
    assembly_hash — the geometry hash from the sibling render manifest, if present
                    (provenance only — the CONTENT hash, not this, gates staleness)

The manifest is what a reviewer agent is pointed at, and what lets the subsystem
say "N renders have never been reviewed." It reads the filesystem only; it never
builds or exports anything (so it can't mutate model geometry — the known
coarse-GLB re-tessellation hazard is on the build side, not here).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


@dataclass(frozen=True)
class RenderEntry:
    """One reviewable render in a build's output."""

    path: str            # repo-root-relative posix path
    content_hash: str    # sha256 of the PNG bytes
    detail: str          # e.g. "platform", "site_overview"
    view: str            # e.g. "iso", "front", "top"
    assembly_hash: str | None = None  # geometry provenance from the render manifest


@dataclass(frozen=True)
class ReviewManifest:
    """The renders a build produced, content-addressed. Ordered by path for a
    stable, diffable manifest."""

    renders: tuple[RenderEntry, ...]

    def by_path(self) -> dict[str, RenderEntry]:
        return {e.path: e for e in self.renders}

    def to_dict(self) -> dict:
        return {
            "renders": [
                {
                    "path": e.path,
                    "content_hash": e.content_hash,
                    "detail": e.detail,
                    "view": e.view,
                    **({"assembly_hash": e.assembly_hash}
                       if e.assembly_hash is not None else {}),
                }
                for e in self.renders
            ]
        }


def _parse_detail_view(png: Path, detail_dir: str) -> tuple[str, str]:
    """``<detail_dir>/<detail>_<view>.png`` -> (detail, view). The detail is the
    containing directory name (authoritative); the view is the filename stem with
    the ``<detail>_`` prefix stripped when present, else the whole stem (so an
    unconventional filename still yields a usable, non-empty view rather than an
    empty string)."""
    stem = png.stem
    prefix = f"{detail_dir}_"
    view = stem[len(prefix):] if stem.startswith(prefix) else stem
    return detail_dir, (view or stem)


def _assembly_hash_for(detail_dir: Path) -> str | None:
    """Best-effort geometry provenance: read ``assembly_hash`` from the detail's
    sibling render manifest (``detail.manifest.json`` nests it under ``build``;
    ``site_overview.manifest.json`` holds it at top level). Provenance only —
    absence is fine and never affects staleness (the CONTENT hash does that)."""
    for name in ("detail.manifest.json", f"{detail_dir.name}.manifest.json"):
        mpath = detail_dir / name
        if not mpath.exists():
            continue
        try:
            data = json.loads(mpath.read_text())
        except (ValueError, OSError):
            return None
        build = data.get("build")
        if isinstance(build, dict) and "assembly_hash" in build:
            return build["assembly_hash"]
        if "assembly_hash" in data:
            return data["assembly_hash"]
    return None


def build_review_manifest(renders_root: str | Path,
                          repo_root: str | Path | None = None) -> ReviewManifest:
    """Enumerate every ``*.png`` under ``renders_root`` into a
    :class:`ReviewManifest`.

    ``repo_root`` sets how ``path`` is expressed (repo-root-relative, matching a
    finding's RenderRef); it defaults to ``renders_root``'s grandparent
    (``outputs/consolidated/renders`` -> repo root), and falls back to
    ``renders_root`` itself if the PNG can't be made relative to it. Renders are
    discovered by walking, so a build that adds a view or a detail appears
    automatically — no hand list of expected images."""
    renders_root = Path(renders_root)
    if repo_root is None:
        # outputs/consolidated/renders -> repo root is three parents up; but be
        # defensive if the tree is shallower than expected.
        repo_root = renders_root
        for _ in range(3):
            if repo_root.parent != repo_root:
                repo_root = repo_root.parent
    repo_root = Path(repo_root)

    entries: list[RenderEntry] = []
    for png in sorted(renders_root.rglob("*.png")):
        detail_dir = png.parent.name
        detail, view = _parse_detail_view(png, detail_dir)
        try:
            rel = png.resolve().relative_to(Path(repo_root).resolve())
            path = rel.as_posix()
        except ValueError:
            path = png.relative_to(renders_root).as_posix()
        entries.append(RenderEntry(
            path=path,
            content_hash=_sha256_file(png),
            detail=detail,
            view=view,
            assembly_hash=_assembly_hash_for(png.parent),
        ))
    entries.sort(key=lambda e: e.path)
    return ReviewManifest(renders=tuple(entries))
