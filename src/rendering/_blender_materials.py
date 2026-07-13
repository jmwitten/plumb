"""Material-tag -> Blender shader-node-tree builder dispatch.

Split out of ``_blender_render.py`` (which runs INSIDE Blender's bundled
Python — a separate process from the venv ``detailgen`` is installed into,
with no ``cadquery``/``OCP`` on its path; see that module's docstring)
purely so this dispatch table is importable and unit-testable from an
ordinary pytest venv: nothing below touches ``bpy``/``bmesh`` by name at
import time — every builder receives an already-constructed Blender node
tree (``nt``) as a plain argument and calls methods on it, so the ``bpy``
name only needs to exist once a REAL node tree object is passed in at
actual Blender-render time, never at import time.

Roadmap item 8, requirement 3: the old ``if/elif`` chain in
``_blender_render.py`` silently fell back to flat gray for an
unrecognized material tag. This module mirrors
``detailgen.core.registry.Registry``'s decorator-registration / rich-
diagnostic shape (see that module's docstring) *locally* — this script
can't import the real registry either, for the same cross-process reason
it can't import the rest of ``detailgen``: :func:`resolve_material_builder`
warns loudly (never crashes, never silently grays) on an unknown tag
instead of a bare fallback.
"""

from __future__ import annotations

import sys

_MATERIAL_BUILDERS: dict = {}


def register_material_tag(tag: str):
    """Decorator: ``@register_material_tag("steel_galv")``. A duplicate
    tag is a hard error at import time — same duplicate-detection rule as
    ``detailgen.core.registry.Registry.register``."""

    def decorator(fn):
        if tag in _MATERIAL_BUILDERS:
            raise ValueError(f"material tag {tag!r} already registered")
        _MATERIAL_BUILDERS[tag] = fn
        return fn

    return decorator


def known_material_tags() -> list[str]:
    return sorted(_MATERIAL_BUILDERS)


def resolve_material_builder(tag: str):
    """Look up ``tag``'s node-tree builder function.

    Returns ``None`` on a miss — ALWAYS after printing a warning (to
    stderr, since this runs headless inside Blender's ``--background``
    process and stdout is reserved for the ``BLENDER DONE`` sentinel) that
    names the unknown tag and lists every known one. Never raises: an
    unknown tag degrades to whatever gray fallback the caller supplies, it
    does not abort the render — but it is never SILENT about doing so.
    """
    builder = _MATERIAL_BUILDERS.get(tag)
    if builder is None:
        print(
            f"WARNING: unknown material tag {tag!r} — no shader registered "
            f"for it; falling back to flat gray. Known tags: "
            f"{known_material_tags()}",
            file=sys.stderr,
        )
    return builder


def _principled(nt, base, rough, metal=0.0):
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf, out


def _seed_texture(node, seed):
    """Pin an explicit, fixed seed on a procedural texture node so repeated
    renders of the same geometry are pixel-stable. Voronoi/Noise texture
    nodes have no literal "seed" property; their optional 4D "W" coordinate
    is the documented convention for one (inert unless noise_dimensions is
    set to "4D"). The Wave texture has no W input — its output is already a
    pure function of its inputs, so we pin "Phase Offset" instead, purely to
    make the deterministic choice explicit rather than an implicit default."""
    if node.bl_idname in ("ShaderNodeTexNoise", "ShaderNodeTexVoronoi"):
        node.noise_dimensions = "4D"
        node.inputs["W"].default_value = seed
    elif node.bl_idname == "ShaderNodeTexWave":
        node.inputs["Phase Offset"].default_value = seed
    else:
        raise ValueError(f"_seed_texture: no seed convention for {node.bl_idname}")


@register_material_tag("steel_galv")
def _mat_steel_galv(nt):
    bsdf, out = _principled(nt, (0.62, 0.65, 0.68), 0.42, 1.0)
    # galvanized spangle via voronoi mottling on roughness
    vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 45
    _seed_texture(vor, 0.0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.75
    nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])


@register_material_tag("steel_zinc")
def _mat_steel_zinc(nt):
    _principled(nt, (0.70, 0.72, 0.76), 0.30, 1.0)


@register_material_tag("lumber_pt")
def _mat_lumber_pt(nt):
    bsdf, out = _principled(nt, (0.55, 0.44, 0.26), 0.72)
    wave = nt.nodes.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 2.2
    wave.inputs["Distortion"].default_value = 6
    _seed_texture(wave, 0.0)
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 12
    _seed_texture(noise, 1.0)
    mix = nt.nodes.new("ShaderNodeMixRGB"); mix.inputs["Fac"].default_value = 0.35
    mix.inputs["Color1"].default_value = (0.55, 0.44, 0.26, 1)
    mix.inputs["Color2"].default_value = (0.44, 0.34, 0.18, 1)
    nt.links.new(wave.outputs["Color"], mix.inputs["Fac"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])


@register_material_tag("lumber_spf")
def _mat_lumber_spf(nt):
    _principled(nt, (0.82, 0.68, 0.45), 0.7)


@register_material_tag("rock")
def _mat_rock(nt):
    bsdf, out = _principled(nt, (0.55, 0.55, 0.56), 0.9)
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 6
    _seed_texture(noise, 2.0)
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


@register_material_tag("concrete")
def _mat_concrete(nt):
    _principled(nt, (0.70, 0.70, 0.68), 0.85)


@register_material_tag("epoxy")
def _mat_epoxy(nt):
    _principled(nt, (0.80, 0.45, 0.20), 0.35)


def default_material(nt) -> None:
    """Flat-gray fallback for an unrecognized tag. Never called silently —
    see :func:`resolve_material_builder`."""
    _principled(nt, (0.7, 0.7, 0.7), 0.6)
