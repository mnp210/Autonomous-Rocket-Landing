"""Unit and integration tests for Curriculum Learning progression and management."""

import gymnasium as gym
import pytest

from environments.curriculum import (
    CurriculumConfig,
    CurriculumManager,
    CurriculumEnvWrapper,
    CurriculumRules,
    load_curriculum_config,
)
from environments.domain_randomization import DomainRandomizationWrapper


class TestCurriculumSystem:
    """Test suite verifying curriculum progression, rollback rules, and wrapper integration."""

    @pytest.fixture
    def test_curriculum_config(self):
        rules = CurriculumRules(
            min_eval_episodes=10,
            success_threshold=0.70,
            rollback_threshold=0.30,
            min_consecutive_passes=2,
            min_steps_per_stage=1000,
        )
        return CurriculumConfig(rules=rules)

    def test_curriculum_manager_initial_state(self, test_curriculum_config):
        """Manager starts at Stage 0 with 0 consecutive passes."""
        mgr = CurriculumManager(test_curriculum_config)
        assert mgr.current_stage_id == 0
        assert mgr.consecutive_passes == 0
        assert mgr.steps_in_current_stage == 0

    def test_advancement_requires_sufficient_episodes(self, test_curriculum_config):
        """Evaluation with fewer than min_eval_episodes must not trigger advancement."""
        mgr = CurriculumManager(test_curriculum_config)
        mgr.record_step_progress(2000)

        # 5 episodes < min_eval_episodes (10)
        changed, reason = mgr.evaluate_progression(landing_success_rate=0.90, eval_episodes=5)
        assert changed is False
        assert "Insufficient eval episodes" in reason
        assert mgr.current_stage_id == 0

    def test_advancement_requires_consecutive_passes(self, test_curriculum_config):
        """Single high score increments pass counter but does not advance until consecutive target reached."""
        mgr = CurriculumManager(test_curriculum_config)
        mgr.record_step_progress(2000)

        # Pass 1: Should not advance yet
        changed1, _ = mgr.evaluate_progression(landing_success_rate=0.80, eval_episodes=10)
        assert changed1 is False
        assert mgr.consecutive_passes == 1
        assert mgr.current_stage_id == 0

        # Pass 2: Consecutive passes met and min steps met -> Advance!
        changed2, reason = mgr.evaluate_progression(landing_success_rate=0.85, eval_episodes=10)
        assert changed2 is True
        assert "ADVANCE" in reason
        assert mgr.current_stage_id == 1
        assert mgr.consecutive_passes == 0
        assert mgr.steps_in_current_stage == 0

    def test_advancement_requires_min_steps(self, test_curriculum_config):
        """High success rate before min_steps_per_stage are completed does not trigger stage advance."""
        mgr = CurriculumManager(test_curriculum_config)
        # Only 500 steps < 1000 required
        mgr.record_step_progress(500)

        mgr.evaluate_progression(landing_success_rate=0.85, eval_episodes=10)
        changed, reason = mgr.evaluate_progression(landing_success_rate=0.85, eval_episodes=10)

        assert changed is False
        assert "Min steps in stage not met" in reason
        assert mgr.current_stage_id == 0

    def test_rollback_on_performance_collapse(self, test_curriculum_config):
        """When in Stage 1+, success rate dropping below rollback_threshold triggers demotion."""
        mgr = CurriculumManager(test_curriculum_config)
        mgr.current_stage_id = 2  # Manually set to higher stage

        changed, reason = mgr.evaluate_progression(landing_success_rate=0.20, eval_episodes=10)
        assert changed is True
        assert "ROLLBACK" in reason
        assert mgr.current_stage_id == 1

    def test_curriculum_env_wrapper_integration(self):
        """CurriculumEnvWrapper wraps environment and attaches curriculum metadata."""
        env = gym.make("LunarLander-v3")
        wrapped = CurriculumEnvWrapper(env)

        assert wrapped.observation_space == env.observation_space
        assert wrapped.action_space == env.action_space

        obs, info = wrapped.reset(seed=42)
        assert "curriculum_stage" in info
        assert "curriculum_stage_name" in info
        assert info["curriculum_stage"] == 0

        # Manually advance stage
        wrapped.set_stage(1)
        obs, info = wrapped.reset(seed=42)
        assert info["curriculum_stage"] == 1

        env.close()
