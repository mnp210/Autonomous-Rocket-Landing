"""Integration tests for Gymnasium RocketRewardShapingWrapper."""

import gymnasium as gym
import numpy as np
import pytest

from environments.env_loader import make_environment
from rewards.reward_config import RewardConfig, RewardStrategy
from rewards.reward_wrapper import RocketRewardShapingWrapper


class TestRewardWrapper:
    """Test suite for RocketRewardShapingWrapper integration."""

    @pytest.fixture
    def base_env(self):
        env = make_environment(env_id="LunarLander-v3", continuous=False)
        yield env
        env.close()

    def test_space_preservation(self, base_env):
        """Wrapper must strictly preserve original observation and action spaces."""
        config = RewardConfig(strategy=RewardStrategy.ENERGY_AWARE)
        wrapped = RocketRewardShapingWrapper(base_env, config=config)

        assert wrapped.observation_space == base_env.observation_space
        assert wrapped.action_space == base_env.action_space
        assert wrapped.action_space.n == 4
        assert wrapped.observation_space.shape == (8,)

    def test_baseline_preserves_original_reward(self, base_env):
        """In BASELINE mode, step returns the exact unmodified original reward."""
        config = RewardConfig(strategy=RewardStrategy.BASELINE)
        wrapped = RocketRewardShapingWrapper(base_env, config=config)

        obs, info = wrapped.reset(seed=42)
        assert "initial_potential" in info

        for action in [0, 1, 2, 3]:
            obs, reward, term, trunc, info = wrapped.step(action)
            assert "reward_components" in info
            comps = info["reward_components"]
            assert comps["strategy"] == "baseline"
            assert comps["shaping_reward"] == 0.0
            assert comps["energy_penalty"] == 0.0
            assert comps["combined_reward"] == comps["original_reward"]
            assert reward == comps["original_reward"]
            if term or trunc:
                break

    def test_potential_based_reward_components(self, base_env):
        """In POTENTIAL_BASED mode, shaping is applied and energy penalty is 0."""
        config = RewardConfig(strategy=RewardStrategy.POTENTIAL_BASED)
        wrapped = RocketRewardShapingWrapper(base_env, config=config)

        obs, _ = wrapped.reset(seed=42)
        obs, reward, term, trunc, info = wrapped.step(2)

        comps = info["reward_components"]
        assert comps["strategy"] == "potential_based"
        assert comps["energy_penalty"] == 0.0
        assert pytest.approx(comps["combined_reward"], 1e-4) == comps["original_reward"] + comps["shaping_reward"]
        assert pytest.approx(reward, 1e-4) == comps["combined_reward"]

    def test_energy_aware_reward_components(self, base_env):
        """In ENERGY_AWARE mode, both shaping and energy penalty are accounted for."""
        config = RewardConfig(strategy=RewardStrategy.ENERGY_AWARE)
        wrapped = RocketRewardShapingWrapper(base_env, config=config)

        obs, _ = wrapped.reset(seed=42)

        # Fire main engine (action 2)
        obs, reward, term, trunc, info = wrapped.step(2)
        comps = info["reward_components"]

        assert comps["strategy"] == "energy_aware"
        assert comps["energy_penalty"] > 0.0
        expected = comps["original_reward"] + comps["shaping_reward"] - comps["energy_penalty"]
        assert pytest.approx(reward, 1e-4) == expected

    def test_episodic_summary_on_termination(self, base_env):
        """On episode end, info contains episode_reward_summary."""
        config = RewardConfig(strategy=RewardStrategy.ENERGY_AWARE)
        wrapped = RocketRewardShapingWrapper(base_env, config=config)

        wrapped.reset(seed=123)
        done = False
        summary = None

        while not done:
            action = wrapped.action_space.sample()
            obs, r, term, trunc, info = wrapped.step(action)
            done = term or trunc
            if done:
                summary = info.get("episode_reward_summary")

        assert summary is not None
        assert "total_original_reward" in summary
        assert "total_shaping_reward" in summary
        assert "total_energy_penalty" in summary
        assert "total_combined_reward" in summary
        assert summary["episode_length"] > 0

    def test_deterministic_seeding(self, base_env):
        """Identical seeds produce identical initial potentials and observations."""
        config = RewardConfig(strategy=RewardStrategy.POTENTIAL_BASED)
        w1 = RocketRewardShapingWrapper(base_env, config=config)
        obs1, info1 = w1.reset(seed=777)

        w2 = RocketRewardShapingWrapper(base_env, config=config)
        obs2, info2 = w2.reset(seed=777)

        np.testing.assert_allclose(obs1, obs2)
        assert info1["initial_potential"] == info2["initial_potential"]
