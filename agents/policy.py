"""Custom policy networks and feature extractors for rocket landing agents."""

from typing import List, Tuple
import torch
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
import gymnasium as gym


class RocketFeatureExtractor(BaseFeaturesExtractor):
    """Custom feature extractor for rocket landing observations.

    Processes kinematic states (position, velocity, angle, angular velocity)
    and sensor flags (leg contact, fuel) with a specialized MLP architecture.
    """

    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 128):
        super().__init__(observation_space, features_dim)
        input_dim = observation_space.shape[0]

        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.Tanh(),
            nn.Linear(128, features_dim),
            nn.Tanh(),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return self.net(observations)


def get_actor_critic_net_arch() -> dict:
    """Returns custom network architecture for actor and critic networks."""
    return dict(pi=[128, 128], vf=[128, 128])
