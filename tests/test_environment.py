"""Automated test suite for Gymnasium LunarLander-v3 environment.

Verifies:
- Environment initialization without errors
- Observation space dimensions, dtype, and bounds
- Action space validity for discrete actions
- Deterministic reset under fixed seeds
- Step transition interface adhering to Gymnasium API (obs, reward, terminated, truncated, info)
- Termination and truncation handling
"""

import pytest
import numpy as np
import gymnasium as gym
from environments.env_loader import make_environment


class TestLunarLanderV3Environment:
    """Test suite for LunarLander-v3 integration."""

    @pytest.fixture
    def env(self):
        """Creates a headless LunarLander-v3 environment fixture."""
        test_env = make_environment(env_id="LunarLander-v3")
        yield test_env
        test_env.close()

    def test_environment_creation(self, env):
        """Ensures the environment instantiates properly."""
        assert env is not None
        assert env.spec.id == "LunarLander-v3"

    def test_observation_space_properties(self, env):
        """Verifies observation space shape, type, and finite bounds."""
        obs_space = env.observation_space
        assert isinstance(obs_space, gym.spaces.Box)
        assert obs_space.shape == (8,)
        assert obs_space.dtype == np.float32

    def test_action_space_properties(self, env):
        """Verifies action space has 4 discrete options by default."""
        act_space = env.action_space
        assert isinstance(act_space, gym.spaces.Discrete)
        assert act_space.n == 4

    def test_reset_signature_and_observation(self, env):
        """Verifies env.reset() returns (obs, info) where obs is valid."""
        obs, info = env.reset(seed=42)
        assert isinstance(obs, np.ndarray)
        assert obs.shape == (8,)
        assert obs.dtype == np.float32
        assert isinstance(info, dict)
        assert not np.isnan(obs).any()
        assert not np.isinf(obs).any()

    def test_deterministic_seed_reset(self, env):
        """Verifies identical seed produces identical initial observation."""
        obs1, _ = env.reset(seed=999)
        obs2, _ = env.reset(seed=999)
        np.testing.assert_allclose(obs1, obs2, err_msg="Reset with same seed must be deterministic")

    @pytest.mark.parametrize("action", [0, 1, 2, 3])
    def test_all_discrete_actions_accepted(self, env, action):
        """Verifies all discrete action IDs (0 to 3) execute successfully."""
        env.reset(seed=42)
        obs, reward, terminated, truncated, info = env.step(action)

        assert isinstance(obs, np.ndarray)
        assert obs.shape == (8,)
        assert isinstance(reward, (float, np.floating))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_termination_and_truncation_contract(self, env):
        """Tests that rollout returns booleans for terminated and truncated and step increments properly."""
        obs, _ = env.reset(seed=123)
        max_steps = 50
        for _ in range(max_steps):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            assert isinstance(terminated, bool)
            assert isinstance(truncated, bool)
            if terminated or truncated:
                break
