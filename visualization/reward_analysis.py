"""Diagnostic and comparative visualization tools for reward shaping analysis.

Generates plots for:
- Original reward vs shaped reward progression
- Distance-to-pad and altitude profiles
- Vertical and horizontal velocity tracking
- Angular stability (tilt angle and roll rate)
- Actuator activation frequencies (main engine vs attitude thrusters)
- Cross-strategy comparative performance benchmarks
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import matplotlib.pyplot as plt
import numpy as np


def plot_episode_telemetry(
    trajectory: List[Dict[str, Any]],
    save_path: Union[str, Path] = "episode_telemetry.png",
    title: str = "Flight Telemetry & Reward Decomposition",
) -> Path:
    """Generates a multi-panel flight telemetry and reward decomposition plot for an episode rollout.

    Args:
        trajectory: List of step dicts containing 'obs', 'action', and 'reward_components'.
        save_path: Destination file path for image.
        title: Figure title.

    Returns:
        Path to saved figure.
    """
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    timesteps = np.arange(len(trajectory))
    obs_array = np.array([step["obs"] for step in trajectory])
    actions = np.array([step["action"] for step in trajectory])

    # Extract decomposed rewards if present
    has_components = "reward_components" in trajectory[0]
    if has_components:
        orig_rewards = np.array([step["reward_components"].get("original_reward", step["reward"]) for step in trajectory])
        shaping_rewards = np.array([step["reward_components"].get("shaping_reward", 0.0) for step in trajectory])
        combined_rewards = np.array([step["reward_components"].get("combined_reward", step["reward"]) for step in trajectory])
    else:
        orig_rewards = np.array([step["reward"] for step in trajectory])
        shaping_rewards = np.zeros_like(orig_rewards)
        combined_rewards = orig_rewards

    fig, axs = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

    # 1. Position & Altitude
    x_pos = obs_array[:, 0]
    y_pos = obs_array[:, 1]
    dist_pad = np.sqrt(x_pos**2 + y_pos**2)
    axs[0].plot(timesteps, x_pos, label="Horizontal (x)", color="#1f77b4", linewidth=1.5)
    axs[0].plot(timesteps, y_pos, label="Altitude (y)", color="#2ca02c", linewidth=1.5)
    axs[0].plot(timesteps, dist_pad, label="Distance to Pad", color="#7f7f7f", linestyle="--")
    axs[0].axhline(0, color="black", linestyle=":", alpha=0.6)
    axs[0].set_ylabel("Position (m)")
    axs[0].set_title(title, fontsize=12, fontweight="bold")
    axs[0].grid(True, alpha=0.3)
    axs[0].legend(loc="upper right")

    # 2. Linear Velocities
    vx = obs_array[:, 2]
    vy = obs_array[:, 3]
    axs[1].plot(timesteps, vx, label="Vx (horizontal)", color="#17becf", linewidth=1.5)
    axs[1].plot(timesteps, vy, label="Vy (vertical)", color="#d62728", linewidth=1.5)
    axs[1].axhline(0, color="black", linestyle=":", alpha=0.6)
    axs[1].set_ylabel("Velocity (m/s)")
    axs[1].grid(True, alpha=0.3)
    axs[1].legend(loc="upper right")

    # 3. Angular Stability (Tilt & Spin)
    tilt = obs_array[:, 4]
    spin = obs_array[:, 5]
    axs[2].plot(timesteps, np.degrees(tilt), label="Tilt Angle (deg)", color="#ff7f0e", linewidth=1.5)
    axs[2].plot(timesteps, spin, label="Roll Rate (rad/s)", color="#9467bd", linestyle="--")
    axs[2].axhline(0, color="black", linestyle=":", alpha=0.6)
    axs[2].set_ylabel("Angle / Spin")
    axs[2].grid(True, alpha=0.3)
    axs[2].legend(loc="upper right")

    # 4. Cumulative Rewards & Actuator Activations
    cum_orig = np.cumsum(orig_rewards)
    cum_comb = np.cumsum(combined_rewards)
    axs[3].plot(timesteps, cum_orig, label="Cumulative Original Reward", color="#2ca02c", linewidth=1.8)
    if has_components and np.any(shaping_rewards != 0.0):
        axs[3].plot(timesteps, cum_comb, label="Cumulative Shaped Reward", color="#9467bd", linestyle="-.")
    axs[3].set_ylabel("Cumulative Reward")
    axs[3].set_xlabel("Timestep")
    axs[3].grid(True, alpha=0.3)
    axs[3].legend(loc="upper left")

    # Secondary axis on subplot 4 for actions
    ax_act = axs[3].twinx()
    ax_act.scatter(timesteps, actions, c=actions, cmap="Set1", s=8, alpha=0.7, label="Action (0..3)")
    ax_act.set_yticks([0, 1, 2, 3])
    ax_act.set_yticklabels(["Idle", "Left", "Main", "Right"])
    ax_act.set_ylabel("Thruster Action")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path


def plot_cross_strategy_comparison(
    metrics_by_strategy: Dict[str, Dict[str, Any]],
    save_path: Union[str, Path] = "strategy_comparison.png",
) -> Path:
    """Generates comparative bar charts benchmarking the 3 reward configurations.

    Args:
        metrics_by_strategy: Mapping of strategy name to evaluation metrics dictionary.
        save_path: Destination image path.

    Returns:
        Path to saved figure.
    """
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    strategies = list(metrics_by_strategy.keys())
    if not strategies:
        raise ValueError("metrics_by_strategy cannot be empty")

    x = np.arange(len(strategies))
    width = 0.35

    mean_rewards = [metrics_by_strategy[s].get("mean_episode_reward", 0.0) for s in strategies]
    std_rewards = [metrics_by_strategy[s].get("reward_std", 0.0) for s in strategies]
    success_rates = [metrics_by_strategy[s].get("landing_success_rate", 0.0) * 100 for s in strategies]
    crash_rates = [metrics_by_strategy[s].get("crash_rate", 0.0) * 100 for s in strategies]
    main_freqs = [metrics_by_strategy[s].get("main_engine_frequency", 0.0) * 100 for s in strategies]

    fig, axs = plt.subplots(1, 3, figsize=(15, 5))

    # 1. Mean Episode Reward
    axs[0].bar(x, mean_rewards, yerr=std_rewards, capsize=5, color=["#1f77b4", "#ff7f0e", "#2ca02c"], alpha=0.8)
    axs[0].set_xticks(x)
    axs[0].set_xticklabels(strategies, rotation=15)
    axs[0].set_ylabel("Mean Reward +/- Std")
    axs[0].set_title("Reward Comparison (Control vs Shaped)")
    axs[0].grid(True, alpha=0.3, axis="y")

    # 2. Success vs Crash Rate
    axs[1].bar(x - width/2, success_rates, width, label="Success %", color="#2ca02c", alpha=0.8)
    axs[1].bar(x + width/2, crash_rates, width, label="Crash %", color="#d62728", alpha=0.8)
    axs[1].set_xticks(x)
    axs[1].set_xticklabels(strategies, rotation=15)
    axs[1].set_ylabel("Rate (%)")
    axs[1].set_ylim(0, 105)
    axs[1].set_title("Landing Outcomes")
    axs[1].grid(True, alpha=0.3, axis="y")
    axs[1].legend()

    # 3. Main Engine Usage Frequency
    axs[2].bar(x, main_freqs, color="#9467bd", alpha=0.8)
    axs[2].set_xticks(x)
    axs[2].set_xticklabels(strategies, rotation=15)
    axs[2].set_ylabel("Main Thruster Activation (%)")
    axs[2].set_title("Energy / Actuation Frequency")
    axs[2].grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path
