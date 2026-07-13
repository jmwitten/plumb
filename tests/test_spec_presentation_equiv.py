"""Presentation-surface self-consistency — a compiled ``SpecDetail`` provides all
five surfaces beyond the declarative lifecycle, and each renders correct, wired
output for every shipped detail:

  1. ``rendered_callouts()`` — param-derived dimension callouts,
  2. ``explode_vectors()`` — per-part exploded-view offsets,
  3. the ``_document`` report (``validation_report.md``),
  4. ``cross_check()`` — the escape-hatch independent constraint solve,
  5. ``_export`` — the GLB + manifest artifacts.

For every detail each surface is present, structurally valid, and internally
consistent: the callouts the manifest cites ARE ``rendered_callouts()``, the
report renders with its coverage matrix, and the cross_check solve returns its
declared shape with a physically-bounded result. The transform/geometry parity
these surfaces ride on is proven to <=1e-6 by ``test_<detail>_spec.py`` against
the frozen-truth corpus.
"""

from __future__ import annotations

import difflib
import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file

DETAILS = Path(__file__).resolve().parents[1] / "details"

#: detail stem -> whether it declares an escape-hatch cross_check (rock anchor's
#: independent leveling-deviation solve; the others declare none).
_HAS_CROSS_CHECK = {
    "rock_anchor": True, "tree_attachment": False,
    "trolley_launch": False, "platform": False,
}
CASES = ["rock_anchor", "tree_attachment", "trolley_launch", "platform"]


@pytest.mark.parametrize("stem", CASES)
def test_presentation_surfaces_render_and_are_consistent(stem, tmp_path):
    d = compile_spec_file(DETAILS / f"{stem}.spec.yaml")
    d.validate()
    part_names = {p.name for p in d.assembly.parts}

    # 1. callouts — resolved against live params; each has a label + two finite,
    #    3-D endpoints. Every shipped detail declares at least one.
    callouts = d.rendered_callouts()
    assert callouts, f"{stem}: expected dimension callouts, got none"
    for c in callouts:
        assert c["label"], f"{stem}: callout with empty label"
        for pt in (c["p0"], c["p1"]):
            assert len(pt) == 3 and all(math.isfinite(v) for v in pt), \
                f"{stem}: non-finite callout endpoint {pt!r}"

    # 2. explode vectors — keyed by real placed-part names, 3-vectors.
    ev = d.explode_vectors()
    assert set(ev) <= part_names, \
        f"{stem}: explode_vectors names unknown parts {set(ev) - part_names}"
    for name, vec in ev.items():
        assert len(vec) == 3 and all(math.isfinite(v) for v in vec), \
            f"{stem}: bad explode vector for {name!r}: {vec!r}"

    # 4. cross_check — present exactly for the details that declare it; the
    #    escape-hatch solve returns a dict whose leveling deviation is a finite,
    #    physically-bounded value (sub-inch on a leveled anchor), not a NaN or a
    #    runaway. (The absolute value drifts ~4e-5in across cadquery solves, so
    #    only its magnitude bound is asserted, per test_trolley_launch_spec.py:26.)
    cc = d.cross_check()
    if _HAS_CROSS_CHECK[stem]:
        assert isinstance(cc, dict) and cc, f"{stem}: expected a cross_check dict"
        assert "max_radial_deviation_in" in cc, f"{stem}: cross_check missing the solved field"
        dev = cc["max_radial_deviation_in"]
        assert math.isfinite(dev) and 0 <= dev < 1.0, \
            f"{stem}: cross_check deviation {dev} not a bounded sub-inch value"
    else:
        assert cc is None, f"{stem}: expected no cross_check, got {cc!r}"

    # 3 + 5. render the artifacts (gated), then check the report + manifest.
    out = tmp_path / stem
    if not d.report.ok:
        # PRE-STRUCT the platform is DIRTY: its deck walking_surface is unsupported
        # at the tree end (the task-SUPPORT acceptance proof), so the GATED render
        # path correctly REFUSES to export it. The ungated presentation surfaces
        # above (callouts / explode / cross_check) are already checked; assert the
        # gate holds and stop (there is nothing to export for a rejected detail).
        with pytest.raises(AssertionError):
            d.render(out)
        return
    d.render(out)

    # 3. the report renders with the coverage matrix the base appends.
    report = (out / "validation_report.md").read_text()
    assert report.strip(), f"{stem}: empty validation_report.md"
    assert "Coverage matrix" in report, f"{stem}: report missing the coverage matrix"

    # 5. the manifest's presentation payload cites the SAME callouts (internal
    #    consistency: the overlay dimensions the viewer draws ARE the detail's
    #    rendered_callouts), and its explode offsets cover the parts.
    manifest = json.loads((out / "detail.manifest.json").read_text())
    assert manifest["dimensions"] == callouts, \
        f"{stem}: manifest dimensions diverge from rendered_callouts()"
    assert {p["name"] for p in manifest["parts"]} == part_names, \
        f"{stem}: manifest parts diverge from the assembly"


# --------------------------------------------------------------------------- #
# Presentation golden — the consolidated build document's TEXT LAYER (docrebuild).
#
# The per-detail self-consistency checks above prove each surface is wired; this
# adds a whole-document drift guard: the rendered zipline build document's prose +
# structure, pinned to a committed baseline. A prose edit (or a model change that
# reaches the document) shows up as a reviewable diff, never a silent drift.
#
# Stripping / normalization (what is deliberately EXCLUDED, and why):
#   * The whole viewer-asset block after the sheet — the coarse per-detail web GLB
#     (gzip mtime bytes differ run-to-run) + its base64 payload + vendored three.js
#     — is excluded by construction: the golden is the ``<div class="sheet">`` body
#     only.
#   * VTK PNG data-URIs (independent-render noise, differ pixel-for-pixel run to
#     run) are replaced with a placeholder.
#   * The provenance assembly-geometry hashes are geometry-coupled (guarded already
#     by tests/baselines/frozen_truth + test_reproducible_builds) and the toolchain
#     version stamp is environment-coupled; both are normalized so this golden
#     tracks PROSE + STRUCTURE, not geometry hashes or the local toolchain.
# The document is assembled with STUBBED image/GLB payloads but REAL per-detail
# manifests (build_manifest) and REAL model-driven sections, so the pinned text
# layer is byte-identical to the fully-rendered document's stripped sheet body
# (verified during docrebuild) while staying fast and off the OCCT render wobble.
# --------------------------------------------------------------------------- #
DOC_GOLDEN = Path(__file__).resolve().parent / "baselines" / "consolidated_doc.textlayer.html"
_PNG_URI = re.compile(r"data:image/png;base64,[A-Za-z0-9+/=]+")
_GEOM_HASH = re.compile(r'(<td class="hash">)[0-9a-f]{16}(</td>)')
_TOOLCHAIN = re.compile(r"(Toolchain:\s*).*?(\s*&middot;\s*generated)", re.S)
#: A1: the header "Generated: <YYYY-MM-DD HH:MM EST>" stamp is the live BUILD
#: moment — environment-coupled, so it is normalized out here (like the toolchain
#: version stamp) and the golden tracks PROSE + STRUCTURE, not the clock.
_GENERATED = re.compile(r"(<dt>Generated</dt><dd>).*?(</dd>)", re.S)


def _build_doc_text_layer() -> str:
    """Assemble the consolidated document and return its normalized text layer
    (the sheet body; see this section's header for the exclusions)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import consolidated_report as cr
    from detailgen.core.buildinfo import build_manifest
    from detailgen.core.cutplan import pack

    details = cr.load_details()
    detail_reports = {n: d.validate() for n, d in details.items()}
    site = cr.load_site()
    site_report = site.validate()
    purchased, existing = cr.combined_bom(details)
    cut_plans = pack(cr.lumber_cut_items(purchased, details))
    images = {n: {v: "data:image/png;base64,AAAA" for v in cr.PANELS[n]["views"]}
              for n in details}
    manifests = {n: {"build": build_manifest(details[n].assembly)} for n in details}
    html = cr.build_html(
        details, images, purchased, existing, cut_plans, manifests,
        {n: {"slug": n} for n in details}, {n: "" for n in details},
        site, site_report, detail_reports)

    m = re.search(r'(<div class="sheet">.*?</div>)\s*<script type="application/json"',
                  html, re.S)
    assert m, "consolidated document has no recognizable sheet body"
    body = m.group(1)
    body = _PNG_URI.sub("data:image/png;base64,<STRIPPED-PNG>", body)
    body = _GEOM_HASH.sub(r"\1<GEOM-HASH>\2", body)
    body = _TOOLCHAIN.sub(r"\1<TOOLCHAIN-VERSIONS>\2", body)
    body = _GENERATED.sub(r"\1<GENERATED-AT>\2", body)
    return body + "\n"


def test_consolidated_document_text_layer_matches_golden():
    """Drift guard for the whole document's prose + structure.

    Regenerate deliberately after an intended change:
        REGEN_DOC_GOLDEN=1 pytest tests/test_spec_presentation_equiv.py -k text_layer
    then REVIEW THE GIT DIFF. A normal run never rewrites the baseline."""
    current = _build_doc_text_layer()
    if os.environ.get("REGEN_DOC_GOLDEN"):
        DOC_GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        DOC_GOLDEN.write_text(current, encoding="utf-8")
        pytest.skip(f"regenerated presentation golden at {DOC_GOLDEN}")
    assert DOC_GOLDEN.exists(), (
        f"presentation golden missing at {DOC_GOLDEN} — regenerate with "
        "REGEN_DOC_GOLDEN=1 pytest tests/test_spec_presentation_equiv.py -k text_layer")
    golden = DOC_GOLDEN.read_text(encoding="utf-8")
    if current != golden:
        diff = "\n".join(difflib.unified_diff(
            golden.splitlines(), current.splitlines(),
            fromfile="golden", tofile="current", lineterm=""))
        raise AssertionError(
            "consolidated document text layer drifted from the presentation "
            "golden. If intended, regenerate with REGEN_DOC_GOLDEN=1 and review "
            f"the diff:\n{diff}")
