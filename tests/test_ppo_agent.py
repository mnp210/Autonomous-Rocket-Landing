"""Unit and integration tests for PPO Agent initialization, prediction, and serialization."""

from pathlib import Path
import tempfile
import gymnasium as gym
import numpy as np
import pytest
from stable_baselines3 import PPO

from environments.env_loader import make_environment
from agents.ppo_agent import create_ppo_agent, load_ppo_agent, validate_environment_spaces


class TestPPOAgent:
    """Test suite for PPO agent integration with LunarLander-v3."""

    @pytest.fixture
    def env(self):
        """Creates a headless LunarLander-v3 environment."""
        env = make_environment(env_id="LunarLander-v3", continuous=False)
        yield env
        env.close()

    def test_environment_space_validation(self, env):
        """Verifies that environment space validation passes for valid LunarLander-v3."""
        # Should not raise exception
        validate_environment_spaces(env)

    def test_invalid_space_rejection(self):
        """Ensures that invalid observation spaces are caught and rejected."""
        dummy_env = gym.make("CartPole-v1")
        with pytest.raises(ValueError, match="Expected observation space Box\\(8,\\)"):
            validate_environment_spaces(dummy_env)
        dummy_env.close()

    def test_ppo_agent_initialization(self, env):
        """Verifies PPO agent builds with correct policy and hyperparameters."""
        custom_config = {
            "learning_rate": 0.0003,
            "n_steps": 256,
            "batch_size": 64,
            "n_epochs": 4,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
        }
        agent = create_ppo_agent(env=env, config=custom_config, seed=42, verbose=0)
        assert isinstance(agent, PPO)
        assert agent.learning_rate == 0.0003
        assert agent.n_steps == 256
        assert agent.batch_size == 64
        assert agent.gamma == 0.99
        assert agent.gae_lambda == 0.95
        assert agent.clip_range(1.0) == 0.2

    def test_agent_prediction_validity(self, env):
        """Ensures deterministic and stochastic predictions return valid discrete actions."""
        agent = create_ppo_agent(env=env, seed=42, verbose=0)
        obs, _ = env.reset(seed=42)

        # Test deterministic prediction
        det_action, _ = agent.predict(obs, deterministic=True)
        assert isinstance(det_action, (np.integer, int, np.ndarray))
        det_int = int(det_action)
        assert det_int in [0, 1, 2, 3]

        # Test stochastic prediction
        stoch_action, _ = agent.predict(obs, deterministic=False)
        stoch_int = int(stoch_action)
        assert stoch_int in [0, 1, 2, 3]

    def test_model_serialization_and_deserialization(self, env):
        """Tests saving and loading PPO model checkpoints."""
        agent = create_ppo_agent(env=env, seed=42, verbose=0)
        obs, _ = env.reset(seed=42)
        initial_action, _ = agent.predict(obs, deterministic=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "test_model.zip"
            agent.save(str(save_path))
            assert save_path.is_file()

            loaded_agent = load_ppo_agent(save_path, env=env)
            assert isinstance(loaded_agent, PPO)

            loaded_action, _ = loaded_agent.predict(obs, deterministic=True)
            assert int(initial_action) == int(loaded_action)
