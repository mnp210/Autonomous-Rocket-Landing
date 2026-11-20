"""Deterministic Simulation Timeline and Snapshot Architecture.

Provides strict separation between Gymnasium / Box2D physics simulation
and the 3D presentation layer. The renderer operates purely on immutable
snapshots and interpolated timelines without feedback into the physical state.
"""

from dataclasses import dataclass, field, replace
import math
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SimulationSnapshot:
    """Immutable physics and telemetry state at a discrete simulation step."""

    step: int
    sim_time: float  # Physical time in seconds (step * 0.02)
    pos_x: float  # Lander horizontal position (Box2D meters)
    pos_y: float  # Lander vertical position (Box2D meters)
    pos_z: float  # Depth (0.0 for 2D Box2D, mapped to 3D center)
    pitch: float  # Pitch angle in radians
    yaw: float  # Yaw angle in radians (0.0 for 2D plane)
    roll: float  # Roll angle in radians (corresponds to Box2D body angle)
    vel_x: float  # Horizontal velocity (m/s)
    vel_y: float  # Vertical velocity (m/s)
    vel_z: float  # Depth velocity (m/s)
    ang_vel: float  # Angular velocity (rad/s)
    action: int  # Discrete action (0: Idle, 1: Left RCS, 2: Main, 3: Right RCS)
    throttle: float  # Main engine thrust level (0.0 to 1.0)
    rcs_left: float  # Left RCS active (0.0 or 1.0)
    rcs_right: float  # Right RCS active (0.0 or 1.0)
    left_contact: bool  # Left landing gear in physical contact
    right_contact: bool  # Right landing gear in physical contact
    altitude: float  # Altitude above landing pad surface (meters)
    touchdown_phase: str  # Flight phase string
    reward: float  # Step reward
    cumulative_reward: float  # Cumulative episode reward
    terminated: bool  # Environment terminated
    truncated: bool  # Environment truncated
    outcome: Optional[str] = None  # SUCCESS, CRASH, OUT_OF_BOUNDS, TIMEOUT, etc.
    wind_force: float = 0.0  # Instantaneous aerodynamic crosswind force (Box2D units)
    impact_vel_x: Optional[float] = None  # Lateral velocity at initial gear contact
    impact_vel_y: Optional[float] = None  # Vertical velocity at initial gear contact
    impact_tilt: Optional[float] = None  # Pitch angle (radians) at initial gear contact
    leg_left_coords: Optional[Tuple[float, float]] = None
    leg_right_coords: Optional[Tuple[float, float]] = None
    terrain_coords: Tuple[Tuple[float, float], ...] = field(default_factory=tuple)
    helipad_bounds: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # x1, x2, y

    @property
    def is_terminal(self) -> bool:
        return self.terminated or self.truncated


class SnapshotTimeline:
    """Deterministic timeline of simulation snapshots supporting smooth temporal interpolation."""

    def __init__(self, dt: float = 0.02):
        self.dt = dt
        self.snapshots: List[SimulationSnapshot] = []

    def clear(self) -> None:
        self.snapshots.clear()

    def add_snapshot(self, snapshot: SimulationSnapshot) -> None:
        if self.snapshots and snapshot.sim_time < self.snapshots[-1].sim_time:
            raise ValueError(
                f"Snapshot time {snapshot.sim_time:.3f}s must be monotonically increasing "
                f"(last was {self.snapshots[-1].sim_time:.3f}s). Call clear() before starting a new episode."
            )
        self.snapshots.append(snapshot)

    def __len__(self) -> int:
        return len(self.snapshots)

    @property
    def total_sim_time(self) -> float:
        if not self.snapshots:
            return 0.0
        return self.snapshots[-1].sim_time

    def get_snapshot(self, index: int) -> SimulationSnapshot:
        if not self.snapshots:
            raise IndexError("SnapshotTimeline is empty")
        idx = max(0, min(len(self.snapshots) - 1, index))
        return self.snapshots[idx]

    def sample_interpolated(
        self,
        presentation_time: float,
        speed_factor: float = 1.0,
    ) -> SimulationSnapshot:
        """Deterministically samples the physical state at presentation time.

        Args:
            presentation_time: Elapsed presentation time in seconds.
            speed_factor: Playback speed multiplier (e.g. 0.5 for half speed).

        Returns:
            An interpolated SimulationSnapshot representing continuous state.
        """
        if not self.snapshots:
            raise ValueError("Cannot sample an empty SnapshotTimeline")

        sim_t = max(0.0, presentation_time * speed_factor)

        # Boundary checks
        if sim_t <= self.snapshots[0].sim_time:
            return self.snapshots[0]
        if sim_t >= self.snapshots[-1].sim_time:
            last = self.snapshots[-1]
            if last.terminated or last.truncated or last.touchdown_phase in ("SETTLED TOUCHDOWN", "DUAL GEAR CONTACT", "LANDING IMPACT"):
                return replace(last, action=0, throttle=0.0, rcs_left=0.0, rcs_right=0.0)
            return last

        # Find enclosing snapshots via step calculation
        step_approx = sim_t / self.dt
        i0 = int(math.floor(step_approx))
        i0 = max(0, min(len(self.snapshots) - 2, i0))
        i1 = i0 + 1

        s0 = self.snapshots[i0]
        s1 = self.snapshots[i1]

        t_span = s1.sim_time - s0.sim_time
        alpha = (sim_t - s0.sim_time) / t_span if t_span > 1e-6 else 0.0
        alpha = max(0.0, min(1.0, alpha))

        # Smooth Hermite/Cosine blending for positions to remove discretization jank
        smooth_alpha = 0.5 * (1.0 - math.cos(math.pi * alpha))

        # Position linear interpolation with smooth step
        pos_x = s0.pos_x + (s1.pos_x - s0.pos_x) * smooth_alpha
        pos_y = s0.pos_y + (s1.pos_y - s0.pos_y) * smooth_alpha
        pos_z = s0.pos_z + (s1.pos_z - s0.pos_z) * smooth_alpha

        # Velocity interpolation
        vel_x = s0.vel_x + (s1.vel_x - s0.vel_x) * alpha
        vel_y = s0.vel_y + (s1.vel_y - s0.vel_y) * alpha
        vel_z = s0.vel_z + (s1.vel_z - s0.vel_z) * alpha
        ang_vel = s0.ang_vel + (s1.ang_vel - s0.ang_vel) * alpha

        # Angle shortest-arc interpolation
        diff_roll = (s1.roll - s0.roll + math.pi) % (2 * math.pi) - math.pi
        roll = s0.roll + diff_roll * smooth_alpha

        diff_pitch = (s1.pitch - s0.pitch + math.pi) % (2 * math.pi) - math.pi
        pitch = s0.pitch + diff_pitch * smooth_alpha

        yaw = s0.yaw + (s1.yaw - s0.yaw) * smooth_alpha

        # Continuous throttle interpolation
        throttle = s0.throttle + (s1.throttle - s0.throttle) * alpha
        rcs_left = s0.rcs_left + (s1.rcs_left - s0.rcs_left) * alpha
        rcs_right = s0.rcs_right + (s1.rcs_right - s0.rcs_right) * alpha
        altitude = max(0.0, s0.altitude + (s1.altitude - s0.altitude) * smooth_alpha)

        # Nearest state for discrete physical triggers (contact, outcome, terminated)
        nearest = s1 if alpha >= 0.5 else s0

        # Enforce propulsion cutoff during post-landing or terminal states
        if (
            nearest.terminated
            or nearest.truncated
            or nearest.touchdown_phase in ("SETTLED TOUCHDOWN", "DUAL GEAR CONTACT", "LANDING IMPACT")
            or (nearest.left_contact and nearest.right_contact and altitude <= 0.08 and abs(vel_x) < 0.25 and abs(vel_y) < 0.25)
        ):
            throttle = 0.0
            rcs_left = 0.0
            rcs_right = 0.0
            effective_action = 0
        else:
            effective_action = nearest.action

        # Leg coordinates interpolation
        leg_l = None
        if s0.leg_left_coords and s1.leg_left_coords:
            leg_l = (
                s0.leg_left_coords[0] + (s1.leg_left_coords[0] - s0.leg_left_coords[0]) * smooth_alpha,
                s0.leg_left_coords[1] + (s1.leg_left_coords[1] - s0.leg_left_coords[1]) * smooth_alpha,
            )
        elif s0.leg_left_coords:
            leg_l = s0.leg_left_coords

        leg_r = None
        if s0.leg_right_coords and s1.leg_right_coords:
            leg_r = (
                s0.leg_right_coords[0] + (s1.leg_right_coords[0] - s0.leg_right_coords[0]) * smooth_alpha,
                s0.leg_right_coords[1] + (s1.leg_right_coords[1] - s0.leg_right_coords[1]) * smooth_alpha,
            )
        elif s0.leg_right_coords:
            leg_r = s0.leg_right_coords

        return SimulationSnapshot(
            step=nearest.step,
            sim_time=sim_t,
            pos_x=pos_x,
            pos_y=pos_y,
            pos_z=pos_z,
            pitch=pitch,
            yaw=yaw,
            roll=roll,
            vel_x=vel_x,
            vel_y=vel_y,
            vel_z=vel_z,
            ang_vel=ang_vel,
            action=effective_action,
            throttle=throttle,
            rcs_left=rcs_left,
            rcs_right=rcs_right,
            left_contact=nearest.left_contact,
            right_contact=nearest.right_contact,
            altitude=altitude,
            touchdown_phase=nearest.touchdown_phase,
            reward=nearest.reward,
            cumulative_reward=nearest.cumulative_reward,
            terminated=nearest.terminated,
            truncated=nearest.truncated,
            outcome=nearest.outcome,
            wind_force=s0.wind_force + (s1.wind_force - s0.wind_force) * alpha,
            impact_vel_x=nearest.impact_vel_x,
            impact_vel_y=nearest.impact_vel_y,
            impact_tilt=nearest.impact_tilt,
            leg_left_coords=leg_l,
            leg_right_coords=leg_r,
            terrain_coords=s0.terrain_coords,
            helipad_bounds=s0.helipad_bounds,
        )


def capture_snapshot_from_env(
    env: Any,
    obs: Any,
    action: int,
    step: int,
    reward: float = 0.0,
    cumulative_reward: float = 0.0,
    terminated: bool = False,
    truncated: bool = False,
    outcome: Optional[str] = None,
    impact_vel_x: Optional[float] = None,
    impact_vel_y: Optional[float] = None,
    impact_tilt: Optional[float] = None,
) -> SimulationSnapshot:
    """Extracts a SimulationSnapshot directly from Gymnasium LunarLander environment state."""
    unwrapped = env.unwrapped
    lander = getattr(unwrapped, "lander", None)

    # Instantaneous wind aerodynamic force calculation
    enable_wind = bool(getattr(unwrapped, "enable_wind", False))
    wind_power = float(getattr(unwrapped, "wind_power", 0.0))
    wind_idx = int(getattr(unwrapped, "wind_idx", 0))
    if enable_wind:
        wind_force = float(math.tanh(math.sin(0.02 * wind_idx) + math.sin(math.pi * 0.01 * wind_idx)) * wind_power)
    else:
        wind_force = 0.0

    # Helipad coordinates
    helipad_x1 = float(getattr(unwrapped, "helipad_x1", 8.0))
    helipad_x2 = float(getattr(unwrapped, "helipad_x2", 12.0))
    helipad_y = float(getattr(unwrapped, "helipad_y", 3.333))
    pad_center_x = (helipad_x1 + helipad_x2) * 0.5

    # Box2D coordinates centered on landing pad (pad center = X 0.0, surface = Y 0.22)
    # In Box2D LunarLander, the chassis center is ~0.592 m above the pad when legs rest on ground
    leg_rest_offset = 0.592
    if lander is not None:
        pos_x = float(lander.position.x) - pad_center_x
        altitude = max(0.0, float(lander.position.y) - helipad_y - leg_rest_offset)
        pos_y = 0.67 + altitude
        angle = float(lander.angle)  # Box2D radians
        vx = float(lander.linearVelocity.x)
        vy = float(lander.linearVelocity.y)
        w = float(lander.angularVelocity)
    else:
        # Fallback to observation array (obs[1] is normalized clearance above touchdown surface)
        pos_x = float(obs[0] * 10.0)
        altitude = max(0.0, float(obs[1] * 6.666))
        pos_y = 0.67 + altitude
        vx = float(obs[2] * 5.0)
        vy = float(obs[3] * 5.0)
        angle = float(obs[4])
        w = float(obs[5] * 2.5)

    # Leg contacts and positions
    legs = getattr(unwrapped, "legs", None)
    if legs and len(legs) >= 2:
        leg_l_contact = bool(legs[0].ground_contact)
        leg_r_contact = bool(legs[1].ground_contact)
        leg_l_pos = (float(legs[0].position.x) - pad_center_x, 0.2 + (float(legs[0].position.y) - helipad_y))
        leg_r_pos = (float(legs[1].position.x) - pad_center_x, 0.2 + (float(legs[1].position.y) - helipad_y))
    else:
        leg_l_contact = bool(obs[6] > 0.5)
        leg_r_contact = bool(obs[7] > 0.5)
        leg_l_pos = None
        leg_r_pos = None

    # Flight phase identification
    is_settled = (
        (leg_l_contact and leg_r_contact and altitude <= 0.08 and abs(vx) < 0.35 and abs(vy) < 0.35)
        or (altitude <= 0.03 and (leg_l_contact or leg_r_contact) and abs(vy) < 0.20)
    )

    if terminated or truncated:
        if outcome == "SUCCESS" or is_settled:
            phase = "SETTLED TOUCHDOWN"
        elif outcome == "CRASH":
            phase = "LANDING IMPACT"
        else:
            phase = "TERMINAL STAGE"
    elif is_settled:
        phase = "SETTLED TOUCHDOWN"
    elif leg_l_contact and leg_r_contact:
        phase = "DUAL GEAR CONTACT"
    elif leg_l_contact or leg_r_contact:
        phase = "INITIAL LEG TOUCH"
    elif altitude < 0.6:
        phase = "GROUND EFFECT FLARE"
    elif altitude < 2.0:
        phase = "TERMINAL DECELERATION"
    elif altitude < 5.0:
        phase = "GUIDANCE CORRECTION"
    else:
        phase = "HIGH DESCENT APPROACH"

    # Throttle and RCS states based on action
    # Explicit post-landing and terminal propulsion shutdown
    if terminated or truncated or is_settled:
        throttle = 0.0
        rcs_left = 0.0
        rcs_right = 0.0
        effective_action = 0
    else:
        effective_action = action
        throttle = 1.0 if action == 2 else 0.0
        rcs_left = 1.0 if action == 1 else 0.0
        rcs_right = 1.0 if action == 3 else 0.0

    # Terrain coordinates
    terrain = getattr(unwrapped, "terrain", None)
    terrain_coords = []
    if terrain:
        for seg in terrain:
            fix = getattr(seg, "fixtures", None)
            if fix:
                shape = fix[0].shape
                v0 = seg.transform * shape.vertices[0]
                v1 = seg.transform * shape.vertices[1]
                terrain_coords.append((float(v0[0]), float(v0[1])))
                terrain_coords.append((float(v1[0]), float(v1[1])))
    # Remove duplicates preserving order and center relative to pad
    unique_terrain = []
    seen = set()
    for pt in terrain_coords:
        rel_bx = pt[0] - pad_center_x
        rel_bz = 0.2 + (pt[1] - helipad_y)
        key = (round(rel_bx, 3), round(rel_bz, 3))
        if key not in seen:
            seen.add(key)
            unique_terrain.append((rel_bx, rel_bz))
    unique_terrain.sort(key=lambda p: p[0])

    return SimulationSnapshot(
        step=step,
        sim_time=step * 0.02,
        pos_x=pos_x,
        pos_y=pos_y,
        pos_z=0.0,
        pitch=0.0,
        yaw=0.0,
        roll=angle,
        vel_x=vx,
        vel_y=vy,
        vel_z=0.0,
        ang_vel=w,
        action=effective_action,
        throttle=throttle,
        rcs_left=rcs_left,
        rcs_right=rcs_right,
        left_contact=leg_l_contact,
        right_contact=leg_r_contact,
        altitude=altitude,
        touchdown_phase=phase,
        reward=reward,
        cumulative_reward=cumulative_reward,
        terminated=terminated,
        truncated=truncated,
        outcome=outcome,
        wind_force=wind_force,
        impact_vel_x=impact_vel_x,
        impact_vel_y=impact_vel_y,
        impact_tilt=impact_tilt,
        leg_left_coords=leg_l_pos,
        leg_right_coords=leg_r_pos,
        terrain_coords=tuple(unique_terrain),
        helipad_bounds=(helipad_x1, helipad_x2, helipad_y),
    )
