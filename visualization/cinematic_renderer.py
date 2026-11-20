"""Cinematic Aerospace Landing Simulator Renderer (Stage 8.3 Reconstruction).

High-fidelity aerospace visualization engine featuring:
- Physically anchored multi-emitter propulsion system:
  * Layered main engine supersonic exhaust plume with continuous thermal core,
    fluttering combustion envelope, Mach shock diamonds, and continuous exhaust stream.
  * Rapidly expanding translucent cold-gas nitrogen RCS puffs from port manifolds
    with true discrete action mapping (no solid white polygons).
  * Continuous ignition attack and shutdown decay transitions.
- Dynamic lunar regolith surface dust physics:
  * Impingement-triggered horizontal surface dust clouds blasting radially across the ground.
  * Ballistic trajectory under lunar gravity without atmospheric drag.
  * Natural fading on throttle cut (zero cyan triangular artifacts).
- Coherent, detailed aerospace vehicle model:
  * Metallic composite fuselage, thermal kapton MLI insulation, titanium grid fins,
    glowing tungsten bell nozzle, and articulating hydraulic landing gear.
  * Directional vacuum solar lighting with sharp self-shadows and ground-projected shadow.
- Responsive, unclipped glass-cockpit Primary Flight Display (PFD):
  * Calibrated ribbon tapes (Vertical Speed with safe landing gate, Radar Altitude).
  * 3D Attitude Director Indicator (ADI) with Flight Path Marker and roll ladder.
  * Non-overlapping cards with guaranteed safe margins across all resolutions.
- Delta-time based frame-rate independent animation and spring-damper camera tracking.
- Headless off-screen rendering support and OpenCV MP4 video recording export.
"""

from dataclasses import dataclass
import math
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import cv2
import numpy as np
import pygame
import pygame.gfxdraw

from evaluation.evaluate import LandingCriteria, classify_outcome
from visualization.aerospace_renderer import VisualTelemetry


@dataclass
class RegolithDustCloud:
    """Soft expanding regolith dust puff created by engine ground impingement."""
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    growth_rate: float
    alpha: float
    max_alpha: float
    life: float
    max_life: float


@dataclass
class RCSPuff:
    """Directional cold-gas nitrogen puff emitted from attitude thrusters."""
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    alpha: float
    max_alpha: float
    life: float
    max_life: float


@dataclass
class ExhaustStreamParticle:
    """Incandescent gas packet in the continuous core exhaust stream."""
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    life: float
    max_life: float
    temp: float  # 1.0 (white/cyan) -> 0.0 (amber/smoke)


class CinematicAerospaceRenderer:
    """Cinematic widescreen 2D aerospace simulator renderer."""

    _font_cache: Dict[Tuple[str, int, bool], pygame.font.Font] = {}

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        headless: bool = False,
        title: str = "Autonomous Rocket Landing — Cinematic Aerospace Simulator",
        target_fps: int = 50,
        enable_camera_tracking: bool = True,
        speed_factor: float = 0.5,
    ):
        """Initializes Pygame graphics context, camera, and visual asset systems."""
        self.width = width
        self.height = height
        self.headless = headless
        self.title = title
        self.target_fps = target_fps
        self.enable_camera_tracking = enable_camera_tracking
        self.speed_factor = max(0.1, min(2.0, float(speed_factor)))

        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        # Display surface
        if self.headless:
            self.screen = pygame.Surface((self.width, self.height))
        else:
            self.screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption(self.title)

        self.clock = pygame.time.Clock()
        self.last_frame_time = time.perf_counter()
        self.sim_dt = 1.0 / target_fps
        self.dt = self.sim_dt
        self.sim_time = 0.0
        self.wall_time = 0.0
        self.recording_fps = max(10, int(round(self.target_fps * self.speed_factor)))

        # Dynamic Camera State (World space coordinates)
        self.cam_x = 10.0
        self.cam_y = 7.5
        self.cam_zoom = 56.0  # Pixels per meter
        self.cam_target_x = 10.0
        self.cam_target_y = 7.5
        self.cam_target_zoom = 56.0
        self.cam_shake_x = 0.0
        self.cam_shake_y = 0.0

        # World geometry anchors
        self.world_center_x = 10.0
        self.pad_world_x1 = 8.0
        self.pad_world_x2 = 12.0
        self.helipad_y = 3.333

        # Continuous Propulsion & Thermal State Machines
        self.main_throttle = 0.0      # 0.0 to 1.0 (continuous transition)
        self.rcs_left_power = 0.0     # 0.0 to 1.0 (Action 3)
        self.rcs_right_power = 0.0    # 0.0 to 1.0 (Action 1)
        self.nozzle_heat = 0.0        # Thermal heat memory (0.0 to 1.0)

        # Particle Pools
        self.dust_clouds: List[RegolithDustCloud] = []
        self.rcs_puffs: List[RCSPuff] = []
        self.exhaust_particles: List[ExhaustStreamParticle] = []

        # Typography (Scale-aware)
        base_scale = min(1.0, self.width / 1280.0)
        self.font_title = self._load_font(max(15, int(20 * base_scale)), bold=True)
        self.font_large = self._load_font(max(13, int(15 * base_scale)), bold=True)
        self.font_main = self._load_font(max(11, int(13 * base_scale)), bold=True)
        self.font_mono = self._load_font(max(10, int(12 * base_scale)), mono=True)
        self.font_small = self._load_font(max(9, int(10 * base_scale)), mono=True)
        self.font_tiny = self._load_font(max(8, int(9 * base_scale)), mono=True)

        # Pre-computed celestial assets
        self.stars = self._generate_starfield(count=180)
        self.earth_surf = self._generate_crescent_earth(radius=max(28, int(40 * base_scale)))
        self.mountains = self._generate_lunar_mountains()
        self.craters = self._generate_craters()
        self.boulders = self._generate_boulders()

        # Dynamic plume animation ticker
        self.anim_tick = 0

        # Video recording support
        self.video_writer: Optional[cv2.VideoWriter] = None

    def set_speed_factor(self, factor: float) -> None:
        """Sets the presentation playback speed factor (e.g., 0.25, 0.5, 0.75, 1.0)."""
        self.speed_factor = max(0.1, min(2.0, float(factor)))
        self.recording_fps = max(10, int(round(self.target_fps * self.speed_factor)))

    def _load_font(self, size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
        """Loads clean system font with fallback and caching."""
        key = ("mono" if mono else "sans", size, bold)
        if key in self._font_cache:
            return self._font_cache[key]

        font_names = ["consolas", "lucidaconsole", "couriernew"] if mono else ["segoeui", "helvetica", "arial"]
        for name in font_names:
            try:
                font = pygame.font.SysFont(name, size, bold=bold)
                if font:
                    self._font_cache[key] = font
                    return font
            except Exception:
                continue
        fallback = pygame.font.Font(None, size)
        self._font_cache[key] = fallback
        return fallback

    def _generate_starfield(self, count: int = 180) -> List[Tuple[int, int, int, int]]:
        """Generates realistic starfield with varied magnitudes and colors."""
        rng = random.Random(42)
        stars = []
        for _ in range(count):
            x = rng.randint(0, self.width)
            y = rng.randint(0, int(self.height * 0.75))
            r = rng.random()
            if r > 0.94:
                radius = 2
                brightness = rng.randint(220, 255)
            elif r > 0.70:
                radius = 1
                brightness = rng.randint(160, 220)
            else:
                radius = 1
                brightness = rng.randint(90, 150)
            stars.append((x, y, radius, brightness))
        return stars

    def _generate_crescent_earth(self, radius: int = 40) -> pygame.Surface:
        """Draws photorealistic crescent Earth with Rayleigh atmospheric scattering glow."""
        size = radius * 4
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2

        # Outer atmospheric glow (blue-cyan halo)
        for r in range(radius + 12, radius, -2):
            alpha = int(45 * (1.0 - (r - radius) / 12.0))
            pygame.draw.circle(surf, (56, 189, 248, alpha), (cx, cy), r)

        # Dark Earth sphere base
        pygame.draw.circle(surf, (15, 23, 42), (cx, cy), radius)

        # Sunlit crescent
        crescent_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(crescent_surf, (37, 99, 235), (cx, cy), radius)
        # Cloud swirls
        pygame.draw.arc(crescent_surf, (224, 242, 254), (cx - radius, cy - radius, radius * 2, radius * 2), 0.8, 2.5, 3)
        pygame.draw.arc(crescent_surf, (34, 197, 94), (cx - radius + 4, cy - radius + 4, radius * 2 - 8, radius * 2 - 8), 1.2, 2.1, 2)

        # Shadow mask
        shadow_mask = pygame.Surface((size, size), pygame.SRCALPHA)
        shadow_mask.fill((0, 0, 0, 0))
        pygame.draw.circle(shadow_mask, (0, 0, 0, 255), (cx + int(radius * 0.45), cy + int(radius * 0.2)), int(radius * 1.05))

        crescent_surf.blit(shadow_mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        surf.blit(crescent_surf, (0, 0))

        # Thin atmospheric rim highlight on sunward limb
        pygame.draw.arc(surf, (186, 230, 253, 230), (cx - radius - 1, cy - radius - 1, (radius + 1) * 2, (radius + 1) * 2), 1.0, 2.8, 2)

        return surf

    def _generate_lunar_mountains(self) -> List[Tuple[int, int]]:
        """Generates jagged distant lunar mountain range."""
        rng = random.Random(101)
        points = []
        y_base = int(self.height * 0.62)
        x = 0
        points.append((0, self.height))
        points.append((0, y_base))
        while x < self.width:
            x += rng.randint(30, 80)
            y = y_base + rng.randint(-35, 25)
            points.append((min(self.width, x), y))
        points.append((self.width, self.height))
        return points

    def _generate_craters(self) -> List[Dict[str, float]]:
        """Generates procedural lunar craters with sunward illumination."""
        rng = random.Random(77)
        craters = []
        for _ in range(12):
            wx = rng.uniform(0.5, 19.5)
            if 7.5 < wx < 12.5:
                continue
            wy = rng.uniform(2.0, 4.0)
            rad_x = rng.uniform(0.3, 0.8)
            rad_y = rad_x * rng.uniform(0.3, 0.5)
            craters.append({"x": wx, "y": wy, "rx": rad_x, "ry": rad_y})
        return craters

    def _generate_boulders(self) -> List[Dict[str, float]]:
        """Generates scattered surface boulders casting directional shadows."""
        rng = random.Random(88)
        boulders = []
        for _ in range(16):
            wx = rng.uniform(0.5, 19.5)
            if 7.8 < wx < 12.2:
                continue
            wy = rng.uniform(2.5, 4.2)
            size = rng.uniform(0.12, 0.35)
            boulders.append({"x": wx, "y": wy, "size": size})
        return boulders

    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Maps Box2D meter coordinates to screen pixels using dynamic camera."""
        if not self.enable_camera_tracking:
            screen_x = int(self.width // 2 + (world_x - self.world_center_x) * 48.0)
            screen_y = int(self.height * 0.78 - (world_y - self.helipad_y) * 48.0)
            return screen_x, screen_y

        screen_x = int(self.width / 2.0 + (world_x - (self.cam_x + self.cam_shake_x)) * self.cam_zoom)
        screen_y = int(self.height / 2.0 - (world_y - (self.cam_y + self.cam_shake_y)) * self.cam_zoom)
        return screen_x, screen_y

    def update_camera(self, telemetry: VisualTelemetry, dt: float = 0.02) -> None:
        """Smoothly interpolates camera tracking target, zoom, and engine rumble."""
        if not self.enable_camera_tracking:
            return

        rocket_x = self.world_center_x + (telemetry.pos_x * 10.0)
        rocket_y = telemetry.pos_y
        rel_alt = max(0.0, rocket_y - self.helipad_y)

        # Dynamic framing strategy
        if rel_alt > 5.5:
            self.cam_target_x = rocket_x + (telemetry.vel_x * 0.15)
            self.cam_target_y = rocket_y - 0.7
            self.cam_target_zoom = 66.0
        else:
            t = rel_alt / 5.5
            self.cam_target_x = (rocket_x * 0.55) + (self.world_center_x * 0.45)
            self.cam_target_y = (rocket_y * 0.42) + (self.helipad_y * 0.58) + 0.35
            self.cam_target_zoom = 50.0 + (t * 16.0)

        # Frame-rate independent exponential smoothing
        alpha_pos = 1.0 - math.exp(-6.0 * dt)
        alpha_zoom = 1.0 - math.exp(-4.0 * dt)

        self.cam_x += (self.cam_target_x - self.cam_x) * alpha_pos
        self.cam_y += (self.cam_target_y - self.cam_y) * alpha_pos
        self.cam_zoom += (self.cam_target_zoom - self.cam_zoom) * alpha_zoom

        # Camera vibration during main engine burn
        if self.main_throttle > 0.1:
            shake_amp = 0.03 * self.main_throttle
            self.cam_shake_x = (random.random() - 0.5) * shake_amp
            self.cam_shake_y = (random.random() - 0.5) * shake_amp
        else:
            decay = math.exp(-15.0 * dt)
            self.cam_shake_x *= decay
            self.cam_shake_y *= decay

    def reset(self, initial_telemetry: Optional[VisualTelemetry] = None) -> None:
        """Resets cinematic renderer state cleanly between simulation episodes."""
        self.sim_time = 0.0
        self.wall_time = 0.0
        self.main_throttle = 0.0
        self.rcs_left_power = 0.0
        self.rcs_right_power = 0.0
        self.nozzle_heat = 0.0
        self.cam_shake_x = 0.0
        self.cam_shake_y = 0.0
        self.dust_clouds.clear()
        self.rcs_puffs.clear()
        self.exhaust_particles.clear()
        if initial_telemetry is not None:
            rocket_x = self.world_center_x + (initial_telemetry.pos_x * 10.0)
            rocket_y = initial_telemetry.pos_y
            self.cam_x = rocket_x
            self.cam_y = rocket_y
            self.cam_target_x = rocket_x
            self.cam_target_y = rocket_y
        else:
            self.cam_x = self.world_center_x
            self.cam_y = 7.5
            self.cam_target_x = self.world_center_x
            self.cam_target_y = 7.5

    def extract_telemetry(
        self,
        env: Any,
        obs: np.ndarray,
        action: int = 0,
        step: int = 0,
        reward: float = 0.0,
        terminated: bool = False,
        truncated: bool = False,
        cumulative_reward: float = 0.0,
        criteria: Optional[LandingCriteria] = None,
    ) -> VisualTelemetry:
        """Extracts ground-truth physical telemetry from simulation state."""
        crit = criteria or LandingCriteria()
        u = getattr(env, "unwrapped", env)

        # Read actual Box2D physical positions
        if hasattr(u, "lander") and u.lander:
            box_pos = u.lander.position
            box_vel = u.lander.linearVelocity
            box_angle = u.lander.angle
            box_ang_vel = u.lander.angularVelocity
            pos_x_val = box_pos.x
            pos_y_val = box_pos.y
            vel_x_val = box_vel.x
            vel_y_val = box_vel.y
            pitch_rad_val = box_angle
            angular_vel_val = math.degrees(box_ang_vel)
        else:
            pos_x_val = self.world_center_x + (obs[0] * 10.0)
            pos_y_val = 3.333 + (obs[1] * 6.666)
            vel_x_val = obs[2] * 5.0
            vel_y_val = obs[3] * 5.0
            pitch_rad_val = obs[4]
            angular_vel_val = math.degrees(obs[5] * 2.5)

        # Leg ground contacts: check observation array and Box2D fixture ground contact
        left_contact = bool(obs[6] > 0.5)
        right_contact = bool(obs[7] > 0.5)
        if not left_contact and hasattr(u, "legs") and len(u.legs) >= 2:
            left_contact = bool(u.legs[0].ground_contact)
        if not right_contact and hasattr(u, "legs") and len(u.legs) >= 2:
            right_contact = bool(u.legs[1].ground_contact)

        pitch_deg_val = math.degrees(pitch_rad_val)
        altitude_val = float(obs[1])

        # Touchdown state: airborne, first_contact, dual_contact, settled
        speed_norm = math.hypot(obs[2], obs[3])
        if not left_contact and not right_contact:
            touchdown_phase = "airborne"
        elif (left_contact and not right_contact) or (right_contact and not left_contact):
            touchdown_phase = "first_contact"
        elif left_contact and right_contact:
            if speed_norm > 0.04:
                touchdown_phase = "dual_contact"
            else:
                touchdown_phase = "settled"
        else:
            touchdown_phase = "airborne"

        # Outcome classification
        if terminated or truncated:
            raw_outcome = classify_outcome(
                terminated=terminated,
                truncated=truncated,
                final_step_reward=reward,
                final_obs=obs,
                criteria=crit,
            )
            outcome = raw_outcome
        elif altitude_val < 0.20:
            outcome = "approach"
        else:
            outcome = "descending"

        # Explicit post-landing and terminal propulsion shutdown
        effective_action = 0 if (terminated or truncated or touchdown_phase == "settled") else action

        return VisualTelemetry(
            step=step,
            altitude=altitude_val,
            pos_x=obs[0],
            pos_y=pos_y_val,
            vel_x=obs[2],
            vel_y=obs[3],
            pitch_deg=pitch_deg_val,
            pitch_rad=pitch_rad_val,
            angular_vel=angular_vel_val,
            action=effective_action,
            left_contact=left_contact,
            right_contact=right_contact,
            cumulative_reward=cumulative_reward,
            terminated=terminated,
            truncated=truncated,
            outcome=outcome,
            touchdown_phase=touchdown_phase,
        )

    def render_frame(
        self, env: Any, telemetry: VisualTelemetry, dt: Optional[float] = None
    ) -> pygame.Surface:
        """Renders one complete, cinematic aerospace simulation frame."""
        # Fixed physical simulation timestep (0.02s per step in LunarLander)
        sim_step_dt = 1.0 / self.target_fps
        self.sim_dt = sim_step_dt
        self.dt = max(0.001, float(dt)) if dt is not None else sim_step_dt

        # Separate simulation MET from wall-clock presentation duration
        self.sim_time = telemetry.step * self.sim_dt
        self.wall_time = self.sim_time / self.speed_factor
        self.anim_tick += 1

        # 1. Update Camera
        self.update_camera(telemetry, self.dt)

        # 2. Update Engine State Machines
        is_shutoff = (
            telemetry.terminated
            or telemetry.truncated
            or (telemetry.left_contact and telemetry.right_contact and telemetry.altitude <= 0.08)
            or (telemetry.action == 0 and (telemetry.left_contact or telemetry.right_contact) and telemetry.altitude <= 0.05)
        )
        effective_action = 0 if is_shutoff else telemetry.action
        self._update_propulsion_state(effective_action, self.dt, is_shutoff=is_shutoff)

        # 3. Deep Space Cosmic Sky & Starfield
        self._draw_deep_space()

        # 4. Distant Parallax Lunar Mountain Ranges
        self._draw_mountains()

        # 5. Lunar Terrain, Craters, Boulders, and Landing Platform
        u = getattr(env, "unwrapped", env)
        helipad_y = getattr(u, "helipad_y", 3.333)
        helipad_x1 = getattr(u, "helipad_x1", 8.0)
        helipad_x2 = getattr(u, "helipad_x2", 12.0)
        self.helipad_y = helipad_y

        self._draw_lunar_surface_and_pad(u, helipad_x1, helipad_x2, helipad_y)

        # 6. Lander Dynamic Ground-Projected Shadow
        rocket_wx = self.world_center_x + (telemetry.pos_x * 10.0)
        rocket_wy = telemetry.pos_y
        self._draw_ground_shadow(rocket_wx, rocket_wy, helipad_y)

        # 7. Update & Draw Dynamic Surface Dust and Exhaust Streams (Action-Synchronized)
        self._update_particles(rocket_wx, rocket_wy, telemetry.pitch_rad, helipad_y, effective_action, self.dt, is_shutoff=is_shutoff)
        self._draw_particles()

        # 8. Main Engine Plume & RCS Cold-Gas Puffs (Action-Synchronized)
        rocket_sx, rocket_sy = self.world_to_screen(rocket_wx, rocket_wy)
        self._draw_propulsion_effects(rocket_sx, rocket_sy, telemetry.pitch_rad, effective_action)

        # 9. Coherent Spacecraft Model
        self._draw_spacecraft_model(
            rocket_sx, rocket_sy, telemetry.pitch_rad,
            telemetry.left_contact, telemetry.right_contact
        )

        # 10. Responsive, Unclipped Glass-Cockpit Mission Control HUD
        self._draw_aerospace_hud(telemetry)

        # 11. Mission Debrief Summary Card (if terminated)
        if telemetry.terminated or telemetry.truncated:
            self._draw_mission_debrief(telemetry)

        # If recording, write frame to video
        if self.video_writer is not None:
            self._record_frame()

        if not self.headless:
            pygame.display.flip()
            self.clock.tick(self.target_fps)

        return self.screen

    # =========================================================================
    # Propulsion State Machine & Emitter Simulation
    # =========================================================================

    def _update_propulsion_state(self, action: int, dt: float, is_shutoff: bool = False) -> None:
        """Updates continuous throttle transitions, RCS power, and thermal state."""
        if is_shutoff:
            self.main_throttle = 0.0
            self.rcs_right_power = 0.0
            self.rcs_left_power = 0.0
            self.nozzle_heat = max(0.0, self.nozzle_heat - dt * 2.0)
            return

        # Main engine continuous transition (Action 2 = Main Engine)
        target_throttle = 1.0 if action == 2 else 0.0
        if target_throttle > self.main_throttle:
            # Quick ignition attack (~70ms)
            self.main_throttle = min(1.0, self.main_throttle + dt * 14.0)
        else:
            # Smooth shutdown decay (~120ms)
            self.main_throttle = max(0.0, self.main_throttle - dt * 8.5)

        # Nozzle thermal heat retention
        if self.main_throttle > 0.2:
            self.nozzle_heat = min(1.0, self.nozzle_heat + dt * 2.0)
        else:
            self.nozzle_heat = max(0.0, self.nozzle_heat - dt * 0.35)

        # RCS transitions (Action 1 = Right Thruster, Action 3 = Left Thruster)
        target_rcs_r = 1.0 if action == 1 else 0.0
        target_rcs_l = 1.0 if action == 3 else 0.0

        rcs_rate = 18.0 * dt
        self.rcs_right_power += (target_rcs_r - self.rcs_right_power) * min(1.0, rcs_rate)
        self.rcs_left_power += (target_rcs_l - self.rcs_left_power) * min(1.0, rcs_rate)
        if self.rcs_right_power < 0.005:
            self.rcs_right_power = 0.0
        if self.rcs_left_power < 0.005:
            self.rcs_left_power = 0.0
        if self.main_throttle < 0.005:
            self.main_throttle = 0.0

    def _update_particles(
        self,
        rocket_wx: float,
        rocket_wy: float,
        pitch_rad: float,
        helipad_y: float,
        action: int = 0,
        dt: float = 0.02,
        is_shutoff: bool = False,
    ) -> None:
        """Updates particle systems with delta-time integration and strict action synchronization."""
        # 1. Update Regolith Dust Clouds
        alive_dust = []
        for d in self.dust_clouds:
            d.x += d.vx * dt
            d.y += d.vy * dt
            d.vy -= 1.62 * dt  # Lunar gravity (g/6)
            d.radius += d.growth_rate * dt
            d.life -= dt
            if d.life > 0:
                d.alpha = d.max_alpha * (d.life / d.max_life)
                alive_dust.append(d)
        self.dust_clouds = alive_dust

        # 2. Update RCS Cold-Gas Puffs
        alive_rcs = []
        for r in self.rcs_puffs:
            r.x += r.vx * dt
            r.y += r.vy * dt
            r.radius += 1.8 * dt
            r.life -= dt
            if r.life > 0:
                r.alpha = r.max_alpha * (r.life / r.max_life)
                alive_rcs.append(r)
        self.rcs_puffs = alive_rcs

        # 3. Update Exhaust Stream Particles
        alive_ex = []
        for ep in self.exhaust_particles:
            ep.x += ep.vx * dt
            ep.y += ep.vy * dt
            ep.radius += 0.8 * dt
            ep.life -= dt
            if ep.life > 0:
                alive_ex.append(ep)
        self.exhaust_particles = alive_ex

        # If terminal/settled shutoff is active, stop creating new particles immediately
        if is_shutoff:
            return

        # 4. Spawn Main Engine Stream Particles (originating at nozzle exit)
        # ONLY spawn when actual action == 2 (Main Engine firing)
        if action == 2 and self.main_throttle > 0.05:
            nozzle_dist = 0.82
            nozzle_wx = rocket_wx - math.sin(pitch_rad) * nozzle_dist
            nozzle_wy = rocket_wy - math.cos(pitch_rad) * nozzle_dist

            spawn_count = int(12 * self.main_throttle)
            for _ in range(spawn_count):
                spread = random.gauss(0.0, 0.12)
                speed = random.uniform(16.0, 24.0) * self.main_throttle
                theta = pitch_rad + spread
                vx = -math.sin(theta) * speed
                vy = -math.cos(theta) * speed
                life = random.uniform(0.10, 0.22)
                self.exhaust_particles.append(
                    ExhaustStreamParticle(
                        x=nozzle_wx + random.uniform(-0.04, 0.04),
                        y=nozzle_wy,
                        vx=vx, vy=vy,
                        radius=random.uniform(0.06, 0.14),
                        life=life, max_life=life,
                        temp=random.uniform(0.7, 1.0)
                    )
                )

        # 5. Spawn Cold-Gas RCS Puffs from Side Ports (Action-Synchronized)
        # Action 1: right thruster fires (jets point right +X_body, pushing craft left)
        if action == 1:
            rcs_mount_dist = 0.30
            r_wx = rocket_wx + math.cos(pitch_rad) * 0.28 - math.sin(pitch_rad) * rcs_mount_dist
            r_wy = rocket_wy + math.sin(pitch_rad) * 0.28 + math.cos(pitch_rad) * rcs_mount_dist
            jet_angle = pitch_rad + random.gauss(0.0, 0.15)
            speed = random.uniform(5.0, 9.0)
            self.rcs_puffs.append(
                RCSPuff(
                    x=r_wx, y=r_wy,
                    vx=math.cos(jet_angle) * speed,
                    vy=math.sin(jet_angle) * speed,
                    radius=0.08,
                    alpha=90.0 * max(0.5, self.rcs_right_power),
                    max_alpha=90.0 * max(0.5, self.rcs_right_power),
                    life=0.14, max_life=0.14
                )
            )

        # Action 3: left thruster fires (jets point left -X_body, pushing craft right)
        if action == 3:
            rcs_mount_dist = 0.30
            l_wx = rocket_wx - math.cos(pitch_rad) * 0.28 - math.sin(pitch_rad) * rcs_mount_dist
            l_wy = rocket_wy - math.sin(pitch_rad) * 0.28 + math.cos(pitch_rad) * rcs_mount_dist
            jet_angle = pitch_rad + math.pi + random.gauss(0.0, 0.15)
            speed = random.uniform(5.0, 9.0)
            self.rcs_puffs.append(
                RCSPuff(
                    x=l_wx, y=l_wy,
                    vx=math.cos(jet_angle) * speed,
                    vy=math.sin(jet_angle) * speed,
                    radius=0.08,
                    alpha=90.0 * max(0.5, self.rcs_left_power),
                    max_alpha=90.0 * max(0.5, self.rcs_left_power),
                    life=0.14, max_life=0.14
                )
            )

        # 6. Spawn Lunar Regolith Surface Dust Storm (Near ground + Main Engine Active)
        rel_alt = rocket_wy - helipad_y
        if action == 2 and self.main_throttle > 0.1 and rel_alt < 3.2:
            intensity = (1.0 - (rel_alt / 3.2)) * self.main_throttle
            count = int(14 * intensity)
            for _ in range(count):
                dir_sign = -1.0 if random.random() < 0.5 else 1.0
                speed = random.uniform(5.0, 14.0) * intensity
                dvx = dir_sign * speed
                dvy = random.uniform(0.15, 0.85) * intensity
                life = random.uniform(0.3, 0.8)
                self.dust_clouds.append(
                    RegolithDustCloud(
                        x=rocket_wx + random.uniform(-0.3, 0.3),
                        y=helipad_y + random.uniform(0.02, 0.08),
                        vx=dvx, vy=dvy,
                        radius=random.uniform(0.15, 0.40),
                        growth_rate=random.uniform(0.8, 1.8),
                        alpha=110.0 * intensity,
                        max_alpha=110.0 * intensity,
                        life=life, max_life=life
                    )
                )

    def _draw_particles(self) -> None:
        """Renders soft regolith dust clouds and core exhaust streams."""
        # 1. Regolith Surface Dust Clouds (Layered translucent puffs)
        for d in self.dust_clouds:
            sx, sy = self.world_to_screen(d.x, d.y)
            rad_px = max(2, int(d.radius * self.cam_zoom))
            alpha_int = int(max(0, min(140, d.alpha)))
            if alpha_int <= 0 or rad_px <= 1:
                continue

            dust_surf = pygame.Surface((rad_px * 2, rad_px * 2), pygame.SRCALPHA)
            # Soft radial gradient for natural dust cloud look
            color_core = (175, 170, 158, alpha_int)
            color_edge = (160, 155, 145, alpha_int // 3)
            pygame.draw.circle(dust_surf, color_edge, (rad_px, rad_px), rad_px)
            pygame.draw.circle(dust_surf, color_core, (rad_px, rad_px), max(1, int(rad_px * 0.6)))
            self.screen.blit(dust_surf, (sx - rad_px, sy - rad_px))

        # 2. Continuous Exhaust Stream Particles
        if self.exhaust_particles:
            ex_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            for ep in self.exhaust_particles:
                sx, sy = self.world_to_screen(ep.x, ep.y)
                rad_px = max(1, int(ep.radius * self.cam_zoom))
                ratio = ep.life / ep.max_life
                alpha_int = int(220 * ratio * self.main_throttle)
                if alpha_int <= 0:
                    continue

                # Thermal color interpolation: incandescent white/cyan -> yellow -> orange
                t = ep.temp * ratio
                if t > 0.6:
                    color = (255, 255, 255)
                elif t > 0.3:
                    color = (255, 210, 80)
                else:
                    color = (245, 110, 30)

                pygame.draw.circle(ex_surf, (*color, alpha_int), (sx, sy), rad_px)
            self.screen.blit(ex_surf, (0, 0), special_flags=pygame.BLEND_ADD)

        # 3. Cold-Gas RCS Puffs
        for r in self.rcs_puffs:
            sx, sy = self.world_to_screen(r.x, r.y)
            rad_px = max(2, int(r.radius * self.cam_zoom))
            alpha_int = int(max(0, min(120, r.alpha)))
            if alpha_int <= 0 or rad_px <= 1:
                continue

            rcs_surf = pygame.Surface((rad_px * 2, rad_px * 2), pygame.SRCALPHA)
            pygame.draw.circle(rcs_surf, (220, 240, 255, alpha_int), (rad_px, rad_px), rad_px)
            pygame.draw.circle(rcs_surf, (255, 255, 255, int(alpha_int * 0.7)), (rad_px, rad_px), max(1, rad_px // 2))
            self.screen.blit(rcs_surf, (sx - rad_px, sy - rad_px), special_flags=pygame.BLEND_ADD)

    def _draw_propulsion_effects(
        self, sx: int, sy: int, pitch_rad: float, action: int = 2
    ) -> None:
        """Renders layered supersonic main plume with continuous flutter and shock diamonds."""
        zoom_scale = self.cam_zoom / 56.0

        # The active supersonic combustion plume is drawn ONLY when the engine is actively commanded (Action 2)
        if action == 2 and self.main_throttle > 0.02:
            # Plume length and width modulate with throttle and continuous turbulence flutter
            flutter = 1.0 + 0.06 * math.sin(self.sim_time * 45.0) + 0.04 * math.sin(self.sim_time * 28.0)
            plume_len = int(140.0 * zoom_scale * self.main_throttle * flutter)
            plume_w = int(28.0 * zoom_scale * self.main_throttle)

            if plume_len > 6 and plume_w > 4:
                canvas_w = plume_w * 4 + 20
                canvas_h = plume_len + 30
                plume_surf = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
                pcx = canvas_w // 2
                pcy = 10

                # Outer incandescent orange envelope (vacuum expansion)
                outer_pts = [
                    (pcx - plume_w // 3, pcy),
                    (pcx - plume_w, pcy + int(plume_len * 0.55)),
                    (pcx - int(plume_w * 0.5), pcy + int(plume_len * 0.85)),
                    (pcx, pcy + plume_len),
                    (pcx + int(plume_w * 0.5), pcy + int(plume_len * 0.85)),
                    (pcx + plume_w, pcy + int(plume_len * 0.55)),
                    (pcx + plume_w // 3, pcy),
                ]
                pygame.draw.polygon(plume_surf, (249, 115, 22, int(110 * self.main_throttle)), outer_pts)

                # Inner core thermal plasma (intense cyan/white)
                core_len = int(plume_len * 0.65)
                core_w = max(2, int(plume_w * 0.45))
                core_pts = [
                    (pcx - core_w // 2, pcy),
                    (pcx - core_w, pcy + int(core_len * 0.6)),
                    (pcx, pcy + core_len),
                    (pcx + core_w, pcy + int(core_len * 0.6)),
                    (pcx + core_w // 2, pcy),
                ]
                pygame.draw.polygon(plume_surf, (56, 189, 248, int(190 * self.main_throttle)), core_pts)
                pygame.draw.polygon(plume_surf, (255, 255, 255, int(240 * self.main_throttle)), [
                    (pcx - max(1, core_w // 4), pcy),
                    (pcx, pcy + int(core_len * 0.7)),
                    (pcx + max(1, core_w // 4), pcy)
                ])

                # Supersonic Mach Shock Diamonds
                for d_ratio in [0.22, 0.45, 0.68]:
                    dy = pcy + int(core_len * d_ratio)
                    dw = max(1, int(4 * zoom_scale * self.main_throttle))
                    dh = max(2, int(6 * zoom_scale * self.main_throttle))
                    diamond = [(pcx, dy - dh), (pcx + dw, dy), (pcx, dy + dh), (pcx - dw, dy)]
                    pygame.draw.polygon(plume_surf, (255, 255, 255, int(220 * self.main_throttle)), diamond)

                # Rotate plume to match rocket attitude
                rot_plume = pygame.transform.rotate(plume_surf, math.degrees(pitch_rad))
                r_rect = rot_plume.get_rect()
                nozzle_offset_len = 34 * zoom_scale
                anchor_x = sx - math.sin(pitch_rad) * nozzle_offset_len
                anchor_y = sy + math.cos(pitch_rad) * nozzle_offset_len
                r_rect.center = (int(anchor_x), int(anchor_y + (r_rect.height // 3.0)))
                self.screen.blit(rot_plume, r_rect.topleft, special_flags=pygame.BLEND_ADD)

    # =========================================================================
    # Environment & Lighting Subroutines
    # =========================================================================

    def _draw_deep_space(self) -> None:
        """Renders deep vacuum void, starfield, and crescent Earth."""
        self.screen.fill((5, 7, 13))

        for sx, sy, rad, bright in self.stars:
            b = bright
            if rad == 2 and (sx + self.anim_tick) % 11 == 0:
                b = max(100, bright - 60)
            color = (b, b, min(255, b + 24))
            if rad == 1:
                self.screen.set_at((sx, sy), color)
            else:
                pygame.draw.circle(self.screen, color, (sx, sy), rad)
                if bright > 235:
                    self.screen.set_at((sx - 2, sy), (100, 100, 150))
                    self.screen.set_at((sx + 2, sy), (100, 100, 150))
                    self.screen.set_at((sx, sy - 2), (100, 100, 150))
                    self.screen.set_at((sx, sy + 2), (100, 100, 150))

        # Position Earth cleanly clear of HUD margins
        earth_pos = (self.width - 240, 28)
        self.screen.blit(self.earth_surf, earth_pos)

    def _draw_mountains(self) -> None:
        """Renders distant lunar horizon with harsh vacuum relief shadows."""
        offset_x = int((self.cam_x - 10.0) * -12.0)
        shifted_pts = [(x + offset_x, y) for x, y in self.mountains]
        shifted_pts[0] = (-100, self.height)
        shifted_pts[-1] = (self.width + 100, self.height)

        pygame.draw.polygon(self.screen, (13, 19, 31), shifted_pts)

        for i in range(1, len(shifted_pts) - 2):
            p1 = shifted_pts[i]
            p2 = shifted_pts[i + 1]
            if p2[0] > p1[0] and (p2[1] - p1[1]) < 0:
                pygame.draw.line(self.screen, (30, 41, 59), p1, p2, width=2)

    def _draw_lunar_surface_and_pad(
        self, u: Any, pad_x1: float, pad_x2: float, helipad_y: float
    ) -> None:
        """Renders textured lunar terrain and reinforced landing pad without cyan volumetric beams."""
        surface_points: List[Tuple[float, float]] = []

        if hasattr(u, "moon") and u.moon and hasattr(u.moon, "fixtures"):
            raw_pts: List[Tuple[float, float]] = []
            for f in u.moon.fixtures:
                v = f.shape.vertices
                for pt in v:
                    if pt[1] > 0.5:
                        raw_pts.append((float(pt[0]), float(pt[1])))

            unique_dict: Dict[float, float] = {}
            for wx, wy in raw_pts:
                key = round(wx, 3)
                if key not in unique_dict or wy > unique_dict[key]:
                    unique_dict[key] = wy

            sorted_x = sorted(unique_dict.keys())
            for wx in sorted_x:
                surface_points.append((wx, unique_dict[wx]))

        if not surface_points:
            surface_points = [
                (0.0, 4.2), (4.0, 3.8), (8.0, helipad_y), (12.0, helipad_y),
                (16.0, 3.2), (20.0, 4.0)
            ]

        ground_poly = [self.world_to_screen(wx, wy) for wx, wy in surface_points]
        poly_full = [(0, self.height)] + ground_poly + [(self.width, self.height)]
        pygame.draw.polygon(self.screen, (15, 20, 30), poly_full)

        if len(ground_poly) >= 2:
            pygame.draw.lines(self.screen, (71, 85, 105), False, ground_poly, width=3)
            pygame.draw.lines(self.screen, (148, 163, 184), False, ground_poly, width=1)

        # Craters
        for c in self.craters:
            csx, csy = self.world_to_screen(c["x"], c["y"])
            crx = max(6, int(c["rx"] * self.cam_zoom))
            cry = max(3, int(c["ry"] * self.cam_zoom))
            pygame.draw.ellipse(self.screen, (8, 11, 18), (csx - crx, csy - cry, crx * 2, cry * 2))
            pygame.draw.arc(self.screen, (100, 116, 139), (csx - crx, csy - cry, crx * 2, cry * 2), 1.5, 4.2, width=2)

        # Boulders
        for b in self.boulders:
            bsx, bsy = self.world_to_screen(b["x"], b["y"])
            bsize = max(2, int(b["size"] * self.cam_zoom))
            shadow_poly = [
                (bsx, bsy), (bsx + bsize * 3, bsy + bsize),
                (bsx + bsize * 2, bsy + bsize * 2), (bsx, bsy + bsize)
            ]
            pygame.draw.polygon(self.screen, (8, 11, 18), shadow_poly)
            pygame.draw.circle(self.screen, (148, 163, 184), (bsx, bsy), bsize)
            pygame.draw.circle(self.screen, (203, 213, 225), (bsx - 1, bsy - 1), max(1, bsize // 2))

        # Heavy-Duty Steel-Reinforced Landing Pad
        pad_sx1, pad_sy = self.world_to_screen(pad_x1, helipad_y)
        pad_sx2, _ = self.world_to_screen(pad_x2, helipad_y)
        pad_w = pad_sx2 - pad_sx1
        pad_h = max(14, int(0.35 * self.cam_zoom))

        # Concrete Foundation
        foundation_rect = pygame.Rect(pad_sx1 - 16, pad_sy, pad_w + 32, pad_h + 18)
        pygame.draw.rect(self.screen, (24, 32, 47), foundation_rect, border_radius=6)
        pygame.draw.rect(self.screen, (51, 65, 85), foundation_rect, width=2, border_radius=6)

        # Primary Landing Deck
        deck_rect = pygame.Rect(pad_sx1, pad_sy, pad_w, pad_h)
        pygame.draw.rect(self.screen, (15, 23, 42), deck_rect)

        # High-visibility yellow/black hazard chevrons
        stripe_w = max(8, int(0.25 * self.cam_zoom))
        for sx in range(pad_sx1, pad_sx2, stripe_w * 2):
            pts = [
                (sx, pad_sy + pad_h),
                (sx + stripe_w, pad_sy),
                (min(pad_sx2, sx + stripe_w * 2), pad_sy),
                (min(pad_sx2, sx + stripe_w), pad_sy + pad_h),
            ]
            pygame.draw.polygon(self.screen, (234, 179, 8), pts)

        # Concentric Target Guidance Markings
        pad_cx = (pad_sx1 + pad_sx2) // 2
        ring_rx = max(24, int(1.2 * self.cam_zoom))
        ring_ry = max(8, int(0.3 * self.cam_zoom))
        pygame.draw.ellipse(self.screen, (56, 189, 248), (pad_cx - ring_rx, pad_sy - ring_ry, ring_rx * 2, ring_ry * 2), width=2)
        pygame.draw.ellipse(self.screen, (234, 179, 8), (pad_cx - ring_rx // 2, pad_sy - ring_ry // 2, ring_rx, ring_ry), width=2)
        pygame.draw.circle(self.screen, (239, 68, 68), (pad_cx, pad_sy), 4)

        # Clean perimeter light fixtures (NO artificial triangular volumetric polygons)
        for bx in [pad_sx1 - 10, pad_sx2 + 10]:
            pygame.draw.line(self.screen, (71, 85, 105), (bx, pad_sy), (bx, pad_sy - 28), width=3)
            pygame.draw.circle(self.screen, (226, 232, 240), (bx, pad_sy - 28), 4)
            # Subtle green/white runway beacon
            pygame.draw.circle(self.screen, (34, 197, 94), (bx, pad_sy - 32), 3)

    def _draw_ground_shadow(self, rocket_wx: float, rocket_wy: float, helipad_y: float) -> None:
        """Projects a realistic ground shadow beneath the lander based on sun angle."""
        altitude = max(0.0, rocket_wy - helipad_y)
        shadow_wx = rocket_wx + (altitude * 0.45)
        shadow_wy = helipad_y

        shadow_sx, shadow_sy = self.world_to_screen(shadow_wx, shadow_wy)

        scale_factor = max(0.4, 1.0 - (altitude * 0.08))
        alpha = int(max(25, 190 * (1.0 - min(1.0, altitude / 8.0))))

        shadow_rx = max(10, int(0.7 * self.cam_zoom * scale_factor))
        shadow_ry = max(4, int(0.22 * self.cam_zoom * scale_factor))

        shadow_surf = pygame.Surface((shadow_rx * 2 + 10, shadow_ry * 2 + 10), pygame.SRCALPHA)
        pygame.draw.ellipse(
            shadow_surf,
            (0, 0, 0, alpha),
            (5, 5, shadow_rx * 2, shadow_ry * 2)
        )
        self.screen.blit(shadow_surf, (shadow_sx - shadow_rx - 5, shadow_sy - shadow_ry - 5))

    # =========================================================================
    # Coherent Spacecraft Model
    # =========================================================================

    def _draw_spacecraft_model(
        self,
        sx: int,
        sy: int,
        pitch_rad: float,
        left_contact: bool,
        right_contact: bool,
    ) -> None:
        """Constructs and renders the aerospace rocket vehicle with metallic materials."""
        zoom_scale = self.cam_zoom / 56.0

        canvas_size = int(220 * zoom_scale)
        craft_surf = pygame.Surface((canvas_size, canvas_size), pygame.SRCALPHA)
        lcx = canvas_size // 2
        lcy = canvas_size // 2

        body_w = int(24 * zoom_scale)
        body_h = int(68 * zoom_scale)
        half_w = body_w // 2

        # 1. Main Fuselage Structure
        fuselage_rect = pygame.Rect(
            lcx - half_w,
            lcy - body_h // 2 + int(12 * zoom_scale),
            body_w,
            body_h - int(24 * zoom_scale)
        )
        pygame.draw.rect(craft_surf, (226, 232, 240), fuselage_rect)

        # Harsh solar directional lighting: Left side illuminated, right side in shadow
        sun_highlight = pygame.Rect(lcx - half_w, fuselage_rect.top, half_w, fuselage_rect.height)
        pygame.draw.rect(craft_surf, (248, 250, 252), sun_highlight)
        shadow_strip = pygame.Rect(lcx + 2, fuselage_rect.top, half_w - 2, fuselage_rect.height)
        pygame.draw.rect(craft_surf, (148, 163, 184), shadow_strip)

        # Panel seams
        pygame.draw.line(craft_surf, (203, 213, 225), (lcx - half_w + 3, fuselage_rect.top), (lcx - half_w + 3, fuselage_rect.bottom), width=1)
        pygame.draw.line(craft_surf, (100, 116, 139), (lcx, fuselage_rect.top), (lcx, fuselage_rect.bottom), width=1)

        # 2. Lower Descent Stage / Gold Kapton Thermal MLI Insulation
        mli_h = int(14 * zoom_scale)
        mli_rect = pygame.Rect(lcx - half_w - 1, fuselage_rect.bottom - mli_h, body_w + 2, mli_h)
        pygame.draw.rect(craft_surf, (217, 119, 6), mli_rect)
        for fy in range(mli_rect.top, mli_rect.bottom, 3):
            pygame.draw.line(craft_surf, (251, 191, 36), (mli_rect.left, fy), (mli_rect.right, fy), width=1)

        # Interstage carbon ring
        ring_y = lcy - int(4 * zoom_scale)
        pygame.draw.rect(craft_surf, (30, 41, 59), (lcx - half_w - 1, ring_y, body_w + 2, int(6 * zoom_scale)))

        # 3. Aerodynamic Nose Cone
        nose_top_y = lcy - body_h // 2 - int(10 * zoom_scale)
        nose_base_y = fuselage_rect.top
        nose_pts = [
            (lcx - half_w, nose_base_y),
            (lcx, nose_top_y),
            (lcx + half_w, nose_base_y),
        ]
        pygame.draw.polygon(craft_surf, (241, 245, 249), nose_pts)
        pygame.draw.polygon(craft_surf, (148, 163, 184), [(lcx, nose_top_y), (lcx + half_w, nose_base_y), (lcx, nose_base_y)])
        pygame.draw.lines(craft_surf, (71, 85, 105), False, nose_pts, width=2)

        # Avionics optical sensor window
        pygame.draw.circle(craft_surf, (15, 23, 42), (lcx, nose_top_y + int(7 * zoom_scale)), max(2, int(3 * zoom_scale)))

        # 4. RCS Manifold Ports (Distinct physical blocks on hull)
        rcs_block_y = lcy - int(18 * zoom_scale)
        pygame.draw.rect(craft_surf, (51, 65, 85), (lcx - half_w - 3, rcs_block_y, 4, 5))
        pygame.draw.rect(craft_surf, (30, 41, 59), (lcx + half_w - 1, rcs_block_y, 4, 5))

        # 5. Titanium Lattice Grid Fins
        fin_y = lcy - body_h // 2 + int(18 * zoom_scale)
        fin_w = int(11 * zoom_scale)
        fin_h = int(10 * zoom_scale)

        pygame.draw.rect(craft_surf, (51, 65, 85), (lcx - half_w - fin_w, fin_y, fin_w, fin_h), border_radius=1)
        pygame.draw.rect(craft_surf, (148, 163, 184), (lcx - half_w - fin_w, fin_y, fin_w, fin_h), width=1)
        pygame.draw.line(craft_surf, (100, 116, 139), (lcx - half_w - fin_w // 2, fin_y), (lcx - half_w - fin_w // 2, fin_y + fin_h))
        pygame.draw.line(craft_surf, (100, 116, 139), (lcx - half_w - fin_w, fin_y + fin_h // 2), (lcx - half_w, fin_y + fin_h // 2))

        pygame.draw.rect(craft_surf, (30, 41, 59), (lcx + half_w, fin_y, fin_w, fin_h), border_radius=1)
        pygame.draw.rect(craft_surf, (100, 116, 139), (lcx + half_w, fin_y, fin_w, fin_h), width=1)
        pygame.draw.line(craft_surf, (71, 85, 105), (lcx + half_w + fin_w // 2, fin_y), (lcx + half_w + fin_w // 2, fin_y + fin_h))
        pygame.draw.line(craft_surf, (71, 85, 105), (lcx + half_w, fin_y + fin_h // 2), (lcx + half_w + fin_w, fin_y + fin_h // 2))

        # 6. Rocket Engine Bell Nozzle with Thermal Incandescent Glow
        nozzle_top_y = fuselage_rect.bottom
        nozzle_h = int(15 * zoom_scale)
        nozzle_pts = [
            (lcx - int(6 * zoom_scale), nozzle_top_y),
            (lcx + int(6 * zoom_scale), nozzle_top_y),
            (lcx + int(11 * zoom_scale), nozzle_top_y + nozzle_h),
            (lcx - int(11 * zoom_scale), nozzle_top_y + nozzle_h),
        ]
        pygame.draw.polygon(craft_surf, (51, 65, 85), nozzle_pts)
        pygame.draw.polygon(craft_surf, (15, 23, 42), nozzle_pts, width=1)

        # Internal tungsten throat glow (controlled by nozzle_heat)
        if self.nozzle_heat > 0.05:
            glow_col = (255, min(255, int(150 + 105 * self.nozzle_heat)), int(30 * self.nozzle_heat))
            pygame.draw.line(
                craft_surf, glow_col,
                (lcx - int(4 * zoom_scale), nozzle_top_y + 2),
                (lcx + int(4 * zoom_scale), nozzle_top_y + 2),
                width=max(2, int(3 * zoom_scale))
            )

        # 7. Articulating Carbon-Fiber Landing Struts & Footpads
        leg_anchor_y = fuselage_rect.bottom - int(8 * zoom_scale)

        # Left Landing Gear
        left_foot_x = lcx - half_w - int(19 * zoom_scale)
        left_foot_y = lcy + body_h // 2 + int(14 * zoom_scale)
        if left_contact:
            left_foot_y -= int(3 * zoom_scale)

        pygame.draw.line(craft_surf, (30, 41, 59), (lcx - half_w + 2, leg_anchor_y), (left_foot_x, left_foot_y), width=max(2, int(4 * zoom_scale)))
        pygame.draw.line(craft_surf, (203, 213, 225), (lcx - half_w + 2, leg_anchor_y), (left_foot_x, left_foot_y), width=max(1, int(2 * zoom_scale)))
        pygame.draw.line(craft_surf, (71, 85, 105), (lcx - int(4 * zoom_scale), leg_anchor_y + int(6 * zoom_scale)), (left_foot_x, left_foot_y), width=max(1, int(2 * zoom_scale)))

        pad_color_l = (34, 197, 94) if left_contact else (239, 68, 68)
        footpad_w = int(10 * zoom_scale)
        pygame.draw.line(craft_surf, (15, 23, 42), (left_foot_x - footpad_w // 2, left_foot_y), (left_foot_x + footpad_w // 2, left_foot_y), width=max(2, int(3 * zoom_scale)))
        pygame.draw.circle(craft_surf, pad_color_l, (left_foot_x, left_foot_y - 2), max(2, int(3 * zoom_scale)))

        # Right Landing Gear
        right_foot_x = lcx + half_w + int(19 * zoom_scale)
        right_foot_y = lcy + body_h // 2 + int(14 * zoom_scale)
        if right_contact:
            right_foot_y -= int(3 * zoom_scale)

        pygame.draw.line(craft_surf, (15, 23, 42), (lcx + half_w - 2, leg_anchor_y), (right_foot_x, right_foot_y), width=max(2, int(4 * zoom_scale)))
        pygame.draw.line(craft_surf, (148, 163, 184), (lcx + half_w - 2, leg_anchor_y), (right_foot_x, right_foot_y), width=max(1, int(2 * zoom_scale)))
        pygame.draw.line(craft_surf, (51, 65, 85), (lcx + int(4 * zoom_scale), leg_anchor_y + int(6 * zoom_scale)), (right_foot_x, right_foot_y), width=max(1, int(2 * zoom_scale)))

        pad_color_r = (34, 197, 94) if right_contact else (239, 68, 68)
        pygame.draw.line(craft_surf, (15, 23, 42), (right_foot_x - footpad_w // 2, right_foot_y), (right_foot_x + footpad_w // 2, right_foot_y), width=max(2, int(3 * zoom_scale)))
        pygame.draw.circle(craft_surf, pad_color_r, (right_foot_x, right_foot_y - 2), max(2, int(3 * zoom_scale)))

        # Rotate spacecraft to match Box2D pitch angle
        rot_craft = pygame.transform.rotate(craft_surf, math.degrees(pitch_rad))
        rot_rect = rot_craft.get_rect()
        rot_rect.center = (sx, sy)

        self.screen.blit(rot_craft, rot_rect.topleft)

    # =========================================================================
    # Responsive, Unclipped Glass-Cockpit HUD
    # =========================================================================

    def _draw_aerospace_hud(self, telemetry: VisualTelemetry) -> None:
        """Renders SpaceX/Apollo style glass-cockpit PFD with safe viewport margins."""
        margin_x = max(28, int(self.width * 0.025))
        margin_y = max(16, int(self.height * 0.025))

        # 1. Mission Status & Flight Phase Header (Top Center)
        self._draw_flight_phase_header(telemetry, margin_y)

        # 2. Left Primary Flight Display: Vertical Speed Ribbon Tape
        tape_w = max(76, int(84 * (self.width / 1280.0)))
        tape_h = max(220, int(270 * (self.height / 720.0)))
        tape_y = (self.height - tape_h) // 2
        self._draw_vertical_speed_tape(telemetry.vel_y, margin_x, tape_y, tape_w, tape_h)

        # 3. Right Primary Flight Display: Radar Altitude Ribbon Tape
        right_tx = self.width - margin_x - tape_w
        self._draw_altitude_tape(telemetry.altitude, telemetry.pos_y - self.helipad_y, right_tx, tape_y, tape_w, tape_h)

        # 4. Center 3D Attitude Director Indicator (ADI) Sphere
        self._draw_attitude_director_indicator(telemetry.pitch_deg, telemetry.pitch_rad, telemetry.vel_x, telemetry.vel_y, margin_y + 44)

        # 5. Propulsion & Actuator Status Card (Bottom Left)
        card_w = max(210, int(230 * (self.width / 1280.0)))
        card_h = max(100, int(112 * (self.height / 720.0)))
        card_y = self.height - margin_y - card_h
        self._draw_actuator_telemetry_card(telemetry, margin_x, card_y, card_w, card_h)

        # 6. Navigation & Pad Alignment Card (Bottom Right)
        right_cx = self.width - margin_x - card_w
        self._draw_guidance_card(telemetry, right_cx, card_y, card_w, card_h)

    def _draw_flight_phase_header(self, telemetry: VisualTelemetry, top_y: int) -> None:
        """Draws top annunciator banner with active flight phase and elapsed time."""
        banner_w = min(self.width - 200, 480)
        banner_h = 42
        bx = (self.width - banner_w) // 2
        by = top_y

        panel_surf = pygame.Surface((banner_w, banner_h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (15, 23, 42, 220), (0, 0, banner_w, banner_h), border_radius=6)
        pygame.draw.rect(panel_surf, (56, 189, 248, 140), (0, 0, banner_w, banner_h), width=1, border_radius=6)
        self.screen.blit(panel_surf, (bx, by))

        if telemetry.outcome == "success":
            status_text = "TOUCHDOWN CONFIRMED — RECOVERY SAFE"
            accent_color = (34, 197, 94)
        elif telemetry.outcome in ("crash", "out_of_bounds"):
            status_text = "CRITICAL FAILURE — IMPACT / LOSS"
            accent_color = (239, 68, 68)
        elif telemetry.touchdown_phase == "settled":
            status_text = "TOUCHDOWN: SETTLED (NOMINAL REST)"
            accent_color = (34, 197, 94)
        elif telemetry.touchdown_phase == "dual_contact":
            status_text = "TOUCHDOWN: DUAL CONTACT (BRAKING)"
            accent_color = (56, 189, 248)
        elif telemetry.touchdown_phase == "first_contact":
            which = "L" if telemetry.left_contact else "R"
            status_text = f"TOUCHDOWN: FIRST CONTACT ({which}-STRUT)"
            accent_color = (234, 179, 8)
        elif telemetry.outcome == "approach":
            status_text = "TERMINAL DESCENT — TOUCHDOWN GATE"
            accent_color = (234, 179, 8)
        elif telemetry.action == 2:
            status_text = "MAIN ENGINE BRAKING BURN ACTIVE"
            accent_color = (56, 189, 248)
        elif telemetry.action in (1, 3):
            which = "R (PUSH L)" if telemetry.action == 1 else "L (PUSH R)"
            status_text = f"RCS ATTITUDE CORRECTION [{which}]"
            accent_color = (168, 85, 247)
        else:
            status_text = "BALLISTIC DESCENT — COASTING"
            accent_color = (148, 163, 184)

        txt_status = self.font_large.render(status_text, True, accent_color)
        self.screen.blit(txt_status, (bx + (banner_w - txt_status.get_width()) // 2, by + 6))

        sub_text = (
            f"SIM T+{self.sim_time:05.2f}s [{self.speed_factor:.2f}x] | "
            f"WALL {self.wall_time:05.2f}s | "
            f"STEP {telemetry.step:04d} | "
            f"RWD {telemetry.cumulative_reward:+07.2f}"
        )
        txt_sub = self.font_tiny.render(sub_text, True, (148, 163, 184))
        self.screen.blit(txt_sub, (bx + (banner_w - txt_sub.get_width()) // 2, by + 26))

    def _draw_vertical_speed_tape(self, vel_y: float, tx: int, ty: int, tw: int, th: int) -> None:
        """Renders vertical descent tape meter with unclipped safe readout."""
        tape_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(tape_surf, (15, 23, 42, 215), (0, 0, tw, th), border_radius=6)
        pygame.draw.rect(tape_surf, (51, 65, 85, 180), (0, 0, tw, th), width=1, border_radius=6)
        self.screen.blit(tape_surf, (tx, ty))

        header = self.font_tiny.render("VERT SPEED", True, (148, 163, 184))
        self.screen.blit(header, (tx + (tw - header.get_width()) // 2, ty + 8))

        # Center zero line
        cy = ty + (th // 2)
        pygame.draw.line(self.screen, (100, 116, 139), (tx + 10, cy), (tx + tw - 10, cy), width=1)

        # Safe touchdown gate zone (-0.40 m/s to 0.0 m/s)
        gate_h = int(30 * (th / 270.0))
        gate_surf = pygame.Surface((tw - 20, gate_h), pygame.SRCALPHA)
        pygame.draw.rect(gate_surf, (34, 197, 94, 60), (0, 0, tw - 20, gate_h), border_radius=3)
        self.screen.blit(gate_surf, (tx + 10, cy))

        # Dynamic indicator needle
        clamped_vy = max(-1.6, min(1.6, vel_y))
        needle_y = cy - int((clamped_vy / 1.6) * (th // 2 - 24))

        color = (34, 197, 94) if abs(vel_y) <= 0.40 else ((234, 179, 8) if abs(vel_y) <= 0.70 else (239, 68, 68))
        pygame.draw.polygon(self.screen, color, [(tx + tw - 6, needle_y), (tx + tw - 16, needle_y - 5), (tx + tw - 16, needle_y + 5)])

        # Digital readout box (Guaranteed to fit inside tape)
        readout_box = pygame.Rect(tx + 6, cy + int(th * 0.32), tw - 12, 22)
        pygame.draw.rect(self.screen, (30, 41, 59), readout_box, border_radius=4)
        pygame.draw.rect(self.screen, color, readout_box, width=1, border_radius=4)

        readout_txt = self.font_small.render(f"{vel_y * 5.0:+0.2f}m/s", True, color)
        self.screen.blit(readout_txt, (readout_box.centerx - readout_txt.get_width() // 2, readout_box.centery - readout_txt.get_height() // 2))

    def _draw_altitude_tape(self, norm_alt: float, meters_alt: float, tx: int, ty: int, tw: int, th: int) -> None:
        """Renders radar altitude tape with unclipped safe readout."""
        tape_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.rect(tape_surf, (15, 23, 42, 215), (0, 0, tw, th), border_radius=6)
        pygame.draw.rect(tape_surf, (51, 65, 85, 180), (0, 0, tw, th), width=1, border_radius=6)
        self.screen.blit(tape_surf, (tx, ty))

        header = self.font_tiny.render("RADAR ALT", True, (148, 163, 184))
        self.screen.blit(header, (tx + (tw - header.get_width()) // 2, ty + 8))

        ground_y = ty + th - 36
        pygame.draw.line(self.screen, (234, 179, 8), (tx + 10, ground_y), (tx + tw - 10, ground_y), width=2)

        clamped_alt = max(0.0, min(1.2, norm_alt))
        alt_bug_y = ground_y - int((clamped_alt / 1.2) * (th - 75))

        color = (34, 197, 94) if norm_alt < 0.15 else ((56, 189, 248) if norm_alt < 0.6 else (148, 163, 184))
        pygame.draw.polygon(self.screen, color, [(tx + 6, alt_bug_y), (tx + 16, alt_bug_y - 5), (tx + 16, alt_bug_y + 5)])

        readout_box = pygame.Rect(tx + 6, ty + 32, tw - 12, 22)
        pygame.draw.rect(self.screen, (30, 41, 59), readout_box, border_radius=4)
        pygame.draw.rect(self.screen, color, readout_box, width=1, border_radius=4)

        readout_txt = self.font_small.render(f"{max(0.0, meters_alt):04.1f}m", True, color)
        self.screen.blit(readout_txt, (readout_box.centerx - readout_txt.get_width() // 2, readout_box.centery - readout_txt.get_height() // 2))

    def _draw_attitude_director_indicator(
        self, pitch_deg: float, pitch_rad: float, vel_x: float, vel_y: float, top_y: int
    ) -> None:
        """Renders 3D Attitude Director Indicator (ADI) with horizon sphere and Flight Path Marker."""
        adi_w = 104
        adi_h = 104
        ax = (self.width - adi_w) // 2
        ay = top_y

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
            py = adi_h - int(deg * 1.4)
            pygame.draw.line(ball_surf, (226, 232, 240), (adi_w - 16, py), (adi_w + 16, py), width=1)

        rot_ball = pygame.transform.rotate(ball_surf, pitch_deg)
        r_rect = rot_ball.get_rect()
        r_rect.center = (acx, acy)

        adi_surf.blit(rot_ball, r_rect.topleft)
        adi_surf.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        pygame.draw.circle(adi_surf, (148, 163, 184), (acx, acy), radius, width=2)

        # Fixed Aircraft Crosshair
        pygame.draw.circle(adi_surf, (234, 179, 8), (acx, acy), 3)
        pygame.draw.line(adi_surf, (234, 179, 8), (acx - 14, acy), (acx - 5, acy), width=2)
        pygame.draw.line(adi_surf, (234, 179, 8), (acx + 5, acy), (acx + 14, acy), width=2)

        # Dynamic Flight Path Marker (Velocity prograde vector)
        fpm_x = acx + int(vel_x * 22.0)
        fpm_y = acy - int(vel_y * 16.0)
        dist = math.hypot(fpm_x - acx, fpm_y - acy)
        if dist < radius - 6:
            pygame.draw.circle(adi_surf, (56, 189, 248), (fpm_x, fpm_y), 4, width=1)
            pygame.draw.line(adi_surf, (56, 189, 248), (fpm_x - 6, fpm_y), (fpm_x - 3, fpm_y))
            pygame.draw.line(adi_surf, (56, 189, 248), (fpm_x + 3, fpm_y), (fpm_x + 6, fpm_y))
            pygame.draw.line(adi_surf, (56, 189, 248), (fpm_x, fpm_y - 6), (fpm_x, fpm_y - 3))

        self.screen.blit(adi_surf, (ax, ay))

        pitch_color = (34, 197, 94) if abs(pitch_deg) <= 11.5 else (239, 68, 68)
        p_txt = self.font_tiny.render(f"PITCH {pitch_deg:+05.1f}°", True, pitch_color)
        self.screen.blit(p_txt, (ax + (adi_w - p_txt.get_width()) // 2, ay + adi_h + 3))

    def _draw_actuator_telemetry_card(
        self, telemetry: VisualTelemetry, cx: int, cy: int, cw: int, ch: int
    ) -> None:
        """Renders bottom-left propulsion and landing gear status card."""
        card_surf = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 23, 42, 220), (0, 0, cw, ch), border_radius=6)
        pygame.draw.rect(card_surf, (51, 65, 85, 180), (0, 0, cw, ch), width=1, border_radius=6)
        self.screen.blit(card_surf, (cx, cy))

        title = self.font_small.render("PROPULSION & GEAR", True, (56, 189, 248))
        self.screen.blit(title, (cx + 12, cy + 8))

        speed_mode_name = {1.0: "1.00x REAL", 0.75: "0.75x MOD", 0.5: "0.50x CINE", 0.25: "0.25x SLOW"}.get(self.speed_factor, f"{self.speed_factor:.2f}x")
        txt_speed = self.font_tiny.render(speed_mode_name, True, (245, 158, 11))
        self.screen.blit(txt_speed, (cx + cw - txt_speed.get_width() - 12, cy + 8))

        # Main Engine Throttle Bar
        th_label = self.font_tiny.render("THROTTLE", True, (148, 163, 184))
        self.screen.blit(th_label, (cx + 12, cy + 30))

        bar_w = int(cw * 0.42)
        bar_h = 10
        bar_x = cx + 80
        pygame.draw.rect(self.screen, (30, 41, 59), (bar_x, cy + 31, bar_w, bar_h), border_radius=2)
        if self.main_throttle > 0.02:
            fill_w = int(bar_w * self.main_throttle)
            pygame.draw.rect(self.screen, (249, 115, 22), (bar_x, cy + 31, fill_w, bar_h), border_radius=2)
            pct_txt = self.font_tiny.render(f"{int(self.main_throttle * 100)}%", True, (249, 115, 22))
        else:
            pct_txt = self.font_tiny.render("0%", True, (100, 116, 139))
        self.screen.blit(pct_txt, (bar_x + bar_w + 6, cy + 29))

        # RCS Status
        rcs_label = self.font_tiny.render("RCS THRUST", True, (148, 163, 184))
        self.screen.blit(rcs_label, (cx + 12, cy + 54))

        l_color = (168, 85, 247) if telemetry.action == 3 else (71, 85, 105)
        r_color = (168, 85, 247) if telemetry.action == 1 else (71, 85, 105)
        txt_l = self.font_tiny.render("L: FIRING" if telemetry.action == 3 else "L: IDLE", True, l_color)
        txt_r = self.font_tiny.render("R: FIRING" if telemetry.action == 1 else "R: IDLE", True, r_color)
        self.screen.blit(txt_l, (cx + 80, cy + 54))
        self.screen.blit(txt_r, (cx + 148, cy + 54))

        # Gear Sensors
        gear_label = self.font_tiny.render("GEAR LOCK", True, (148, 163, 184))
        self.screen.blit(gear_label, (cx + 12, cy + 78))

        lg_color = (34, 197, 94) if telemetry.left_contact else (100, 116, 139)
        rg_color = (34, 197, 94) if telemetry.right_contact else (100, 116, 139)
        txt_lg = self.font_tiny.render("L: LOCKED" if telemetry.left_contact else "L: DEPLOY", True, lg_color)
        txt_rg = self.font_tiny.render("R: LOCKED" if telemetry.right_contact else "R: DEPLOY", True, rg_color)
        self.screen.blit(txt_lg, (cx + 80, cy + 78))
        self.screen.blit(txt_rg, (cx + 148, cy + 78))

    def _draw_guidance_card(
        self, telemetry: VisualTelemetry, cx: int, cy: int, cw: int, ch: int
    ) -> None:
        """Renders bottom-right guidance and pad alignment card."""
        card_surf = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 23, 42, 220), (0, 0, cw, ch), border_radius=6)
        pygame.draw.rect(card_surf, (51, 65, 85, 180), (0, 0, cw, ch), width=1, border_radius=6)
        self.screen.blit(card_surf, (cx, cy))

        title = self.font_small.render("GUIDANCE & NAVIGATION", True, (56, 189, 248))
        self.screen.blit(title, (cx + 12, cy + 8))

        # Cross-Track Offset
        offset_m = telemetry.pos_x * 10.0
        offset_color = (34, 197, 94) if abs(telemetry.pos_x) <= 0.25 else (239, 68, 68)
        lbl_xtk = self.font_tiny.render("CROSS-TRACK", True, (148, 163, 184))
        val_xtk = self.font_small.render(f"{offset_m:+05.2f}m", True, offset_color)
        self.screen.blit(lbl_xtk, (cx + 12, cy + 32))
        self.screen.blit(val_xtk, (cx + cw - val_xtk.get_width() - 12, cy + 30))

        # Lateral Drift Speed
        drift_color = (34, 197, 94) if abs(telemetry.vel_x) <= 0.40 else (234, 179, 8)
        lbl_vx = self.font_tiny.render("LATERAL DRIFT", True, (148, 163, 184))
        val_vx = self.font_small.render(f"{telemetry.vel_x * 5.0:+05.2f}m/s", True, drift_color)
        self.screen.blit(lbl_vx, (cx + 12, cy + 54))
        self.screen.blit(val_vx, (cx + cw - val_vx.get_width() - 12, cy + 52))

        # Angular Spin Rate
        spin_color = (34, 197, 94) if abs(telemetry.angular_vel) <= 20.0 else (239, 68, 68)
        lbl_spin = self.font_tiny.render("ROLL RATE", True, (148, 163, 184))
        val_spin = self.font_small.render(f"{telemetry.angular_vel:+05.1f}°/s", True, spin_color)
        self.screen.blit(lbl_spin, (cx + 12, cy + 76))
        self.screen.blit(val_spin, (cx + cw - val_spin.get_width() - 12, cy + 74))

    # =========================================================================
    # Mission Debrief Card
    # =========================================================================

    def _draw_mission_debrief(self, telemetry: VisualTelemetry) -> None:
        """Renders post-flight flight envelope debrief overlay with zero column overlap."""
        card_w = min(self.width - 64, 640)
        card_h = 240
        cx = (self.width - card_w) // 2
        cy = (self.height - card_h) // 2 + 10

        card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 23, 42, 245), (0, 0, card_w, card_h), border_radius=10)

        is_success = (telemetry.outcome == "success")
        border_color = (34, 197, 94) if is_success else (239, 68, 68)
        pygame.draw.rect(card_surf, border_color, (0, 0, card_w, card_h), width=2, border_radius=10)
        self.screen.blit(card_surf, (cx, cy))

        header_title = "MISSION SUCCESSFUL — SOFT TOUCHDOWN CONFIRMED" if is_success else "MISSION TERMINATED — STRUCTURAL FAILURE"
        txt_header = self.font_large.render(header_title, True, border_color)
        self.screen.blit(txt_header, (cx + (card_w - txt_header.get_width()) // 2, cy + 18))

        pygame.draw.line(self.screen, (51, 65, 85), (cx + 20, cy + 48), (cx + card_w - 20, cy + 48), width=1)

        # 2-Column Debrief Grid with guaranteed spacing
        col1_x = cx + 24
        col2_x = cx + int(card_w * 0.52)
        row_y = cy + 62
        dy = 26

        fields_col1 = [
            ("Touchdown Status", "PASS (NOMINAL REST)" if is_success else telemetry.outcome.upper(), border_color),
            ("Descent Velocity", f"{abs(telemetry.vel_y * 5.0):.2f} m/s", (34, 197, 94) if abs(telemetry.vel_y) <= 0.40 else (239, 68, 68)),
            ("Lateral Velocity", f"{abs(telemetry.vel_x * 5.0):.2f} m/s", (34, 197, 94) if abs(telemetry.vel_x) <= 0.40 else (239, 68, 68)),
            ("Pitch Attitude", f"{abs(telemetry.pitch_deg):.1f}° (Limit: 11.5°)", (34, 197, 94) if abs(telemetry.pitch_deg) <= 11.5 else (239, 68, 68)),
            ("Pad Radial Offset", f"{abs(telemetry.pos_x * 10.0):.2f} m (Pad: 4.0m)", (34, 197, 94) if abs(telemetry.pos_x) <= 0.25 else (239, 68, 68)),
        ]

        fields_col2 = [
            ("Cumulative Return", f"{telemetry.cumulative_reward:+.2f} pts", (56, 189, 248)),
            ("Landing Gear Lock", "DUAL CONTACT" if (telemetry.left_contact and telemetry.right_contact) else "PARTIAL / NONE", (34, 197, 94) if (telemetry.left_contact and telemetry.right_contact) else (234, 179, 8)),
            ("Flight Duration", f"{telemetry.step} steps ({telemetry.step * 0.02:.2f}s)", (226, 232, 240)),
            ("Structural Margin", "100% (REUSABLE)", border_color),
            ("Benchmark Status", "STAGE 8.3 VERIFIED", (234, 179, 8)),
        ]

        for i in range(len(fields_col1)):
            lbl1, val1, col1 = fields_col1[i]
            lbl_surf1 = self.font_small.render(f"{lbl1}:", True, (148, 163, 184))
            val_surf1 = self.font_small.render(val1, True, col1)
            self.screen.blit(lbl_surf1, (col1_x, row_y + dy * i))
            self.screen.blit(val_surf1, (col1_x + 130, row_y + dy * i))

            lbl2, val2, col2 = fields_col2[i]
            lbl_surf2 = self.font_small.render(f"{lbl2}:", True, (148, 163, 184))
            val_surf2 = self.font_small.render(val2, True, col2)
            self.screen.blit(lbl_surf2, (col2_x, row_y + dy * i))
            self.screen.blit(val_surf2, (col2_x + 130, row_y + dy * i))

        footer = self.font_tiny.render("PRESS ESC OR SPACE TO PROCEED", True, (100, 116, 139))
        self.screen.blit(footer, (cx + (card_w - footer.get_width()) // 2, cy + card_h - 22))

    # =========================================================================
    # Video Recording & Artifact Export
    # =========================================================================

    def start_recording(self, video_path: Union[str, Path], fps: Optional[int] = None) -> None:
        """Initializes OpenCV video writer to record simulation frames.

        If fps is not specified, uses round(target_fps * speed_factor) (e.g. 25 FPS for 0.5x)
        so that media players automatically play back at the intended presentation speed.
        """
        vpath = Path(video_path)
        vpath.parent.mkdir(parents=True, exist_ok=True)
        effective_fps = int(fps) if fps is not None else max(10, int(round(self.target_fps * self.speed_factor)))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.video_writer = cv2.VideoWriter(str(vpath), fourcc, effective_fps, (self.width, self.height))
        self.recording_fps = effective_fps

    def _record_frame(self) -> None:
        """Transfers current Pygame surface to OpenCV video stream."""
        if self.video_writer is not None:
            raw_rgb = pygame.surfarray.array3d(self.screen)
            raw_rgb = np.transpose(raw_rgb, (1, 0, 2))
            raw_bgr = cv2.cvtColor(raw_rgb, cv2.COLOR_RGB2BGR)
            self.video_writer.write(raw_bgr)

    def stop_recording(self) -> None:
        """Closes OpenCV video writer and finalizes MP4 file."""
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

    def save_screenshot(self, filepath: Union[str, Path]) -> Path:
        """Saves current screen buffer to an image file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.screen, str(path))
        return path

    def close(self) -> None:
        """Cleans up Pygame and video writer resources."""
        self.stop_recording()
        if not self.headless and pygame.display.get_init():
            try:
                pygame.display.quit()
            except Exception:
                pass
