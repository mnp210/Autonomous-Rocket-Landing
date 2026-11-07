"""Test basic environment creation and imports."""

import pytest
from environments.lunar_lander import make_lunar_lander_env
from environments.custom_lander import CustomRocketLanderEnv
from rewards.shaped_reward import ShapedRocketRewardWrapper


def test_custom_lander_initialization():
    env = CustomRocketLanderEnv()
    obs, info = env.reset()
    assert obs is not None
    assert len(obs) == 9
    assert env.action_space.shape == (2,)


def test_shaped_reward_wrapper():
    env = CustomRocketLanderEnv()
    wrapped_env = ShapedRocketRewardWrapper(env)
    obs, info = wrapped_env.reset()
    assert obs is not None
