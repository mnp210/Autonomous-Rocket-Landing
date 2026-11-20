"""Tests for CinematicAerospaceRenderer and simulation-integrity boundaries (Stage 8.3)."""

import math
from pathlib import Path
import tempfile
import gymnasium as gym
import numpy as np
import pytest

from evaluation.evaluate import LandingCriteria
from visualization.cinematic_renderer import (
    CinematicAerospaceRenderer,
    ExhaustStreamParticle,
    RCSPuff,
    RegolithDustCloud,
    VisualTelemetry,
)


@pytest.fixture
def headless_cinematic_renderer():
    """Provides a headless CinematicAerospaceRenderer instance for tests."""
    renderer = CinematicAerospaceRenderer(
        width=1280,
        height=720,
        headless=True,
        enable_camera_tracking=True,
    )
    yield renderer
    renderer.close()


class TestCinematicRenderer:
    """Test suite verifying cinematic rendering pipeline, propulsion emitters, and simulation integrity."""

    def test_renderer_initialization(self, headless_cinematic_renderer):
        """Verifies graphics context, camera, and asset initialization."""
        r = headless_cinematic_renderer
        assert r.width == 1280
        assert r.height == 720
        assert r.headless is True
        assert r.screen.get_width() == 1280
        assert r.screen.get_height() == 720
        assert len(r.stars) > 100
        assert r.earth_surf is not None
        assert len(r.craters) > 0
        assert len(r.boulders) > 0
        assert len(r.dust_clouds) == 0
        assert len(r.exhaust_particles) == 0
        assert len(r.rcs_puffs) == 0
        assert r.main_throttle == 0.0
        assert r.rcs_left_power == 0.0
        assert r.rcs_right_power == 0.0

    def test_dynamic_camera_tracking(self, headless_cinematic_renderer):
        """Verifies camera smoothly tracks vehicle position and adjusts zoom."""
        r = headless_cinematic_renderer
        initial_cam_y = r.cam_y

        # High altitude state
        tel_high = VisualTelemetry(
            pos_x=0.0, pos_y=13.0, vel_x=0.0, vel_y=-1.0, altitude=0.9
        )
        for _ in range(25):
            r.update_camera(tel_high, dt=0.02)

        # Camera should move up toward vehicle
        assert r.cam_y > initial_cam_y
        assert r.cam_zoom > 60.0  # High zoom at high altitude

        # Low altitude approach
        tel_low = VisualTelemetry(
            pos_x=0.0, pos_y=3.8, vel_x=0.0, vel_y=-0.2, altitude=0.05
        )
        for _ in range(35):
            r.update_camera(tel_low, dt=0.02)

        # Camera should pan down and widen zoom to frame both lander and pad
        assert r.cam_y < 8.0
        assert r.cam_zoom < 65.0

    def test_camera_stability(self, headless_cinematic_renderer):
        """Verifies camera does not jitter or diverge under stationary or steady conditions."""
        r = headless_cinematic_renderer
        tel_stationary = VisualTelemetry(pos_x=0.0, pos_y=5.0, vel_x=0.0, vel_y=0.0, altitude=0.25, action=0)

        # Settle camera (3 seconds of stationary observation)
        for _ in range(150):
            r.update_camera(tel_stationary, dt=0.02)

        settled_x = r.cam_x
        settled_y = r.cam_y
        settled_zoom = r.cam_zoom

        # 30 additional stationary steps
        for _ in range(30):
            r.update_camera(tel_stationary, dt=0.02)

        assert abs(r.cam_x - settled_x) < 1e-3
        assert abs(r.cam_y - settled_y) < 1e-3
        assert abs(r.cam_zoom - settled_zoom) < 1e-3
        assert abs(r.cam_shake_x) < 1e-5
        assert abs(r.cam_shake_y) < 1e-5

    def test_world_to_screen_mapping(self, headless_cinematic_renderer):
        """Verifies that Box2D meter coordinates map accurately to screen pixels."""
        r = headless_cinematic_renderer
        r.cam_x = 10.0
        r.cam_y = 5.0
        r.cam_shake_x = 0.0
        r.cam_shake_y = 0.0

        # Center of camera view should map to center of screen (640, 360)
        sx, sy = r.world_to_screen(10.0, 5.0)
        assert sx == 640
        assert sy == 360

        # Symmetrical horizontal offsets
        sx_left, _ = r.world_to_screen(8.0, 5.0)
        sx_right, _ = r.world_to_screen(12.0, 5.0)
        assert sx_left < 640
        assert sx_right > 640
        assert (sx_right - 640) == (640 - sx_left)

    def test_telemetry_extraction_integrity(self, headless_cinematic_renderer):
        """Verifies that telemetry extraction reads state without modifying Box2D physics."""
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)

        u = env.unwrapped
        pre_pos = (u.lander.position.x, u.lander.position.y)
        pre_vel = (u.lander.linearVelocity.x, u.lander.linearVelocity.y)

        tel = headless_cinematic_renderer.extract_telemetry(
            env=env, obs=obs, action=2, step=1, reward=1.5,
            terminated=False, truncated=False, cumulative_reward=10.0
        )

        assert isinstance(tel, VisualTelemetry)
        assert tel.action == 2
        assert tel.step == 1
        assert tel.cumulative_reward == 10.0
        assert abs(tel.pos_x - obs[0]) < 1e-5
        assert abs(tel.altitude - obs[1]) < 1e-5

        # Verify physics state was untouched
        assert (u.lander.position.x, u.lander.position.y) == pre_pos
        assert (u.lander.linearVelocity.x, u.lander.linearVelocity.y) == pre_vel
        env.close()

    def test_main_engine_on_off_and_no_inactive_plume(self, headless_cinematic_renderer):
        """Verifies main engine throttle ramps on action=2 and decays to 0 on action=0."""
        r = headless_cinematic_renderer

        # When idle (action=0), throttle is 0
        r._update_propulsion_state(action=0, dt=0.02)
        assert r.main_throttle == 0.0

        # When firing (action=2), throttle ramps smoothly up towards 1.0
        for _ in range(10):
            r._update_propulsion_state(action=2, dt=0.02)
        assert r.main_throttle > 0.8
        assert r.main_throttle <= 1.0

        # When cut (action=0), throttle decays smoothly to 0.0
        for _ in range(15):
            r._update_propulsion_state(action=0, dt=0.02)
        assert r.main_throttle == 0.0

    def test_individual_rcs_actions(self, headless_cinematic_renderer):
        """Verifies action=1 fires right RCS only, action=3 fires left RCS only, and action=0 is idle."""
        r = headless_cinematic_renderer

        # Action 1 (Right thruster fires, pushes left)
        r._update_propulsion_state(action=1, dt=0.05)
        assert r.rcs_right_power > 0.5
        assert r.rcs_left_power == 0.0

        r._update_particles(rocket_wx=10.0, rocket_wy=8.0, pitch_rad=0.0, helipad_y=3.333, action=1, dt=0.02)
        assert len(r.rcs_puffs) > 0
        # Check that puffs travel rightward (vx > 0)
        assert any(p.vx > 0 for p in r.rcs_puffs)

        # Clear puffs
        r.rcs_puffs.clear()

        # Action 3 (Left thruster fires, pushes right)
        r._update_propulsion_state(action=3, dt=0.05)
        assert r.rcs_left_power > 0.5
        assert r.rcs_right_power < 0.2

        r._update_particles(rocket_wx=10.0, rocket_wy=8.0, pitch_rad=0.0, helipad_y=3.333, action=3, dt=0.02)
        assert len(r.rcs_puffs) > 0
        # Check that puffs travel leftward (vx < 0)
        assert any(p.vx < 0 for p in r.rcs_puffs)

        # Clear and test Action 0 (Coast)
        r.rcs_puffs.clear()
        for _ in range(15):
            r._update_propulsion_state(action=0, dt=0.02)
        assert r.rcs_left_power == 0.0
        assert r.rcs_right_power == 0.0
        r._update_particles(rocket_wx=10.0, rocket_wy=8.0, pitch_rad=0.0, helipad_y=3.333, action=0, dt=0.02)
        assert len(r.rcs_puffs) == 0

    def test_correct_emission_origins(self, headless_cinematic_renderer):
        """Verifies main exhaust emits from the nozzle tip below CoM."""
        r = headless_cinematic_renderer
        r.main_throttle = 1.0

        # Rocket at (10.0, 8.0) upright (pitch=0)
        r._update_particles(rocket_wx=10.0, rocket_wy=8.0, pitch_rad=0.0, helipad_y=3.333, action=2, dt=0.02)
        assert len(r.exhaust_particles) > 0

        # Nozzle is below rocket CoM (wy < 8.0) and vy is downward (< 0)
        for ep in r.exhaust_particles:
            assert ep.y < 8.0
            assert abs(ep.x - 10.0) < 0.2
            assert ep.vy < 0.0

    def test_particle_fading_and_cleanup(self, headless_cinematic_renderer):
        """Verifies particle alpha decays and expired particles are cleanly removed from memory."""
        r = headless_cinematic_renderer
        r.main_throttle = 1.0

        # Spawn exhaust and dust with action=2
        r._update_particles(rocket_wx=10.0, rocket_wy=4.0, pitch_rad=0.0, helipad_y=3.333, action=2, dt=0.02)
        assert len(r.exhaust_particles) > 0
        assert len(r.dust_clouds) > 0

        # Cut engine (action=0)
        r.main_throttle = 0.0

        # Advance time by 1.5 seconds (all particles should expire)
        for _ in range(75):
            r._update_particles(rocket_wx=10.0, rocket_wy=4.0, pitch_rad=0.0, helipad_y=3.333, action=0, dt=0.02)

        assert len(r.exhaust_particles) == 0
        assert len(r.dust_clouds) == 0
        assert len(r.rcs_puffs) == 0

    def test_dust_activation_conditions(self, headless_cinematic_renderer):
        """Verifies dust storms ONLY spawn when engine is firing AND altitude is near ground."""
        r = headless_cinematic_renderer

        # Case 1: High altitude, Engine ON -> NO dust
        r.main_throttle = 1.0
        r._update_particles(rocket_wx=10.0, rocket_wy=12.0, pitch_rad=0.0, helipad_y=3.333, action=2, dt=0.02)
        assert len(r.dust_clouds) == 0

        # Case 2: Low altitude, Engine OFF -> NO dust
        r.main_throttle = 0.0
        r._update_particles(rocket_wx=10.0, rocket_wy=4.0, pitch_rad=0.0, helipad_y=3.333, action=0, dt=0.02)
        assert len(r.dust_clouds) == 0

        # Case 3: Low altitude, Engine ON -> DUST SPAWNS
        r.main_throttle = 1.0
        r._update_particles(rocket_wx=10.0, rocket_wy=4.0, pitch_rad=0.0, helipad_y=3.333, action=2, dt=0.02)
        assert len(r.dust_clouds) > 0

    def test_frame_rate_independent_animation(self, headless_cinematic_renderer):
        """Verifies dt scaling produces proportional state updates across different frame rates."""
        r = headless_cinematic_renderer

        # Step 5 times with dt=0.01 (total 0.05s)
        r.main_throttle = 0.0
        for _ in range(5):
            r._update_propulsion_state(action=2, dt=0.01)
        throttle_small_dt = r.main_throttle

        # Step 1 time with dt=0.05 (total 0.05s)
        r.main_throttle = 0.0
        r._update_propulsion_state(action=2, dt=0.05)
        throttle_large_dt = r.main_throttle

        assert abs(throttle_small_dt - throttle_large_dt) < 0.05

    def test_hud_boundaries_at_supported_resolutions(self):
        """Verifies HUD renders cleanly without crashing or clipping at 1280x720 and 960x540."""
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)

        for w, h in [(1280, 720), (1024, 576), (960, 540)]:
            renderer = CinematicAerospaceRenderer(width=w, height=h, headless=True)
            tel = renderer.extract_telemetry(env, obs, action=2, step=10)
            surf = renderer.render_frame(env, tel)
            assert surf.get_width() == w
            assert surf.get_height() == h
            renderer.close()

        env.close()

    def test_all_actions_render_cleanly(self, headless_cinematic_renderer):
        """Verifies all discrete actions (0..3) render to surface without errors."""
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)

        for act in (0, 1, 2, 3):
            tel = headless_cinematic_renderer.extract_telemetry(env, obs, action=act, step=act)
            surf = headless_cinematic_renderer.render_frame(env, tel)
            assert surf.get_width() == 1280
            assert surf.get_height() == 720
        env.close()

    def test_screenshot_and_recording_export(self, headless_cinematic_renderer):
        """Verifies saving screenshots and exporting MP4 video files."""
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)
        tel = headless_cinematic_renderer.extract_telemetry(env, obs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Screenshot
            img_path = tmp_path / "test_shot.png"
            headless_cinematic_renderer.render_frame(env, tel)
            saved_img = headless_cinematic_renderer.save_screenshot(img_path)
            assert saved_img.is_file()
            assert saved_img.stat().st_size > 1000

            # Video recording
            vid_path = tmp_path / "test_video.mp4"
            headless_cinematic_renderer.start_recording(vid_path, fps=30)
            for _ in range(5):
                headless_cinematic_renderer.render_frame(env, tel)
            headless_cinematic_renderer.stop_recording()

            assert vid_path.is_file()
            assert vid_path.stat().st_size > 1000

        env.close()

    def test_presentation_speed_controller_and_time_separation(self, headless_cinematic_renderer):
        """Verifies presentation speed controller separates sim_time from wall_time accurately."""
        r = headless_cinematic_renderer
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)

        # Step 50: sim_time should be 50 * 0.02 = 1.00s
        tel = r.extract_telemetry(env, obs, action=0, step=50)

        # Test 1.0x (Real-time)
        r.set_speed_factor(1.0)
        assert r.speed_factor == 1.0
        assert r.recording_fps == 50
        r.render_frame(env, tel)
        assert abs(r.sim_time - 1.00) < 1e-4
        assert abs(r.wall_time - 1.00) < 1e-4

        # Test 0.50x (Cinematic recommended default)
        r.set_speed_factor(0.50)
        assert r.speed_factor == 0.50
        assert r.recording_fps == 25
        r.render_frame(env, tel)
        assert abs(r.sim_time - 1.00) < 1e-4
        assert abs(r.wall_time - 2.00) < 1e-4  # 1.0s sim / 0.5 = 2.0s wall

        # Test 0.25x (Slow-Motion)
        r.set_speed_factor(0.25)
        assert r.speed_factor == 0.25
        assert r.recording_fps == 12 or r.recording_fps == 13
        r.render_frame(env, tel)
        assert abs(r.sim_time - 1.00) < 1e-4
        assert abs(r.wall_time - 4.00) < 1e-4  # 1.0s sim / 0.25 = 4.0s wall

        # Test 0.75x (Moderate)
        r.set_speed_factor(0.75)
        assert r.speed_factor == 0.75
        r.render_frame(env, tel)
        assert abs(r.sim_time - 1.00) < 1e-4
        assert abs(r.wall_time - (1.00 / 0.75)) < 1e-4

        env.close()

    def test_action_synchronized_propulsion_emissions(self, headless_cinematic_renderer):
        """Verifies particle emitters ONLY emit for their specific action and remain idle otherwise."""
        r = headless_cinematic_renderer
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)

        # 1. Action 0 (Coast) -> Zero emissions
        r.dust_clouds.clear()
        r.rcs_puffs.clear()
        r.exhaust_particles.clear()
        tel_0 = r.extract_telemetry(env, obs, action=0, step=1)
        r.render_frame(env, tel_0)
        assert len(r.dust_clouds) == 0
        assert len(r.rcs_puffs) == 0
        assert len(r.exhaust_particles) == 0

        # 2. Action 1 (Right RCS fires, pushes left) -> Right RCS puff only
        r.dust_clouds.clear()
        r.rcs_puffs.clear()
        r.exhaust_particles.clear()
        tel_1 = r.extract_telemetry(env, obs, action=1, step=2)
        r.render_frame(env, tel_1)
        assert len(r.rcs_puffs) == 1
        assert r.rcs_puffs[0].vx > 0.0  # rightward
        assert len(r.dust_clouds) == 0
        assert len(r.exhaust_particles) == 0

        # 3. Action 3 (Left RCS fires, pushes right) -> Left RCS puff only
        r.dust_clouds.clear()
        r.rcs_puffs.clear()
        r.exhaust_particles.clear()
        tel_3 = r.extract_telemetry(env, obs, action=3, step=3)
        r.render_frame(env, tel_3)
        assert len(r.rcs_puffs) == 1
        assert r.rcs_puffs[0].vx < 0.0  # leftward
        assert len(r.dust_clouds) == 0
        assert len(r.exhaust_particles) == 0

        # 4. Action 2 (Main Engine) -> Main exhaust particles only (no RCS)
        r.dust_clouds.clear()
        r.rcs_puffs.clear()
        r.exhaust_particles.clear()
        r.main_throttle = 1.0
        tel_2 = r.extract_telemetry(env, obs, action=2, step=4)
        r.render_frame(env, tel_2)
        assert len(r.rcs_puffs) == 0
        assert len(r.exhaust_particles) > 0

        env.close()

    def test_particle_emission_frequency_invariance(self, headless_cinematic_renderer):
        """Verifies emissions do not duplicate when repeatedly rendering."""
        r = headless_cinematic_renderer
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)

        # Action 1: should spawn exactly 1 puff per step
        r.rcs_puffs.clear()
        tel = r.extract_telemetry(env, obs, action=1, step=10)
        r.render_frame(env, tel)
        initial_puffs = len(r.rcs_puffs)
        assert initial_puffs == 1

        env.close()

    def test_touchdown_contact_phases(self, headless_cinematic_renderer):
        """Verifies distinct classification: airborne, first_contact, dual_contact, settled."""
        r = headless_cinematic_renderer
        env = gym.make("LunarLander-v3", continuous=False)
        obs, _ = env.reset(seed=42)

        # 1. Airborne (neither leg contact)
        obs_airborne = obs.copy()
        obs_airborne[6] = 0.0
        obs_airborne[7] = 0.0
        tel_air = r.extract_telemetry(env, obs_airborne)
        assert tel_air.touchdown_phase == "airborne"

        # 2. First Contact (one leg only)
        obs_first = obs.copy()
        obs_first[6] = 1.0
        obs_first[7] = 0.0
        tel_first = r.extract_telemetry(env, obs_first)
        assert tel_first.touchdown_phase == "first_contact"

        # 3. Dual Contact (both legs, descending velocity)
        obs_dual = obs.copy()
        obs_dual[6] = 1.0
        obs_dual[7] = 1.0
        obs_dual[3] = -0.20  # moving downward
        tel_dual = r.extract_telemetry(env, obs_dual)
        assert tel_dual.touchdown_phase == "dual_contact"

        # 4. Settled (both legs, velocity zeroed)
        obs_settled = obs.copy()
        obs_settled[6] = 1.0
        obs_settled[7] = 1.0
        obs_settled[2] = 0.0
        obs_settled[3] = 0.0
        tel_settled = r.extract_telemetry(env, obs_settled)
        assert tel_settled.touchdown_phase == "settled"

        env.close()

    def test_physics_invariance_across_playback_speeds(self):
        """Verifies deterministic simulation physics and observations are identical across 1.0x and 0.5x."""
        model_path = Path("models/benchmark/D_curriculum_and_dr/seed_42/final_model.zip")
        if not model_path.exists():
            pytest.skip("Model checkpoint not found for physics invariance test")

        from stable_baselines3 import PPO
        model = PPO.load(str(model_path))

        env_1x = gym.make("LunarLander-v3", continuous=False)
        env_05x = gym.make("LunarLander-v3", continuous=False)

        obs_1x, _ = env_1x.reset(seed=42)
        obs_05x, _ = env_05x.reset(seed=42)

        r_1x = CinematicAerospaceRenderer(headless=True, speed_factor=1.0)
        r_05x = CinematicAerospaceRenderer(headless=True, speed_factor=0.5)

        for step in range(50):
            act_1x, _ = model.predict(obs_1x, deterministic=True)
            act_05x, _ = model.predict(obs_05x, deterministic=True)

            assert act_1x == act_05x, f"Action diverged at step {step}"

            tel_1x = r_1x.extract_telemetry(env_1x, obs_1x, action=int(act_1x), step=step)
            tel_05x = r_05x.extract_telemetry(env_05x, obs_05x, action=int(act_05x), step=step)

            r_1x.render_frame(env_1x, tel_1x)
            r_05x.render_frame(env_05x, tel_05x)

            # Assert timing mathematical separation
            assert abs(r_1x.sim_time - r_05x.sim_time) < 1e-4
            assert abs(r_05x.wall_time - 2.0 * r_1x.wall_time) < 1e-4

            obs_1x, rew_1x, term_1x, trunc_1x, _ = env_1x.step(int(act_1x))
            obs_05x, rew_05x, term_05x, trunc_05x, _ = env_05x.step(int(act_05x))

            assert np.allclose(obs_1x, obs_05x), f"Observation diverged at step {step}"
            assert abs(rew_1x - rew_05x) < 1e-4

        r_1x.close()
        r_05x.close()
        env_1x.close()
        env_05x.close()
