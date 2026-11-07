"""Gymnasium environment wrapper for custom reward shaping and energy penalty accounting."""

from typing import Any, Dict, Optional, Tuple, Union
import gymnasium as gym
import numpy as np

from rewards.reward_config import RewardConfig, RewardStrategy, load_reward_config
from rewards.reward_functions import compute_energy_penalty, compute_potential, compute_potential_shaping


class RocketRewardShapingWrapper(gym.Wrapper):
    """Gymnasium Wrapper implementing modular reward shaping for LunarLander-v3.

    Supports:
        - Baseline (unmodified original reward)
        - Potential-Based Reward Shaping (PBRS, Ng et al. 1999)
        - Energy-Aware Reward Shaping (PBRS + discrete thruster consumption penalty)

    Preserves exact observation space, action space, termination, truncation, and environment metadata.
    Provides detailed reward decomposition metrics in the step `info` dictionary.
    """

    def __init__(
        self,
        env: gym.Env,
        config: Optional[Union[RewardConfig, Dict[str, Any]]] = None,
    ):
        super().__init__(env)
        if config is None:
            self.config = RewardConfig(strategy=RewardStrategy.BASELINE)
        elif isinstance(config, RewardConfig):
            self.config = config
        else:
            self.config = load_reward_config(config)

        self.current_obs: Optional[np.ndarray] = None
        self.current_phi: float = 0.0
        self.prev_action: Optional[int] = None

        # Episodic cumulative tracking
        self.ep_original_reward: float = 0.0
        self.ep_shaping_reward: float = 0.0
        self.ep_energy_penalty: float = 0.0
        self.ep_combined_reward: float = 0.0
        self.ep_steps: int = 0

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        obs, info = self.env.reset(seed=seed, options=options)
        self.current_obs = np.array(obs, copy=True)
        self.current_phi = compute_potential(
            self.current_obs,
            weights=self.config.potential_weights,
            normalizers=self.config.normalizers,
        )
        self.prev_action = None

        # Reset episode accumulators
        self.ep_original_reward = 0.0
        self.ep_shaping_reward = 0.0
        self.ep_energy_penalty = 0.0
        self.ep_combined_reward = 0.0
        self.ep_steps = 0

        info["initial_potential"] = self.current_phi
        return obs, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        obs, original_reward, terminated, truncated, info = self.env.step(action)
        self.ep_steps += 1
        original_reward = float(original_reward)

        strategy = self.config.strategy

        if strategy == RewardStrategy.BASELINE:
            shaping_reward = 0.0
            energy_penalty = 0.0
            combined_reward = original_reward
            phi_next = self.current_phi

        else:
            # Compute potential of subsequent state Phi(s')
            phi_next = compute_potential(
                obs,
                weights=self.config.potential_weights,
                normalizers=self.config.normalizers,
            )

            # Potential-based shaping F(s, s') = gamma * Phi(s') - Phi(s)
            shaping_reward = compute_potential_shaping(
                phi_current=self.current_phi,
                phi_next=phi_next,
                gamma=self.config.gamma,
                terminated=terminated,
                zero_terminal_potential=self.config.zero_terminal_potential,
                shaping_scale=self.config.shaping_scale,
            )

            # Energy penalty (only active in ENERGY_AWARE strategy)
            if strategy == RewardStrategy.ENERGY_AWARE:
                energy_penalty = compute_energy_penalty(
                    action=int(action),
                    prev_action=self.prev_action,
                    penalties=self.config.energy_penalties,
                )
            else:
                energy_penalty = 0.0

            combined_reward = original_reward + shaping_reward - energy_penalty

        # Update state trackers for next step
        self.current_phi = phi_next
        self.current_obs = np.array(obs, copy=True)
        self.prev_action = int(action)

        # Accumulate metrics
        self.ep_original_reward += original_reward
        self.ep_shaping_reward += shaping_reward
        self.ep_energy_penalty += energy_penalty
        self.ep_combined_reward += combined_reward

        # Enrich info dictionary with transparent step-level decomposition
        reward_components = {
            "strategy": strategy.value,
            "original_reward": original_reward,
            "shaping_reward": shaping_reward,
            "energy_penalty": energy_penalty,
            "combined_reward": combined_reward,
            "potential_current": self.current_phi,
            "potential_next": phi_next,
            "action": int(action),
        }
        info["reward_components"] = reward_components

        # On episode conclusion, append episodic totals
        if terminated or truncated:
            info["episode_reward_summary"] = {
                "strategy": strategy.value,
                "total_original_reward": round(self.ep_original_reward, 3),
                "total_shaping_reward": round(self.ep_shaping_reward, 3),
                "total_energy_penalty": round(self.ep_energy_penalty, 3),
                "total_combined_reward": round(self.ep_combined_reward, 3),
                "episode_length": self.ep_steps,
            }

        return obs, float(combined_reward), terminated, truncated, info
