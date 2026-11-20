"""Realistic 3D Presentation Layer for Autonomous Rocket Landing.

Built on Panda3D hardware-accelerated OpenGL / Vulkan engine with simplepbr
physically-based rendering, dynamic solar shadows, 3D spacecraft geometry,
articulated landing gear, volumetric propulsion plume with Mach shock diamonds,
directional RCS micro-jets, ground-impingement regolith dust, and responsive
SpaceX/Apollo style glass-cockpit aerospace HUD.
"""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# On Windows, PyTorch's c10.dll must be pre-loaded before Panda3D OpenGL runtime
try:
    import torch
except Exception:
    pass

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import cv2
from direct.showbase.ShowBase import ShowBase
import numpy as np
from panda3d.core import (
    AmbientLight,
    BitMask32,
    DirectionalLight,
    GraphicsOutput,
    LineSegs,
    NodePath,
    PointLight,
    Texture,
    Vec3,
    Vec4,
    loadPrcFileData,
)
import pygame
import simplepbr

from evaluation.evaluate import LandingCriteria, classify_outcome
from visualization.mesh_builder import (
    build_3d_lunar_terrain,
    create_beam,
    create_box,
    create_cylinder_or_cone,
    create_earth_globe,
    create_launch_clamp_arm,
    create_orbital_booster_rocket,
    create_ring_or_disc,
    create_spaceport_bunker,
    create_spaceport_ground,
    create_spaceport_launchpad,
    create_spaceport_sky,
    create_spaceport_tower,
    create_sphere,
    create_starfield,
)
from visualization.timeline import SimulationSnapshot, SnapshotTimeline, capture_snapshot_from_env


class Realistic3DRenderer:
    """Photorealistic 3D Aerospace Simulator Renderer.

    Decouples rendering from Box2D physical stepping. Operates on immutable
    SimulationSnapshot states with smooth camera kinematics, dynamic lighting,
    and glass-cockpit flight instruments.
    """

    def __init__(
        self,
        headless: bool = False,
        width: int = 1280,
        height: int = 720,
        speed_factor: float = 0.5,
        fps: int = 60,
        theme: str = "spaceport",
    ):
        self.theme = theme
        self.headless = headless
        self.width = width
        self.height = height
        self.speed_factor = max(0.1, min(2.0, speed_factor))
        self.target_fps = fps

        # Presentation & wall timing
        self.sim_time = 0.0
        self.wall_time = 0.0
        self.last_render_wall_t = time.perf_counter()

        # Telemetry tracking for initial gear impact vs settled rest
        self.first_contact_info: Optional[Dict[str, float]] = None

        # Camera spring-damper state
        self.cam_target_x = 0.0
        self.cam_target_z = 7.5 if self.theme == "spaceport" else 2.0
        self.cam_smooth_x = 0.0
        self.cam_smooth_z = 7.5 if self.theme == "spaceport" else 2.0

        # Propulsion animation smoothing
        self.current_throttle = 0.0
        self.current_rcs_l = 0.0
        self.current_rcs_r = 0.0
        self.dust_intensity = 0.0

        # Initialize Panda3D Offscreen Core
        loadPrcFileData("", "window-type offscreen")
        loadPrcFileData("", f"win-size {self.width} {self.height}")
        loadPrcFileData("", "audio-library-name null")
        loadPrcFileData("", "gl-debug false")
        loadPrcFileData("", "notify-level-glgsg fatal")
        loadPrcFileData("", "notify-level-display fatal")

        self.base = ShowBase(windowType="offscreen")
        clear_col = Vec4(0.42, 0.65, 0.92, 1.0) if self.theme == "spaceport" else Vec4(0.003, 0.005, 0.01, 1.0)
        self.base.win.setClearColor(clear_col)

        # PBR Shading Pipeline
        self.pbr = simplepbr.init(
            render_node=self.base.render,
            window=self.base.win,
            enable_shadows=(self.theme == "spaceport"),
        )

        # Texture Buffer Extraction Target
        self.render_tex = Texture()
        self.base.win.addRenderTexture(self.render_tex, GraphicsOutput.RTM_copy_ram)

        # Camera lens setup
        self.base.camLens.setFov(62.0)
        self.base.camLens.setNearFar(0.2, 500.0)

        # Build 3D Scene Components
        self._init_lighting()
        self._init_celestial_environment()
        self._init_lunar_pad_and_surface()
        self._init_spacecraft_model()
        self._init_propulsion_fx()
        self._init_dust_ejecta()

        # Initialize Pygame overlay & fonts
        pygame.init()
        pygame.font.init()
        if not self.headless:
            pygame.display.set_caption(
                "Autonomous Rocket Landing — Stage 8.4 Realistic 3D Aerospace Simulator"
            )
            self.screen = pygame.display.set_mode((self.width, self.height))
        else:
            self.screen = pygame.Surface((self.width, self.height))

        self.clock = pygame.time.Clock()
        self._init_fonts()

    def _init_fonts(self) -> None:
        """Loads clean, readable typography for mission control HUD."""
        font_candidates = ["Segoe UI", "Consolas", "Lucida Console", "Arial"]
        sys_font = pygame.font.match_font(font_candidates[0])
        self.font_large = pygame.font.Font(sys_font, max(16, int(20 * (self.height / 720.0))))
        self.font_mid = pygame.font.Font(sys_font, max(14, int(16 * (self.height / 720.0))))
        self.font_small = pygame.font.Font(sys_font, max(12, int(13 * (self.height / 720.0))))
        self.font_tiny = pygame.font.Font(sys_font, max(10, int(11 * (self.height / 720.0))))

    def _init_lighting(self) -> None:
        """Sets up realistic directional sunlight and ambient sky fill."""
        if self.theme == "spaceport":
            self.sun = DirectionalLight("sun")
            self.sun.setColor(Vec4(1.75, 1.70, 1.58, 1.0))
            # Optimized 2048x2048 shadow-map resolution for RTX 3050 Ti Laptop GPU (4GB VRAM target)
            self.sun.setShadowCaster(True, 2048, 2048)
            self.sun.setCameraMask(BitMask32.bit(0))
            self.sun.getLens().setFilmSize(55, 55)
            self.sun.getLens().setNearFar(5.0, 95.0)
            self.sun_np = self.base.render.attachNewNode(self.sun)
            self.sun_np.setPos(26, 26, 38)
            self.sun_np.lookAt(0, 0, 0)
            self.base.render.setLight(self.sun_np)

            self.ambient = AmbientLight("sky_ambient")
            self.ambient.setColor(Vec4(0.38, 0.42, 0.50, 1.0))
            self.amb_np = self.base.render.attachNewNode(self.ambient)
            self.base.render.setLight(self.amb_np)
        else:
            # Low-angle Sun (sharp shadows across craters and lander)
            self.sun = DirectionalLight("sun")
            self.sun.setColor(Vec4(1.5, 1.45, 1.38, 1.0))
            self.sun_np = self.base.render.attachNewNode(self.sun)
            self.sun_np.setHpr(42, -28, 0)
            self.base.render.setLight(self.sun_np)

            # Ambient Earthshine fill (cool cyan-blue ambient tint)
            self.ambient = AmbientLight("earthshine")
            self.ambient.setColor(Vec4(0.14, 0.18, 0.25, 1.0))
            self.amb_np = self.base.render.attachNewNode(self.ambient)
            self.base.render.setLight(self.amb_np)

        # Engine exhaust point illumination
        self.plight = PointLight("engine_glow")
        self.plight.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
        self.plight.setAttenuation(Vec3(0.5, 0.1, 0.05))
        self.plight_np = self.base.render.attachNewNode(self.plight)
        self.plight_np.setPos(0, 0, 1.0)
        self.base.render.setLight(self.plight_np)

    def _init_celestial_environment(self) -> None:
        """Spawns spaceport daytime sky or deep space celestial environment."""
        if self.theme == "spaceport":
            self.sky_np = create_spaceport_sky(radius=180.0)
            self.sky_np.setTwoSided(True)
            self.sky_np.hide(BitMask32.bit(0))
            self.sky_np.show(BitMask32.bit(1))
            self.sky_np.reparentTo(self.base.render)
            self.base.cam.node().setCameraMask(BitMask32.bit(0) | BitMask32.bit(1))
        else:
            self.stars_np = create_starfield(count=2500, radius=120.0)
            self.stars_np.reparentTo(self.base.render)

            self.earth_np = create_earth_globe(radius=4.2)
            self.earth_np.setPos(-18, 55, 12.0)
            self.earth_np.reparentTo(self.base.render)

    def _init_lunar_pad_and_surface(self) -> None:
        """Constructs 3D launch complex or lunar terrain and landing pad."""
        if self.theme == "spaceport":
            self.terrain_np = create_spaceport_ground(radius=160.0)
            self.terrain_np.reparentTo(self.base.render)

            self.pad_root = create_spaceport_launchpad()
            self.pad_root.reparentTo(self.base.render)

            # Left and right blue/white steel lattice towers (positioned at Y=14.0 for optimal framing & shadow depth)
            self.tower_l = create_spaceport_tower(height=26.0)
            self.tower_l.setPos(-16.0, 14.0, 0.2)
            self.tower_l.reparentTo(self.base.render)

            self.tower_r = create_spaceport_tower(height=26.0)
            self.tower_r.setPos(16.0, 14.0, 0.2)
            self.tower_r.reparentTo(self.base.render)

            # Service Bunkers (Cyan facade with roof railings)
            self.bunker_l = create_spaceport_bunker(width=3.8, depth=4.8, height=2.2)
            self.bunker_l.setPos(-9.2, 1.0, 0.2)
            self.bunker_l.reparentTo(self.base.render)

            self.bunker_r = create_spaceport_bunker(width=3.8, depth=4.8, height=2.2)
            self.bunker_r.setPos(9.2, 1.0, 0.2)
            self.bunker_r.reparentTo(self.base.render)

            self.shed_l = create_spaceport_bunker(width=2.6, depth=3.4, height=1.7)
            self.shed_l.setPos(-11.5, -9.0, 0.2)
            self.shed_l.reparentTo(self.base.render)

            self.shed_r = create_spaceport_bunker(width=2.6, depth=3.4, height=1.7)
            self.shed_r.setPos(11.5, -9.0, 0.2)
            self.shed_r.reparentTo(self.base.render)

            # Mechanical launch support clamp arms with yellow clamping heads
            self.clamp_arms = []
            for idx, ang in enumerate([45, 135, 225, 315]):
                rad = math.radians(ang)
                c = create_launch_clamp_arm(height=3.8)
                c.setPos(math.cos(rad) * 2.3, math.sin(rad) * 2.3, 0.2)
                c.setHpr(-ang - 90, 0, 0)
                c.reparentTo(self.base.render)
                self.clamp_arms.append(c)
        else:
            default_terrain = [
                (-18.0, -0.4), (-12.0, 0.3), (-6.0, -0.1), (-2.0, 0.15),
                (0.0, 0.2), (2.0, 0.15), (6.0, -0.1), (12.0, 0.3), (18.0, -0.4)
            ]
            self.terrain_np = build_3d_lunar_terrain(default_terrain, y_front=-9.0, y_back=9.0, depth_segments=12)
            self.terrain_np.reparentTo(self.base.render)

            # Landing Pad
            self.pad_root = NodePath("landing_pad")
            self.pad_base = create_box(3.6, 3.6, 0.14, center=(0, 0, 0.2), color=(0.24, 0.26, 0.29, 1.0))
            self.pad_base.reparentTo(self.pad_root)

            # Yellow target concentric rings
            ring_outer = create_ring_or_disc(1.3, 1.42, segments=36, color=(0.88, 0.68, 0.12, 1.0))
            ring_outer.setPos(0, 0, 0.28)
            ring_outer.reparentTo(self.pad_root)

            ring_inner = create_ring_or_disc(0.45, 0.55, segments=36, color=(0.96, 0.82, 0.2, 1.0))
            ring_inner.setPos(0, 0, 0.28)
            ring_inner.reparentTo(self.pad_root)

            # Corner navigation LED beacon stanchions
            for cx, cy in [(-1.7, -1.7), (1.7, -1.7), (-1.7, 1.7), (1.7, 1.7)]:
                stanchion = create_cylinder_or_cone(0.045, 0.045, 0.38, color=(0.32, 0.34, 0.38, 1.0))
                stanchion.setPos(cx, cy, 0.2)
                stanchion.reparentTo(self.pad_root)

                led = create_sphere(radius=0.085, color=(0.1, 1.0, 0.45, 1.0))
                led.setPos(cx, cy, 0.58)
                led.reparentTo(self.pad_root)

            self.pad_root.reparentTo(self.base.render)

    def _init_spacecraft_model(self) -> None:
        """Constructs detailed multi-part 3D spacecraft."""
        if self.theme == "spaceport":
            self.lander_np, nodes = create_orbital_booster_rocket(name="lander_root")
            self.core = nodes["core"]
            self.nozzle = nodes["nozzle"]
            self.leg_nodes = nodes["legs"]
            self.rcs_pods = nodes["rcs_pods"]
            self.lander_np.reparentTo(self.base.render)
        else:
            self.lander_np = NodePath("lander_root")

            # 1. Main Pressurized Avionics Core
            self.core = create_cylinder_or_cone(0.34, 0.34, 1.15, color=(0.82, 0.84, 0.88, 1.0), segments=24)
            self.core.setPos(0, 0, 0.45)
            self.core.reparentTo(self.lander_np)

            # 2. Lower Descent Stage / Gold Kapton MLI Thermal Blanket
            self.mli = create_cylinder_or_cone(0.44, 0.44, 0.45, color=(0.88, 0.66, 0.12, 1.0), segments=12)
            self.mli.setPos(0, 0, 0.0)
            self.mli.reparentTo(self.lander_np)

            # 3. Upper Conical Nose Section
            self.nose = create_cylinder_or_cone(0.34, 0.06, 0.55, color=(0.94, 0.94, 0.96, 1.0), segments=24)
            self.nose.setPos(0, 0, 1.6)
            self.nose.reparentTo(self.lander_np)

            # 4. Machined Titanium de Laval Bell Nozzle
            self.nozzle = create_cylinder_or_cone(0.12, 0.26, 0.40, color=(0.20, 0.20, 0.22, 1.0), segments=20)
            self.nozzle.setHpr(0, 180, 0)
            self.nozzle.setPos(0, 0, 0.0)
            self.nozzle.reparentTo(self.lander_np)

            # 5. RCS Quads & Lateral Thruster Pods
            self.rcs_pods = []
            for px in (-0.38, 0.38):
                rcs_pod = create_box(0.13, 0.13, 0.13, center=(px, 0, 1.35), color=(0.35, 0.36, 0.39, 1.0))
                rcs_pod.reparentTo(self.lander_np)
                nozzle_micro = create_cylinder_or_cone(0.03, 0.015, 0.1, color=(0.15, 0.15, 0.18, 1.0))
                nozzle_micro.setHpr(90 if px > 0 else -90, 0, 0)
                nozzle_micro.setPos(px + (0.065 if px > 0 else -0.065), 0, 1.35)
                nozzle_micro.reparentTo(self.lander_np)
                self.rcs_pods.append((px, nozzle_micro))

            # 6. Articulated Landing Gear (Left, Right, Front, Rear)
            self.leg_nodes = {}
            legs_cfg = {
                "left": (Vec3(-0.35, 0, 0.2), Vec3(-0.85, 0, -0.45)),
                "right": (Vec3(0.35, 0, 0.2), Vec3(0.85, 0, -0.45)),
                "front": (Vec3(0, -0.35, 0.2), Vec3(0, -0.85, -0.45)),
                "rear": (Vec3(0, 0.35, 0.2), Vec3(0, 0.85, -0.45)),
            }

            for name, (p_hip, p_foot) in legs_cfg.items():
                leg_grp = NodePath(f"leg_{name}")
                strut = create_beam(p_hip, p_foot, radius=0.032, color=(0.72, 0.74, 0.78, 1.0))
                strut.reparentTo(leg_grp)

                p_brace_start = Vec3(p_hip.x * 0.4, p_hip.y * 0.4, 0.0)
                p_mid = (p_hip + p_foot) * 0.55
                brace = create_beam(p_brace_start, p_mid, radius=0.022, color=(0.45, 0.47, 0.50, 1.0))
                brace.reparentTo(leg_grp)

                foot = create_cylinder_or_cone(0.16, 0.16, 0.04, color=(0.30, 0.32, 0.35, 1.0), segments=16)
                foot.setPos(p_foot.x, p_foot.y, p_foot.z)
                foot.reparentTo(leg_grp)

                leg_grp.reparentTo(self.lander_np)
                self.leg_nodes[name] = leg_grp

            self.lander_np.reparentTo(self.base.render)

    def _init_propulsion_fx(self) -> None:
        """Constructs volumetric 3D main engine plume with shock diamonds and RCS jets."""
        self.plume_root = NodePath("main_plume")

        # Outer amber/orange expanding plume
        self.p_outer = create_cylinder_or_cone(0.26, 0.06, 1.6, color=(0.95, 0.45, 0.08, 0.45), caps=False)
        self.p_outer.setHpr(0, 180, 0)
        self.p_outer.setTransparency(True)
        self.p_outer.reparentTo(self.plume_root)

        # Inner cyan-white supersonic core
        self.p_inner = create_cylinder_or_cone(0.14, 0.02, 1.15, color=(0.4, 0.92, 1.0, 0.85), caps=False)
        self.p_inner.setHpr(0, 180, 0)
        self.p_inner.setTransparency(True)
        self.p_inner.reparentTo(self.plume_root)

        # Mach shock diamonds
        self.shock_diamonds = []
        for d_z in (-0.28, -0.56, -0.84):
            diamond = create_sphere(radius=0.065, color=(1.0, 1.0, 1.0, 0.95))
            diamond.setScale(0.8, 0.8, 1.6)
            diamond.setPos(0, 0, d_z)
            diamond.reparentTo(self.plume_root)
            self.shock_diamonds.append(diamond)

        self.plume_root.reparentTo(self.lander_np)
        self.plume_root.hide()

        # RCS Left and Right micro-jets
        rcs_z = 3.4 if self.theme == "spaceport" else 1.35
        rcs_x = 0.42 if self.theme == "spaceport" else 0.45
        self.rcs_jet_l = create_cylinder_or_cone(0.08, 0.02, 0.45, color=(0.85, 0.95, 1.0, 0.8), caps=False)
        self.rcs_jet_l.setHpr(-90, 0, 0)
        self.rcs_jet_l.setPos(-rcs_x, 0, rcs_z)
        self.rcs_jet_l.setTransparency(True)
        self.rcs_jet_l.reparentTo(self.lander_np)
        self.rcs_jet_l.hide()

        self.rcs_jet_r = create_cylinder_or_cone(0.08, 0.02, 0.45, color=(0.85, 0.95, 1.0, 0.8), caps=False)
        self.rcs_jet_r.setHpr(90, 0, 0)
        self.rcs_jet_r.setPos(rcs_x, 0, rcs_z)
        self.rcs_jet_r.setTransparency(True)
        self.rcs_jet_r.reparentTo(self.lander_np)
        self.rcs_jet_r.hide()

    def _init_dust_ejecta(self) -> None:
        """Constructs 3D radial regolith dust plume discs at surface level."""
        self.dust_root = NodePath("dust_root")
        self.dust_discs = []

        dust_col = (0.72, 0.70, 0.64, 0.40) if self.theme == "spaceport" else (0.65, 0.64, 0.62, 0.35)
        for r_in, r_out in [(0.4, 1.6), (1.4, 2.8), (2.4, 4.2)]:
            disc = create_ring_or_disc(r_in, r_out, segments=32, color=dust_col)
            disc.setPos(0, 0, 0.22)
            disc.setTransparency(True)
            disc.reparentTo(self.dust_root)
            self.dust_discs.append(disc)

        self.dust_root.reparentTo(self.base.render)
        self.dust_root.hide()

    def update_terrain_from_coords(self, terrain_coords: Sequence[Tuple[float, float]]) -> None:
        """Dynamically recreates 3D lunar terrain mesh if environment points change."""
        if self.theme != "spaceport" and terrain_coords and len(terrain_coords) >= 2:
            self.terrain_np.removeNode()
            self.terrain_np = build_3d_lunar_terrain(list(terrain_coords), y_front=-9.0, y_back=9.0, depth_segments=12)
            self.terrain_np.reparentTo(self.base.render)

    def reset(
        self,
        initial_snapshot: Optional[SimulationSnapshot] = None,
        terrain_coords: Optional[Sequence[Tuple[float, float]]] = None,
    ) -> None:
        """Resets the 3D presentation state cleanly between simulation episodes.

        Guarantees that no stale propulsion, camera lag, particle/dust, or terrain state
        persists from a previous episode into a new run.
        """
        self.sim_time = 0.0
        self.wall_time = 0.0
        self.last_render_wall_t = time.perf_counter()
        self.first_contact_info = None

        # Hard-reset propulsion actuators, lights, and dust
        self.current_throttle = 0.0
        self.current_rcs_l = 0.0
        self.current_rcs_r = 0.0
        self.dust_intensity = 0.0

        if hasattr(self, "plume_root"):
            self.plume_root.hide()
        if hasattr(self, "rcs_jet_l"):
            self.rcs_jet_l.hide()
        if hasattr(self, "rcs_jet_r"):
            self.rcs_jet_r.hide()
        if hasattr(self, "dust_root"):
            self.dust_root.hide()
        if hasattr(self, "plight"):
            self.plight.setColor(Vec4(0.0, 0.0, 0.0, 1.0))

        # Reset landing gear struts to uncompressed state
        if hasattr(self, "leg_nodes"):
            for leg in self.leg_nodes.values():
                leg.setScale(1.0, 1.0, 1.0)

        # Update terrain if new profile coordinates provided
        if terrain_coords:
            self.update_terrain_from_coords(terrain_coords)

        # Reset camera immediately to initial spawn position without lagging spring creep
        if initial_snapshot is not None:
            pad_surface_z = 0.22 if self.theme == "spaceport" else 0.27
            origin_z = pad_surface_z + 0.45 + initial_snapshot.altitude
            if self.theme == "spaceport":
                target_cam_x = initial_snapshot.pos_x * 0.4
                target_cam_z = max(7.5, origin_z * 0.55 + 6.0)
                target_cam_dist = 22.0 + max(0.0, origin_z - 2.5) * 0.60
                target_look_z = max(1.8, origin_z * 0.55 + 2.2)
                target_look_y = 2.0
            else:
                target_cam_x = initial_snapshot.pos_x * 0.6
                target_cam_z = max(2.5, origin_z * 0.55 + 1.4)
                target_cam_dist = 13.0 + max(0.0, origin_z - 2.5) * 0.65
                target_look_z = max(0.8, origin_z * 0.68 + 0.3)
                target_look_y = 0.0

            self.cam_smooth_x = target_cam_x
            self.cam_smooth_z = target_cam_z
            self.cam_target_x = target_cam_x
            self.cam_target_z = target_cam_z

            self.base.cam.setPos(self.cam_smooth_x, -target_cam_dist, self.cam_smooth_z)
            self.base.cam.lookAt(self.cam_smooth_x * 0.5, target_look_y, target_look_z)

            # Snap lander pose
            if hasattr(self, "lander_np"):
                self.lander_np.setPos(initial_snapshot.pos_x, 0.0, origin_z)
                self.lander_np.setR(-math.degrees(initial_snapshot.roll))
        else:
            if self.theme == "spaceport":
                self.cam_smooth_x = 0.0
                self.cam_smooth_z = 10.5
                self.cam_target_x = 0.0
                self.cam_target_z = 10.5
            else:
                self.cam_smooth_x = 0.0
                self.cam_smooth_z = 7.0
                self.cam_target_x = 0.0
                self.cam_target_z = 7.0

    def set_speed_factor(self, factor: float) -> None:
        """Sets the presentation playback speed multiplier (e.g. 1.0, 0.75, 0.5, 0.25)."""
        self.speed_factor = max(0.1, min(2.0, factor))

    def render_snapshot(self, snapshot: SimulationSnapshot) -> np.ndarray:
        """Deterministically renders a SimulationSnapshot to a 1280x720 RGB NumPy array."""
        now = time.perf_counter()
        dt_wall = min(0.1, now - self.last_render_wall_t)
        self.last_render_wall_t = now

        self.sim_time = snapshot.sim_time
        self.wall_time += dt_wall

        # 1. Update Spacecraft 3D Position and Orientation
        # Feet are at -0.45 from model origin; pad surface is at 0.22 (spaceport) or 0.27 (lunar)
        pad_surface_z = 0.22 if self.theme == "spaceport" else 0.27
        origin_z = pad_surface_z + 0.45 + snapshot.altitude
        self.lander_np.setPos(snapshot.pos_x, 0.0, origin_z)
        # Roll corresponds to Box2D angle
        self.lander_np.setR(-math.degrees(snapshot.roll))

        # 2. Articulate Landing Gear on Ground Contact
        # When contact is true, slightly compress strut
        if snapshot.left_contact:
            self.leg_nodes["left"].setScale(1.0, 1.0, 0.94)
        else:
            self.leg_nodes["left"].setScale(1.0, 1.0, 1.0)

        if snapshot.right_contact:
            self.leg_nodes["right"].setScale(1.0, 1.0, 0.94)
        else:
            self.leg_nodes["right"].setScale(1.0, 1.0, 1.0)

        # 3. Update Propulsion Effects
        # Explicit post-landing and terminal shutdown
        is_touchdown_or_terminal = (
            snapshot.is_terminal
            or snapshot.touchdown_phase in ("SETTLED TOUCHDOWN", "DUAL GEAR CONTACT", "LANDING IMPACT")
            or (snapshot.left_contact and snapshot.right_contact and snapshot.altitude <= 0.08)
            or (snapshot.action == 0 and (snapshot.left_contact or snapshot.right_contact) and snapshot.altitude <= 0.05)
            or (snapshot.throttle == 0.0 and snapshot.rcs_left == 0.0 and snapshot.rcs_right == 0.0 and (snapshot.left_contact or snapshot.right_contact))
        )

        if is_touchdown_or_terminal:
            self.current_throttle = 0.0
            self.current_rcs_l = 0.0
            self.current_rcs_r = 0.0
            self.plume_root.hide()
            self.plight.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
            self.rcs_jet_l.hide()
            self.rcs_jet_r.hide()
            self.dust_intensity = 0.0
            self.dust_root.hide()
        else:
            # Throttle smoothing
            target_throttle = snapshot.throttle
            self.current_throttle += (target_throttle - self.current_throttle) * 0.4

            if self.current_throttle > 0.05:
                self.plume_root.show()
                p_scale_z = 0.4 + 0.6 * self.current_throttle
                # Subtle random flame flicker
                flicker = 1.0 + random.uniform(-0.06, 0.06)
                self.plume_root.setScale(1.0, 1.0, p_scale_z * flicker)

                # Plume illumination
                intensity = self.current_throttle * 1.5
                self.plight.setColor(Vec4(1.2 * intensity, 0.65 * intensity, 0.2 * intensity, 1.0))
                self.plight_np.setPos(snapshot.pos_x, 0.0, max(0.2, snapshot.pos_y - 0.6))
            else:
                self.plume_root.hide()
                self.plight.setColor(Vec4(0.0, 0.0, 0.0, 1.0))

            # RCS micro-jets
            if snapshot.rcs_left > 0.05:
                self.rcs_jet_l.show()
                self.rcs_jet_l.setScale(snapshot.rcs_left * 1.2)
            else:
                self.rcs_jet_l.hide()

            if snapshot.rcs_right > 0.05:
                self.rcs_jet_r.show()
                self.rcs_jet_r.setScale(snapshot.rcs_right * 1.2)
            else:
                self.rcs_jet_r.hide()

            # 4. Surface Dust Impingement (Regolith / Terrestrial Pad Dust)
            if snapshot.altitude < 2.5 and self.current_throttle > 0.1:
                self.dust_root.show()
                alt_factor = max(0.0, (2.5 - snapshot.altitude) / 2.5)
                self.dust_intensity += (alt_factor * self.current_throttle - self.dust_intensity) * 0.3
                wind_drift_x = getattr(snapshot, "wind_force", 0.0) * 0.10
                self.dust_root.setPos(snapshot.pos_x * 0.6 + wind_drift_x, 0.0, 0.0)
                scale_x = (1.0 + self.dust_intensity * 0.8) * (1.0 + min(1.2, abs(getattr(snapshot, "wind_force", 0.0)) * 0.04))
                self.dust_root.setScale(scale_x, 1.0 + self.dust_intensity * 0.8, 1.0 + self.dust_intensity * 0.8)
                self.dust_root.setR(self.sim_time * 25.0)
            else:
                self.dust_intensity *= 0.8
                if self.dust_intensity < 0.02:
                    self.dust_root.hide()

        # 5. Smooth Spring-Damper Camera Kinematics
        # Keeps both lander and landing pad in optimal cinematic perspective
        if self.theme == "spaceport":
            target_cam_x = snapshot.pos_x * 0.4
            target_cam_z = max(7.5, origin_z * 0.55 + 6.0)
            target_cam_dist = 22.0 + max(0.0, origin_z - 2.5) * 0.60
            target_look_z = max(1.8, origin_z * 0.55 + 2.2)
            target_look_y = 2.0
        else:
            target_cam_x = snapshot.pos_x * 0.6
            target_cam_z = max(2.5, origin_z * 0.55 + 1.4)
            target_cam_dist = 13.0 + max(0.0, origin_z - 2.5) * 0.65
            target_look_z = max(0.8, origin_z * 0.68 + 0.3)
            target_look_y = 0.0

        self.cam_smooth_x += (target_cam_x - self.cam_smooth_x) * 0.22
        self.cam_smooth_z += (target_cam_z - self.cam_smooth_z) * 0.22

        self.base.cam.setPos(self.cam_smooth_x, -target_cam_dist, self.cam_smooth_z)
        self.base.cam.lookAt(self.cam_smooth_x * 0.5, target_look_y, target_look_z)

        # 6. Render Panda3D Frame & Extract Buffer
        self.base.taskMgr.step()
        self.base.graphicsEngine.renderFrame()

        data = self.render_tex.getRamImageAs("RGB")
        frame_rgb = np.frombuffer(data, dtype=np.uint8).reshape((self.height, self.width, 3))
        frame_rgb = np.flipud(frame_rgb)

        # 7. Overlay Mission Control Glass-Cockpit HUD
        final_surf = self._composite_hud_overlay(frame_rgb, snapshot)

        # Always blit to self.screen (used by save_screenshot and get_frame_rgb)
        self.screen.blit(final_surf, (0, 0))
        if not self.headless:
            pygame.display.flip()

        # Return RGB array
        return pygame.surfarray.array3d(self.screen).swapaxes(0, 1)

    def _composite_hud_overlay(self, frame_rgb: np.ndarray, snapshot: SimulationSnapshot) -> pygame.Surface:
        """Renders SpaceX/Apollo style glass-cockpit PFD telemetry over the 3D frame."""
        # Convert NumPy RGB to Pygame surface
        base_surf = pygame.image.frombuffer(frame_rgb.tobytes(), (self.width, self.height), "RGB")

        # Margins
        margin_x = max(28, int(self.width * 0.025))
        margin_y = max(16, int(self.height * 0.025))

        # 1. Flight Phase Header Banner (Top Center)
        self._draw_flight_phase_header(base_surf, snapshot, margin_y)

        # 2. Vertical Speed Indicator Ribbon Tape (Left)
        tape_w = max(76, int(84 * (self.width / 1280.0)))
        tape_h = max(220, int(270 * (self.height / 720.0)))
        tape_y = (self.height - tape_h) // 2
        self._draw_vertical_speed_tape(base_surf, snapshot.vel_y, margin_x, tape_y, tape_w, tape_h)

        # 3. Radar Altitude Ribbon Tape (Right)
        right_tx = self.width - margin_x - tape_w
        self._draw_altitude_tape(base_surf, snapshot.altitude, right_tx, tape_y, tape_w, tape_h)

        # 4. 3D Attitude Director Indicator (ADI) — Placed at Upper-Left Next to VSI Tape
        pitch_deg = math.degrees(snapshot.roll)
        adi_x = margin_x + tape_w + 20
        self._draw_attitude_director_indicator(
            base_surf, pitch_deg, snapshot.vel_x, snapshot.vel_y, adi_x, margin_y + 10
        )

        # 5. Actuator & Propulsion Telemetry Card (Bottom Left)
        card_w = max(210, int(230 * (self.width / 1280.0)))
        card_h = max(100, int(112 * (self.height / 720.0)))
        card_y = self.height - margin_y - card_h
        self._draw_actuator_telemetry_card(base_surf, snapshot, margin_x, card_y, card_w, card_h)

        # 6. Navigation & Pad Alignment Card (Bottom Right)
        right_cx = self.width - margin_x - card_w
        self._draw_guidance_card(base_surf, snapshot, right_cx, card_y, card_w, card_h)

        # 7. Post-Flight Debrief Overlay on Terminal Completion
        if snapshot.is_terminal:
            self._draw_mission_debrief(base_surf, snapshot)

        return base_surf

    def _draw_flight_phase_header(self, surf: pygame.Surface, snapshot: SimulationSnapshot, top_y: int) -> None:
        """Renders top annunciator banner with flight phase and temporal synchronization info."""
        banner_w = min(self.width - 200, 520)
        banner_h = 42
        bx = (self.width - banner_w) // 2
        by = top_y

        panel_surf = pygame.Surface((banner_w, banner_h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (15, 23, 42, 220), (0, 0, banner_w, banner_h), border_radius=6)
        pygame.draw.rect(panel_surf, (56, 189, 248, 140), (0, 0, banner_w, banner_h), width=1, border_radius=6)
        surf.blit(panel_surf, (bx, by))

        status_text = snapshot.touchdown_phase
        if snapshot.outcome == "SUCCESS":
            status_text = "MISSION SUCCESS — TOUCHDOWN CONFIRMED"
            accent_color = (34, 197, 94)
        elif snapshot.outcome == "CRASH":
            status_text = "CRITICAL FAILURE — IMPACT / LOSS"
            accent_color = (239, 68, 68)
        elif "TOUCH" in status_text or "CONTACT" in status_text:
            accent_color = (34, 197, 94)
        elif snapshot.throttle > 0.05:
            status_text = "MAIN ENGINE BRAKING BURN ACTIVE"
            accent_color = (56, 189, 248)
        elif snapshot.rcs_left > 0 or snapshot.rcs_right > 0:
            which = "L" if snapshot.rcs_left > 0 else "R"
            status_text = f"RCS ATTITUDE CORRECTION [{which}]"
            accent_color = (168, 85, 247)
        else:
            status_text = "BALLISTIC DESCENT — COASTING"
            accent_color = (148, 163, 184)

        txt_status = self.font_large.render(status_text, True, accent_color)
        surf.blit(txt_status, (bx + (banner_w - txt_status.get_width()) // 2, by + 6))

        sub_text = (
            f"SIM T+{snapshot.sim_time:05.2f}s [{self.speed_factor:.2f}x] | "
            f"WALL {self.wall_time:05.2f}s | "
            f"STEP {snapshot.step:04d} | "
            f"RWD {snapshot.cumulative_reward:+07.2f}"
        )
        txt_sub = self.font_tiny.render(sub_text, True, (148, 163, 184))
        surf.blit(txt_sub, (bx + (banner_w - txt_sub.get_width()) // 2, by + 26))

    def _draw_vertical_speed_tape(
        self, surf: pygame.Surface, vel_y: float, tx: int, ty: int, tw: int, th: int
    ) -> None:
        """Renders vertical descent tape meter."""
        tape_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(tape_surf, (15, 23, 42, 215), (0, 0, tw, th), border_radius=6)
        pygame.draw.rect(tape_surf, (51, 65, 85, 180), (0, 0, tw, th), width=1, border_radius=6)
        surf.blit(tape_surf, (tx, ty))

        header = self.font_tiny.render("VERT SPEED", True, (148, 163, 184))
        surf.blit(header, (tx + (tw - header.get_width()) // 2, ty + 8))

        cy = ty + (th // 2)
        pygame.draw.line(surf, (100, 116, 139), (tx + 10, cy), (tx + tw - 10, cy), width=1)

        # Gate zone
        gate_h = int(30 * (th / 270.0))
        gate_surf = pygame.Surface((tw - 20, gate_h), pygame.SRCALPHA)
        pygame.draw.rect(gate_surf, (34, 197, 94, 60), (0, 0, tw - 20, gate_h), border_radius=3)
        surf.blit(gate_surf, (tx + 10, cy))

        # Dynamic indicator needle
        clamped_vy = max(-1.6, min(1.6, vel_y))
        needle_y = cy - int((clamped_vy / 1.6) * (th // 2 - 24))

        color = (34, 197, 94) if abs(vel_y) <= 0.40 else ((234, 179, 8) if abs(vel_y) <= 0.70 else (239, 68, 68))
        pygame.draw.polygon(surf, color, [(tx + tw - 6, needle_y), (tx + tw - 16, needle_y - 5), (tx + tw - 16, needle_y + 5)])

        readout_box = pygame.Rect(tx + 6, cy + int(th * 0.32), tw - 12, 22)
        pygame.draw.rect(surf, (30, 41, 59), readout_box, border_radius=4)
        pygame.draw.rect(surf, color, readout_box, width=1, border_radius=4)

        readout_txt = self.font_small.render(f"{vel_y * 5.0:+0.2f}m/s", True, color)
        surf.blit(readout_txt, (readout_box.centerx - readout_txt.get_width() // 2, readout_box.centery - readout_txt.get_height() // 2))

    def _draw_altitude_tape(
        self, surf: pygame.Surface, altitude: float, tx: int, ty: int, tw: int, th: int
    ) -> None:
        """Renders radar altitude tape with clear numerical readouts."""
        tape_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(tape_surf, (15, 23, 42, 215), (0, 0, tw, th), border_radius=6)
        pygame.draw.rect(tape_surf, (51, 65, 85, 180), (0, 0, tw, th), width=1, border_radius=6)
        surf.blit(tape_surf, (tx, ty))

        header = self.font_tiny.render("RADAR ALT", True, (148, 163, 184))
        surf.blit(header, (tx + (tw - header.get_width()) // 2, ty + 8))

        ground_y = ty + th - 36
        pygame.draw.line(surf, (234, 179, 8), (tx + 10, ground_y), (tx + tw - 10, ground_y), width=2)

        norm_alt = altitude / 10.0
        clamped_alt = max(0.0, min(1.2, norm_alt))
        alt_bug_y = ground_y - int((clamped_alt / 1.2) * (th - 75))

        color = (34, 197, 94) if altitude < 1.0 else ((56, 189, 248) if altitude < 5.0 else (148, 163, 184))
        pygame.draw.polygon(surf, color, [(tx + 6, alt_bug_y), (tx + 16, alt_bug_y - 5), (tx + 16, alt_bug_y + 5)])

        readout_box = pygame.Rect(tx + 6, ty + 32, tw - 12, 22)
        pygame.draw.rect(surf, (30, 41, 59), readout_box, border_radius=4)
        pygame.draw.rect(surf, color, readout_box, width=1, border_radius=4)

        readout_txt = self.font_small.render(f"{max(0.0, altitude):04.1f}m", True, color)
        surf.blit(readout_txt, (readout_box.centerx - readout_txt.get_width() // 2, readout_box.centery - readout_txt.get_height() // 2))

    def _draw_attitude_director_indicator(
        self, surf: pygame.Surface, pitch_deg: float, vel_x: float, vel_y: float, ax: int, ay: int
    ) -> None:
        """Renders 3D Attitude Director Indicator (ADI) with horizon sphere."""
        adi_w = 104
        adi_h = 104

        adi_surf = pygame.Surface((adi_w, adi_h), pygame.SRCALPHA)
        acx, acy = adi_w // 2, adi_h // 2
        radius = 45

        mask_surf = pygame.Surface((adi_w, adi_h), pygame.SRCALPHA)
        pygame.draw.circle(mask_surf, (255, 255, 255, 255), (acx, acy), radius)

        ball_surf = pygame.Surface((adi_w * 2, adi_h * 2), pygame.SRCALPHA)
        pygame.draw.rect(ball_surf, (30, 58, 138), (0, 0, adi_w * 2, adi_h))
        pygame.draw.rect(ball_surf, (88, 28, 12), (0, adi_h, adi_w * 2, adi_h))
        pygame.draw.line(ball_surf, (255, 255, 255), (0, adi_h), (adi_w * 2, adi_h), width=2)

        for deg in [-20, -10, 10, 20]:
            py_pos = adi_h - int(deg * 1.4)
            pygame.draw.line(ball_surf, (226, 232, 240), (adi_w - 16, py_pos), (adi_w + 16, py_pos), width=1)

        rot_ball = pygame.transform.rotate(ball_surf, pitch_deg)
        r_rect = rot_ball.get_rect()
        r_rect.center = (acx, acy)
        adi_surf.blit(rot_ball, r_rect.topleft)
        adi_surf.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        pygame.draw.circle(adi_surf, (148, 163, 184), (acx, acy), radius, width=2)

        # Crosshair
        pygame.draw.circle(adi_surf, (234, 179, 8), (acx, acy), 3)
        pygame.draw.line(adi_surf, (234, 179, 8), (acx - 14, acy), (acx - 5, acy), width=2)
        pygame.draw.line(adi_surf, (234, 179, 8), (acx + 5, acy), (acx + 14, acy), width=2)

        # Flight Path Marker
        fpm_x = acx + int(vel_x * 22.0)
        fpm_y = acy - int(vel_y * 16.0)
        dist = math.hypot(fpm_x - acx, fpm_y - acy)
        if dist < radius - 6:
            pygame.draw.circle(adi_surf, (56, 189, 248), (fpm_x, fpm_y), 4, width=1)
            pygame.draw.line(adi_surf, (56, 189, 248), (fpm_x - 6, fpm_y), (fpm_x - 3, fpm_y))
            pygame.draw.line(adi_surf, (56, 189, 248), (fpm_x + 3, fpm_y), (fpm_x + 6, fpm_y))

        surf.blit(adi_surf, (ax, ay))

        pitch_color = (34, 197, 94) if abs(pitch_deg) <= 11.5 else (239, 68, 68)
        p_txt = self.font_tiny.render(f"PITCH {pitch_deg:+05.1f}°", True, pitch_color)
        surf.blit(p_txt, (ax + (adi_w - p_txt.get_width()) // 2, ay + adi_h + 3))

    def _draw_actuator_telemetry_card(
        self, surf: pygame.Surface, snapshot: SimulationSnapshot, cx: int, cy: int, cw: int, ch: int
    ) -> None:
        """Renders propulsion and landing gear actuator status."""
        card_surf = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 23, 42, 220), (0, 0, cw, ch), border_radius=6)
        pygame.draw.rect(card_surf, (51, 65, 85, 180), (0, 0, cw, ch), width=1, border_radius=6)
        surf.blit(card_surf, (cx, cy))

        title = self.font_small.render("PROPULSION & GEAR", True, (56, 189, 248))
        surf.blit(title, (cx + 12, cy + 8))

        mode_name = {1.0: "1.00x REAL", 0.75: "0.75x MOD", 0.5: "0.50x CINE", 0.25: "0.25x SLOW"}.get(
            self.speed_factor, f"{self.speed_factor:.2f}x"
        )
        txt_speed = self.font_tiny.render(mode_name, True, (245, 158, 11))
        surf.blit(txt_speed, (cx + cw - txt_speed.get_width() - 12, cy + 8))

        # Throttle Bar
        th_label = self.font_tiny.render("THROTTLE", True, (148, 163, 184))
        surf.blit(th_label, (cx + 12, cy + 30))

        bar_w = int(cw * 0.42)
        bar_h = 10
        bar_x = cx + 80
        pygame.draw.rect(surf, (30, 41, 59), (bar_x, cy + 31, bar_w, bar_h), border_radius=2)
        if snapshot.throttle > 0.02:
            fill_w = int(bar_w * snapshot.throttle)
            pygame.draw.rect(surf, (249, 115, 22), (bar_x, cy + 31, fill_w, bar_h), border_radius=2)
            pct_txt = self.font_tiny.render(f"{int(snapshot.throttle * 100)}%", True, (249, 115, 22))
        else:
            pct_txt = self.font_tiny.render("0%", True, (100, 116, 139))
        surf.blit(pct_txt, (bar_x + bar_w + 6, cy + 29))

        # RCS
        rcs_label = self.font_tiny.render("RCS THRUST", True, (148, 163, 184))
        surf.blit(rcs_label, (cx + 12, cy + 54))
        l_color = (168, 85, 247) if snapshot.rcs_left > 0.5 else (71, 85, 105)
        r_color = (168, 85, 247) if snapshot.rcs_right > 0.5 else (71, 85, 105)
        txt_l = self.font_tiny.render("L: FIRING" if snapshot.rcs_left > 0.5 else "L: IDLE", True, l_color)
        txt_r = self.font_tiny.render("R: FIRING" if snapshot.rcs_right > 0.5 else "R: IDLE", True, r_color)
        surf.blit(txt_l, (cx + 80, cy + 54))
        surf.blit(txt_r, (cx + 148, cy + 54))

        # Gear
        gear_label = self.font_tiny.render("GEAR LOCK", True, (148, 163, 184))
        surf.blit(gear_label, (cx + 12, cy + 78))
        lg_color = (34, 197, 94) if snapshot.left_contact else (100, 116, 139)
        rg_color = (34, 197, 94) if snapshot.right_contact else (100, 116, 139)
        txt_lg = self.font_tiny.render("L: LOCKED" if snapshot.left_contact else "L: DEPLOY", True, lg_color)
        txt_rg = self.font_tiny.render("R: LOCKED" if snapshot.right_contact else "R: DEPLOY", True, rg_color)
        surf.blit(txt_lg, (cx + 80, cy + 78))
        surf.blit(txt_rg, (cx + 148, cy + 78))

    def _draw_guidance_card(
        self, surf: pygame.Surface, snapshot: SimulationSnapshot, cx: int, cy: int, cw: int, ch: int
    ) -> None:
        """Renders guidance, cross-track offset, and lateral drift readouts."""
        card_surf = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 23, 42, 220), (0, 0, cw, ch), border_radius=6)
        pygame.draw.rect(card_surf, (51, 65, 85, 180), (0, 0, cw, ch), width=1, border_radius=6)
        surf.blit(card_surf, (cx, cy))

        title = self.font_small.render("GUIDANCE & NAVIGATION", True, (56, 189, 248))
        surf.blit(title, (cx + 12, cy + 8))

        offset_m = snapshot.pos_x
        offset_color = (34, 197, 94) if abs(snapshot.pos_x) <= 1.8 else (239, 68, 68)
        lbl_xtk = self.font_tiny.render("CROSS-TRACK", True, (148, 163, 184))
        val_xtk = self.font_small.render(f"{offset_m:+05.2f}m", True, offset_color)
        surf.blit(lbl_xtk, (cx + 12, cy + 32))
        surf.blit(val_xtk, (cx + cw - val_xtk.get_width() - 12, cy + 30))

        drift_color = (34, 197, 94) if abs(snapshot.vel_x) <= 0.40 else (234, 179, 8)
        lbl_vx = self.font_tiny.render("LATERAL DRIFT", True, (148, 163, 184))
        val_vx = self.font_small.render(f"{snapshot.vel_x * 5.0:+05.2f}m/s", True, drift_color)
        surf.blit(lbl_vx, (cx + 12, cy + 54))
        surf.blit(val_vx, (cx + cw - val_vx.get_width() - 12, cy + 52))

        spin_deg = math.degrees(snapshot.ang_vel)
        spin_color = (34, 197, 94) if abs(spin_deg) <= 20.0 else (239, 68, 68)
        lbl_spin = self.font_tiny.render("ROLL RATE", True, (148, 163, 184))
        val_spin = self.font_small.render(f"{spin_deg:+05.1f}°/s", True, spin_color)
        surf.blit(lbl_spin, (cx + 12, cy + 76))
        surf.blit(val_spin, (cx + cw - val_spin.get_width() - 12, cy + 74))

    def _draw_mission_debrief(self, surf: pygame.Surface, snapshot: SimulationSnapshot) -> None:
        """Renders comprehensive post-landing mission debrief overlay."""
        card_w = min(self.width - 64, 640)
        card_h = 240
        cx = (self.width - card_w) // 2
        cy = (self.height - card_h) // 2 + 10

        card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 23, 42, 245), (0, 0, card_w, card_h), border_radius=10)

        is_success = (snapshot.outcome == "SUCCESS")
        border_color = (34, 197, 94) if is_success else (239, 68, 68)
        pygame.draw.rect(card_surf, border_color, (0, 0, card_w, card_h), width=2, border_radius=10)
        surf.blit(card_surf, (cx, cy))

        # Dynamic root-cause failure labeling
        if is_success:
            header_title = "MISSION SUCCESSFUL — SOFT TOUCHDOWN CONFIRMED"
        elif snapshot.outcome == "TIMEOUT":
            header_title = "MISSION TERMINATED — HOVER TIMEOUT (FUEL EXHAUSTION)"
        elif snapshot.outcome == "OUT_OF_BOUNDS":
            header_title = "MISSION TERMINATED — TRAJECTORY DRIFT (OUT OF BOUNDS)"
        elif snapshot.impact_vel_x is not None and abs(snapshot.impact_vel_x) > 0.40:
            header_title = "MISSION TERMINATED — STRUCTURAL FAILURE (EXCESSIVE LATERAL SHEAR)"
        elif snapshot.impact_vel_y is not None and abs(snapshot.impact_vel_y) > 0.40:
            header_title = "MISSION TERMINATED — STRUCTURAL FAILURE (EXCESSIVE IMPACT KINETIC ENERGY)"
        elif snapshot.impact_tilt is not None and abs(math.degrees(snapshot.impact_tilt)) > 11.5:
            header_title = "MISSION TERMINATED — STRUCTURAL FAILURE (ROLLOVER TILT)"
        else:
            header_title = "MISSION TERMINATED — STRUCTURAL FAILURE (CHASSIS IMPACT)"

        txt_header = self.font_large.render(header_title, True, border_color)
        surf.blit(txt_header, (cx + (card_w - txt_header.get_width()) // 2, cy + 18))

        pygame.draw.line(surf, (51, 65, 85), (cx + 20, cy + 48), (cx + card_w - 20, cy + 48), width=1)

        col1_x = cx + 24
        col2_x = cx + int(card_w * 0.52)
        row_y = cy + 62
        dy = 26

        pitch_deg = math.degrees(snapshot.roll)
        # Separate first-contact impact measurements from settled-state rest values
        if snapshot.impact_vel_y is not None and snapshot.impact_vel_x is not None:
            impact_vy_str = f"{abs(snapshot.impact_vel_y):.2f} m/s"
            impact_vx_str = f"{abs(snapshot.impact_vel_x):.2f} m/s"
            impact_vy_col = (34, 197, 94) if abs(snapshot.impact_vel_y) <= 0.40 else (239, 68, 68)
            impact_vx_col = (34, 197, 94) if abs(snapshot.impact_vel_x) <= 0.40 else (239, 68, 68)
        else:
            impact_vy_str = f"{abs(snapshot.vel_y * 5.0):.2f} m/s"
            impact_vx_str = f"{abs(snapshot.vel_x * 5.0):.2f} m/s"
            impact_vy_col = (34, 197, 94) if abs(snapshot.vel_y) <= 0.40 else (239, 68, 68)
            impact_vx_col = (34, 197, 94) if abs(snapshot.vel_x) <= 0.40 else (239, 68, 68)

        impact_tilt_deg = math.degrees(snapshot.impact_tilt) if snapshot.impact_tilt is not None else pitch_deg
        tilt_col = (34, 197, 94) if abs(impact_tilt_deg) <= 11.5 else (239, 68, 68)

        fields_col1 = [
            ("Touchdown Status", "PASS (NOMINAL REST)" if is_success else str(snapshot.outcome), border_color),
            ("Impact Descent Vy", f"{impact_vy_str} (Limit: 0.40)", impact_vy_col),
            ("Impact Lateral Vx", f"{impact_vx_str} (Limit: 0.40)", impact_vx_col),
            ("Impact Attitude", f"{abs(impact_tilt_deg):.1f}° (Limit: 11.5°)", tilt_col),
            ("Pad Radial Offset", f"{abs(snapshot.pos_x):.2f} m (Pad: 3.6m)", (34, 197, 94) if abs(snapshot.pos_x) <= 1.8 else (239, 68, 68)),
        ]

        wind_val = abs(getattr(snapshot, "wind_force", 0.0))
        wind_str = f"{wind_val:.1f} N/kg" if wind_val > 0.05 else "CALM (0 m/s)"
        fields_col2 = [
            ("Gear Leg Lock", "DUAL CONTACT (L+R)" if snapshot.left_contact and snapshot.right_contact else "PARTIAL / OFF", (34, 197, 94) if snapshot.left_contact and snapshot.right_contact else (239, 68, 68)),
            ("Wind Disturbance", wind_str, (56, 189, 248) if "CALM" not in wind_str else (148, 163, 184)),
            ("Mission Time", f"T+{snapshot.sim_time:.2f}s ({snapshot.step} steps)", (148, 163, 184)),
            ("Reward Score", f"{snapshot.cumulative_reward:+.2f} pts", (34, 197, 94) if snapshot.cumulative_reward >= 200 else (234, 179, 8)),
            ("Architecture", "Panda3D Hardware PBR (OpenGL)", (56, 189, 248)),
        ]

        for i, (label, val, col) in enumerate(fields_col1):
            lbl_surf = self.font_tiny.render(label, True, (148, 163, 184))
            val_surf = self.font_small.render(val, True, col)
            surf.blit(lbl_surf, (col1_x, row_y + i * dy))
            surf.blit(val_surf, (col1_x + 130, row_y + i * dy - 1))

        for i, (label, val, col) in enumerate(fields_col2):
            lbl_surf = self.font_tiny.render(label, True, (148, 163, 184))
            val_surf = self.font_small.render(val, True, col)
            surf.blit(lbl_surf, (col2_x, row_y + i * dy))
            surf.blit(val_surf, (col2_x + 120, row_y + i * dy - 1))

        hint_txt = self.font_tiny.render("Press SPACE or ESC to proceed | Press 1..4 to change replay speed", True, (100, 116, 139))
        surf.blit(hint_txt, (cx + (card_w - hint_txt.get_width()) // 2, cy + card_h - 22))

    def render_frame(
        self,
        env: Any,
        snapshot_or_obs: Union[SimulationSnapshot, np.ndarray],
        action: int = 0,
        step: int = 0,
        reward: float = 0.0,
        cumulative_reward: float = 0.0,
        terminated: bool = False,
        truncated: bool = False,
        outcome: Optional[str] = None,
    ) -> np.ndarray:
        """Adapts interactive environment stepping to 3D rendering pipeline."""
        if isinstance(snapshot_or_obs, SimulationSnapshot):
            snapshot = snapshot_or_obs
        else:
            snapshot = capture_snapshot_from_env(
                env=env,
                obs=snapshot_or_obs,
                action=action,
                step=step,
                reward=reward,
                cumulative_reward=cumulative_reward,
                terminated=terminated,
                truncated=truncated,
                outcome=outcome,
            )

        return self.render_snapshot(snapshot)

    def extract_telemetry(
        self,
        env: Any,
        obs: np.ndarray,
        action: int = 0,
        step: int = 0,
        reward: float = 0.0,
        cumulative_reward: float = 0.0,
        terminated: bool = False,
        truncated: bool = False,
        criteria: Optional[LandingCriteria] = None,
    ) -> SimulationSnapshot:
        """Compatibility adapter matching legacy renderer extract_telemetry signature."""
        outcome = None
        if terminated or truncated:
            crit = criteria or LandingCriteria()
            outcome = classify_outcome(
                terminated=terminated,
                truncated=truncated,
                final_step_reward=reward,
                final_obs=obs,
                criteria=crit,
            ).upper()

        # Track initial contact kinematics before settling
        legs = getattr(env.unwrapped, "legs", None)
        left_c = bool(legs[0].ground_contact) if legs and len(legs) >= 2 else bool(obs[6] > 0.5)
        right_c = bool(legs[1].ground_contact) if legs and len(legs) >= 2 else bool(obs[7] > 0.5)

        if (left_c or right_c) and self.first_contact_info is None:
            lander = getattr(env.unwrapped, "lander", None)
            if lander is not None:
                imp_vx = float(lander.linearVelocity.x)
                imp_vy = float(lander.linearVelocity.y)
                imp_th = float(lander.angle)
            else:
                imp_vx = float(obs[2] * 5.0)
                imp_vy = float(obs[3] * 5.0)
                impact_th = float(obs[4])
            self.first_contact_info = {
                "impact_vel_x": imp_vx,
                "impact_vel_y": imp_vy,
                "impact_tilt": imp_th,
            }

        imp_vx = self.first_contact_info["impact_vel_x"] if self.first_contact_info else None
        imp_vy = self.first_contact_info["impact_vel_y"] if self.first_contact_info else None
        imp_th = self.first_contact_info["impact_tilt"] if self.first_contact_info else None

        return capture_snapshot_from_env(
            env=env,
            obs=obs,
            action=action,
            step=step,
            reward=reward,
            cumulative_reward=cumulative_reward,
            terminated=terminated,
            truncated=truncated,
            outcome=outcome,
            impact_vel_x=imp_vx,
            impact_vel_y=imp_vy,
            impact_tilt=imp_th,
        )

    def save_screenshot(self, filepath: str) -> None:
        """Saves current rendered frame directly to disk as PNG."""
        frame_rgb = pygame.surfarray.array3d(self.screen).swapaxes(0, 1)
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        cv2.imwrite(filepath, frame_bgr)

    def get_frame_rgb(self) -> np.ndarray:
        """Returns the current composite frame as (H, W, 3) RGB uint8 array."""
        return pygame.surfarray.array3d(self.screen).swapaxes(0, 1)

    def get_frame_bgr(self) -> np.ndarray:
        """Returns the current composite frame as (H, W, 3) BGR uint8 array for OpenCV."""
        frame_rgb = self.get_frame_rgb()
        return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    def close(self) -> None:
        """Releases Panda3D and Pygame graphics resources cleanly."""
        try:
            self.base.destroy()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass
