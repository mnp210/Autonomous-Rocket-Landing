"""Professional 2D Aerospace Landing Simulator Renderer.

Implements a high-fidelity vector rendering engine in Pygame featuring:
- 16:9 widescreen presentation (1280x720) with deep space atmospheric gradient.
- High-detail procedural rocket model (fuselage, aerodynamic nose cone, grid fins,
  engine nozzle bell, articulating dual landing gear, and footpads).
- Dynamic action-driven thruster plumes (supersonic shock-diamond main flame, cold-gas RCS bursts).
- Realistic lunar/planetary terrain with anti-aliased surface profile without clipping or spikes.
- Modern reinforced landing deck with hazard caution chevrons, target crosshairs, and beacon lights.
- Glass-cockpit HUD telemetry dashboard with digital readouts and miniature attitude horizon.
- Post-flight mission debrief card with touchdown validation metrics.
"""

from dataclasses import dataclass
import math
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import numpy as np
import pygame
import pygame.gfxdraw

from evaluation.evaluate import LandingCriteria, classify_outcome


@dataclass
class VisualTelemetry:
    """Current flight telemetry extracted from environment and policy state."""
    step: int = 0
    altitude: float = 0.0          # Normalized altitude
    pos_x: float = 0.0             # Horizontal position relative to pad center
    pos_y: float = 0.0             # Vertical position
    vel_x: float = 0.0             # Horizontal velocity
    vel_y: float = 0.0             # Vertical velocity (negative is descent)
    pitch_deg: float = 0.0         # Pitch angle in degrees (0 = vertical)
    pitch_rad: float = 0.0         # Pitch angle in radians
    angular_vel: float = 0.0       # Angular velocity (deg/s)
    action: int = 0                # Current discrete action (0: Coast, 1: Left, 2: Main, 3: Right)
    left_contact: bool = False     # Left landing leg in ground contact
    right_contact: bool = False    # Right landing leg in ground contact
    cumulative_reward: float = 0.0
    terminated: bool = False
    truncated: bool = False
    outcome: str = "descending"    # descending, approach, touchdown, crash, timeout
    touchdown_phase: str = "airborne"  # airborne, first_contact, dual_contact, settled


class AerospaceRenderer:
    """Professional widescreen 2D aerospace simulator renderer."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        headless: bool = False,
        title: str = "Autonomous Rocket Landing — Aerospace Simulator",
        target_fps: int = 50,
    ):
        """Initializes Pygame graphics context and visual assets."""
        self.width = width
        self.height = height
        self.headless = headless
        self.title = title
        self.target_fps = target_fps

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

        # Coordinate transformation setup
        self.world_center_x = 10.0
        self.pad_screen_x = self.width // 2
        self.pad_screen_y = int(self.height * 0.78)  # 561 px from top
        self.scale = 48.0  # Pixels per meter

        # Setup typography
        self.font_large = self._load_font(20, bold=True)
        self.font_main = self._load_font(15, bold=True)
        self.font_mono = self._load_font(13, mono=True)
        self.font_small = self._load_font(11, mono=True)
        self.font_banner = self._load_font(16, bold=True)

        # Pre-generate static starfield for visual depth
        self.stars = self._generate_starfield(count=140)

        # Dynamic plume animation state
        self.anim_tick = 0
        self.exhaust_particles: List[Dict[str, Any]] = []

    def _load_font(self, size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
        """Loads clean system font with fallback."""
        font_names = ["consolas", "lucidaconsole", "couriernew"] if mono else ["segoeui", "helvetica", "arial"]
        for name in font_names:
            try:
                font = pygame.font.SysFont(name, size, bold=bold)
                if font:
                    return font
            except Exception:
                continue
        return pygame.font.Font(None, size)

    def _generate_starfield(self, count: int) -> List[Tuple[int, int, int, int]]:
        """Generates reproducible star positions, radius, and brightness."""
        rng = random.Random(42)
        stars = []
        max_y = int(self.height * 0.72)
        for _ in range(count):
            x = rng.randint(0, self.width)
            y = rng.randint(0, max_y)
            radius = 1 if rng.random() > 0.15 else 2
            brightness = rng.randint(140, 255)
            stars.append((x, y, radius, brightness))
        return stars

    def world_to_screen(self, world_x: float, world_y: float, helipad_y: float = 3.333) -> Tuple[int, int]:
        """Converts Box2D meters to Pygame viewport screen pixels."""
        screen_x = int(self.pad_screen_x + (world_x - self.world_center_x) * self.scale)
        screen_y = int(self.pad_screen_y - (world_y - helipad_y) * self.scale)
        return screen_x, screen_y

    def reset(self) -> None:
        """Resets renderer state cleanly between simulation episodes."""
        self.particles.clear()
        self.flame_history.clear()

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

        # Read actual Box2D physical positions if available
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

        # Leg ground contacts
        if hasattr(u, "legs") and len(u.legs) >= 2:
            left_contact = bool(u.legs[0].ground_contact)
            right_contact = bool(u.legs[1].ground_contact)
        else:
            left_contact = bool(obs[6] > 0.5)
            right_contact = bool(obs[7] > 0.5)

        pitch_deg_val = math.degrees(pitch_rad_val)
        altitude_val = float(obs[1])

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
        elif altitude_val < 0.25:
            outcome = "approach"
        else:
            outcome = "descending"

        # Explicit post-landing and terminal propulsion shutdown
        is_settled = (
            (left_contact and right_contact and altitude_val <= 0.08 and abs(vel_x_val) < 0.35 and abs(vel_y_val) < 0.35)
            or (altitude_val <= 0.03 and (left_contact or right_contact) and abs(vel_y_val) < 0.20)
        )
        effective_action = 0 if (terminated or truncated or is_settled) else action

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
        )

    def render_frame(self, env: Any, telemetry: VisualTelemetry) -> pygame.Surface:
        """Renders one complete, high-fidelity aerospace simulation frame."""
        self.anim_tick += 1

        # 1. Background Atmosphere Gradient & Stars
        self._draw_sky_and_stars()

        # 2. Lunar Terrain & Landing Platform
        u = getattr(env, "unwrapped", env)
        helipad_y = getattr(u, "helipad_y", 3.333)
        helipad_x1 = getattr(u, "helipad_x1", 8.0)
        helipad_x2 = getattr(u, "helipad_x2", 12.0)
        self._draw_terrain_and_pad(u, helipad_x1, helipad_x2, helipad_y)

        # 3. Dynamic Thruster Plumes
        rocket_cx, rocket_cy = self.world_to_screen(
            telemetry.pos_y if False else (self.world_center_x + telemetry.pos_x * 10.0),
            telemetry.pos_y,
            helipad_y
        )
        self._draw_thruster_plumes(rocket_cx, rocket_cy, telemetry.pitch_rad, telemetry.action)

        # 4. Rocket Vehicle (Fuselage, Fins, Nozzle, Legs)
        self._draw_rocket_vehicle(rocket_cx, rocket_cy, telemetry.pitch_rad, telemetry.left_contact, telemetry.right_contact)

        # 5. Glass-Cockpit HUD (Flight Telemetry & Status)
        self._draw_hud(telemetry)

        # 6. Mission Debrief Card (if flight completed)
        if telemetry.terminated or telemetry.truncated:
            self._draw_mission_debrief(telemetry)

        if not self.headless:
            pygame.display.flip()
            self.clock.tick(self.target_fps)

        return self.screen

    def _draw_sky_and_stars(self) -> None:
        """Renders deep space gradient and crisp procedural starfield."""
        top_color = (6, 10, 20)
        bottom_color = (14, 23, 48)
        h = self.height

        steps = 32
        chunk_h = h // steps
        for i in range(steps):
            ratio = i / float(steps)
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
            pygame.draw.rect(self.screen, (r, g, b), (0, i * chunk_h, self.width, chunk_h + 1))

        # Stars
        for sx, sy, rad, bright in self.stars:
            b = bright
            if rad == 2 and (sx + self.anim_tick) % 9 == 0:
                b = max(110, bright - 45)
            color = (b, b, min(255, b + 18))
            if rad == 1:
                self.screen.set_at((sx, sy), color)
            else:
                pygame.draw.circle(self.screen, color, (sx, sy), rad)

    def _draw_terrain_and_pad(self, u: Any, pad_x1: float, pad_x2: float, helipad_y: float) -> None:
        """Renders lunar terrain polyline and dedicated reinforced landing platform."""
        surface_points: List[Tuple[float, float]] = []

        if hasattr(u, "moon") and u.moon and hasattr(u.moon, "fixtures"):
            # Collect only actual surface vertices (filter out baseline fixtures where y < 0.5)
            raw_pts: List[Tuple[float, float]] = []
            for f in u.moon.fixtures:
                v = f.shape.vertices
                for pt in v:
                    if pt[1] > 0.5:  # Surface points only
                        raw_pts.append((float(pt[0]), float(pt[1])))

            # Group uniquely and sort by X
            unique_dict: Dict[float, float] = {}
            for wx, wy in raw_pts:
                # Discretize slightly to deduplicate
                key = round(wx, 3)
                if key not in unique_dict or wy > unique_dict[key]:
                    unique_dict[key] = wy

            sorted_x = sorted(unique_dict.keys())
            for wx in sorted_x:
                surface_points.append((wx, unique_dict[wx]))

        if not surface_points:
            # Fallback terrain
            surface_points = [
                (0.0, 4.2), (4.0, 3.8), (8.0, helipad_y), (12.0, helipad_y),
                (16.0, 3.2), (20.0, 4.0)
            ]

        # Convert to screen coordinates
        ground_poly: List[Tuple[int, int]] = []
        for wx, wy in surface_points:
            ground_poly.append(self.world_to_screen(wx, wy, helipad_y))

        # Ensure first point starts at left edge and last reaches right edge
        if ground_poly:
            ground_poly[0] = (0, ground_poly[0][1])
            ground_poly[-1] = (self.width, ground_poly[-1][1])

        # Solid basalt terrain polygon down to screen bottom
        poly_full = [(0, self.height)] + ground_poly + [(self.width, self.height)]
        pygame.draw.polygon(self.screen, (15, 23, 42), poly_full)  # Slate 900 (#0F172A)

        # Anti-aliased terrain crust outline
        if len(ground_poly) >= 2:
            pygame.draw.lines(self.screen, (51, 65, 85), False, ground_poly, width=3)  # Slate 700 (#334155)

        # Dedicated Reinforced Landing Platform
        pad_sx1, pad_sy = self.world_to_screen(pad_x1, helipad_y, helipad_y)
        pad_sx2, _ = self.world_to_screen(pad_x2, helipad_y, helipad_y)
        pad_w = pad_sx2 - pad_sx1
        pad_h = 16

        # Reinforced deck foundation
        foundation_rect = pygame.Rect(pad_sx1 - 8, pad_sy, pad_w + 16, pad_h + 12)
        pygame.draw.rect(self.screen, (30, 41, 59), foundation_rect, border_radius=4)
        pygame.draw.rect(self.screen, (71, 85, 105), foundation_rect, width=2, border_radius=4)

        # Hazard caution stripes on deck face
        deck_rect = pygame.Rect(pad_sx1, pad_sy, pad_w, pad_h)
        pygame.draw.rect(self.screen, (15, 23, 42), deck_rect)

        stripe_w = 14
        for sx in range(pad_sx1, pad_sx2, stripe_w * 2):
            pts = [
                (sx, pad_sy + pad_h),
                (sx + stripe_w, pad_sy),
                (min(pad_sx2, sx + stripe_w * 2), pad_sy),
                (min(pad_sx2, sx + stripe_w), pad_sy + pad_h),
            ]
            pygame.draw.polygon(self.screen, (234, 179, 8), pts)  # Amber (#EAB308)

        # Concentric Target Markings & Bullseye
        center_x = (pad_sx1 + pad_sx2) // 2
        center_y = pad_sy
        pygame.draw.ellipse(self.screen, (56, 189, 248), (center_x - 34, center_y - 6, 68, 12), width=2)
        pygame.draw.ellipse(self.screen, (234, 179, 8), (center_x - 18, center_y - 3, 36, 6), width=2)
        pygame.draw.circle(self.screen, (239, 68, 68), (center_x, center_y), 3)

        # Perimeter Beacon Floodlights
        for bx in [pad_sx1 - 6, pad_sx2 + 6]:
            pygame.draw.line(self.screen, (100, 116, 139), (bx, pad_sy), (bx, pad_sy - 18), width=3)
            beacon_glow = 180 + int(70 * math.sin(self.anim_tick * 0.15))
            pygame.draw.circle(self.screen, (34, 197, 94), (bx, pad_sy - 18), 4)
            halo_surf = pygame.Surface((24, 24), pygame.SRCALPHA)
            pygame.draw.circle(halo_surf, (34, 197, 94, int(beacon_glow * 0.35)), (12, 12), 10)
            self.screen.blit(halo_surf, (bx - 12, pad_sy - 30))

    def _draw_rocket_vehicle(
        self,
        cx: int,
        cy: int,
        angle_rad: float,
        left_contact: bool,
        right_contact: bool,
    ) -> None:
        """Renders procedural aerospace rocket (fuselage, nose, fins, nozzle, articulating gear)."""
        body_w = 20
        body_h = 56
        half_w = body_w // 2

        s_size = 140
        surf = pygame.Surface((s_size, s_size), pygame.SRCALPHA)
        local_cx = s_size // 2
        local_cy = s_size // 2

        # 1. Main Cylindrical Fuselage
        fuselage_pts = [
            (-half_w, -body_h // 2 + 10),
            (half_w, -body_h // 2 + 10),
            (half_w + 1, body_h // 2 - 8),
            (-half_w - 1, body_h // 2 - 8),
        ]
        poly_screen = [(local_cx + x, local_cy + y) for x, y in fuselage_pts]
        pygame.draw.polygon(surf, (226, 232, 240), poly_screen)

        # Metallic shading strip (right side highlight)
        shade_pts = [
            (local_cx + 2, local_cy - body_h // 2 + 10),
            (local_cx + half_w, local_cy - body_h // 2 + 10),
            (local_cx + half_w + 1, local_cy + body_h // 2 - 8),
            (local_cx + 2, local_cy + body_h // 2 - 8),
        ]
        pygame.draw.polygon(surf, (148, 163, 184), shade_pts)

        # Carbon interstage ring (#1E293B)
        pygame.draw.rect(surf, (30, 41, 59), (local_cx - half_w - 1, local_cy + 4, body_w + 2, 6))

        # 2. Aerodynamic Nose Cone
        nose_pts = [
            (-half_w, -body_h // 2 + 10),
            (0, -body_h // 2 - 12),
            (half_w, -body_h // 2 + 10),
        ]
        nose_screen = [(local_cx + x, local_cy + y) for x, y in nose_pts]
        pygame.draw.polygon(surf, (241, 245, 249), nose_screen)
        pygame.draw.lines(surf, (100, 116, 139), False, nose_screen, width=2)

        # 3. Dual Grid Fins
        fin_y = local_cy - body_h // 2 + 16
        pygame.draw.rect(surf, (71, 85, 105), (local_cx - half_w - 9, fin_y, 9, 8), border_radius=1)
        pygame.draw.rect(surf, (148, 163, 184), (local_cx - half_w - 9, fin_y, 9, 8), width=1)
        pygame.draw.rect(surf, (71, 85, 105), (local_cx + half_w, fin_y, 9, 8), border_radius=1)
        pygame.draw.rect(surf, (148, 163, 184), (local_cx + half_w, fin_y, 9, 8), width=1)

        # 4. Engine Bell Nozzle
        nozzle_top_y = local_cy + body_h // 2 - 8
        nozzle_pts = [
            (local_cx - 5, nozzle_top_y),
            (local_cx + 5, nozzle_top_y),
            (local_cx + 9, nozzle_top_y + 11),
            (local_cx - 9, nozzle_top_y + 11),
        ]
        pygame.draw.polygon(surf, (51, 65, 85), nozzle_pts)
        pygame.draw.polygon(surf, (15, 23, 42), nozzle_pts, width=1)
        pygame.draw.line(surf, (251, 191, 36), (local_cx - 4, nozzle_top_y + 1), (local_cx + 4, nozzle_top_y + 1), width=2)

        # 5. Articulating Carbon Landing Gear Struts & Footpads
        leg_attach_y = local_cy + body_h // 2 - 14

        # Left Landing Leg
        left_foot_x = local_cx - half_w - 15
        left_foot_y = local_cy + body_h // 2 + 12
        pygame.draw.line(surf, (30, 41, 59), (local_cx - half_w + 2, leg_attach_y), (left_foot_x, left_foot_y), width=3)
        pygame.draw.line(surf, (71, 85, 105), (local_cx - 4, leg_attach_y + 6), (left_foot_x, left_foot_y), width=2)
        foot_color_l = (34, 197, 94) if left_contact else (100, 116, 139)
        pygame.draw.rect(surf, foot_color_l, (left_foot_x - 5, left_foot_y, 10, 3), border_radius=1)

        # Right Landing Leg
        right_foot_x = local_cx + half_w + 15
        right_foot_y = local_cy + body_h // 2 + 12
        pygame.draw.line(surf, (30, 41, 59), (local_cx + half_w - 2, leg_attach_y), (right_foot_x, right_foot_y), width=3)
        pygame.draw.line(surf, (71, 85, 105), (local_cx + 4, leg_attach_y + 6), (right_foot_x, right_foot_y), width=2)
        foot_color_r = (34, 197, 94) if right_contact else (100, 116, 139)
        pygame.draw.rect(surf, foot_color_r, (right_foot_x - 5, right_foot_y, 10, 3), border_radius=1)

        # Vehicle Border Outline
        pygame.draw.lines(surf, (71, 85, 105), True, poly_screen, width=2)

        # Rotate according to physical pitch angle
        rot_deg = math.degrees(angle_rad)
        rot_surf = pygame.transform.rotate(surf, rot_deg)
        rot_rect = rot_surf.get_rect(center=(cx, cy))
        self.screen.blit(rot_surf, rot_rect.topleft)

    def _draw_thruster_plumes(self, cx: int, cy: int, angle_rad: float, action: int) -> None:
        """Renders action-driven dynamic supersonic flame and cold-gas RCS plumes."""
        if action == 2:
            self._draw_main_engine_flame(cx, cy, angle_rad)
        elif action == 1:
            self._draw_rcs_burst(cx, cy, angle_rad, side="left")
        elif action == 3:
            self._draw_rcs_burst(cx, cy, angle_rad, side="right")

    def _draw_main_engine_flame(self, cx: int, cy: int, angle_rad: float) -> None:
        """Renders brilliant glowing supersonic flame with cyan core and orange plume."""
        s_size = 180
        flame_surf = pygame.Surface((s_size, s_size), pygame.SRCALPHA)
        flame_cx = s_size // 2
        nozzle_exit_y = flame_cx + 31

        flicker = random.randint(-4, 4)
        plume_len = 50 + flicker

        # 1. Outer Supersonic Envelope (Vibrant Orange / Amber Glow)
        outer_plume = [
            (flame_cx - 8, nozzle_exit_y),
            (flame_cx + 8, nozzle_exit_y),
            (flame_cx + 15, nozzle_exit_y + int(plume_len * 0.45)),
            (flame_cx, nozzle_exit_y + plume_len),
            (flame_cx - 15, nozzle_exit_y + int(plume_len * 0.45)),
        ]
        pygame.draw.polygon(flame_surf, (245, 158, 11, 230), outer_plume)

        # 2. Mid Core Plume (Intense Gold)
        mid_plume = [
            (flame_cx - 6, nozzle_exit_y),
            (flame_cx + 6, nozzle_exit_y),
            (flame_cx + 9, nozzle_exit_y + int(plume_len * 0.5)),
            (flame_cx, nozzle_exit_y + int(plume_len * 0.8)),
            (flame_cx - 9, nozzle_exit_y + int(plume_len * 0.5)),
        ]
        pygame.draw.polygon(flame_surf, (251, 191, 36, 240), mid_plume)

        # 3. Inner Combustion Core & Shock Diamonds (Electric Cyan / White Hot)
        core_len = int(plume_len * 0.52)
        core_plume = [
            (flame_cx - 4, nozzle_exit_y),
            (flame_cx + 4, nozzle_exit_y),
            (flame_cx + 5, nozzle_exit_y + int(core_len * 0.5)),
            (flame_cx, nozzle_exit_y + core_len),
            (flame_cx - 5, nozzle_exit_y + int(core_len * 0.5)),
        ]
        pygame.draw.polygon(flame_surf, (56, 189, 248), core_plume)
        pygame.draw.ellipse(flame_surf, (255, 255, 255), (flame_cx - 3, nozzle_exit_y, 6, 14))

        # Rotate flame to match vehicle pitch
        rot_deg = math.degrees(angle_rad)
        rot_flame = pygame.transform.rotate(flame_surf, rot_deg)
        rot_rect = rot_flame.get_rect(center=(cx, cy))
        self.screen.blit(rot_flame, rot_rect.topleft)

    def _draw_rcs_burst(self, cx: int, cy: int, angle_rad: float, side: str) -> None:
        """Renders cold-gas high-pressure attitude control puffs."""
        s_size = 140
        rcs_surf = pygame.Surface((s_size, s_size), pygame.SRCALPHA)
        local_cx = s_size // 2
        local_cy = s_size // 2

        port_y = local_cy - 12
        direction = -1 if side == "left" else 1
        port_x = local_cx + (direction * 11)

        puff_len = 18 + random.randint(-2, 3)
        pts = [
            (port_x, port_y - 2),
            (port_x + direction * puff_len, port_y - 6),
            (port_x + direction * (puff_len + 4), port_y),
            (port_x + direction * puff_len, port_y + 6),
            (port_x, port_y + 2),
        ]
        pygame.draw.polygon(rcs_surf, (56, 189, 248, 220), pts)
        pygame.draw.polygon(rcs_surf, (255, 255, 255, 240), [
            (port_x, port_y - 1),
            (port_x + direction * (puff_len // 2), port_y),
            (port_x, port_y + 1),
        ])

        rot_deg = math.degrees(angle_rad)
        rot_rcs = pygame.transform.rotate(rcs_surf, rot_deg)
        rot_rect = rot_rcs.get_rect(center=(cx, cy))
        self.screen.blit(rot_rcs, rot_rect.topleft)

    def _draw_hud(self, t: VisualTelemetry) -> None:
        """Renders primary flight display (PFD) and propulsion status cards."""
        # 1. Top-Left Primary Flight Display Card
        pfd_w = 310
        pfd_h = 175
        self._draw_glass_panel(18, 18, pfd_w, pfd_h, title="PRIMARY FLIGHT DISPLAY (PFD)")

        alt_str = f"{t.altitude * 100:.1f} m" if t.altitude >= 0 else "0.0 m"
        offset_dir = "◄ " if t.pos_x < -0.02 else ("► " if t.pos_x > 0.02 else "● ")
        offset_str = f"{offset_dir}{abs(t.pos_x * 10.0):.2f} m"

        vy_safe = abs(t.vel_y) <= 0.40
        vy_color = (34, 197, 94) if vy_safe else (239, 68, 68)
        vx_safe = abs(t.vel_x) <= 0.40
        vx_color = (34, 197, 94) if vx_safe else (239, 68, 68)
        tilt_safe = abs(t.pitch_deg) <= 11.45
        tilt_color = (34, 197, 94) if tilt_safe else (234, 179, 8)

        rows = [
            ("ALTITUDE (AGL)", alt_str, (241, 245, 249)),
            ("LATERAL OFFSET", offset_str, (56, 189, 248)),
            ("DESCENT RATE (Vy)", f"{t.vel_y:+.2f} m/s", vy_color),
            ("LATERAL SPEED (Vx)", f"{t.vel_x:+.2f} m/s", vx_color),
            ("PITCH ATTITUDE (θ)", f"{t.pitch_deg:+.1f}°", tilt_color),
            ("ANGULAR RATE", f"{t.angular_vel:+.1f}°/s", (203, 213, 225)),
        ]

        row_y = 48
        for label, val, color in rows:
            lbl_surf = self.font_mono.render(label, True, (148, 163, 184))
            val_surf = self.font_mono.render(val, True, color)
            self.screen.blit(lbl_surf, (30, row_y))
            self.screen.blit(val_surf, (200, row_y))
            row_y += 20

        # Miniature Attitude Horizon Indicator on PFD
        horizon_cx = 30 + pfd_w - 38
        horizon_cy = 38
        horizon_r = 16
        pygame.draw.circle(self.screen, (30, 41, 59), (horizon_cx, horizon_cy), horizon_r)
        # Horizon tilt line
        rad = math.radians(t.pitch_deg)
        dx = int(math.cos(rad) * (horizon_r - 2))
        dy = int(math.sin(rad) * (horizon_r - 2))
        pygame.draw.line(self.screen, (56, 189, 248), (horizon_cx - dx, horizon_cy + dy), (horizon_cx + dx, horizon_cy - dy), width=2)
        pygame.draw.circle(self.screen, (234, 179, 8), (horizon_cx, horizon_cy), 2)
        pygame.draw.circle(self.screen, (71, 85, 105), (horizon_cx, horizon_cy), horizon_r, width=1)

        # 2. Top-Right Actuator & Systems Status Card
        sys_w = 280
        sys_h = 175
        sys_x = self.width - sys_w - 18
        self._draw_glass_panel(sys_x, 18, sys_w, sys_h, title="PROPULSION & GEAR SYSTEMS")

        main_active = (t.action == 2)
        rcs_l_active = (t.action == 1)
        rcs_r_active = (t.action == 3)

        sys_rows = [
            ("MAIN ENGINE", "[ 100% THRUST ]" if main_active else "[ STANDBY ]", (249, 115, 22) if main_active else (100, 116, 139)),
            ("RCS PORT 1 (CW)", "[ FIRING ]" if rcs_l_active else "[ OFF ]", (56, 189, 248) if rcs_l_active else (100, 116, 139)),
            ("RCS PORT 2 (CCW)", "[ FIRING ]" if rcs_r_active else "[ OFF ]", (56, 189, 248) if rcs_r_active else (100, 116, 139)),
            ("GEAR CONTACT L", "[ LOCKED ]" if t.left_contact else "[ FREE ]", (34, 197, 94) if t.left_contact else (148, 163, 184)),
            ("GEAR CONTACT R", "[ LOCKED ]" if t.right_contact else "[ FREE ]", (34, 197, 94) if t.right_contact else (148, 163, 184)),
            ("AUTOPILOT", "[ PPO ACTIVE ]", (56, 189, 248)),
        ]

        s_y = 48
        for label, val, color in sys_rows:
            lbl_surf = self.font_mono.render(label, True, (148, 163, 184))
            val_surf = self.font_mono.render(val, True, color)
            self.screen.blit(lbl_surf, (sys_x + 14, s_y))
            self.screen.blit(val_surf, (sys_x + 160, s_y))
            s_y += 20

        # 3. Top-Center Mission Status Banner
        banner_w = 480
        banner_h = 36
        banner_x = (self.width - banner_w) // 2
        banner_y = 18

        if t.outcome == "success":
            banner_text = "● TOUCHDOWN CONFIRMED — MISSION SUCCESS"
            banner_bg = (6, 78, 59, 220)
            banner_border = (34, 197, 94)
            text_color = (240, 253, 244)
        elif t.outcome == "crash":
            banner_text = "▲ VEHICLE COLLISION DETECTED — MISSION FAILURE"
            banner_bg = (127, 29, 29, 220)
            banner_border = (239, 68, 68)
            text_color = (254, 242, 242)
        elif t.outcome == "timeout":
            banner_text = "■ TRAJECTORY TIMEOUT EXPIRED"
            banner_bg = (120, 53, 15, 220)
            banner_border = (234, 179, 8)
            text_color = (254, 243, 199)
        elif t.outcome == "approach":
            banner_text = "▼ FINAL APPROACH & TERMINAL GUIDANCE"
            banner_bg = (15, 23, 42, 220)
            banner_border = (56, 189, 248)
            text_color = (224, 242, 254)
        else:
            banner_text = "▲ AUTONOMOUS DESCENT & ATTITUDE ALIGNMENT"
            banner_bg = (15, 23, 42, 220)
            banner_border = (71, 85, 105)
            text_color = (226, 232, 240)

        banner_surf = pygame.Surface((banner_w, banner_h), pygame.SRCALPHA)
        pygame.draw.rect(banner_surf, banner_bg, (0, 0, banner_w, banner_h), border_radius=6)
        pygame.draw.rect(banner_surf, banner_border, (0, 0, banner_w, banner_h), width=1, border_radius=6)
        self.screen.blit(banner_surf, (banner_x, banner_y))

        txt = self.font_banner.render(banner_text, True, text_color)
        t_rect = txt.get_rect(center=(banner_x + banner_w // 2, banner_y + banner_h // 2))
        self.screen.blit(txt, t_rect)

    def _draw_glass_panel(self, x: int, y: int, w: int, h: int, title: str) -> None:
        """Renders dark glassmorphic UI container with subtle glow border."""
        panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (15, 23, 42, 210), (0, 0, w, h), border_radius=6)
        pygame.draw.rect(panel_surf, (51, 65, 85, 180), (0, 0, w, h), width=1, border_radius=6)
        pygame.draw.line(panel_surf, (56, 189, 248, 160), (10, 24), (w - 10, 24), width=1)
        self.screen.blit(panel_surf, (x, y))

        title_surf = self.font_small.render(title, True, (56, 189, 248))
        self.screen.blit(title_surf, (x + 12, y + 8))

    def _draw_mission_debrief(self, t: VisualTelemetry) -> None:
        """Renders post-flight mission debrief card in center viewport."""
        card_w = 540
        card_h = 240
        cx = (self.width - card_w) // 2
        cy = (self.height - card_h) // 2

        card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        pygame.draw.rect(card_surf, (15, 23, 42, 235), (0, 0, card_w, card_h), border_radius=8)

        is_success = (t.outcome == "success")
        border_color = (34, 197, 94) if is_success else (239, 68, 68)
        pygame.draw.rect(card_surf, border_color, (0, 0, card_w, card_h), width=2, border_radius=8)
        self.screen.blit(card_surf, (cx, cy))

        header_title = "MISSION DEBRIEF: SOFT TOUCHDOWN SUCCESS" if is_success else "MISSION DEBRIEF: TOUCHDOWN FAILURE"
        header_color = (34, 197, 94) if is_success else (239, 68, 68)
        h_surf = self.font_large.render(header_title, True, header_color)
        h_rect = h_surf.get_rect(center=(cx + card_w // 2, cy + 28))
        self.screen.blit(h_surf, h_rect)

        debrief_rows = [
            ("FLIGHT DURATION", f"{t.step} STEPS (~{t.step/50.0:.1f}s)", (226, 232, 240)),
            ("EPISODE REWARD", f"{t.cumulative_reward:+.2f}", (251, 191, 36)),
            ("TOUCHDOWN LATERAL OFFSET", f"{abs(t.pos_x * 10.0):.3f} m (LIMIT: <= 2.50 m)", (34, 197, 94) if abs(t.pos_x) <= 0.25 else (239, 68, 68)),
            ("TOUCHDOWN VELOCITY (Vy)", f"{abs(t.vel_y):.3f} m/s (LIMIT: <= 0.40 m/s)", (34, 197, 94) if abs(t.vel_y) <= 0.40 else (239, 68, 68)),
            ("RESTING PITCH ANGLE (θ)", f"{abs(t.pitch_deg):.2f}° (LIMIT: <= 11.45°)", (34, 197, 94) if abs(t.pitch_deg) <= 11.45 else (239, 68, 68)),
            ("GEAR SENSORS (L, R)", f"DUAL LOCKED (1, 1)" if (t.left_contact and t.right_contact) else f"({int(t.left_contact)}, {int(t.right_contact)})", (34, 197, 94) if (t.left_contact and t.right_contact) else (239, 68, 68)),
        ]

        row_y = cy + 62
        for label, val, color in debrief_rows:
            lbl_surf = self.font_mono.render(label, True, (148, 163, 184))
            val_surf = self.font_mono.render(val, True, color)
            self.screen.blit(lbl_surf, (cx + 28, row_y))
            self.screen.blit(val_surf, (cx + 250, row_y))
            row_y += 24

    def save_screenshot(self, filepath: Union[str, Path]) -> Path:
        """Saves current screen buffer as a crisp PNG file."""
        out_path = Path(filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.screen, str(out_path))
        return out_path

    def close(self) -> None:
        """Releases Pygame resources."""
        if not self.headless and pygame.get_init():
            pygame.display.quit()
