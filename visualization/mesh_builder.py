"""Procedural 3D Geometry and Mesh Generation Utilities for Panda3D.

Constructs detailed aerospace models, celestial bodies, and lunar terrains
with accurate vertex normals, tangents, and material color attributes.
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from panda3d.core import (
    Geom,
    GeomLines,
    GeomNode,
    GeomPoints,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Material,
    NodePath,
    Vec3,
    Vec4,
)


def create_material(
    name: str,
    diffuse: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
    specular: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0),
    ambient: Tuple[float, float, float, float] = (0.2, 0.2, 0.2, 1.0),
    shininess: float = 32.0,
    emission: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> Material:
    """Creates a configured Panda3D Material."""
    mat = Material(name)
    mat.setDiffuse(Vec4(*diffuse))
    mat.setSpecular(Vec4(*specular))
    mat.setAmbient(Vec4(*ambient))
    mat.setShininess(shininess)
    mat.setEmission(Vec4(*emission))
    return mat


def create_cylinder_or_cone(
    radius_bottom: float,
    radius_top: float,
    height: float,
    segments: int = 24,
    color: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
    caps: bool = True,
    name: str = "cylinder",
) -> NodePath:
    """Generates a smooth tapered cylinder or cone aligned along the Z axis."""
    vformat = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    # Side wall slope calculation for correct normals
    slant = (radius_bottom - radius_top) / height if height > 0 else 0.0

    for i in range(segments):
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments

        c0, s0 = math.cos(a0), math.sin(a0)
        c1, s1 = math.cos(a1), math.sin(a1)

        n0 = Vec3(c0, s0, slant)
        n0.normalize()
        n1 = Vec3(c1, s1, slant)
        n1.normalize()

        p0_b = Vec3(c0 * radius_bottom, s0 * radius_bottom, 0.0)
        p1_b = Vec3(c1 * radius_bottom, s1 * radius_bottom, 0.0)
        p1_t = Vec3(c1 * radius_top, s1 * radius_top, height)
        p0_t = Vec3(c0 * radius_top, s0 * radius_top, height)

        v_idx = i * 4
        vertex.addData3(p0_b); normal.addData3(n0); col.addData4(*color)
        vertex.addData3(p1_b); normal.addData3(n1); col.addData4(*color)
        vertex.addData3(p1_t); normal.addData3(n1); col.addData4(*color)
        vertex.addData3(p0_t); normal.addData3(n0); col.addData4(*color)

        tri.addVertices(v_idx, v_idx + 1, v_idx + 2)
        tri.addVertices(v_idx, v_idx + 2, v_idx + 3)

    base_idx = segments * 4

    if caps:
        if radius_bottom > 1e-4:
            c_idx = base_idx
            vertex.addData3(Vec3(0, 0, 0)); normal.addData3(Vec3(0, 0, -1)); col.addData4(*color)
            for i in range(segments):
                a = 2.0 * math.pi * i / segments
                vertex.addData3(Vec3(math.cos(a) * radius_bottom, math.sin(a) * radius_bottom, 0.0))
                normal.addData3(Vec3(0, 0, -1))
                col.addData4(*color)

            for i in range(segments):
                i0 = c_idx + 1 + i
                i1 = c_idx + 1 + ((i + 1) % segments)
                tri.addVertices(c_idx, i1, i0)
            base_idx += segments + 1

        if radius_top > 1e-4:
            c_idx = base_idx
            vertex.addData3(Vec3(0, 0, height)); normal.addData3(Vec3(0, 0, 1)); col.addData4(*color)
            for i in range(segments):
                a = 2.0 * math.pi * i / segments
                vertex.addData3(Vec3(math.cos(a) * radius_top, math.sin(a) * radius_top, height))
                normal.addData3(Vec3(0, 0, 1))
                col.addData4(*color)

            for i in range(segments):
                i0 = c_idx + 1 + i
                i1 = c_idx + 1 + ((i + 1) % segments)
                tri.addVertices(c_idx, i0, i1)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def create_beam(
    p0: Vec3,
    p1: Vec3,
    radius: float = 0.032,
    color: Tuple[float, float, float, float] = (0.75, 0.77, 0.8, 1.0),
    segments: int = 12,
    name: str = "beam",
) -> NodePath:
    """Generates a cylinder precisely connecting point p0 to point p1 in 3D space."""
    diff = p1 - p0
    length = diff.length()
    if length < 1e-5:
        return NodePath(name)

    vformat = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    # Generated along +Y axis so lookAt orientates it directly
    for i in range(segments):
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments
        c0, s0 = math.cos(a0), math.sin(a0)
        c1, s1 = math.cos(a1), math.sin(a1)
        idx = i * 4

        vertex.addData3(Vec3(c0 * radius, 0.0, s0 * radius)); normal.addData3(Vec3(c0, 0, s0)); col.addData4(*color)
        vertex.addData3(Vec3(c1 * radius, 0.0, s1 * radius)); normal.addData3(Vec3(c1, 0, s1)); col.addData4(*color)
        vertex.addData3(Vec3(c1 * radius, length, s1 * radius)); normal.addData3(Vec3(c1, 0, s1)); col.addData4(*color)
        vertex.addData3(Vec3(c0 * radius, length, s0 * radius)); normal.addData3(Vec3(c0, 0, s0)); col.addData4(*color)

        tri.addVertices(idx, idx + 1, idx + 2)
        tri.addVertices(idx, idx + 2, idx + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    np = NodePath(node)
    np.setPos(p0)
    np.lookAt(p1)
    return np


def create_box(
    sx: float,
    sy: float,
    sz: float,
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    color: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
    name: str = "box",
) -> NodePath:
    """Generates an axis-aligned box with dedicated face normals."""
    vformat = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    cx, cy, cz = center

    faces = [
        (Vec3(1, 0, 0), [Vec3(hx, -hy, -hz), Vec3(hx, hy, -hz), Vec3(hx, hy, hz), Vec3(hx, -hy, hz)]),
        (Vec3(-1, 0, 0), [Vec3(-hx, hy, -hz), Vec3(-hx, -hy, -hz), Vec3(-hx, -hy, hz), Vec3(-hx, hy, hz)]),
        (Vec3(0, 1, 0), [Vec3(hx, hy, -hz), Vec3(-hx, hy, -hz), Vec3(-hx, hy, hz), Vec3(hx, hy, hz)]),
        (Vec3(0, -1, 0), [Vec3(-hx, -hy, -hz), Vec3(hx, -hy, -hz), Vec3(hx, -hy, hz), Vec3(-hx, -hy, hz)]),
        (Vec3(0, 0, 1), [Vec3(-hx, -hy, hz), Vec3(hx, -hy, hz), Vec3(hx, hy, hz), Vec3(-hx, hy, hz)]),
        (Vec3(0, 0, -1), [Vec3(-hx, hy, -hz), Vec3(hx, -hy, -hz), Vec3(hx, -hy, -hz), Vec3(-hx, hy, -hz)]),
    ]

    for f_idx, (fn, corners) in enumerate(faces):
        idx = f_idx * 4
        for c in corners:
            vertex.addData3(Vec3(c.x + cx, c.y + cy, c.z + cz))
            normal.addData3(fn)
            col.addData4(*color)
        tri.addVertices(idx, idx + 1, idx + 2)
        tri.addVertices(idx, idx + 2, idx + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def create_sphere(
    radius: float = 1.0,
    rings: int = 16,
    sectors: int = 24,
    color: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
    name: str = "sphere",
) -> NodePath:
    """Generates a UV-sphere with smooth radial normals."""
    vformat = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    for r in range(rings + 1):
        theta = math.pi * r / rings
        sin_t, cos_t = math.sin(theta), math.cos(theta)
        for s in range(sectors + 1):
            phi = 2.0 * math.pi * s / sectors
            sin_p, cos_p = math.sin(phi), math.cos(phi)

            nx = sin_t * cos_p
            ny = sin_t * sin_p
            nz = cos_t

            vertex.addData3(Vec3(nx * radius, ny * radius, nz * radius))
            normal.addData3(Vec3(nx, ny, nz))
            col.addData4(*color)

    for r in range(rings):
        for s in range(sectors):
            i0 = r * (sectors + 1) + s
            i1 = (r + 1) * (sectors + 1) + s
            i2 = (r + 1) * (sectors + 1) + (s + 1)
            i3 = r * (sectors + 1) + (s + 1)

            tri.addVertices(i0, i1, i2)
            tri.addVertices(i0, i2, i3)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def create_ring_or_disc(
    inner_radius: float,
    outer_radius: float,
    segments: int = 24,
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    normal_dir: Vec3 = Vec3(0, 0, 1),
    name: str = "ring",
) -> NodePath:
    """Generates a planar circular ring or solid disc."""
    vformat = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    for i in range(segments):
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments

        c0, s0 = math.cos(a0), math.sin(a0)
        c1, s1 = math.cos(a1), math.sin(a1)

        idx = i * 4
        vertex.addData3(Vec3(c0 * inner_radius, s0 * inner_radius, 0.0)); normal.addData3(normal_dir); col.addData4(*color)
        vertex.addData3(Vec3(c1 * inner_radius, s1 * inner_radius, 0.0)); normal.addData3(normal_dir); col.addData4(*color)
        vertex.addData3(Vec3(c1 * outer_radius, s1 * outer_radius, 0.0)); normal.addData3(normal_dir); col.addData4(*color)
        vertex.addData3(Vec3(c0 * outer_radius, s0 * outer_radius, 0.0)); normal.addData3(normal_dir); col.addData4(*color)

        tri.addVertices(idx, idx + 1, idx + 2)
        tri.addVertices(idx, idx + 2, idx + 3)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def build_3d_lunar_terrain(
    terrain_coords: List[Tuple[float, float]],
    y_front: float = -8.0,
    y_back: float = 8.0,
    depth_segments: int = 10,
    name: str = "lunar_terrain",
) -> NodePath:
    """Extrudes 2D Box2D terrain points into a realistic 3D lunar surface mesh."""
    if not terrain_coords or len(terrain_coords) < 2:
        terrain_coords = [(-16.0, 0.0), (16.0, 0.0)]

    vformat = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    nx_points = len(terrain_coords)
    ny_points = depth_segments + 1
    rng = random.Random(42)

    for iy in range(ny_points):
        v_ratio = iy / depth_segments
        y_val = y_front + (y_back - y_front) * v_ratio
        basin_offset = (v_ratio - 0.5) ** 2 * 0.4

        for ix in range(nx_points):
            bx, bz = terrain_coords[ix]
            dist_from_pad = abs(bx)
            if dist_from_pad > 1.4:
                noise_z = rng.uniform(-0.07, 0.07) + math.sin(bx * 0.7 + y_val * 0.4) * 0.1
            else:
                noise_z = 0.0

            z_val = bz - basin_offset + noise_z
            tone = rng.uniform(0.18, 0.28)

            vertex.addData3(Vec3(bx, y_val, z_val))
            normal.addData3(Vec3(0, 0, 1))
            col.addData4(tone, tone * 0.98, tone * 0.95, 1.0)

    for iy in range(depth_segments):
        for ix in range(nx_points - 1):
            i0 = iy * nx_points + ix
            i1 = iy * nx_points + (ix + 1)
            i2 = (iy + 1) * nx_points + (ix + 1)
            i3 = (iy + 1) * nx_points + ix

            tri.addVertices(i0, i1, i2)
            tri.addVertices(i0, i2, i3)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    np = NodePath(node)

    # Front cliff wall to seal the near horizon
    cliff = create_box(
        sx=(terrain_coords[-1][0] - terrain_coords[0][0]) * 1.2,
        sy=1.0,
        sz=4.0,
        center=(0.0, y_front - 0.5, -2.0),
        color=(0.12, 0.12, 0.13, 1.0),
        name="cliff_wall",
    )
    cliff.reparentTo(np)
    return np


def create_starfield(count: int = 2500, radius: float = 100.0, name: str = "starfield") -> NodePath:
    """Generates an immersive celestial sphere of stars in deep black vacuum."""
    vformat = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    col = GeomVertexWriter(vdata, "color")
    points = GeomPoints(Geom.UHStatic)

    rng = random.Random(1337)
    for i in range(count):
        u = rng.uniform(-1.0, 1.0)
        phi = rng.uniform(0.0, 2.0 * math.pi)
        r_scale = math.sqrt(max(0.0, 1.0 - u * u))

        px = r_scale * math.cos(phi) * radius
        py = r_scale * math.sin(phi) * radius
        pz = u * radius

        mag = rng.uniform(0.35, 1.0)
        c_choice = rng.random()
        if c_choice < 0.2:
            r, g, b = 0.8 * mag, 0.9 * mag, 1.0 * mag
        elif c_choice < 0.35:
            r, g, b = 1.0 * mag, 0.9 * mag, 0.7 * mag
        else:
            r, g, b = 0.95 * mag, 0.95 * mag, 0.95 * mag

        vertex.addData3(Vec3(px, py, pz))
        col.addData4(r, g, b, 1.0)
        points.addVertex(i)

    geom = Geom(vdata)
    geom.addPrimitive(points)
    node = GeomNode(name)
    node.addGeom(geom)
    np = NodePath(node)
    np.setLightOff()
    return np


def create_earth_globe(radius: float = 3.8, name: str = "earth_globe") -> NodePath:
    """Creates a high-realism distant Earth globe with continents, clouds, and atmosphere."""
    root = NodePath(name)

    ocean = create_sphere(radius=radius, rings=24, sectors=36, color=(0.06, 0.22, 0.52, 1.0), name="ocean")
    ocean.reparentTo(root)

    clouds = create_sphere(radius=radius * 1.015, rings=20, sectors=30, color=(0.95, 0.98, 1.0, 0.35), name="clouds")
    clouds.setTransparency(True)
    clouds.reparentTo(root)

    halo = create_ring_or_disc(radius * 1.01, radius * 1.12, segments=36, color=(0.2, 0.55, 0.95, 0.35), name="halo")
    halo.setTransparency(True)
    halo.reparentTo(root)

    return root


def create_spaceport_sky(radius: float = 220.0, name: str = "spaceport_sky") -> NodePath:
    """Builds an atmospheric daytime skydome with realistic blue gradient and cumulus clouds."""
    root = NodePath(name)
    vformat = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("sky_geom", vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    rings = 16
    sectors = 32
    # Upper hemisphere only
    for r in range(rings + 1):
        phi = (math.pi * 0.5) * (r / rings)
        z = math.sin(phi) * radius
        r_xy = math.cos(phi) * radius
        t_elev = r / rings  # 0 at horizon, 1 at zenith

        # Sky gradient: pale cyan/white at horizon -> rich aerospace blue at zenith
        red = 0.72 - 0.54 * t_elev
        green = 0.84 - 0.38 * t_elev
        blue = 0.96 - 0.08 * t_elev

        for s in range(sectors + 1):
            theta = 2.0 * math.pi * s / sectors
            x = math.cos(theta) * r_xy
            y = math.sin(theta) * r_xy
            vertex.addData3(Vec3(x, y, z))
            col.addData4(red, green, blue, 1.0)

    for r in range(rings):
        for s in range(sectors):
            i0 = r * (sectors + 1) + s
            i1 = i0 + 1
            i2 = (r + 1) * (sectors + 1) + s + 1
            i3 = (r + 1) * (sectors + 1) + s
            tri.addVertices(i0, i2, i1)
            tri.addVertices(i0, i3, i2)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode("sky_dome")
    node.addGeom(geom)
    dome_np = root.attachNewNode(node)
    dome_np.setLightOff()

    # Fluffy cumulus cloud banks along the distant horizon
    rng = random.Random(42)
    clouds_root = root.attachNewNode("clouds")
    for i in range(24):
        ang = rng.uniform(0.0, 2.0 * math.pi)
        dist = rng.uniform(radius * 0.65, radius * 0.85)
        cx = math.cos(ang) * dist
        cy = math.sin(ang) * dist
        cz = rng.uniform(radius * 0.08, radius * 0.22)
        cw = rng.uniform(18.0, 36.0)
        ch = rng.uniform(6.0, 14.0)

        cloud = create_box(cw, cw * 0.6, ch, color=(0.96, 0.96, 0.98, 0.85), name=f"cloud_{i}")
        cloud.setPos(cx, cy, cz)
        cloud.setTransparency(True)
        cloud.setLightOff()
        cloud.reparentTo(clouds_root)

    return root


def create_spaceport_ground(radius: float = 200.0, name: str = "spaceport_ground") -> NodePath:
    """Creates expansive green grassland terrain with rolling hills and perimeter access roads."""
    vformat = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, vformat, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    col = GeomVertexWriter(vdata, "color")
    tri = GeomTriangles(Geom.UHStatic)

    rings = 18
    sectors = 36
    for r in range(rings + 1):
        frac = r / rings
        dist = 8.0 + (radius - 8.0) * (frac ** 1.3)
        for s in range(sectors + 1):
            theta = 2.0 * math.pi * s / sectors
            x = math.cos(theta) * dist
            y = math.sin(theta) * dist

            # Gentle rolling hills, flattening near center launchpad
            hill = 0.0
            if dist > 22.0:
                hill = math.sin(x * 0.04) * math.cos(y * 0.04) * 2.5 + math.sin(theta * 3.0) * 1.5
            if dist > 90.0:
                hill += math.sin(theta * 5.0) * 6.0

            z = hill - 0.1

            # Meadow green with distance atmospheric haze
            g_red = 0.26 + 0.12 * frac
            g_green = 0.42 + 0.08 * frac
            g_blue = 0.18 + 0.18 * frac

            vertex.addData3(Vec3(x, y, z))
            normal.addData3(Vec3(0, 0, 1))
            col.addData4(g_red, g_green, g_blue, 1.0)

    for r in range(rings):
        for s in range(sectors):
            i0 = r * (sectors + 1) + s
            i1 = i0 + 1
            i2 = (r + 1) * (sectors + 1) + s + 1
            i3 = (r + 1) * (sectors + 1) + s
            tri.addVertices(i0, i1, i2)
            tri.addVertices(i0, i2, i3)

    geom = Geom(vdata)
    geom.addPrimitive(tri)
    node = GeomNode(name)
    node.addGeom(geom)
    np = NodePath(node)

    # Perimeter dark asphalt access roads
    road = create_ring_or_disc(34.0, 36.5, segments=48, color=(0.20, 0.21, 0.22, 1.0), name="access_road")
    road.setPos(0, 0, 0.02)
    road.reparentTo(np)

    road2 = create_ring_or_disc(68.0, 71.0, segments=64, color=(0.22, 0.23, 0.25, 1.0), name="perimeter_road")
    road2.setPos(0, 0, 0.02)
    road2.reparentTo(np)

    return np


def create_spaceport_launchpad(name: str = "spaceport_pad") -> NodePath:
    """Builds realistic concrete launch/landing pad complex with expansion seams, markings, and flame trench."""
    root = NodePath(name)

    # 1. Main concrete apron slab (light warm grey concrete)
    pad_base = create_box(26.0, 36.0, 0.20, center=(0.0, 0.0, 0.10), color=(0.68, 0.70, 0.72, 1.0), name="pad_slab")
    pad_base.reparentTo(root)

    # Concrete apron expansion joint seams (subtle dark grid lines across apron)
    seam_col = (0.42, 0.44, 0.47, 1.0)
    for sx in (-9.0, -4.5, 4.5, 9.0):
        seam_x = create_box(0.04, 36.0, 0.01, center=(sx, 0.0, 0.205), color=seam_col)
        seam_x.reparentTo(root)
    for sy in (-12.0, -6.0, 6.0, 12.0):
        seam_y = create_box(26.0, 0.04, 0.01, center=(0.0, sy, 0.205), color=seam_col)
        seam_y.reparentTo(root)

    # Concrete apron expansion curbs / border trims
    curb_l = create_box(0.35, 36.0, 0.26, center=(-13.0, 0.0, 0.13), color=(0.45, 0.47, 0.50, 1.0))
    curb_l.reparentTo(root)
    curb_r = create_box(0.35, 36.0, 0.26, center=(13.0, 0.0, 0.13), color=(0.45, 0.47, 0.50, 1.0))
    curb_r.reparentTo(root)
    curb_f = create_box(26.0, 0.35, 0.26, center=(0.0, 18.0, 0.13), color=(0.45, 0.47, 0.50, 1.0))
    curb_f.reparentTo(root)
    curb_b = create_box(26.0, 0.35, 0.26, center=(0.0, -18.0, 0.13), color=(0.45, 0.47, 0.50, 1.0))
    curb_b.reparentTo(root)

    # Perimeter industrial safety railings along apron boundaries
    rail_col = (0.32, 0.35, 0.38, 1.0)
    for rx in (-12.8, 12.8):
        for ry in range(-16, 17, 4):
            post = create_beam(Vec3(rx, ry, 0.25), Vec3(rx, ry, 1.15), radius=0.022, color=rail_col)
            post.reparentTo(root)
        rail_bar = create_beam(Vec3(rx, -16.0, 1.15), Vec3(rx, 16.0, 1.15), radius=0.018, color=rail_col)
        rail_bar.reparentTo(root)
        rail_mid = create_beam(Vec3(rx, -16.0, 0.70), Vec3(rx, 16.0, 0.70), radius=0.015, color=rail_col)
        rail_mid.reparentTo(root)

    # 2. Dual yellow guidance / railway tracks
    for tx in (-1.8, 1.8):
        track = create_box(0.35, 32.0, 0.02, center=(tx, 0.0, 0.21), color=(0.94, 0.78, 0.12, 1.0), name=f"track_{tx}")
        track.reparentTo(root)
        rail = create_box(0.12, 32.0, 0.04, center=(tx, 0.0, 0.23), color=(0.22, 0.22, 0.24, 1.0))
        rail.reparentTo(root)

    # Center yellow hazard dashed line
    center_line = create_box(0.25, 24.0, 0.02, center=(0.0, 0.0, 0.21), color=(0.95, 0.82, 0.14, 1.0))
    center_line.reparentTo(root)

    # 3. Central launch mount ring with octagonal hazard perimeter
    oct_r = 5.2
    for i in range(8):
        a0 = i * (math.pi / 4)
        a1 = (i + 1) * (math.pi / 4)
        p0 = Vec3(math.cos(a0) * oct_r, math.sin(a0) * oct_r, 0.21)
        p1 = Vec3(math.cos(a1) * oct_r, math.sin(a1) * oct_r, 0.21)
        oct_seg = create_beam(p0, p1, radius=0.05, color=(0.92, 0.74, 0.10, 1.0))
        oct_seg.reparentTo(root)

    mount_ring = create_ring_or_disc(2.4, 3.8, segments=36, color=(0.30, 0.32, 0.35, 1.0), name="mount_ring")
    mount_ring.setPos(0, 0, 0.22)
    mount_ring.reparentTo(root)

    # Inner exhaust flame pit (recessed dark deflector grate & ramp)
    flame_pit = create_ring_or_disc(0.0, 2.4, segments=24, color=(0.11, 0.11, 0.13, 1.0), name="flame_pit")
    flame_pit.setPos(0, 0, 0.18)
    flame_pit.reparentTo(root)

    flame_grate1 = create_box(0.10, 4.4, 0.04, center=(0.0, 0.0, 0.19), color=(0.22, 0.24, 0.26, 1.0))
    flame_grate1.reparentTo(root)
    flame_grate2 = create_box(4.4, 0.10, 0.04, center=(0.0, 0.0, 0.19), color=(0.22, 0.24, 0.26, 1.0))
    flame_grate2.reparentTo(root)

    # Yellow-black hazard warning border around flame trench
    hazard_ring = create_ring_or_disc(3.8, 4.15, segments=36, color=(0.92, 0.74, 0.10, 1.0))
    hazard_ring.setPos(0, 0, 0.22)
    hazard_ring.reparentTo(root)

    # 4. Corner navigation beacons
    for bx, by in [(-12.5, -17.0), (12.5, -17.0), (-12.5, 17.0), (12.5, 17.0)]:
        post = create_cylinder_or_cone(0.06, 0.06, 0.6, color=(0.35, 0.37, 0.40, 1.0))
        post.setPos(bx, by, 0.2)
        post.reparentTo(root)
        beacon = create_sphere(0.10, color=(1.0, 0.65, 0.1, 1.0))
        beacon.setPos(bx, by, 0.8)
        beacon.reparentTo(root)

    return root


def create_spaceport_tower(height: float = 20.0, base_w: float = 2.4, top_w: float = 1.0, name: str = "tower") -> NodePath:
    """Creates a tall steel lattice floodlight/comm tower with blue and white bands."""
    root = NodePath(name)
    stages = 6
    stage_h = height / stages
    corner_signs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]

    for s in range(stages):
        z0 = s * stage_h
        z1 = (s + 1) * stage_h
        w0 = base_w - (base_w - top_w) * (s / stages)
        w1 = base_w - (base_w - top_w) * ((s + 1) / stages)

        if s in (2, 3):
            col = (0.94, 0.95, 0.97, 1.0)  # White band
        else:
            col = (0.10, 0.32, 0.68, 1.0)  # Blue band

        # 4 Corner legs for this stage
        for cx, cy in corner_signs:
            p0 = Vec3(cx * w0 * 0.5, cy * w0 * 0.5, z0)
            p1 = Vec3(cx * w1 * 0.5, cy * w1 * 0.5, z1)
            leg = create_beam(p0, p1, radius=0.045, color=col)
            leg.reparentTo(root)

        # 4 Horizontal girts at top of this stage
        for i in range(4):
            c_a = corner_signs[i]
            c_b = corner_signs[(i + 1) % 4]
            pa = Vec3(c_a[0] * w1 * 0.5, c_a[1] * w1 * 0.5, z1)
            pb = Vec3(c_b[0] * w1 * 0.5, c_b[1] * w1 * 0.5, z1)
            girt = create_beam(pa, pb, radius=0.035, color=col)
            girt.reparentTo(root)

        # X-bracing on all 4 faces
        for i in range(4):
            c_a = corner_signs[i]
            c_b = corner_signs[(i + 1) % 4]
            p_bl = Vec3(c_a[0] * w0 * 0.5, c_a[1] * w0 * 0.5, z0)
            p_br = Vec3(c_b[0] * w0 * 0.5, c_b[1] * w0 * 0.5, z0)
            p_tl = Vec3(c_a[0] * w1 * 0.5, c_a[1] * w1 * 0.5, z1)
            p_tr = Vec3(c_b[0] * w1 * 0.5, c_b[1] * w1 * 0.5, z1)

            x1 = create_beam(p_bl, p_tr, radius=0.024, color=col)
            x1.reparentTo(root)
            x2 = create_beam(p_br, p_tl, radius=0.024, color=col)
            x2.reparentTo(root)

        # Intermediate service grating platforms at stage 2 and 4
        if s in (1, 3):
            plat = create_box(w1 * 1.15, w1 * 1.15, 0.04, center=(0, 0, z1), color=(0.30, 0.32, 0.35, 1.0))
            plat.reparentTo(root)

    # Floodlight array platform on top
    head_frame = create_box(top_w * 2.2, top_w * 0.8, 0.15, center=(0, 0, height + 0.08), color=(0.25, 0.26, 0.28, 1.0))
    head_frame.reparentTo(root)

    # Floodlight lamps (2 rows of 4 lamps each)
    lamp_xs = [-top_w * 0.75, -top_w * 0.25, top_w * 0.25, top_w * 0.75]
    for lx in lamp_xs:
        for ly in (-0.22, 0.22):
            fixture = create_box(0.32, 0.26, 0.38, center=(lx, ly, height + 0.45), color=(0.20, 0.22, 0.25, 1.0))
            fixture.reparentTo(root)
            lamp = create_box(0.26, 0.04, 0.30, center=(lx, ly - 0.12, height + 0.45), color=(0.98, 0.98, 1.0, 1.0))
            lamp.setLightOff()
            lamp.reparentTo(root)

    # Aviation obstruction warning antenna mast atop tower
    antenna_mast = create_beam(Vec3(0, 0, height + 0.5), Vec3(0, 0, height + 3.2), radius=0.025, color=(0.88, 0.90, 0.94, 1.0))
    antenna_mast.reparentTo(root)
    red_beacon = create_sphere(radius=0.10, color=(1.0, 0.15, 0.15, 1.0))
    red_beacon.setPos(0, 0, height + 3.2)
    red_beacon.setLightOff()
    red_beacon.reparentTo(root)

    return root


def create_spaceport_bunker(width: float = 3.6, depth: float = 4.8, height: float = 2.2, name: str = "bunker") -> NodePath:
    """Builds a launch complex utility bunker with cyan walls, roof railing, windows, and industrial details."""
    root = NodePath(name)

    # 1. Main cyan/aqua building walls
    walls = create_box(width, depth, height, center=(0, 0, height * 0.5), color=(0.48, 0.68, 0.72, 1.0), name="walls")
    walls.reparentTo(root)

    # Architectural foundation base plinth
    plinth = create_box(width + 0.15, depth + 0.15, 0.12, center=(0, 0, 0.06), color=(0.35, 0.37, 0.40, 1.0))
    plinth.reparentTo(root)

    # 2. Overhanging concrete flat roof
    roof = create_box(width + 0.4, depth + 0.4, 0.20, center=(0, 0, height + 0.10), color=(0.60, 0.62, 0.65, 1.0), name="roof")
    roof.reparentTo(root)

    # 3. Rooftop perimeter safety handrail
    rail_col = (0.35, 0.38, 0.42, 1.0)
    hw, hd, hz = width * 0.5 + 0.1, depth * 0.5 + 0.1, height + 0.20
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    for i in range(4):
        ca, cb = corners[i], corners[(i + 1) % 4]
        post = create_beam(Vec3(ca[0], ca[1], hz), Vec3(ca[0], ca[1], hz + 0.45), radius=0.02, color=rail_col)
        post.reparentTo(root)
        bar = create_beam(Vec3(ca[0], ca[1], hz + 0.45), Vec3(cb[0], cb[1], hz + 0.45), radius=0.018, color=rail_col)
        bar.reparentTo(root)

    # Rooftop HVAC ventilation unit & communications antenna
    hvac_box = create_box(width * 0.35, depth * 0.25, 0.35, center=(width * 0.2, depth * 0.15, height + 0.38), color=(0.40, 0.42, 0.45, 1.0))
    hvac_box.reparentTo(root)
    vent_fan = create_ring_or_disc(0.05, 0.25, segments=16, color=(0.25, 0.26, 0.28, 1.0))
    vent_fan.setPos(width * 0.2, depth * 0.15, height + 0.56)
    vent_fan.reparentTo(root)

    antenna_mast = create_beam(Vec3(-width * 0.3, -depth * 0.3, height + 0.2), Vec3(-width * 0.3, -depth * 0.3, height + 1.6), radius=0.018, color=(0.3, 0.32, 0.35, 1.0))
    antenna_mast.reparentTo(root)

    # 4. Dark roll-up equipment door on front with industrial frame
    door_frame = create_box(width * 0.60, 0.10, height * 0.80, center=(0.0, -depth * 0.5 - 0.03, height * 0.40), color=(0.30, 0.32, 0.35, 1.0))
    door_frame.reparentTo(root)
    door = create_box(width * 0.54, 0.06, height * 0.74, center=(0.0, -depth * 0.5 - 0.05, height * 0.38), color=(0.18, 0.19, 0.21, 1.0))
    door.reparentTo(root)

    # Exterior door security lamp
    lamp_fixture = create_box(0.18, 0.12, 0.10, center=(0.0, -depth * 0.5 - 0.10, height * 0.84), color=(0.25, 0.26, 0.28, 1.0))
    lamp_fixture.reparentTo(root)

    # 5. Side tinted observation windows
    window_frame_l = create_box(0.08, depth * 0.45, height * 0.35, center=(-width * 0.5 - 0.02, 0.0, height * 0.55), color=(0.25, 0.26, 0.28, 1.0))
    window_frame_l.reparentTo(root)
    window_glass_l = create_box(0.04, depth * 0.40, height * 0.30, center=(-width * 0.5 - 0.03, 0.0, height * 0.55), color=(0.15, 0.25, 0.35, 0.95))
    window_glass_l.reparentTo(root)

    window_frame_r = create_box(0.08, depth * 0.45, height * 0.35, center=(width * 0.5 + 0.02, 0.0, height * 0.55), color=(0.25, 0.26, 0.28, 1.0))
    window_frame_r.reparentTo(root)
    window_glass_r = create_box(0.04, depth * 0.40, height * 0.30, center=(width * 0.5 + 0.03, 0.0, height * 0.55), color=(0.15, 0.25, 0.35, 0.95))
    window_glass_r.reparentTo(root)

    return root


def create_launch_clamp_arm(height: float = 3.6, name: str = "clamp_arm") -> NodePath:
    """Creates a mechanical launch support clamp arm with blue lattice, hydraulic cylinder, and yellow head."""
    root = NodePath(name)
    blue_col = (0.10, 0.32, 0.68, 1.0)
    yellow_col = (0.92, 0.78, 0.12, 1.0)
    piston_col = (0.78, 0.80, 0.84, 1.0)
    dark_col = (0.22, 0.24, 0.27, 1.0)

    # Heavy structural base anchored to launchpad
    base_box = create_box(0.9, 0.9, 0.5, center=(0, 0, 0.25), color=dark_col)
    base_box.reparentTo(root)
    hinge_pin = create_cylinder_or_cone(0.08, 0.08, 0.8, color=(0.4, 0.42, 0.45, 1.0))
    hinge_pin.setHpr(90, 0, 0)
    hinge_pin.setPos(0, 0.15, 0.42)
    hinge_pin.reparentTo(root)

    p_b0 = Vec3(-0.35, 0.25, 0.4)
    p_b1 = Vec3(0.35, 0.25, 0.4)
    p_top0 = Vec3(-0.25, -0.2, height)
    p_top1 = Vec3(0.25, -0.2, height)

    beam1 = create_beam(p_b0, p_top0, radius=0.045, color=blue_col)
    beam1.reparentTo(root)
    beam2 = create_beam(p_b1, p_top1, radius=0.045, color=blue_col)
    beam2.reparentTo(root)

    diag1 = create_beam(p_b0, p_top1, radius=0.028, color=blue_col)
    diag1.reparentTo(root)
    diag2 = create_beam(p_b1, p_top0, radius=0.028, color=blue_col)
    diag2.reparentTo(root)

    # Hydraulic retraction actuator cylinder and chrome piston rod
    hyd_cyl = create_beam(Vec3(0.0, 0.35, 0.3), Vec3(0.0, 0.1, height * 0.55), radius=0.055, color=dark_col)
    hyd_cyl.reparentTo(root)
    hyd_rod = create_beam(Vec3(0.0, 0.1, height * 0.55), Vec3(0.0, -0.15, height * 0.90), radius=0.035, color=piston_col)
    hyd_rod.reparentTo(root)

    # Articulated yellow clamp head with rubber grip pads
    clamp_head = create_box(0.7, 0.5, 0.4, center=(0.0, -0.25, height + 0.1), color=yellow_col, name="clamp_head")
    clamp_head.reparentTo(root)
    clamp_pad = create_box(0.55, 0.08, 0.28, center=(0.0, -0.48, height + 0.1), color=(0.14, 0.14, 0.15, 1.0))
    clamp_pad.reparentTo(root)

    return root


def create_orbital_booster_rocket(name: str = "orbital_rocket") -> Tuple[NodePath, Dict[str, NodePath]]:
    """Builds a modern multistage booster rocket with payload fairing, 4 side boosters, engine interior, and legs."""
    root = NodePath(name)
    nodes = {}

    white_mat = (0.95, 0.96, 0.98, 1.0)
    black_mat = (0.12, 0.12, 0.14, 1.0)
    titanium_mat = (0.22, 0.23, 0.25, 1.0)
    throat_mat = (0.85, 0.48, 0.16, 1.0)

    # 1. Main Core Booster Cylinder
    core_stage = create_cylinder_or_cone(0.34, 0.34, 3.2, color=white_mat, segments=24, name="core_stage")
    core_stage.setPos(0, 0, 0.45)
    core_stage.reparentTo(root)
    nodes["core"] = core_stage

    # Core interstage raceway conduit / bands
    band1 = create_cylinder_or_cone(0.35, 0.35, 0.10, color=black_mat, segments=24)
    band1.setPos(0, 0, 1.9)
    band1.reparentTo(root)

    raceway = create_box(0.06, 0.08, 2.8, center=(0.34, 0.0, 1.85), color=black_mat)
    raceway.reparentTo(root)

    # 2. Distinctive Payload Fairing (Black & White quadrant livery from photo)
    fairing_cyl = create_cylinder_or_cone(0.34, 0.34, 0.50, color=white_mat, segments=24)
    fairing_cyl.setPos(0, 0, 3.65)
    fairing_cyl.reparentTo(root)

    fairing_cone = create_cylinder_or_cone(0.34, 0.06, 0.95, color=white_mat, segments=24)
    fairing_cone.setPos(0, 0, 4.15)
    fairing_cone.reparentTo(root)

    nose_cap = create_cylinder_or_cone(0.12, 0.02, 0.30, color=black_mat, segments=20)
    nose_cap.setPos(0, 0, 4.80)
    nose_cap.reparentTo(root)

    black_stripe_l = create_box(0.04, 0.28, 0.70, center=(-0.33, 0.0, 4.35), color=black_mat)
    black_stripe_l.reparentTo(root)
    black_stripe_r = create_box(0.04, 0.28, 0.70, center=(0.33, 0.0, 4.35), color=black_mat)
    black_stripe_r.reparentTo(root)

    # 3. Four Strap-On Boosters
    booster_angles = [0, 90, 180, 270]
    for idx, ang in enumerate(booster_angles):
        rad = math.radians(ang)
        bx = math.cos(rad) * 0.58
        by = math.sin(rad) * 0.58

        b_root = root.attachNewNode(f"booster_{idx}")
        b_root.setPos(bx, by, 0.40)

        b_cyl = create_cylinder_or_cone(0.18, 0.18, 1.70, color=white_mat, segments=20)
        b_cyl.reparentTo(b_root)

        # Black aerodynamic nose band
        b_band = create_cylinder_or_cone(0.185, 0.185, 0.08, color=black_mat, segments=20)
        b_band.setPos(0, 0, 1.62)
        b_band.reparentTo(b_root)

        b_nose = create_cylinder_or_cone(0.18, 0.02, 0.45, color=white_mat, segments=20)
        b_nose.setPos(0, 0, 1.70)
        b_nose.reparentTo(b_root)

        b_nozzle = create_cylinder_or_cone(0.07, 0.14, 0.24, color=titanium_mat, segments=16)
        b_nozzle.setHpr(0, 180, 0)
        b_nozzle.setPos(0, 0, 0.0)
        b_nozzle.reparentTo(b_root)

        strut1 = create_beam(Vec3(0, 0, 0.5), Vec3(-bx * 0.4, -by * 0.4, 0.5), radius=0.022, color=black_mat)
        strut1.reparentTo(b_root)
        strut2 = create_beam(Vec3(0, 0, 1.4), Vec3(-bx * 0.4, -by * 0.4, 1.4), radius=0.022, color=black_mat)
        strut2.reparentTo(b_root)

    # 4. Central Core Engine Nozzle with interior throat glow & gimbal rings
    core_nozzle = create_cylinder_or_cone(0.13, 0.28, 0.45, color=titanium_mat, segments=24, name="core_nozzle")
    core_nozzle.setHpr(0, 180, 0)
    core_nozzle.setPos(0, 0, 0.45)
    core_nozzle.reparentTo(root)
    nodes["nozzle"] = core_nozzle

    # Internal combustion throat insert
    throat = create_cylinder_or_cone(0.12, 0.07, 0.22, color=throat_mat, segments=20)
    throat.setHpr(0, 180, 0)
    throat.setPos(0, 0, 0.44)
    throat.reparentTo(root)

    # 5. Articulated Landing Gear with Hydraulic Dampers & Footpads
    leg_nodes = {}
    legs_cfg = {
        "left": (Vec3(-0.35, 0, 0.6), Vec3(-0.95, 0, -0.45)),
        "right": (Vec3(0.35, 0, 0.6), Vec3(0.95, 0, -0.45)),
        "front": (Vec3(0, -0.35, 0.6), Vec3(0, -0.95, -0.45)),
        "rear": (Vec3(0, 0.35, 0.6), Vec3(0, 0.95, -0.45)),
    }

    for name, (p_hip, p_foot) in legs_cfg.items():
        leg_grp = NodePath(f"leg_{name}")
        main_strut = create_beam(p_hip, p_foot, radius=0.038, color=(0.88, 0.90, 0.94, 1.0))
        main_strut.reparentTo(leg_grp)

        # Hydraulic shock-absorber cylinder sleeve
        p_hip_damper = (p_hip * 0.65 + p_foot * 0.35)
        damper_sleeve = create_beam(p_hip, p_hip_damper, radius=0.046, color=(0.35, 0.37, 0.40, 1.0))
        damper_sleeve.reparentTo(leg_grp)

        p_brace_start = Vec3(p_hip.x * 0.45, p_hip.y * 0.45, 0.3)
        p_mid = (p_hip + p_foot) * 0.55
        brace = create_beam(p_brace_start, p_mid, radius=0.026, color=(0.25, 0.26, 0.28, 1.0))
        brace.reparentTo(leg_grp)

        # Articulated beveled footpad
        foot_pad = create_cylinder_or_cone(0.18, 0.18, 0.04, color=(0.22, 0.23, 0.25, 1.0), segments=16)
        foot_pad.setPos(p_foot.x, p_foot.y, p_foot.z)
        foot_pad.reparentTo(leg_grp)

        leg_grp.reparentTo(root)
        leg_nodes[name] = leg_grp

    nodes["legs"] = leg_nodes

    # 6. RCS Pods
    rcs_pods = []
    for px in (-0.36, 0.36):
        rcs_pod = create_box(0.12, 0.12, 0.12, center=(px, 0, 3.4), color=black_mat)
        rcs_pod.reparentTo(root)
        nozzle_micro = create_cylinder_or_cone(0.025, 0.015, 0.08, color=titanium_mat)
        nozzle_micro.setHpr(90 if px > 0 else -90, 0, 0)
        nozzle_micro.setPos(px + (0.06 if px > 0 else -0.06), 0, 3.4)
        nozzle_micro.reparentTo(root)
        rcs_pods.append((px, nozzle_micro))

    nodes["rcs_pods"] = rcs_pods
    return root, nodes

    # 6. RCS Pods
    rcs_pods = []
    for px in (-0.36, 0.36):
        rcs_pod = create_box(0.12, 0.12, 0.12, center=(px, 0, 3.4), color=black_mat)
        rcs_pod.reparentTo(root)
        nozzle_micro = create_cylinder_or_cone(0.025, 0.015, 0.08, color=titanium_mat)
        nozzle_micro.setHpr(90 if px > 0 else -90, 0, 0)
        nozzle_micro.setPos(px + (0.06 if px > 0 else -0.06), 0, 3.4)
        nozzle_micro.reparentTo(root)
        rcs_pods.append((px, nozzle_micro))

    nodes["rcs_pods"] = rcs_pods
    return root, nodes

