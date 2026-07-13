"""The consolidated document gains the visual-review section additively: present
when a review block is supplied, absent (byte-for-byte no change) when it is
not — so the presentation golden and prose guard, which build without it, stay
stable. The section sits AFTER the coverage matrix (secondary to the verdict)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import consolidated_report as cr  # noqa: E402


@pytest.fixture(scope="module")
def stub_args():
    details = cr.load_details()
    detail_reports = {n: d.validate() for n, d in details.items()}
    site = cr.load_site()
    site_report = site.validate()
    purchased, existing = cr.combined_bom(details)
    from detailgen.core.cutplan import pack
    cut_plans = pack(cr.lumber_cut_items(purchased, details))
    images = {n: {v: "data:image/png;base64,AAAA" for v in cr.PANELS[n]["views"]}
              for n in details}
    payloads = {n: {"slug": n} for n in details}
    glb_b64 = {n: "" for n in details}
    manifests = {n: {"build": {"versions": {"python": "3.x"}, "assembly_hash": "0" * 16}}
                 for n in details}
    return dict(details=details, images=images, purchased=purchased, existing=existing,
                cut_plans=cut_plans, manifests=manifests, payloads=payloads,
                glb_b64=glb_b64, site=site, site_report=site_report,
                detail_reports=detail_reports)


def _build(stub_args, **extra):
    a = stub_args
    return cr.build_html(a["details"], a["images"], a["purchased"], a["existing"],
                         a["cut_plans"], a["manifests"], a["payloads"], a["glb_b64"],
                         a["site"], a["site_report"], a["detail_reports"], **extra)


def test_no_review_block_leaves_document_unchanged(stub_args):
    assert _build(stub_args) == _build(stub_args, review_block="")


def test_review_block_appears_after_coverage_matrix(stub_args):
    block = '<section class="notes visual-review"><h2>VR-MARKER</h2></section>'
    html = _build(stub_args, review_block=block)
    assert "VR-MARKER" in html
    # secondary to the verdict: it follows the coverage-matrix section
    assert html.index("coverage-matrix") < html.index("VR-MARKER")
    # ...and precedes the buy list (stays within the model-honesty band)
    assert html.index("VR-MARKER") < html.index("Buy list")


def test_build_review_block_renders_the_seed_findings():
    # exercises the real wiring helper end-to-end against the committed store
    block = cr.build_review_block()
    assert 'class="notes visual-review"' in block
    assert "smell test" in block.lower()
    assert "unresolved" in block.lower()
