"""Per-detail findings-store enumeration (task VISREVSTORES): the naming
convention as a first-class surface. Discovery finds the real committed stores
(zipline + caddy visual + caddy design), a NEW detail's store is loadable with
ZERO test/plumbing edits (the class this task closes), a duplicate id ACROSS a
detail's two stores is loud, and the legacy bare ``findings.yaml`` still resolves
as the zipline's visual store (compat read)."""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.review import (
    enumerate_detail_stores,
    find_detail_store,
    load_detail_stores,
)
from detailgen.review.finding import ReviewSchemaError

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "reviews" / "visual"


# -- discovery over the REAL committed stores --------------------------------


def test_enumeration_finds_zipline_and_both_caddy_stores():
    stores = enumerate_detail_stores(REVIEWS)
    # both details are discovered by filename alone — nothing hand-registered.
    assert set(stores) >= {"zipline", "caddy"}
    # the zipline's store is the renamed main store; it has a visual store, no design.
    assert stores["zipline"].visual.name == "zipline-findings.yaml"
    assert stores["zipline"].design is None
    # the caddy has BOTH kinds, and the design suffix is not mistaken for a
    # visual store named "caddy-design".
    assert stores["caddy"].visual.name == "caddy-findings.yaml"
    assert stores["caddy"].design.name == "caddy-design-findings.yaml"
    assert "caddy-design" not in stores


def test_enumeration_order_is_byte_stable():
    stores = enumerate_detail_stores(REVIEWS)
    assert list(stores) == sorted(stores)


def test_find_detail_store_resolves_by_name_and_kind():
    assert find_detail_store(REVIEWS, "zipline", "visual").name == "zipline-findings.yaml"
    assert find_detail_store(REVIEWS, "caddy", "design").name == "caddy-design-findings.yaml"
    # an absent kind / unknown detail is None, not an error (additive surface).
    assert find_detail_store(REVIEWS, "zipline", "design") is None
    assert find_detail_store(REVIEWS, "nope", "visual") is None


def test_load_detail_stores_loads_the_real_caddy_stores():
    loaded = load_detail_stores(REVIEWS, "caddy")
    assert loaded.visual is not None and loaded.design is not None
    # C1-C4 visual, D1-D5 design — no cross-store id collision (guard passes).
    assert {f.id for f in loaded.visual.findings} == {"C1", "C2", "C3", "C4"}
    assert {f.id for f in loaded.design.findings} == {"D1", "D2", "D3", "D4", "D5", "D6"}


# -- the class this task closes: a NEW detail needs zero plumbing ------------


_MIN_FINDING = """
  - id: {id}
    subject: a new detail's subject
    suspected_issue: something looks off
    severity: LOW
    visual_evidence: newdetail_iso.png shows it
    renders:
      - path: outputs/newdetail/iso.png
    invariant_family: UNKNOWN
    recommended_action: confirm against an invariant
    resolution:
      status: unresolved
"""


def _write_store(path: Path, ids: list[str]) -> None:
    path.write_text("version: 1\nfindings:" + "".join(_MIN_FINDING.format(id=i) for i in ids))


def test_new_detail_store_is_discovered_and_loaded_with_zero_edits(tmp_path):
    # a reviewer drops a store for a brand-new detail into the directory...
    _write_store(tmp_path / "newdetail-findings.yaml", ["N1", "N2"])
    stores = enumerate_detail_stores(tmp_path)
    assert set(stores) == {"newdetail"}                      # found, no registration
    loaded = load_detail_stores(tmp_path, "newdetail")
    assert [f.id for f in loaded.visual.findings] == ["N1", "N2"]
    assert loaded.design is None


def test_unknown_detail_is_a_teaching_error_naming_known_details(tmp_path):
    _write_store(tmp_path / "newdetail-findings.yaml", ["N1"])
    with pytest.raises(ReviewSchemaError) as e:
        load_detail_stores(tmp_path, "ghost")
    assert "newdetail" in str(e.value)                       # names what DOES exist


# -- cross-store id namespace is loud ----------------------------------------


def test_duplicate_id_across_a_details_stores_is_loud(tmp_path):
    _write_store(tmp_path / "dup-findings.yaml", ["X1", "X2"])
    _write_store(tmp_path / "dup-design-findings.yaml", ["X2", "X3"])   # X2 collides
    with pytest.raises(ReviewSchemaError) as e:
        load_detail_stores(tmp_path, "dup")
    msg = str(e.value)
    assert "X2" in msg and "dup-findings.yaml" in msg and "dup-design-findings.yaml" in msg


# -- schema drift stays loud (inherited from the per-file loader) ------------


def test_schema_drift_in_an_enumerated_store_is_loud(tmp_path):
    (tmp_path / "bad-findings.yaml").write_text(
        "version: 1\nfindings:\n  - id: B1\n    subjekt: typo\n")
    with pytest.raises(ReviewSchemaError):
        load_detail_stores(tmp_path, "bad")


# -- compat read + ambiguity -------------------------------------------------


def test_legacy_bare_findings_yaml_resolves_as_zipline_visual(tmp_path):
    _write_store(tmp_path / "findings.yaml", ["L1"])
    assert find_detail_store(tmp_path, "zipline", "visual").name == "findings.yaml"
    loaded = load_detail_stores(tmp_path, "zipline")
    assert [f.id for f in loaded.visual.findings] == ["L1"]


def test_canonical_and_legacy_zipline_store_cannot_coexist(tmp_path):
    _write_store(tmp_path / "findings.yaml", ["L1"])
    _write_store(tmp_path / "zipline-findings.yaml", ["Z1"])
    with pytest.raises(ReviewSchemaError) as e:
        enumerate_detail_stores(tmp_path)
    assert "zipline" in str(e.value).lower()


def test_missing_reviews_dir_is_empty_not_an_error(tmp_path):
    assert enumerate_detail_stores(tmp_path / "does-not-exist") == {}
