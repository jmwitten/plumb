"""Headless Blender 4.x render script (run BY Blender, not imported).

Invoked as:
    blender --background --factory-startup --python _blender_render.py -- \
        --glb detail.glb --manifest detail.manifest.json --out DIR \
        --modes presentation,exploded,hidden,dimensioned --samples 180 \
        --resolution 1500 --gpu 1

Produces render_<mode>.png for each mode, plus camera_map.json (world->pixel
projection of the manifest dimension anchors, for a PIL overlay pass).

Materials are reassigned by the manifest's material tag (glTF colors are only a
fallback). The GLB arrives in millimeters; we scale the scene to metres so
Cycles light falloff behaves.
"""
import sys, os, json, math, argparse, re
from pathlib import Path

# This file runs as a standalone Blender script (see module docstring), not
# as part of the `detailgen` package — Blender's bundled Python has no
# `cadquery`/`OCP` on its path, so it can't import anything from
# `detailgen` proper. `_blender_materials.py` lives alongside this file
# specifically because it has no such dependency (see its own docstring);
# make sure this file's own directory is on sys.path before importing it,
# rather than relying on Blender's `--python <script>` invocation to have
# already put it there.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _blender_materials import apply_material  # noqa: E402

import bpy
import bmesh
from mathutils import Vector

MM_TO_M = 0.001


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--glb", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--modes", default="presentation")
    p.add_argument("--samples", type=int, default=180)
    p.add_argument("--resolution", type=int, default=1500)
    p.add_argument("--gpu", default="1")
    return p.parse_args(argv_after_ddash())


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = {}
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            name = re.sub(r"\.\d{3}$", "", o.name)
            # scale mm -> m
            o.scale = (MM_TO_M, MM_TO_M, MM_TO_M)
            meshes[name] = o
    bpy.context.view_layer.update()
    for o in list(meshes.values()):
        o.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(meshes.values()))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return meshes


# ------------------------------- materials ---------------------------------
# Node-tree builders per material tag now live in `_blender_materials.py`
# (imported above) so the tag -> builder dispatch is testable without a
# running Blender process; see that module's docstring for why "route the
# if/elif chain through a registry" means a LOCAL mirror of
# `detailgen.core.registry.Registry` here rather than importing the real
# thing (cross-process: this script runs inside Blender's own Python).
def make_material(tag, rgba):
    m = bpy.data.materials.new(tag)
    m.use_nodes = True
    nt = m.node_tree
    apply_material(nt, tag, rgba)
    return m


def assign_materials(meshes, manifest):
    cache = {}
    for part in manifest["parts"]:
        obj = meshes.get(part["name"])
        if not obj:
            continue
        tag = part["material"]
        rgba = tuple(part["rgba"])
        key = (tag, rgba)
        if key not in cache:
            cache[key] = make_material(tag, rgba)
        obj.data.materials.clear()
        obj.data.materials.append(cache[key])


def prep_smooth(meshes):
    """Merge doubles + smooth shading so Freestyle silhouettes are clean and
    cylinders don't facet."""
    for o in meshes.values():
        me = o.data
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.to_mesh(me); bm.free()
        for poly in me.polygons:
            poly.use_smooth = True


# --------------------------------- scene -----------------------------------
def scene_bounds(meshes):
    mn = Vector((1e9, 1e9, 1e9)); mx = Vector((-1e9, -1e9, -1e9))
    for o in meshes.values():
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector((min(mn[i], w[i]) for i in range(3)))
            mx = Vector((max(mx[i], w[i]) for i in range(3)))
    return mn, mx


def setup_camera(meshes, iso=True, fit=1.15):
    mn, mx = scene_bounds(meshes)
    center = (mn + mx) / 2
    size = (mx - mn)
    cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    if iso:
        az, el = math.radians(45), math.radians(35.264)
    else:
        # front elevation looking along -X (the 2D "section" direction): the
        # rod pair spreads horizontally in Y, vertical features in Z — so every
        # dimension anchor projects with real length.
        az, el = math.radians(90), math.radians(0.5)
    dist = size.length * 2 + 1
    dir_v = Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az),
                    math.sin(el)))
    cam.location = center + dir_v * dist
    # aim
    look = center - cam.location
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    cam_data.ortho_scale = size.length * fit
    bpy.context.scene.camera = cam
    return cam, center, size


def _area_light(name, loc, target, energy, size_m):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size_m
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    o.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(o)
    return o


def setup_lighting(center, size):
    d = size.length              # scene diagonal, metres (~0.5 for this detail)
    world = bpy.data.worlds.new("w"); bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.12
    # Irradiance-tuned (energy ~ distance^2 so exposure is size-independent):
    # key = soft top-front-right, fill from upper-left. Constants set by eye at
    # this ~0.5 m detail scale.
    _area_light("key", center + Vector((d, -d, d * 1.6)), center, 150 * d * d, d * 1.2)
    _area_light("fill", center + Vector((-d * 1.2, d * 0.8, d)), center, 55 * d * d, d * 1.4)
    # shadow-catcher ground just under the lowest point
    mn = center - size / 2
    bpy.ops.mesh.primitive_plane_add(size=d * 8,
                                     location=(center.x, center.y, mn.z - 1e-3))
    plane = bpy.context.active_object
    plane.is_shadow_catcher = True
    return plane


def setup_render(args, gpu):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    if gpu:
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "METAL"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = True
            sc.cycles.device = "GPU"
        except Exception as e:
            print("GPU setup failed, CPU:", e)
    sc.cycles.samples = args.samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = args.resolution
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    # composite the transparent film over pure white, preserving contact shadow
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    bg = nt.nodes.new("CompositorNodeRGB")
    bg.outputs[0].default_value = (1, 1, 1, 1)
    over = nt.nodes.new("CompositorNodeAlphaOver")
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(bg.outputs[0], over.inputs[1])
    nt.links.new(rl.outputs["Image"], over.inputs[2])
    nt.links.new(over.outputs[0], comp.inputs["Image"])


def render_to(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ------------------------------ hidden line --------------------------------
def enable_freestyle():
    sc = bpy.context.scene
    sc.render.use_freestyle = True
    sc.cycles.samples = 1
    vl = bpy.context.view_layer
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(40)
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    vis = fs.linesets.new("visible")
    vis.select_silhouette = vis.select_border = vis.select_crease = True
    vis.visibility = "VISIBLE"
    vis.linestyle.thickness = 2.0
    vis.linestyle.color = (0, 0, 0)
    hid = fs.linesets.new("hidden")
    hid.select_silhouette = hid.select_crease = True
    hid.visibility = "HIDDEN"
    st = hid.linestyle
    st.thickness = 1.0
    st.color = (0.4, 0.4, 0.4)
    st.use_dashed_line = True
    st.dash1, st.gap1 = 8, 6


def whiten(meshes):
    m = bpy.data.materials.new("white"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (1, 1, 1, 1)
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    for o in meshes.values():
        o.data.materials.clear(); o.data.materials.append(m)


# ------------------------------ dimensions ---------------------------------
def project_dimensions(cam, manifest, args, out):
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    rx, ry = args.resolution, args.resolution
    pts = []
    for dim in manifest.get("dimensions", []):
        rec = {"label": dim["label"], "p0": None, "p1": None}
        for key in ("p0", "p1"):
            w = Vector([c * MM_TO_M for c in dim[key]])
            co = world_to_camera_view(sc, cam, w)
            rec[key] = [co.x * rx, (1 - co.y) * ry]
        pts.append(rec)
    (out / "camera_map.json").write_text(json.dumps(pts, indent=1))


# --------------------------------- main ------------------------------------
def main():
    args = parse_args()
    from pathlib import Path
    out = Path(args.out)
    manifest = json.loads(Path(args.manifest).read_text())
    modes = args.modes.split(",")
    gpu = args.gpu == "1"

    for mode in modes:
        clean_scene()
        meshes = import_glb(args.glb)
        prep_smooth(meshes)
        cam, center, size = setup_camera(meshes, iso=(mode != "dimensioned"))
        setup_lighting(center, size)
        setup_render(args, gpu)

        if mode == "exploded":
            for part in manifest["parts"]:
                o = meshes.get(part["name"])
                ex = part.get("explode")
                if o and ex:
                    o.location += Vector([c * MM_TO_M for c in ex])
        if mode == "hidden":
            whiten(meshes)
            enable_freestyle()
        if mode == "dimensioned":
            project_dimensions(cam, manifest, args, out)

        render_to(str(out / f"render_{mode}.png"))
    print("BLENDER DONE")


if __name__ == "__main__":
    main()
