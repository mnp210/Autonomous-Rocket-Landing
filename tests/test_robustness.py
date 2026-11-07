"""Unit and integration tests for Robustness Evaluation harness."""

from pathlib import Path
import tempfile
import gymnasium as gym
import numpy as np
import pytest
from stable_baselines3 import PPO

from environments.env_loader import make_environment
from evaluation.robustness_evaluation import (
    ROBUSTNESS_TEST_CONDITIONS,
    build_fixed_stress_environment,
    evaluate_robustness,
)


class TestRobustnessEvaluation:
    """Test suite verifying environmental stress testing and robustness benchmarking."""

    @pytest.fixture
    def smoke_model(self):
        """Creates a dummy untrained PPO model for smoke testing."""
        env = make_environment(env_id="LunarLander-v3")
        model = PPO("MlpPolicy", env, n_steps=64, batch_size=32, n_epochs=1, verbose=0)
        with tempfile.TemporaryDirectory() as tmp_dir:
            model_path = Path(tmp_dir) / "test_model.zip"
            model.save(str(model_path))
            yield model_path
        env.close()

    def test_condition_matrix_integrity(self):
        """Ensures all canonical conditions specify valid physical parameters and categories."""
        for name, cond in ROBUSTNESS_TEST_CONDITIONS.items():
            assert "category" in cond
            assert cond["category"] in ("in_distribution", "out_of_distribution")
            assert "gravity" in cond
            assert cond["gravity"] < 0.0  # Downward gravity
            assert "enable_wind" in cond
            assert "wind_power" in cond
            assert "turbulence_power" in cond

    def test_fixed_stress_environment_construction(self):
        """Building fixed stress environment sets Box2D world parameters accurately."""
        test_cond = {
            "gravity": -14.5,
            "enable_wind": True,
            "wind_power": 25.0,
            "turbulence_power": 2.8,
        }
        env = build_fixed_stress_environment(test_cond, seed=42)
        obs, info = env.reset(seed=42)

        assert pytest.approx(env.unwrapped.world.gravity.y, 1e-3) == -14.5
        assert env.unwrapped.enable_wind is True
        assert env.unwrapped.wind_power == 25.0
        assert env.unwrapped.turbulence_power == 2.8
        assert info["env_params"]["gravity"] == -14.5

        env.close()

    def test_robustness_evaluation_smoke_run(self, smoke_model):
        """Runs short multi-condition robustness evaluation verifying output structure."""
        with tempfile.TemporaryDirectory() as out_dir:
            # Subset of 2 conditions for fast execution
            test_subset = {
                "Nominal": {
                    "category": "in_distribution",
                    "description": "Standard",
                    "gravity": -10.0,
                    "enable_wind": False,
                    "wind_power": 0.0,
                    "turbulence_power": 0.0,
                },
                "Extreme_OOD": {
                    "category": "out_of_distribution",
                    "description": "OOD extreme",
                    "gravity": -15.0,
                    "enable_wind": True,
                    "wind_power": 30.0,
                    "turbulence_power": 3.0,
                },
            }

            scorecard = evaluate_robustness(
                model_path=smoke_model,
                episodes_per_condition=2,
                conditions=test_subset,
                output_dir=out_dir,
                seed=42,
            )

            assert "in_distribution" in scorecard
            assert "out_of_distribution" in scorecard
            assert "conditions" in scorecard
            assert len(scorecard["conditions"]) == 2

            assert Path(scorecard["saved_json"]).is_file()
            assert Path(scorecard["saved_csv"]).is_file()
