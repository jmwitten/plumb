"""Post-render review manifest: path/hash/detail/view enumeration and geometry
provenance — including one pass against a REAL rendered PNG."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from detailgen.review.manifest import build_review_manifest

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"


def _write_png(path: Path, payload: bytes) -> None:
    """A minimal stand-in PNG (real signature + arbitrary bytes) — enough to
    exercise the enumerate/hash/parse path without a multi-second render."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + payload)


def test_enumerates_paths_hashes_detail_and_view(tmp_path):
    renders = tmp_path / "outputs" / "consolidated" / "renders"
    _write_png(renders / "platform" / "platform_iso.png", b"a")
    _write_png(renders / "platform" / "platform_front.png", b"b")
    _write_png(renders / "site_overview" / "site_overview_top.png", b"c")

    man = build_review_manifest(renders, repo_root=tmp_path)
    by_path = man.by_path()

    assert set(by_path) == {
        "outputs/consolidated/renders/platform/platform_iso.png",
        "outputs/consolidated/renders/platform/platform_front.png",
        "outputs/consolidated/renders/site_overview/site_overview_top.png",
    }
    e = by_path["outputs/consolidated/renders/platform/platform_front.png"]
    assert e.detail == "platform"
    assert e.view == "front"
    assert e.content_hash == hashlib.sha256(b"\x89PNG\r\n\x1a\nb").hexdigest()
    site = by_path["outputs/consolidated/renders/site_overview/site_overview_top.png"]
    assert site.detail == "site_overview" and site.view == "top"


def test_content_hash_changes_when_bytes_change(tmp_path):
    renders = tmp_path / "renders"
    p = renders / "platform" / "platform_iso.png"
    _write_png(p, b"one")
    h1 = build_review_manifest(renders, repo_root=tmp_path).renders[0].content_hash
    _write_png(p, b"two")
    h2 = build_review_manifest(renders, repo_root=tmp_path).renders[0].content_hash
    assert h1 != h2  # this is what makes a stale review detectable


def test_assembly_hash_provenance_from_detail_manifest(tmp_path):
    renders = tmp_path / "renders"
    _write_png(renders / "platform" / "platform_iso.png", b"a")
    (renders / "platform" / "detail.manifest.json").write_text(
        json.dumps({"build": {"assembly_hash": "abc123"}}))
    (renders / "site_overview" / "site_overview_iso.png").parent.mkdir(parents=True)
    _write_png(renders / "site_overview" / "site_overview_iso.png", b"b")
    (renders / "site_overview" / "site_overview.manifest.json").write_text(
        json.dumps({"assembly_hash": "def456"}))  # top-level form

    by_path = build_review_manifest(renders, repo_root=tmp_path).by_path()
    assert by_path[[p for p in by_path if "platform" in p][0]].assembly_hash == "abc123"
    assert by_path[[p for p in by_path if "site_overview" in p][0]].assembly_hash == "def456"


def test_missing_manifest_leaves_assembly_hash_none(tmp_path):
    renders = tmp_path / "renders"
    _write_png(renders / "platform" / "platform_iso.png", b"a")
    assert build_review_manifest(renders, repo_root=tmp_path).renders[0].assembly_hash is None


def test_manifest_is_ordered_and_stable(tmp_path):
    renders = tmp_path / "renders"
    for name in ("zeta", "alpha", "mid"):
        _write_png(renders / name / f"{name}_iso.png", name.encode())
    paths = [e.path for e in build_review_manifest(renders, repo_root=tmp_path).renders]
    assert paths == sorted(paths)


def test_manifest_against_a_real_render(tmp_path):
    """Manifest generation against a REAL build's render: compile a detail,
    VALIDATE it, render one PNG, then enumerate the on-disk image.

    Rendered IN-PROCESS. This used to require a subprocess because
    ``export_png`` tessellated the shared cached OCCT solids in place, dirtying
    process-global geometry that the 1e-6 transform oracles read. That is fixed
    at the source — the exporters now mesh ``isolated_world_solids`` deep
    copies (see ``rendering.export`` / ``assemblies.assembly``), and
    ``tests/test_export_cache_isolation.py`` proves a render leaves the cache
    byte-identical — so a real render no longer contaminates anything and needs
    no isolation."""
    from detailgen.spec.compiler import compile_spec_file
    from detailgen.rendering.export import export_png

    renders = tmp_path / "outputs" / "consolidated" / "renders"
    out = renders / "rock_anchor"
    out.mkdir(parents=True)
    png = out / "rock_anchor_iso.png"

    detail = compile_spec_file(DETAILS / "rock_anchor.spec.yaml")
    report = detail.validate()                  # validate BEFORE exporting
    assert report.ok, "rock_anchor did not validate clean before export"
    export_png(detail.assembly, png, view="iso", size=(400, 300))
    assert png.exists() and png.stat().st_size > 0

    man = build_review_manifest(renders, repo_root=tmp_path)
    entry = man.by_path()["outputs/consolidated/renders/rock_anchor/rock_anchor_iso.png"]
    assert entry.detail == "rock_anchor"
    assert entry.view == "iso"
    assert entry.content_hash == hashlib.sha256(png.read_bytes()).hexdigest()
