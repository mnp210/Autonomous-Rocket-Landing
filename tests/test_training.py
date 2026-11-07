"""Tests for training pipeline, callbacks, and evaluation metric computation."""

import json
from pathlib import Path
import tempfile
import numpy as np
import pytest
from stable_baselines3 import PPO

from environments.env_loader import make_environment
from training.train import train_baseline_agent
from training.callbacks import create_training_callbacks
from evaluation.evaluate import classify_outcome, evaluate_policy, save_evaluation_artifacts


class TestTrainingPipeline:
    """Test suite for training pipeline, callbacks, and evaluation logic."""

    def test_outcome_classification_logic(self):
        """Verifies deterministic outcome categorization based on physical criteria."""
        # Safe rest with high reward and legs touching pad
        safe_obs = np.array([0.05, 0.0, 0.01, -0.05, 0.02, 0.01, 1.0, 1.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=100.0, final_obs=safe_obs) == "success"

        # Crash with negative reward
        crash_obs = np.array([0.2, 0.0, 1.5, -2.5, 1.2, 3.0, 0.0, 0.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=-100.0, final_obs=crash_obs) == "crash"

        # Out of bounds
        oob_obs = np.array([1.2, 0.5, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=-100.0, final_obs=oob_obs) == "out_of_bounds"

        # Truncated / Timeout
        midair_obs = np.array([0.0, 0.5, 0.0, -0.1, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        assert classify_outcome(terminated=False, truncated=True, final_step_reward=-0.1, final_obs=midair_obs) == "timeout"

    def test_callback_generation_and_paths(self):
        """Verifies callback construction creates expected destination directories."""
        eval_env = make_environment(env_id="LunarLander-v3", continuous=False)
        with tempfile.TemporaryDirectory() as tmp_dir:
            chk_dir = Path(tmp_dir) / "checkpoints"
            best_dir = Path(tmp_dir) / "best_model"
            eval_log_dir = Path(tmp_dir) / "eval_log"

            callbacks = create_training_callbacks(
                eval_env=eval_env,
                checkpoint_dir=str(chk_dir),
                best_model_dir=str(best_dir),
                eval_log_dir=str(eval_log_dir),
                checkpoint_freq=128,
                eval_freq=128,
                n_eval_episodes=2,
                verbose=0,
            )
            assert len(callbacks.callbacks) == 3
            assert chk_dir.is_dir()
            assert best_dir.is_dir()
            assert eval_log_dir.is_dir()

        eval_env.close()

    def test_training_smoke_test(self):
        """Runs a short end-to-end training smoke test (256 timesteps) verifying full pipeline."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cfg_path = tmp_path / "test_cfg.yaml"

            test_config_content = f"""
algorithm:
  policy: "MlpPolicy"
  learning_rate: 0.0003
  n_steps: 128
  batch_size: 64
  n_epochs: 2
  gamma: 0.99
  gae_lambda: 0.95
  clip_range: 0.2
  verbose: 0

environment:
  env_id: "LunarLander-v3"
  continuous: false
  seed: 42

training:
  total_timesteps: 256
  eval_freq: 128
  eval_episodes: 2
  checkpoint_freq: 128
  log_interval: 1

paths:
  models_dir: "{tmp_path.as_posix()}/models"
  logs_dir: "{tmp_path.as_posix()}/logs"
  experiments_dir: "{tmp_path.as_posix()}/experiments"
"""
            cfg_path.write_text(test_config_content, encoding="utf-8")

            summary = train_baseline_agent(
                config_path=cfg_path,
                total_timesteps=256,
                seed=42,
                run_id="smoke_test_run",
                verbose=0,
            )

            assert summary["run_id"] == "smoke_test_run"
            assert Path(summary["final_model_path"]).is_file()
            assert Path(summary["config_snapshot"]).is_file()

            # Verify evaluation on saved model works
            loaded_model = PPO.load(summary["final_model_path"])
            eval_env = make_environment(env_id="LunarLander-v3", continuous=False)
            metrics, records = evaluate_policy(loaded_model, eval_env, n_episodes=3, deterministic=True)
            eval_env.close()

            assert metrics["n_episodes"] == 3
            assert "mean_episode_reward" in metrics
            assert "landing_success_rate" in metrics
            assert "crash_rate" in metrics
            assert len(records) == 3

            # Verify artifact export
            json_file, csv_file = save_evaluation_artifacts(metrics, records, tmp_path / "eval_out")
            assert json_file.is_file()
            assert csv_file.is_file()
