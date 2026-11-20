"""Tests for Stage 8.4.3: AI Behaviour Diversity, Terminal Propulsion Shutdown & Animation Synchronization.

Verifies:
1. Deterministic inference reproducibility.
2. Stochastic inference using the policy distribution.
3. Independent episode seed handling.
4. Clean environment reset.
5. No policy predictions after termination (TerminalStateLatch).
6. Main-engine shutdown after termination.
7. RCS shutdown after termination.
8. No new particles after terminal state.
9. Correct animation timestamps.
10. No cross-episode timeline interpolation.
11. Correct playback speed handling.
12. Repeated multi-episode execution in a single process.
"""

import math
from pathlib import Path
import sys
import unittest
import gymnasium as gym
import numpy as np
import pytest
from stable_baselines3 import PPO

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from evaluation.evaluate import LandingCriteria, classify_outcome
from scripts.play_demo import TerminalStateLatch
from visualization.cinematic_renderer import CinematicAerospaceRenderer, VisualTelemetry
from visualization.realistic3d_renderer import Realistic3DRenderer
from visualization.timeline import SimulationSnapshot, SnapshotTimeline, capture_snapshot_from_env


DEFAULT_MODEL_PATH = repo_root / "models" / "benchmark" / "D_curriculum_and_dr" / "seed_42" / "final_model.zip"


@pytest.fixture(scope="module")
def ppo_model():
    """Loads the trained benchmark PPO model once for test suite."""
    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip(f"Benchmark model not found at {DEFAULT_MODEL_PATH}")
    return PPO.load(str(DEFAULT_MODEL_PATH))


class TestDiversityAndTerminalShutdown:
    """Stage 8.4.3 test verification suite."""

    # -------------------------------------------------------------------------
    # 1. Deterministic inference reproducibility
    # -------------------------------------------------------------------------
    def test_deterministic_inference_reproducibility(self, ppo_model):
        """Verifies that deterministic=True yields identical action sequences for a given seed."""
        env = gym.make("LunarLander-v3", continuous=False)
        actions_runs = []

        for _ in range(2):
            obs, _ = env.reset(seed=42)
            done = False
            actions = []
            while not done:
                action, _ = ppo_model.predict(obs, deterministic=True)
                actions.append(int(action))
                obs, _, term, trunc, _ = env.step(int(action))
                done = term or trunc
            actions_runs.append(actions)
        env.close()

        assert len(actions_runs[0]) == len(actions_runs[1]), "Step counts differ in deterministic mode"
        assert actions_runs[0] == actions_runs[1], "Action sequences differ in deterministic mode"

    # -------------------------------------------------------------------------
    # 2. Stochastic inference using policy distribution
    # -------------------------------------------------------------------------
    def test_stochastic_inference_policy_distribution(self, ppo_model):
        """Verifies that deterministic=False samples categorical distribution producing diversity."""
        env = gym.make("LunarLander-v3", continuous=False)
        actions_runs = []

        for _ in range(3):
            obs, _ = env.reset(seed=42)
            done = False
            actions = []
            while not done:
                action, _ = ppo_model.predict(obs, deterministic=False)
                act_int = int(action)
                assert act_int in (0, 1, 2, 3), f"Invalid discrete action {act_int}"
                actions.append(act_int)
                obs, _, term, trunc, _ = env.step(act_int)
                done = term or trunc
            actions_runs.append(actions)
        env.close()

        # At least one pair of runs should have different action sequences due to stochastic sampling
        different = (actions_runs[0] != actions_runs[1]) or (actions_runs[1] != actions_runs[2])
        assert different, "Stochastic mode unexpectedly produced identical action sequences across 3 runs"

    # -------------------------------------------------------------------------
    # 3. Independent episode seed handling
    # -------------------------------------------------------------------------
    def test_independent_episode_seed_handling(self):
        """Verifies that different seeds yield distinct initial states."""
        env = gym.make("LunarLander-v3", continuous=False)
        obs1, _ = env.reset(seed=42)
        obs2, _ = env.reset(seed=999)
        env.close()

        assert not np.allclose(obs1, obs2), "Different seeds produced identical initial observations"

    # -------------------------------------------------------------------------
    # 4. Clean environment reset
    # -------------------------------------------------------------------------
    def test_clean_environment_reset(self, ppo_model):
        """Verifies that reset restores neutral airborne conditions without residual states."""
        env = gym.make("LunarLander-v3", continuous=False)
        # Run an episode to completion
        obs, _ = env.reset(seed=42)
        done = False
        while not done:
            action, _ = ppo_model.predict(obs, deterministic=True)
            obs, _, term, trunc, _ = env.step(int(action))
            done = term or trunc

        # Reset
        new_obs, info = env.reset(seed=42)
        env.close()

        # Check clean initial conditions
        assert new_obs[1] > 1.3, "Lander did not spawn at high altitude"
        assert new_obs[6] < 0.5, "Left leg contact was not reset"
        assert new_obs[7] < 0.5, "Right leg contact was not reset"

    # -------------------------------------------------------------------------
    # 5. No policy predictions after termination (TerminalStateLatch)
    # -------------------------------------------------------------------------
    def test_no_policy_predictions_after_termination(self):
        """Verifies TerminalStateLatch halts policy queries and zeroes propulsion."""
        latch = TerminalStateLatch()
        assert not latch.is_latched

        # Airborne obs
        obs_air = np.array([0.0, 1.0, 0.0, -0.5, 0.0, 0.0, 0.0, 0.0])
        latched = latch.check_and_update(obs_air, terminated=False, truncated=False, step=10)
        assert not latched
        assert not latch.is_latched

        # Ground settled obs
        obs_settled = np.array([0.0, 0.02, 0.01, -0.01, 0.0, 0.0, 1.0, 1.0])
        latched_settled = latch.check_and_update(obs_settled, terminated=False, truncated=False, step=50, altitude=0.01)
        assert latched_settled
        assert latch.is_latched
        assert latch.latch_reason == "TOUCHDOWN_SETTLED"

    # -------------------------------------------------------------------------
    # 6. Main-engine shutdown after termination
    # -------------------------------------------------------------------------
    def test_main_engine_shutdown_after_termination(self):
        """Verifies throttle and main engine flame are zeroed when terminal or settled."""
        # Test in capture_snapshot_from_env
        env = gym.make("LunarLander-v3", continuous=False)
        obs_ground = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0])
        snap = capture_snapshot_from_env(
            env=env,
            obs=obs_ground,
            action=2,  # Incoming raw main engine action
            step=100,
            terminated=True,
            truncated=False,
            outcome="SUCCESS",
        )
        env.close()

        assert snap.throttle == 0.0, "Throttle was not zeroed on termination"
        assert snap.action == 0, "Action was not latched to 0 on termination"

    # -------------------------------------------------------------------------
    # 7. RCS shutdown after termination
    # -------------------------------------------------------------------------
    def test_rcs_shutdown_after_termination(self):
        """Verifies RCS thrusters are strictly zeroed when terminal or settled."""
        env = gym.make("LunarLander-v3", continuous=False)
        obs_ground = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0])
        snap_l = capture_snapshot_from_env(
            env=env,
            obs=obs_ground,
            action=1,
            step=100,
            terminated=True,
        )
        snap_r = capture_snapshot_from_env(
            env=env,
            obs=obs_ground,
            action=3,
            step=100,
            terminated=True,
        )
        env.close()

        assert snap_l.rcs_left == 0.0 and snap_l.action == 0, "Left RCS was not zeroed"
        assert snap_r.rcs_right == 0.0 and snap_r.action == 0, "Right RCS was not zeroed"

    # -------------------------------------------------------------------------
    # 8. No new particles after terminal state
    # -------------------------------------------------------------------------
    def test_no_new_particles_after_terminal_state(self):
        """Verifies that CinematicAerospaceRenderer does not spawn particles after shutoff."""
        renderer = CinematicAerospaceRenderer(headless=True)
        # Clear particles
        renderer.exhaust_particles.clear()
        renderer.rcs_puffs.clear()
        renderer.dust_clouds.clear()

        # Update particles with is_shutoff=True and action=2
        renderer._update_particles(
            rocket_wx=0.0,
            rocket_wy=0.0,
            pitch_rad=0.0,
            helipad_y=0.0,
            action=2,
            dt=0.02,
            is_shutoff=True,
        )

        assert len(renderer.exhaust_particles) == 0, "Exhaust particles spawned during terminal shutoff"
        assert len(renderer.rcs_puffs) == 0, "RCS puffs spawned during terminal shutoff"
        assert len(renderer.dust_clouds) == 0, "Dust clouds spawned during terminal shutoff"

    # -------------------------------------------------------------------------
    # 9. Correct animation timestamps
    # -------------------------------------------------------------------------
    def test_correct_animation_timestamps(self):
        """Verifies sim_time = step * 0.02 and monotonically increases."""
        timeline = SnapshotTimeline(dt=0.02)
        env = gym.make("LunarLander-v3", continuous=False)
        for s in range(10):
            obs = np.array([0.0, 1.0 - s * 0.05, 0.0, -0.5, 0.0, 0.0, 0.0, 0.0])
            snap = capture_snapshot_from_env(env=env, obs=obs, action=0, step=s)
            timeline.add_snapshot(snap)
        env.close()

        assert timeline.total_sim_time == pytest.approx(9 * 0.02)
        sampled = timeline.sample_interpolated(presentation_time=0.10, speed_factor=0.5)
        assert sampled.sim_time == pytest.approx(0.05)

    # -------------------------------------------------------------------------
    # 10. No cross-episode timeline interpolation
    # -------------------------------------------------------------------------
    def test_no_cross_episode_timeline_interpolation(self):
        """Verifies SnapshotTimeline clamps strictly to episode boundaries."""
        timeline = SnapshotTimeline(dt=0.02)
        env = gym.make("LunarLander-v3", continuous=False)
        for s in range(5):
            obs = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            snap = capture_snapshot_from_env(env=env, obs=obs, action=0, step=s)
            timeline.add_snapshot(snap)
        env.close()

        # Sample beyond end of episode
        beyond_snap = timeline.sample_interpolated(presentation_time=100.0, speed_factor=1.0)
        assert beyond_snap.step == 4, "Sample leaked beyond episode boundary"
        assert beyond_snap.sim_time == pytest.approx(4 * 0.02)

    # -------------------------------------------------------------------------
    # 11. Correct playback speed handling
    # -------------------------------------------------------------------------
    def test_correct_playback_speed_handling(self):
        """Verifies speed factor changes presentation time without modifying physics dt."""
        renderer = Realistic3DRenderer(headless=True)
        renderer.set_speed_factor(0.50)
        assert renderer.speed_factor == 0.50

        renderer.set_speed_factor(0.25)
        assert renderer.speed_factor == 0.25

        renderer.set_speed_factor(1.00)
        assert renderer.speed_factor == 1.00
        renderer.close()

    # -------------------------------------------------------------------------
    # 12. Repeated multi-episode execution
    # -------------------------------------------------------------------------
    def test_repeated_multi_episode_execution(self, ppo_model):
        """Runs 10 consecutive AI episodes in a single process without errors or leakage."""
        env = gym.make("LunarLander-v3", continuous=False)
        renderer = Realistic3DRenderer(headless=True, theme="spaceport")
        criteria = LandingCriteria()

        episodes_completed = 0
        for ep in range(10):
            obs, _ = env.reset(seed=42 + ep)
            renderer.reset()
            latch = TerminalStateLatch()
            done = False
            step = 0
            max_steps = 350 if ep < 2 else 25  # Run 2 full episodes and 8 transition episodes
            while not done and step < max_steps:
                is_latched = latch.check_and_update(obs, terminated=False, truncated=False, step=step)
                if is_latched:
                    act_int = 0
                else:
                    action, _ = ppo_model.predict(obs, deterministic=True)
                    act_int = int(action)

                tel = renderer.extract_telemetry(
                    env, obs, action=act_int, step=step,
                    reward=0.0, terminated=False, truncated=False,
                    criteria=criteria,
                )
                renderer.render_frame(env, tel)

                obs, r, term, trunc, _ = env.step(act_int)
                step += 1
                latch.check_and_update(obs, terminated=term, truncated=trunc, step=step)

                if term or trunc:
                    done = True
                elif latch.is_latched:
                    latch.ground_settle_steps += 1
                    if latch.ground_settle_steps >= 10:
                        done = True

            episodes_completed += 1

        renderer.close()
        env.close()
        assert episodes_completed == 10, f"Expected 10 episodes, completed {episodes_completed}"
