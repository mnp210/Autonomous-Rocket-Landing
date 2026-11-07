"""Visualization dashboard for flight trajectories, fuel usage, and training curves."""

from typing import List, Dict, Any
import matplotlib.pyplot as plt
import numpy as np


def plot_trajectory_telemetry(trajectory: List[Dict[str, Any]], save_path: str = "trajectory.png"):
    """Plots altitude, horizontal displacement, velocities, and engine throttle over time.

    Args:
        trajectory: List of transition steps with 'state' and 'action'.
        save_path: File path to save generated plot.
    """
    timesteps = np.arange(len(trajectory))
    states = np.array([step["state"] for step in trajectory])
    actions = np.array([step["action"] for step in trajectory])

    fig, axs = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

    # Position
    axs[0].plot(timesteps, states[:, 0], label="Horizontal Position (x)")
    axs[0].plot(timesteps, states[:, 1], label="Altitude (y)", color="green")
    axs[0].set_ylabel("Position")
    axs[0].grid(True)
    axs[0].legend()

    # Velocity
    axs[1].plot(timesteps, states[:, 2], label="Vx")
    axs[1].plot(timesteps, states[:, 3], label="Vy", color="red")
    axs[1].set_ylabel("Velocity")
    axs[1].grid(True)
    axs[1].legend()

    # Controls
    axs[2].plot(timesteps, actions[:, 0], label="Main Throttle", color="orange")
    if actions.shape[1] > 1:
        axs[2].plot(timesteps, actions[:, 1], label="Steering / Lateral", color="purple")
    axs[2].set_ylabel("Action")
    axs[2].set_xlabel("Timestep")
    axs[2].grid(True)
    axs[2].legend()

    plt.tight_layout()
    plt.savefig(save_path)
    print(f"Telemetry plot saved to {save_path}")
    plt.close()
