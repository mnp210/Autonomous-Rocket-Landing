"""Unit and regression tests for AerospaceRenderer.

Verifies:
1. Headless renderer initialization and canvas geometry (1280x720).
2. World-to-screen coordinate transformations and scaling.
3. Physical telemetry extraction from Box2D environment state.
4. Action-driven plume rendering across all discrete actions (0, 1, 2, 3).
5. HUD banner and mission debrief card states (success, crash, timeout, approach).
6. High-resolution screenshot capture and file integrity.
"""

from pathlib import Path
import tempfile
import numpy as np
import pytest
import gymnasium as gym

from evaluation.evaluate import LandingCriteria
from visualization.aerospace_renderer import AerospaceRenderer, VisualTelemetry


@pytest.fixture
def headless_renderer():
    """Provides a headless AerospaceRenderer instance."""
    renderer = AerospaceRenderer(width=1280, height=720, headless=True)
    yield renderer
    renderer.close()


@pytest.fixture
def sample_env():
    """Provides an initialized LunarLander-v3 environment."""
    env = gym.make("LunarLander-v3")
    obs, info = env.reset(seed=42)
    yield env, obs
    env.close()


class TestAerospaceRenderer:
    """Test suite for aerospace visualization engine."""

    def test_renderer_initialization(self, headless_renderer):
        """Verifies surface geometry, headless flag, fonts, and starfield."""
        assert headless_renderer.width == 1280
        assert headless_renderer.height == 720
        assert headless_renderer.headless is True
        assert headless_renderer.screen.get_size() == (1280, 720)
        assert len(headless_renderer.stars) == 140
        assert headless_renderer.font_large is not None
        assert headless_renderer.font_mono is not None

    def test_world_to_screen_mapping(self, headless_renderer):
        """Tests that Box2D meter coordinates map accurately to screen pixels."""
        helipad_y = 3.333

        # Pad center (X=10.0m, Y=helipad_y) must map exactly to pad center on screen (640, pad_screen_y)
        center_x, center_y = headless_renderer.world_to_screen(10.0, helipad_y, helipad_y)
        assert center_x == 640
        assert center_y == headless_renderer.pad_screen_y

        # Offset left (X=8.0m) and right (X=12.0m)
        left_x, _ = headless_renderer.world_to_screen(8.0, helipad_y, helipad_y)
        right_x, _ = headless_renderer.world_to_screen(12.0, helipad_y, helipad_y)
        assert left_x < 640
        assert right_x > 640
        assert (right_x - 640) == (640 - left_x)  # Symmetric

        # High altitude (Y=13.33m) must produce smaller Y (near top of screen)
        _, high_y = headless_renderer.world_to_screen(10.0, 13.333, helipad_y)
        assert high_y < center_y
        assert high_y > 0  # In viewport

    def test_telemetry_extraction(self, headless_renderer, sample_env):
        """Verifies physical telemetry extraction matches Box2D simulation state."""
        env, obs = sample_env
        criteria = LandingCriteria()

        tel = headless_renderer.extract_telemetry(
            env=env,
            obs=obs,
            action=2,
            step=10,
            reward=1.5,
            terminated=False,
            truncated=False,
            cumulative_reward=10.0,
            criteria=criteria,
        )

        assert isinstance(tel, VisualTelemetry)
        assert tel.step == 10
        assert tel.action == 2
        assert tel.cumulative_reward == 10.0
        assert isinstance(tel.altitude, float)
        assert isinstance(tel.pitch_deg, float)
        assert isinstance(tel.left_contact, bool)
        assert isinstance(tel.right_contact, bool)
        assert tel.outcome in ("descending", "approach")

    def test_render_all_discrete_actions(self, headless_renderer, sample_env):
        """Verifies rendering executes cleanly without exceptions for all actions."""
        env, obs = sample_env

        for act in [0, 1, 2, 3]:
            tel = headless_renderer.extract_telemetry(
                env=env,
                obs=obs,
                action=act,
                step=act * 10,
            )
            surf = headless_renderer.render_frame(env, tel)
            assert surf.get_size() == (1280, 720)

    def test_banner_and_debrief_outcome_states(self, headless_renderer, sample_env):
        """Verifies HUD status banners for all termination outcomes."""
        env, obs = sample_env

        outcomes = ["success", "crash", "timeout", "approach", "descending"]
        for out in outcomes:
            tel = VisualTelemetry(
                step=300,
                altitude=0.0 if out in ("success", "crash") else 1.2,
                pos_x=0.05,
                pos_y=3.333,
                vel_x=0.0,
                vel_y=0.0,
                pitch_deg=0.5,
                pitch_rad=0.01,
                action=0,
                left_contact=True,
                right_contact=True,
                cumulative_reward=240.0,
                terminated=(out in ("success", "crash")),
                truncated=(out == "timeout"),
                outcome=out,
            )
            surf = headless_renderer.render_frame(env, tel)
            assert surf.get_size() == (1280, 720)

    def test_screenshot_saving(self, headless_renderer, sample_env):
        """Verifies high-resolution screenshot export produces valid PNG file."""
        env, obs = sample_env
        tel = headless_renderer.extract_telemetry(env, obs, action=2, step=50)
        headless_renderer.render_frame(env, tel)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "test_screenshot.png"
            saved_path = headless_renderer.save_screenshot(out_file)

            assert saved_path.exists()
            assert saved_path.is_file()
            assert saved_path.stat().st_size > 10000  # Non-empty PNG
