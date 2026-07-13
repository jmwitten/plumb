"""``rendering/_blender_materials.py``: the material-tag dispatch table
split out of ``_blender_render.py`` (roadmap item 8, requirement 3 — the
Blender ``if/elif`` chain that used to silently gray an unrecognized
material tag). Deliberately importable WITHOUT ``bpy``/a Blender install —
that is the whole point of the split (see the module's own docstring) —
so this test file exercises it directly in the ordinary pytest venv.
"""

from __future__ import annotations

import pytest

from detailgen.rendering._blender_materials import (
    known_material_tags,
    register_material_tag,
    resolve_material_builder,
)


def test_known_tags_cover_every_material_used_by_shipped_details():
    # Every MATERIALS key in core/materials.py except "stainless" (not used
    # by any shipped detail's material_key — see components/*.py).
    expected = {
        "steel_galv", "steel_zinc", "lumber_pt", "lumber_spf",
        "rock", "concrete", "epoxy",
    }
    assert expected <= set(known_material_tags())


def test_resolve_known_tag_returns_its_builder_no_warning(capsys):
    builder = resolve_material_builder("steel_galv")
    assert callable(builder)
    assert capsys.readouterr().err == ""


def test_resolve_unknown_tag_warns_and_returns_none(capsys):
    builder = resolve_material_builder("no_such_tag_xyz")
    assert builder is None
    err = capsys.readouterr().err
    assert "no_such_tag_xyz" in err
    assert "WARNING" in err


def test_resolve_unknown_tag_warning_lists_known_tags(capsys):
    resolve_material_builder("no_such_tag_xyz")
    err = capsys.readouterr().err
    assert "steel_galv" in err


def test_registering_a_duplicate_tag_is_a_hard_error():
    with pytest.raises(ValueError):
        register_material_tag("steel_galv")(lambda nt: None)  # already registered
