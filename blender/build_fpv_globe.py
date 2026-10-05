"""Build the FPV Earth Blender scene from the audited project tables.

Run with Blender 3.6+:
  blender -b --python blender/build_fpv_globe.py

The scene uses WGS84 longitude/latitude converted to a geocentric sphere.  The
visual event animation is evidence-aware: Yamakura is a localized-change pulse,
Omkareshwar is a below-detection pulse, and the only translated object is the
explicitly labelled 40 m *synthetic* Tengeh replay (visually exaggerated).
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "external" / "global_fpv_inventory_2023.csv"
WORLD = ROOT / "docs" / "assets" / "world-countries.geojson"
OUT = ROOT / "blender" / "output"
WEB_OUT = ROOT / "docs" / "assets" / "blender"
RADIUS = 3.2
EXAGGERATION = 15000.0


def material(name, color, metallic=0.0, roughness=0.45, emission=None, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def move_to(obj, col):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)


def ll_xyz(lon, lat, radius=RADIUS):
    lam, phi = math.radians(lon), math.radians(lat)
    cp = math.cos(phi)
    return Vector((radius * cp * math.cos(lam), radius * cp * math.sin(lam), radius * math.sin(phi)))


def local_basis(lon, lat):
    lam, phi = math.radians(lon), math.radians(lat)
    east = Vector((-math.sin(lam), math.cos(lam), 0.0))
    north = Vector((-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)))
    up = ll_xyz(lon, lat, 1.0)
    return east, north, up


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        pass


def add_globe(col, ocean):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=192, ring_count=96, radius=RADIUS)
    globe = bpy.context.object
    globe.name = "Earth_WGS84"
    globe.data.materials.append(ocean)
    bpy.ops.object.shade_smooth()
    move_to(globe, col)
    return globe


def add_graticule(col, mat):
    curves = []
    for lat in range(-60, 61, 30):
        curves.append([ll_xyz(lon, lat, RADIUS * 1.0025) for lon in range(-180, 181, 3)])
    for lon in range(-180, 180, 30):
        curves.append([ll_xyz(lon, lat, RADIUS * 1.0025) for lat in range(-89, 90, 2)])
    make_polycurves("WGS84_graticule", curves, col, mat, 0.0024)


def make_polycurves(name, lines, col, mat, bevel):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 1
    data.bevel_depth = bevel
    data.bevel_resolution = 0
    for line in lines:
        if len(line) < 2:
            continue
        spline = data.splines.new("POLY")
        spline.points.add(len(line) - 1)
        for point, xyz in zip(spline.points, line):
            point.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, data)
    data.materials.append(mat)
    col.objects.link(obj)
    return obj


def add_country_boundaries(col, mat):
    geo = json.loads(WORLD.read_text(encoding="utf-8"))
    lines = []
    for feature in geo["features"]:
        geom = feature.get("geometry") or {}
        polys = geom.get("coordinates", [])
        if geom.get("type") == "Polygon":
            polys = [polys]
        if geom.get("type") != "MultiPolygon" and geom.get("type") != "Polygon":
            continue
        for poly in polys:
            if not poly:
                continue
            ring = poly[0]
            step = max(1, len(ring) // 180)
            line = [ll_xyz(float(p[0]), float(p[1]), RADIUS * 1.004) for p in ring[::step]]
            if line and (line[-1] - line[0]).length > 1e-5:
                line.append(line[0])
            lines.append(line)
    return make_polycurves("Natural_Earth_country_boundaries", lines, col, mat, 0.0045)


def load_inventory():
    rows = []
    with INVENTORY.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                row["longitude"] = float(row["longitude"])
                row["latitude"] = float(row["latitude"])
            except (TypeError, ValueError):
                continue
            rows.append(row)
    return rows


def add_marker_cloud(rows, col, mat):
    vertices, faces = [], []
    scale = 0.022
    for row in rows:
        lon, lat = row["longitude"], row["latitude"]
        center = ll_xyz(lon, lat, RADIUS * 1.012)
        east, north, up = local_basis(lon, lat)
        base = len(vertices)
        vertices.extend([
            center + up * scale * 1.9,
            center + east * scale - north * scale * 0.65,
            center - east * scale - north * scale * 0.65,
            center + north * scale,
        ])
        faces.extend([(base, base + 1, base + 2), (base, base + 1, base + 3),
                      (base, base + 2, base + 3), (base + 1, base + 2, base + 3)])
    mesh = bpy.data.meshes.new("FPV_517_geolocated_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new("FPV_517_geolocated_records", mesh)
    obj["semantic"] = "catalogue locations, not detected motion"
    col.objects.link(obj)
    return obj


def add_country_columns(rows, col, mat):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["country"], []).append(row)
    for country, items in grouped.items():
        lon = sum(i["longitude"] for i in items) / len(items)
        lat = sum(i["latitude"] for i in items) / len(items)
        base = ll_xyz(lon, lat, RADIUS * 1.008)
        up = base.normalized()
        height = 0.055 + math.log2(len(items) + 1) * 0.045
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.022, radius2=0.010, depth=height,
                                        location=base + up * height / 2)
        obj = bpy.context.object
        obj.name = f"Country_{country}_{len(items)}"
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(up)
        obj.data.materials.append(mat)
        obj["country"] = country
        obj["mapped_records"] = len(items)
        move_to(obj, col)


def add_event_marker(name, lon, lat, col, mat, frame_start, status):
    pos = ll_xyz(lon, lat, RADIUS * 1.035)
    bpy.ops.mesh.primitive_torus_add(major_segments=48, minor_segments=8, location=pos,
                                    major_radius=0.075, minor_radius=0.009)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(pos.normalized())
    obj.data.materials.append(mat)
    obj["evidence_status"] = status
    move_to(obj, col)
    for frame, scale in ((1, 0.0), (frame_start, 0.0), (frame_start + 12, 1.0),
                         (frame_start + 28, 1.45), (frame_start + 44, 1.0), (360, 1.0)):
        obj.scale = (scale,) * 3
        obj.keyframe_insert("scale", frame=frame)
    return obj


def add_synthetic_motion(col, original_mat, moved_mat):
    lon, lat = 103.643, 1.350
    east, _, up = local_basis(lon, lat)
    start = ll_xyz(lon, lat, RADIUS * 1.045)
    visible_delta = east * (40.0 / 6_371_000.0 * RADIUS * EXAGGERATION)
    end = start + visible_delta
    for label, pos, mat in (("Tengeh_original", start, original_mat), ("Tengeh_synthetic_40m", end, moved_mat)):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.045, location=pos)
        obj = bpy.context.object
        obj.name = label
        obj.data.materials.append(mat)
        obj["scientific_status"] = "controlled synthetic injection; not observed physical drift"
        move_to(obj, col)
        if "synthetic" in label:
            for frame, fac in ((1, 0.0), (245, 0.0), (285, 1.0), (360, 1.0)):
                obj.location = start.lerp(end, fac)
                obj.keyframe_insert("location", frame=frame)
    make_arrow("Tengeh_40m_E_synthetic_exaggerated", start, end, col, moved_mat)


def make_arrow(name, start, end, col, mat):
    direction = end - start
    length = direction.length
    middle = (start + end) / 2
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.012, depth=length * 0.82, location=middle - direction.normalized() * length * 0.09)
    shaft = bpy.context.object
    shaft.name = name + "_shaft"
    shaft.rotation_mode = "QUATERNION"
    shaft.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction.normalized())
    shaft.data.materials.append(mat)
    move_to(shaft, col)
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.038, depth=length * 0.18,
                                    location=end - direction.normalized() * length * 0.09)
    head = bpy.context.object
    head.name = name + "_head"
    head.rotation_mode = "QUATERNION"
    head.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction.normalized())
    head.data.materials.append(mat)
    move_to(head, col)
    for obj in (shaft, head):
        obj["display_exaggeration"] = EXAGGERATION
        obj["actual_injection_m"] = 40.0
        for frame, scale in ((1, 0.0), (244, 0.0), (260, 1.0), (360, 1.0)):
            obj.scale = (scale,) * 3
            obj.keyframe_insert("scale", frame=frame)


def add_text(text, location, size, col, mat, name, align="LEFT"):
    data = bpy.data.curves.new(name, "FONT")
    data.body = text
    data.align_x = align
    data.size = size
    data.extrude = 0.004
    data.materials.append(mat)
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    col.objects.link(obj)
    return obj


def camera_and_lighting(col, text_mat):
    # Centre the portfolio preview on the Asia-Pacific concentration rather
    # than on an empty hemisphere.
    bpy.ops.object.camera_add(location=(-2.05, 10.7, 2.15))
    camera = bpy.context.object
    camera.name = "Camera_Global"
    camera.data.lens = 52
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 10.9
    move_to(camera, col)
    bpy.context.scene.camera = camera
    target = bpy.data.objects.new("Camera_Target", None)
    target.location = (0, 0, 0)
    col.objects.link(target)
    con = camera.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    bpy.ops.object.light_add(type="AREA", location=(-4.5, -5.5, 6.0))
    key = bpy.context.object
    key.name = "Key_Light"
    key.data.energy = 1100
    key.data.shape = "DISK"
    key.data.size = 5.0
    move_to(key, col)
    bpy.ops.object.light_add(type="POINT", location=(4, 0, -1))
    rim = bpy.context.object
    rim.name = "Cyan_Rim"
    rim.data.energy = 580
    rim.data.color = (0.04, 0.65, 0.78)
    move_to(rim, col)
    title = add_text("FPV EARTH  /  OBSERVABILITY", (-4.5, -5.1, 3.75), 0.28, col, text_mat, "Title")
    title.rotation_euler = (math.radians(76), 0, 0)
    subtitle = add_text("643 catalogued  |  517 geolocated  |  measured ≠ synthetic", (-4.48, -5.08, 3.38), 0.12, col, text_mat, "Subtitle")
    subtitle.rotation_euler = (math.radians(76), 0, 0)


def configure_scene(rotation_rig):
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 360
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 3
    scene.eevee.gtao_factor = 1.2
    scene.render.resolution_x, scene.render.resolution_y = 1600, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.001, 0.003, 0.008)
    scene["crs"] = "EPSG:4326 transformed to geocentric display sphere"
    scene["catalogue_scope"] = "Nobre et al. survey through April 2023; not a live census"
    scene["movement_policy"] = "only controlled synthetic Tengeh translation is animated"
    scene["blendergis_role"] = "optional import/georeferencing bridge; numerical animation uses audited project coordinates"
    rotation_rig.rotation_euler = (0, 0, math.radians(-25))
    rotation_rig.keyframe_insert("rotation_euler", frame=1)
    rotation_rig.rotation_euler.z += math.radians(360)
    rotation_rig.keyframe_insert("rotation_euler", frame=360)
    for curve in rotation_rig.animation_data.action.fcurves:
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"
    scene.frame_set(1)


def main():
    clear_scene()
    OUT.mkdir(parents=True, exist_ok=True)
    WEB_OUT.mkdir(parents=True, exist_ok=True)
    earth_col, cat_col, event_col, annotation_col = [collection(n) for n in ("EARTH", "FPV_CATALOGUE", "EVENTS", "ANNOTATION")]
    ocean = material("Ocean", (0.006, 0.025, 0.045), metallic=0.35, roughness=0.26)
    coast = material("Boundaries", (0.10, 0.34, 0.39), emission=(0.06, 0.23, 0.29), strength=1.3)
    grid = material("Graticule", (0.025, 0.12, 0.16), emission=(0.02, 0.08, 0.10), strength=0.55)
    fpv = material("FPV_catalogue", (0.02, 0.80, 0.66), emission=(0.01, 0.52, 0.43), strength=2.0)
    columns = material("Country_density", (0.06, 0.48, 0.74), emission=(0.03, 0.27, 0.60), strength=1.7)
    event = material("Documented_event", (0.95, 0.18, 0.12), emission=(0.9, 0.06, 0.02), strength=3.5)
    null = material("Below_detection", (0.96, 0.55, 0.10), emission=(0.75, 0.25, 0.02), strength=2.4)
    synthetic = material("Synthetic_motion", (0.82, 0.18, 0.92), emission=(0.48, 0.02, 0.72), strength=3.0)
    text = material("Text", (0.78, 0.92, 0.93), emission=(0.55, 0.85, 0.88), strength=1.2)
    globe = add_globe(earth_col, ocean)
    add_graticule(earth_col, grid)
    add_country_boundaries(earth_col, coast)
    rows = load_inventory()
    add_marker_cloud(rows, cat_col, fpv)
    add_country_columns(rows, cat_col, columns)
    add_event_marker("Yamakura_localized_change_2019", 140.134, 35.4915, event_col, event, 115,
                     "documented damage; localized SAR change; rigid translation unresolved")
    add_event_marker("Omkareshwar_below_detection_2024", 76.210, 22.2145, event_col, null, 185,
                     "storm-spanning result below empirical detection threshold")
    add_synthetic_motion(event_col, fpv, synthetic)
    rotation_rig = bpy.data.objects.new("Earth_Rotation_Rig", None)
    earth_col.objects.link(rotation_rig)
    for source in (earth_col, cat_col, event_col):
        for obj in list(source.objects):
            if obj is not rotation_rig:
                obj.parent = rotation_rig
    camera_and_lighting(annotation_col, text)
    configure_scene(rotation_rig)
    scene = bpy.context.scene
    scene.render.filepath = str(WEB_OUT / "fpv_globe_preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "fpv_earth_observatory.blend"))
    bpy.ops.render.render(write_still=True)
    scene.frame_set(285)
    bpy.ops.export_scene.gltf(filepath=str(WEB_OUT / "fpv_globe_scene.glb"), export_format="GLB",
                              use_selection=False, export_animations=True)
    manifest = {
        "scene": "fpv_earth_observatory.blend",
        "catalogued": 643,
        "geolocated_rendered": len(rows),
        "timeline_frames": [1, 360],
        "event_semantics": {
            "Yamakura": "localized structural change; no resolved rigid translation",
            "Omkareshwar": "below detection; not zero motion",
            "Tengeh": f"40 m controlled synthetic eastward injection; display {int(EXAGGERATION)}x exaggerated",
        },
        "coordinate_transform": "WGS84 lon/lat to geocentric sphere",
    }
    (OUT / "scene_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
