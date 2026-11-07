"""Unit and integration tests for Prompt 05 Benchmarking, Physical Criteria, and Statistics."""

import json
from pathlib import Path
import tempfile
import numpy as np
import pytest

from evaluation.evaluate import LandingCriteria, classify_outcome
from evaluation.statistical_analysis import (
    compute_confidence_interval,
    compute_welch_t_test,
    analyze_paradigm_runs,
    perform_comparative_statistical_analysis,
)
from training.benchmark_runner import run_benchmark_matrix, load_benchmark_config


class TestBenchmarkSuite:
    """Test suite verifying statistical analysis, landing criteria, and benchmark execution."""

    def test_strict_landing_criteria_validation(self):
        """Verifies that stricter physical criteria reject marginal or unsafe touchdown states."""
        crit = LandingCriteria(
            max_pad_offset_x=0.20,
            max_touchdown_vx=0.30,
            max_touchdown_vy=0.30,
            max_touchdown_tilt=0.15,
            max_touchdown_spin=0.20,
            require_both_legs=True,
        )

        # 1. Perfectly valid touchdown
        # [x, y, vx, vy, theta, theta_dot, left_contact, right_contact]
        valid_touchdown = np.array([0.05, 0.0, 0.10, -0.15, 0.05, 0.02, 1.0, 1.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=100.0, final_obs=valid_touchdown, criteria=crit) == "success"

        # 2. Excessive horizontal velocity (shear risk)
        high_vx_touchdown = np.array([0.05, 0.0, 0.55, -0.15, 0.05, 0.02, 1.0, 1.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=100.0, final_obs=high_vx_touchdown, criteria=crit) == "crash"

        # 3. Off-pad landing (landed beyond helipad flags)
        off_pad_touchdown = np.array([0.45, 0.0, 0.05, -0.10, 0.02, 0.01, 1.0, 1.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=100.0, final_obs=off_pad_touchdown, criteria=crit) == "crash"

        # 4. Severe tilt angle (chassis tip risk)
        severe_tilt_touchdown = np.array([0.05, 0.0, 0.05, -0.10, 0.35, 0.01, 1.0, 1.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=100.0, final_obs=severe_tilt_touchdown, criteria=crit) == "crash"

        # 5. One leg only (missing secondary foot contact)
        one_leg_touchdown = np.array([0.05, 0.0, 0.05, -0.10, 0.05, 0.01, 1.0, 0.0], dtype=np.float32)
        assert classify_outcome(terminated=True, truncated=False, final_step_reward=100.0, final_obs=one_leg_touchdown, criteria=crit) == "crash"

    def test_confidence_interval_computation(self):
        """Verifies Student's t 95% confidence interval calculations."""
        # 3-seed sample
        data = [0.80, 0.85, 0.90]
        ci = compute_confidence_interval(data, confidence=0.95)

        assert ci.sample_size == 3
        assert pytest.approx(ci.mean, 1e-4) == 0.85
        assert ci.lower_bound < ci.mean < ci.upper_bound
        assert ci.margin_of_error > 0.0

        # Single element sample
        ci_single = compute_confidence_interval([0.75])
        assert ci_single.mean == 0.75
        assert ci_single.margin_of_error == 0.0

        # Empty sequence
        ci_empty = compute_confidence_interval([])
        assert ci_empty.sample_size == 0

    def test_welch_t_test_calculation(self):
        """Verifies Welch's t-test computation between contrasting distributions."""
        sample_ctrl = [0.10, 0.15, 0.12]
        sample_treatment = [0.85, 0.90, 0.88]

        res = compute_welch_t_test(sample_ctrl, sample_treatment)
        assert res["t_statistic"] > 10.0
        assert res["p_value"] < 0.01
        assert res["significant_p05"] is True
        assert res["mean_difference"] > 0.70

    def test_paired_t_test_calculation(self):
        """Verifies paired Student's t-test calculation across matched seed blocks."""
        from evaluation.statistical_analysis import compute_paired_t_test
        sample_ctrl = [0.20, 0.25, 0.22]
        sample_treatment = [0.80, 0.85, 0.82]

        res = compute_paired_t_test(sample_ctrl, sample_treatment)
        assert res["sample_size"] == 3
        assert res["mean_difference"] == 0.60
        assert res["p_value"] < 0.01
        assert res["significant_p05"] is True
        assert res["cohens_d"] > 10.0

    def test_benchmark_config_loader(self):
        """Verifies benchmark YAML configuration loading and structure."""
        cfg = load_benchmark_config("experiments/benchmark_config.yaml")
        assert "experiment_paradigms" in cfg
        assert "training" in cfg
        assert "evaluation" in cfg
        assert "landing_criteria" in cfg
        assert len(cfg["experiment_paradigms"]) == 4

    def test_end_to_end_benchmark_smoke_test(self):
        """Runs short end-to-end benchmark smoke test across 2 paradigms with small budget."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            smoke_cfg_content = f"""
experiment_paradigms:
  A_standard:
    name: "Standard PPO"
    type: "standard"
  B_dr_only:
    name: "PPO + Domain Randomization"
    type: "dr_only"

training:
  total_timesteps: 128
  seeds: [42]
  reward_strategy: "baseline"
  ppo_config_path: "configs/ppo_config.yaml"
  curriculum_config_path: "configs/curriculum.yaml"
  dr_config_path: "configs/domain_randomization.yaml"
  resume_existing: true

evaluation:
  episodes_per_condition: 2
  eval_seed_base: 5000
  deterministic: true

landing_criteria:
  max_pad_offset_x: 0.25
  max_touchdown_vx: 0.40
  max_touchdown_vy: 0.40
  max_touchdown_tilt: 0.20
  max_touchdown_spin: 0.35
  require_both_legs: true

paths:
  models_dir: "{tmp_path.as_posix()}/models"
  logs_dir: "{tmp_path.as_posix()}/logs"
  experiments_dir: "{tmp_path.as_posix()}/experiments"
"""
            cfg_file = tmp_path / "test_benchmark.yaml"
            cfg_file.write_text(smoke_cfg_content, encoding="utf-8")

            summary = run_benchmark_matrix(
                config_path=cfg_file,
                paradigms_to_run=["A_standard", "B_dr_only"],
                seeds_override=[42],
                timesteps_override=128,
                eval_episodes_override=2,
                resume=False,
                verbose=0,
            )

            assert "completed_runs" in summary
            assert len(summary["completed_runs"]) == 2
            assert "paradigm_statistical_analyses" in summary
            assert "A_standard" in summary["paradigm_statistical_analyses"]
            assert "B_dr_only" in summary["paradigm_statistical_analyses"]
            assert len(summary["generated_plots"]) == 4
            for p_file in summary["generated_plots"]:
                assert Path(p_file).is_file()
