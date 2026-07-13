"""Doc-level prose-vs-model guard for the consolidated build document.

The site model is TREEFREE: the platform is free-standing and the beams CLEAR the
live trunk by a growth gap — nothing lags or slots into the tree. The consolidated
document's authored prose (panels, field notes, site section, footer) must describe
that reality, so any 'lag' / 'slotted' / 'slot-hole' token in the rendered prose is
a stale-prose bug. This is the doc-level twin of
``test_tree_attachment_detail.test_report_prose_has_no_lag_or_slot_tokens`` — the
same defect-class guard, one altitude up.

The document is assembled with STUBBED geometry (fake image/GLB/manifest payloads):
the panels, field-fit list, footer and the model-driven site/coverage/BOM sections
are all real, but no PNG/GLB is rendered, so this stays fast and off the tree
detail's OCCT bounding-box wobble.
"""

from __future__ import annotations

import html as htmlmod
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import consolidated_report as cr  # noqa: E402


def _prose(html: str) -> str:
    """The human-readable prose of the document: the sheet body with the viewer
    JS/CSS, base64 payloads and markup stripped. (The interactive viewer's own
    code legitimately uses 'slot' — 'viewer-slot' — and base64 GLB blobs contain
    random letters; neither is prose, so both are removed before the token scan.)"""
    m = re.search(r'<div class="sheet">(.*?)</div>\s*<script type="application/json"',
                  html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S)
    body = re.sub(r"data:[^\"']+", " ", body)          # data URIs
    body = re.sub(r"<[^>]+>", " ", body)               # tags (drops class= attrs)
    return htmlmod.unescape(body).lower()


@pytest.fixture(scope="module")
def doc_prose() -> str:
    details = cr.load_details()
    detail_reports = {n: d.validate() for n, d in details.items()}
    site = cr.load_site()
    site_report = site.validate()
    purchased, existing = cr.combined_bom(details)
    from detailgen.core.cutplan import pack
    cut_plans = pack(cr.lumber_cut_items(purchased, details))

    # Stubbed geometry surfaces — this guard is about prose, not renders.
    images = {n: {v: "data:image/png;base64,AAAA" for v in cr.PANELS[n]["views"]}
              for n in details}
    payloads = {n: {"slug": n} for n in details}
    glb_b64 = {n: "" for n in details}
    manifests = {n: {"build": {"versions": {"python": "3.x"},
                               "assembly_hash": "0" * 16}} for n in details}

    return _prose(cr.build_html(
        details, images, purchased, existing, cut_plans, manifests,
        payloads, glb_b64, site, site_report, detail_reports))


@pytest.mark.parametrize("pattern", [
    r"\blags?\b", r"\blagg(?:ed|ing)\b",   # lag / lags / lagged / lagging
    r"\bslotted\b", r"\bslots?\b",          # slotted / slot / slots
    r"slot[-\s]?hole",                       # slot-hole / slot hole
])
def test_document_prose_has_no_lag_or_slot_tokens(doc_prose, pattern):
    hit = re.search(pattern, doc_prose)
    assert hit is None, (
        f"stale {pattern!r} token in the consolidated document prose "
        f"(context: ...{doc_prose[max(0, hit.start() - 60):hit.end() + 60]}...)"
    )


def test_document_prose_describes_the_clearance_reality(doc_prose):
    """A positive companion to the token guard: the tree panel is the growth-gap
    clearance version, and the platform reads free-standing — so the model's
    reality is actually present, not merely un-contradicted."""
    assert "growth gap" in doc_prose
    assert "free-standing" in doc_prose
    assert "clear" in doc_prose  # 'clears the trunk' / 'clear of the bark'
