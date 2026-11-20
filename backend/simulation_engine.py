"""Authoritative Headless Simulation Engine for Backend Sessions.

Runs Gymnasium LunarLander-v3 with isolated Box2D world, TerminalStateLatch,
and strict 2D physics snapshot extraction.
"""

import math
import threading
from typing import Any, List, Optional, Tuple
import uuid

import gymnasium as gym
import numpy as np

from backend.config import DEFAULT_GRAVITY, MAX_EPISODE_STEPS, PHYSICS_DT
from backend.latch import TerminalStateLatch
from backend.schemas import (
    AtmosphereState,
    EpisodeCompletePayload,
    FlightMode,
    ImpactTelemetry,
    Kinematics2D,
    LandingGearState,
    LifecycleState,
    PolicyMode,
    PropulsionState,
    SessionReadyPayload,
    SimulationSnapshotPayload,
    StormSeverity,
)
from evaluation.evaluate import LandingCriteria, classify_outcome


class SimulationSession:
    """Isolated server-side simulation session wrapping an authoritative Box2D instance."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        mode: FlightMode = FlightMode.AI,
        policy_mode: PolicyMode = PolicyMode.DETERMINISTIC,
        seed: Optional[int] = None,
        storm_severity: StormSeverity = StormSeverity.MODERATE,
        wind: Optional[float] = None,
        turbulence: Optional[float] = None,
    ):
        self.session_id: str = session_id or str(uuid.uuid4())
        self.episode_id: int = 1
        self.mode: FlightMode = mode
        self.policy_mode: PolicyMode = policy_mode
        self.seed: int = seed if seed is not None else 42
        self.storm_severity: StormSeverity = storm_severity

        # Determine wind and turbulence configuration
        storm_presets = {
            StormSeverity.MODERATE: (10.0, 0.8),
            StormSeverity.SEVERE: (15.0, 1.2),
            StormSeverity.EXTREME: (20.0, 2.0),
        }
        preset_wind, preset_turb = storm_presets.get(self.storm_severity, (10.0, 0.8))
        self.enable_wind: bool = (self.mode == FlightMode.STORM)
        self.wind_power: float = (
            wind if wind is not None else (preset_wind if self.enable_wind else 0.0)
        )
        self.turbulence: float = (
            turbulence if turbulence is not None else (preset_turb if self.enable_wind else 0.0)
        )

        # Create isolated Gymnasium Box2D environment
        self.env = gym.make(
            "LunarLander-v3",
            render_mode=None,  # Headless mode: no Pygame or display windows
            continuous=False,
            gravity=DEFAULT_GRAVITY,
            enable_wind=self.enable_wind,
            wind_power=self.wind_power,
            turbulence_power=self.turbulence,
        )

        self.criteria = LandingCriteria()
        self.latch = TerminalStateLatch()

        # Concurrency & Ownership Fencing
        self._step_lock = threading.RLock()
        self.owner_id: str = str(uuid.uuid4())
        self.step_generation: int = 1

        # Telemetry tracking state
        self.step_count: int = 0
        self.sim_time: float = 0.0
        self.cumulative_reward: float = 0.0
        self.last_reward: float = 0.0
        self.terminated: bool = False
        self.truncated: bool = False
        self.outcome: Optional[str] = None
        self.last_action: int = 0
        self.speed_factor: float = 1.0
        self.is_paused: bool = False

        # Static environment geometry caches
        self._helipad_bounds: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._terrain_coords: List[Tuple[float, float]] = []

        # Initialize environment with seed
        self.last_obs, _ = self.env.reset(seed=self.seed)
        self._cache_static_geometry()

    def _cache_static_geometry(self) -> None:
        """Caches helipad bounds and terrain profile points for client initial handshake."""
        unwrapped = self.env.unwrapped
        hx1 = float(getattr(unwrapped, "helipad_x1", 8.0))
        hx2 = float(getattr(unwrapped, "helipad_x2", 12.0))
        hy = float(getattr(unwrapped, "helipad_y", 3.333))
        self._helipad_bounds = (hx1, hx2, hy)
        pad_center_x = (hx1 + hx2) * 0.5

        pts: List[Tuple[float, float]] = []

        # 1. Extract from unwrapped.moon (Gymnasium LunarLander-v3 Box2D body fixtures)
        moon = getattr(unwrapped, "moon", None)
        if moon and hasattr(moon, "fixtures"):
            for fix in moon.fixtures:
                v = fix.shape.vertices
                # Ignore the bottom bounding box edge at y=0.0
                if v[0][1] > 0.05 or v[1][1] > 0.05:
                    pts.append((float(v[0][0]), float(v[0][1])))
                    pts.append((float(v[1][0]), float(v[1][1])))

        # 2. Fallback to legacy terrain attribute if present
        terrain = getattr(unwrapped, "terrain", None)
        if not pts and terrain:
            for seg in terrain:
                fix = getattr(seg, "fixtures", None)
                if fix:
                    shape = fix[0].shape
                    v0 = seg.transform * shape.vertices[0]
                    v1 = seg.transform * shape.vertices[1]
                    pts.append((float(v0[0]), float(v0[1])))
                    pts.append((float(v1[0]), float(v1[1])))

        # De-duplicate and align relative to helipad center
        unique_pts = []
        seen = set()
        for p in pts:
            rel_x = p[0] - pad_center_x
            rel_y = p[1] - hy
            key = (round(rel_x, 3), round(rel_y, 3))
            if key not in seen:
                seen.add(key)
                unique_pts.append((round(rel_x, 3), round(rel_y, 3)))
        unique_pts.sort(key=lambda item: item[0])
        self._terrain_coords = unique_pts

    def claim_ownership(self, new_owner_id: str) -> int:
        """Atomically transfers ownership to a new controller, advancing the generation token.
        
        Blocks until any active physics step in a worker thread has finished,
        preventing concurrent execution or state corruption during takeover.
        """
        with self._step_lock:
            self.step_generation += 1
            self.owner_id = new_owner_id
            return self.step_generation

    def reset(self, new_seed: Optional[int] = None) -> SimulationSnapshotPayload:
        """Resets the simulation session cleanly for a new episode."""
        with self._step_lock:
            if new_seed is not None:
                self.seed = new_seed
            else:
                self.seed += 1
                self.episode_id += 1

            self.last_obs, _ = self.env.reset(seed=self.seed)
            self.latch = TerminalStateLatch()
            self.step_count = 0
            self.sim_time = 0.0
            self.cumulative_reward = 0.0
            self.last_reward = 0.0
            self.terminated = False
            self.truncated = False
            self.outcome = None
            self.last_action = 0
            self.is_paused = False

            self._cache_static_geometry()
            return self.extract_snapshot()

    def step_ai(self, model: Any, generation: Optional[int] = None) -> SimulationSnapshotPayload:
        """Advances simulation by 1 step (0.02s) using preloaded PPO model."""
        with self._step_lock:
            if generation is not None and generation != self.step_generation:
                return self.extract_snapshot()

            if self.is_done():
                return self.extract_snapshot()

            # Check latch before predicting
            is_latched = self.latch.check_and_update(
                obs=self.last_obs,
                terminated=self.terminated,
                truncated=self.truncated,
                step=self.step_count,
            )

            if is_latched:
                action = 0
            else:
                deterministic = (self.policy_mode == PolicyMode.DETERMINISTIC)
                action_pred, _ = model.predict(self.last_obs, deterministic=deterministic)
                action = self.latch.filter_action(int(action_pred))

            return self._execute_step(action)

    def step_human(self, action: int, generation: Optional[int] = None) -> SimulationSnapshotPayload:
        """Advances simulation by 1 step (0.02s) using validated human input.
        
        Raises ValueError if action is not an integer in {0, 1, 2, 3}.
        """
        with self._step_lock:
            if generation is not None and generation != self.step_generation:
                return self.extract_snapshot()

            if self.is_done():
                return self.extract_snapshot()

            # Strict validation: Reject non-integers, booleans, and out-of-range values
            if not isinstance(action, int) or isinstance(action, bool) or action not in (0, 1, 2, 3):
                raise ValueError(
                    f"Invalid discrete action '{action}'. Action must be an integer in {{0, 1, 2, 3}}."
                )

            # Filter through latch (e.g. terminal propulsion shutdown)
            self.latch.check_and_update(
                obs=self.last_obs,
                terminated=self.terminated,
                truncated=self.truncated,
                step=self.step_count,
            )
            filtered_action = self.latch.filter_action(action)

            return self._execute_step(filtered_action)

    def _execute_step(self, action: int) -> SimulationSnapshotPayload:
        """Executes a single authoritative Box2D physics step."""
        self.last_action = action
        obs, reward, term, trunc, _ = self.env.step(action)
        self.last_obs = obs
        self.last_reward = float(reward)
        self.cumulative_reward += float(reward)
        self.step_count += 1
        self.sim_time = self.step_count * PHYSICS_DT

        # Check hard maximum step cutoff
        if self.step_count >= MAX_EPISODE_STEPS:
            trunc = True

        self.terminated = bool(term)
        self.truncated = bool(trunc)

        # Update latch with step results
        self.latch.check_and_update(
            obs=obs,
            terminated=self.terminated,
            truncated=self.truncated,
            step=self.step_count,
        )

        # Terminal state progression
        if self.terminated or self.truncated:
            raw_outcome = classify_outcome(
                terminated=self.terminated,
                truncated=self.truncated,
                final_step_reward=self.last_reward,
                final_obs=obs,
                criteria=self.criteria,
            )
            self.outcome = raw_outcome.upper()
        elif self.latch.is_latched:
            self.latch.ground_settle_steps += 1
            if self.latch.ground_settle_steps >= self.latch.settle_budget_steps:
                self.terminated = True
                raw_outcome = classify_outcome(
                    terminated=True,
                    truncated=False,
                    final_step_reward=self.last_reward,
                    final_obs=obs,
                    criteria=self.criteria,
                )
                self.outcome = raw_outcome.upper()

        return self.extract_snapshot()

    def is_done(self) -> bool:
        """Returns True if the episode has reached a terminal or truncated state."""
        return self.terminated or self.truncated

    def extract_snapshot(self) -> SimulationSnapshotPayload:
        """Serializes current authoritative Box2D state into a validated snapshot."""
        unwrapped = self.env.unwrapped
        lander = getattr(unwrapped, "lander", None)
        pad_center_x = (self._helipad_bounds[0] + self._helipad_bounds[1]) * 0.5
        helipad_y = self._helipad_bounds[2]

        leg_rest_offset = 0.592
        if lander is not None:
            pos_x = float(lander.position.x) - pad_center_x
            altitude = max(0.0, float(lander.position.y) - helipad_y - leg_rest_offset)
            pos_y = float(lander.position.y)
            angle = float(lander.angle)
            vel_x = float(lander.linearVelocity.x)
            vel_y = float(lander.linearVelocity.y)
            ang_vel = float(lander.angularVelocity)
        else:
            pos_x = float(self.last_obs[0] * 10.0)
            altitude = max(0.0, float(self.last_obs[1] * 6.666))
            pos_y = 0.67 + altitude
            angle = float(self.last_obs[4])
            vel_x = float(self.last_obs[2] * 5.0)
            vel_y = float(self.last_obs[3] * 5.0)
            ang_vel = float(self.last_obs[5])

        # Contacts directly from Box2D sensors
        legs = getattr(unwrapped, "legs", None)
        if legs and len(legs) >= 2:
            left_contact = bool(legs[0].ground_contact)
            right_contact = bool(legs[1].ground_contact)
        else:
            left_contact = bool(self.last_obs[6] > 0.5)
            right_contact = bool(self.last_obs[7] > 0.5)

        # Aerodynamic wind forces
        enable_wind = bool(getattr(unwrapped, "enable_wind", False))
        wind_power = float(getattr(unwrapped, "wind_power", 0.0))
        wind_idx = int(getattr(unwrapped, "wind_idx", 0))
        if enable_wind:
            wind_force = float(math.tanh(math.sin(0.02 * wind_idx) + math.sin(math.pi * 0.01 * wind_idx)) * wind_power)
            turbulence = float(math.tanh(math.sin(0.01 * wind_idx)) * self.turbulence)
        else:
            wind_force = 0.0
            turbulence = 0.0

        # Propulsion status (zeroed if latched or done)
        if self.is_done() or self.latch.is_latched:
            throttle = 0.0
            rcs_l = 0.0
            rcs_r = 0.0
            eff_action = 0
        else:
            eff_action = self.last_action
            throttle = 1.0 if eff_action == 2 else 0.0
            rcs_l = 1.0 if eff_action == 1 else 0.0
            rcs_r = 1.0 if eff_action == 3 else 0.0

        imp = self.latch.first_contact
        imp_vx = imp.vel_x if imp else None
        imp_vy = imp.vel_y if imp else None
        imp_tilt = imp.tilt_rad if imp else None

        return SimulationSnapshotPayload(
            protocol_version="1.0.0",
            session_id=self.session_id,
            episode_id=self.episode_id,
            kinematics=Kinematics2D(
                pos_x=pos_x,
                pos_y=pos_y,
                vel_x=vel_x,
                vel_y=vel_y,
                angle=angle,
                ang_vel=ang_vel,
                altitude=altitude,
            ),
            propulsion=PropulsionState(
                action=eff_action,
                throttle=throttle,
                rcs_left=rcs_l,
                rcs_right=rcs_r,
            ),
            landing_gear=LandingGearState(
                left_contact=left_contact,
                right_contact=right_contact,
            ),
            atmosphere=AtmosphereState(
                wind_force=wind_force,
                turbulence=turbulence,
            ),
            lifecycle=LifecycleState(
                step=self.step_count,
                sim_time=self.sim_time,
                touchdown_phase=self.latch.touchdown_phase,
                step_reward=self.last_reward,
                cumulative_reward=self.cumulative_reward,
                terminated=self.terminated,
                truncated=self.truncated,
                outcome=self.outcome,
            ),
            impact=ImpactTelemetry(
                impact_vel_x=imp_vx,
                impact_vel_y=imp_vy,
                impact_tilt=imp_tilt,
            ),
        )

    def get_session_ready_payload(self) -> SessionReadyPayload:
        """Returns the initial session configuration and static environment geometry."""
        return SessionReadyPayload(
            session_id=self.session_id,
            dt=PHYSICS_DT,
            mode=self.mode,
            policy_mode=self.policy_mode,
            seed=self.seed,
            helipad_bounds=self._helipad_bounds,
            terrain=self._terrain_coords,
        )

    def get_episode_complete_payload(self) -> EpisodeCompletePayload:
        """Constructs final debrief report on episode termination."""
        imp = self.latch.first_contact
        snap = self.extract_snapshot()
        return EpisodeCompletePayload(
            session_id=self.session_id,
            episode_id=self.episode_id,
            outcome=self.outcome or "UNKNOWN",
            total_steps=self.step_count,
            total_sim_time=self.sim_time,
            cumulative_reward=self.cumulative_reward,
            impact_vel_x=imp.vel_x if imp else None,
            impact_vel_y=imp.vel_y if imp else None,
            impact_tilt_deg=math.degrees(imp.tilt_rad) if imp else None,
            final_clearance=snap.kinematics.altitude,
            final_tilt_deg=math.degrees(snap.kinematics.angle),
        )

    def close(self) -> None:
        """Releases the underlying Box2D C++ environment resources."""
        with self._step_lock:
            if hasattr(self, "env") and self.env is not None:
                try:
                    self.env.close()
                except Exception:
                    pass
                self.env = None
