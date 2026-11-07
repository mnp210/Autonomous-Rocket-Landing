"""Unit and integration tests for Domain Randomization in LunarLander-v3."""

import gymnasium as gym
import numpy as np
import pytest

from environments.env_loader import make_environment
from environments.domain_randomization import (
    DomainRandomizationConfig,
    DomainRandomizationWrapper,
    WindRandomizationConfig,
    InitialPerturbationConfig,
    load_domain_randomization_config,
)


class TestDomainRandomization:
    """Test suite verifying domain randomization parameters, spaces, and reproducibility."""

    @pytest.fixture
    def base_env(self):
        env = gym.make("LunarLander-v3")
        yield env
        env.close()

    def test_space_preservation(self, base_env):
        """Domain randomization wrapper must strictly preserve observation and action spaces."""
        config = DomainRandomizationConfig(enabled=True)
        wrapped = DomainRandomizationWrapper(base_env, config=config)

        assert wrapped.observation_space == base_env.observation_space
        assert wrapped.action_space == base_env.action_space
        assert wrapped.action_space.n == 4
        assert wrapped.observation_space.shape == (8,)

    def test_parameter_sampling_within_bounds(self, base_env):
        """Sampled physical values on reset must lie within specified ranges."""
        cfg = DomainRandomizationConfig(
            enabled=True,
            mode="randomized",
            gravity_range=(-12.0, -8.0),
            wind=WindRandomizationConfig(
                probability=1.0,  # Force wind active
                power_range=(10.0, 20.0),
                turbulence_range=(1.0, 2.0),
            ),
        )
        wrapped = DomainRandomizationWrapper(base_env, config=cfg)

        for ep in range(10):
            obs, info = wrapped.reset(seed=100 + ep)
            params = info["env_params"]

            assert -12.0 <= params["gravity"] <= -8.0
            assert params["enable_wind"] is True
            assert 10.0 <= params["wind_power"] <= 20.0
            assert 1.0 <= params["turbulence_power"] <= 2.0

            # Verify world gravity actually matches sampled gravity
            world_grav = wrapped.unwrapped.world.gravity.y
            assert pytest.approx(world_grav, 1e-3) == params["gravity"]

    def test_fixed_mode_behavior(self, base_env):
        """In fixed mode, wrapper applies exact nominal parameters."""
        cfg = DomainRandomizationConfig(
            enabled=True,
            mode="fixed",
            fixed_gravity=-7.5,
            fixed_enable_wind=True,
            fixed_wind_power=14.0,
            fixed_turbulence_power=1.2,
        )
        wrapped = DomainRandomizationWrapper(base_env, config=cfg)
        obs, info = wrapped.reset(seed=42)
        params = info["env_params"]

        assert params["gravity"] == -7.5
        assert params["enable_wind"] is True
        assert params["wind_power"] == 14.0
        assert params["turbulence_power"] == 1.2
        assert pytest.approx(wrapped.unwrapped.world.gravity.y, 1e-3) == -7.5

    def test_disabled_randomization_matches_baseline(self, base_env):
        """When enabled=False, parameters remain standard Gymnasium defaults."""
        cfg = DomainRandomizationConfig(enabled=False)
        wrapped = DomainRandomizationWrapper(base_env, config=cfg)
        obs, info = wrapped.reset(seed=42)
        params = info["env_params"]

        assert params["gravity"] == -10.0
        assert params["enable_wind"] is False
        assert pytest.approx(wrapped.unwrapped.world.gravity.y, 1e-3) == -10.0

    def test_seed_reproducibility(self, base_env):
        """Identical seeds must produce identical sampled physical parameters across resets."""
        cfg = DomainRandomizationConfig(enabled=True, mode="randomized")
        w1 = DomainRandomizationWrapper(base_env, config=cfg)
        obs1, info1 = w1.reset(seed=999)

        w2 = DomainRandomizationWrapper(base_env, config=cfg)
        obs2, info2 = w2.reset(seed=999)

        assert info1["env_params"] == info2["env_params"]
        np.testing.assert_allclose(obs1, obs2)

    def test_parameter_logging_throughout_steps(self, base_env):
        """Step returns must continue to carry env_params in the info dict."""
        cfg = DomainRandomizationConfig(enabled=True)
        wrapped = DomainRandomizationWrapper(base_env, config=cfg)
        wrapped.reset(seed=42)

        for action in [0, 1, 2, 3]:
            obs, reward, term, trunc, info = wrapped.step(action)
            assert "env_params" in info
            assert "gravity" in info["env_params"]
            if term or trunc:
                break
