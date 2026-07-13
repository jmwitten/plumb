"""Registry semantics (core/registry.py, W2-8) + the four concrete
registries populated by their defining modules at import time."""

from __future__ import annotations

import pytest

from detailgen.core.registry import (
    Registry,
    UnknownEntryError,
    DuplicateEntryError,
    components,
    materials,
    exporters,
    checks,
)


def test_register_and_get():
    r = Registry("widget")

    @r.register("a")
    class A:
        pass

    assert r.get("a") is A
    assert r["a"] is A


def test_get_unknown_raises_with_suggestion():
    r = Registry("widget")
    r.register("hex_bolt")(object())
    with pytest.raises(UnknownEntryError) as exc:
        r.get("hexbolt")
    assert "hex_bolt" in str(exc.value)
    assert exc.value.known_keys == ["hex_bolt"]
    assert exc.value.name == "hexbolt"


def test_get_unknown_no_suggestion_when_nothing_close():
    r = Registry("widget")
    r.register("alpha")(object())
    with pytest.raises(UnknownEntryError) as exc:
        r.get("zzz_totally_unrelated")
    assert "did you mean" not in str(exc.value)


def test_duplicate_registration_is_hard_error():
    r = Registry("widget")
    r.register("a")(1)
    with pytest.raises(DuplicateEntryError):
        r.register("a")(2)
    assert r.get("a") == 1  # first registration untouched


def test_override_true_replaces_entry():
    r = Registry("widget")
    r.register("a")(1)
    r.register("a", override=True)(2)
    assert r.get("a") == 2


def test_names_lists_registered_keys():
    r = Registry("widget")
    r.register("a")(1)
    r.register("b")(2)
    assert sorted(r.names()) == ["a", "b"]


def test_contains_and_len():
    r = Registry("widget")
    assert "a" not in r
    r.register("a")(1)
    assert "a" in r
    assert len(r) == 1


def test_dict_like_getitem_matches_get():
    r = Registry("widget")
    r.register("a")(1)
    assert r["a"] == r.get("a") == 1
    with pytest.raises(UnknownEntryError):
        r["missing"]


# -- concrete registries, populated by their defining module's import ------


def test_components_registry_has_expected_names():
    import detailgen.components  # noqa: F401 (import runs registration)

    expected = {
        "lumber", "concrete_pier", "footing", "slab", "boulder", "epoxy",
        "lag_screw", "hex_bolt", "washer", "structural_screw", "hex_nut",
        "threaded_rod", "joist_hanger", "post_base", "angle_bracket",
    }
    assert expected <= set(components.names())


def test_components_registry_resolves_to_the_right_class():
    import detailgen.components as comps

    assert components.get("lumber") is comps.Lumber
    assert components.get("hex_bolt") is comps.HexBolt


def test_materials_registry_matches_materials_dict():
    from detailgen.core.materials import MATERIALS

    assert set(MATERIALS) <= set(materials.names())
    for key, mat in MATERIALS.items():
        assert materials.get(key) is mat


def test_exporters_registry_has_expected_names():
    import detailgen.rendering  # noqa: F401

    expected = {"step", "stl", "png", "glb", "manifest"}
    assert expected <= set(exporters.names())


def test_exporters_registry_resolves_to_the_right_function():
    from detailgen.rendering import export_step, export_glb

    assert exporters.get("step") is export_step
    assert exporters.get("glb") is export_glb


def test_checks_registry_has_standard_pipeline_stage_names():
    import detailgen.validation.checks  # noqa: F401

    expected = {
        "interference", "contact", "bearing", "through_hole",
        "floating", "parameters",
    }
    assert expected <= set(checks.names())


def test_load_entry_points_is_a_documented_noop():
    from detailgen.core.registry import load_entry_points

    assert load_entry_points() is None
