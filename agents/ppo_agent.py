"""PPO Agent module for Autonomous Rocket Landing.

Provides factory functions to build, configure, and load Proximal Policy Optimization (PPO)
agents using Stable-Baselines3 with configurable hyperparameters and space validation.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import gymnasium as gym
import numpy as np
import torch
import yaml
from stable_baselines3 import PPO


DEFAULT_PPO_CONFIG: Dict[str, Any] = {
    "policy": "MlpPolicy",
    "learning_rate": 0.0003,
    "n_steps": 2048,
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.0,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
    "verbose": 1,
}


def load_config_file(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Loads YAML configuration file."""
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_environment_spaces(env: gym.Env) -> None:
    """Validates that environment observation and action spaces match LunarLander specifications.

    Observation space must be 8-dimensional Box.
    Action space must be Discrete(4).
    """
    obs_space = env.observation_space
    act_space = env.action_space

    if not isinstance(obs_space, gym.spaces.Box) or obs_space.shape != (8,):
        raise ValueError(
            f"Expected observation space Box(8,), but got {obs_space} with shape {getattr(obs_space, 'shape', None)}"
        )

    if not isinstance(act_space, gym.spaces.Discrete) or act_space.n != 4:
        raise ValueError(f"Expected action space Discrete(4), but got {act_space}")


def create_ppo_agent(
    env: gym.Env,
    config: Optional[Dict[str, Any]] = None,
    tensorboard_log: Optional[str] = None,
    seed: Optional[int] = 42,
    verbose: Optional[int] = None,
    device: str = "auto",
) -> PPO:
    """Builds and initializes a PPO agent for LunarLander-v3.

    Args:
        env: The Gymnasium training environment.
        config: Dictionary containing PPO hyperparameters.
        tensorboard_log: Directory path for TensorBoard logging.
        seed: Random seed for deterministic reproducibility.
        verbose: Verbosity level (0: none, 1: info, 2: debug). Overrides config if provided.
        device: PyTorch device ('auto', 'cpu', 'cuda').

    Returns:
        Configured Stable-Baselines3 PPO agent.
    """
    validate_environment_spaces(env)

    # Merge default config with user provided config
    hyperparams = DEFAULT_PPO_CONFIG.copy()
    if config:
        # Check if config has nested 'algorithm' block
        algo_cfg = config.get("algorithm", config)
        for key in hyperparams.keys():
            if key in algo_cfg:
                hyperparams[key] = algo_cfg[key]

    if verbose is not None:
        hyperparams["verbose"] = verbose

    policy = hyperparams.pop("policy", "MlpPolicy")

    model = PPO(
        policy=policy,
        env=env,
        tensorboard_log=tensorboard_log,
        seed=seed,
        device=device,
        **hyperparams,
    )
    return model


def load_ppo_agent(
    model_path: Union[str, Path],
    env: Optional[gym.Env] = None,
    device: str = "auto",
) -> PPO:
    """Loads a serialized PPO agent checkpoint from disk.

    Args:
        model_path: Path to the .zip model file.
        env: Optional environment to attach to the model.
        device: Device to load the model on ('auto', 'cpu', 'cuda').

    Returns:
        Loaded PPO model instance.
    """
    path = Path(model_path)
    if not path.is_file():
        # Check if .zip extension is omitted
        zip_path = path.with_suffix(".zip")
        if zip_path.is_file():
            path = zip_path
        else:
            raise FileNotFoundError(f"Model checkpoint not found at: {model_path}")

    return PPO.load(str(path), env=env, device=device)
