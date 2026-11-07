"""Visualization tools for curriculum progression and robustness analysis.

Generates:
  1. Curriculum progression timeline and rolling success rate.
  2. Domain randomization sampled parameter distributions.
  3. Success rate and metrics across curriculum stages.
  4. Comparative cross-condition robustness bar charts (Standard vs DR vs Curriculum).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import matplotlib.pyplot as plt
import numpy as np


def plot_curriculum_progression(
    curriculum_history: List[Dict[str, Any]],
    save_path: Union[str, Path] = "curriculum_progression.png",
    title: str = "Curriculum Progression & Stage Transitions",
) -> Path:
    """Plots stage transition events and historical success rates across training steps."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax1 = plt.subplots(figsize=(10, 5))

    if not curriculum_history:
        ax1.text(0.5, 0.5, "No stage transitions recorded yet.", horizontalalignment="center")
        plt.savefig(save_path)
        plt.close()
        return save_path

    timesteps = [h["timestep"] for h in curriculum_history]
    stages = [h["to_stage"] for h in curriculum_history]
    rates = [h["success_rate"] * 100 for h in curriculum_history]
    events = [h["event"] for h in curriculum_history]

    color = "#1f77b4"
    ax1.set_xlabel("Training Timesteps", fontweight="bold")
    ax1.set_ylabel("Curriculum Stage (0 to 4)", color=color, fontweight="bold")
    ax1.step(timesteps, stages, where="post", color=color, linewidth=2.5, label="Active Stage")
    ax1.scatter(timesteps, stages, color=color, s=40, zorder=5)
    ax1.set_yticks([0, 1, 2, 3, 4])
    ax1.set_ylim(-0.5, 4.5)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    color2 = "#2ca02c"
    ax2.set_ylabel("Eval Landing Success Rate (%)", color=color2, fontweight="bold")
    ax2.plot(timesteps, rates, color=color2, linestyle="--", marker="o", alpha=0.8, label="Success Rate")
    ax2.axhline(70, color="orange", linestyle=":", label="Advance Threshold (70%)")
    ax2.axhline(30, color="red", linestyle=":", label="Rollback Threshold (30%)")
    ax2.set_ylim(0, 105)

    # Annotate events
    for t, s, e in zip(timesteps, stages, events):
        badge = "^ Advance" if e == "advance" else "v Rollback"
        ax1.annotate(badge, (t, s), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8)

    plt.title(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path


def plot_robustness_comparison(
    models_robustness_reports: Dict[str, Dict[str, Any]],
    save_path: Union[str, Path] = "robustness_comparison.png",
    title: str = "Environmental Robustness Benchmark Comparison",
) -> Path:
    """Generates comparative multi-condition bar chart across multiple trained policies.

    Args:
        models_robustness_reports: Mapping from model/experiment label to its robustness report dict.
        save_path: Destination image file path.
        title: Plot title.
    """
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect condition names from first report
    first_report = next(iter(models_robustness_reports.values()))
    conditions = list(first_report["conditions"].keys())
    model_labels = list(models_robustness_reports.keys())

    n_conds = len(conditions)
    n_models = len(model_labels)
    x = np.arange(n_conds)
    total_width = 0.8
    bar_width = total_width / n_models

    fig, ax = plt.subplots(figsize=(13, 6))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for idx, (label, report) in enumerate(models_robustness_reports.items()):
        success_rates = [
            report["conditions"][c]["metrics"]["landing_success_rate"] * 100
            for c in conditions
        ]
        offset = (idx - n_models / 2 + 0.5) * bar_width
        ax.bar(
            x + offset,
            success_rates,
            bar_width,
            label=label,
            color=colors[idx % len(colors)],
            alpha=0.85,
        )

    ax.set_ylabel("Landing Success Rate (%)", fontweight="bold")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in conditions], fontsize=9)
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="upper right")

    # Add vertical line dividing ID and OOD conditions
    ood_idx = None
    for i, c in enumerate(conditions):
        if first_report["conditions"][c]["category"] == "out_of_distribution":
            ood_idx = i
            break

    if ood_idx is not None:
        ax.axvline(ood_idx - 0.5, color="red", linestyle="--", linewidth=1.5, alpha=0.7)
        ax.text(ood_idx - 0.4, 98, "OUT-OF-DISTRIBUTION ->", color="red", fontweight="bold", fontsize=9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path


def plot_domain_randomization_distribution(
    sampled_params: List[Dict[str, Any]],
    save_path: Union[str, Path] = "dr_parameter_distributions.png",
) -> Path:
    """Plots histograms of sampled environmental parameters across episodes."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    gravities = [p["gravity"] for p in sampled_params if "gravity" in p]
    winds = [p["wind_power"] for p in sampled_params if p.get("enable_wind", False)]
    turbs = [p["turbulence_power"] for p in sampled_params if p.get("enable_wind", False)]

    fig, axs = plt.subplots(1, 3, figsize=(14, 4))

    # Gravity
    if gravities:
        axs[0].hist(gravities, bins=15, color="#1f77b4", edgecolor="black", alpha=0.7)
    axs[0].set_title("Sampled Gravity Distribution")
    axs[0].set_xlabel("Gravity (m/s^2)")
    axs[0].set_ylabel("Frequency")
    axs[0].grid(True, alpha=0.3)

    # Wind Power
    if winds:
        axs[1].hist(winds, bins=15, color="#2ca02c", edgecolor="black", alpha=0.7)
    axs[1].set_title("Active Wind Power Distribution")
    axs[1].set_xlabel("Wind Power (m/s)")
    axs[1].grid(True, alpha=0.3)

    # Turbulence Power
    if turbs:
        axs[2].hist(turbs, bins=15, color="#ff7f0e", edgecolor="black", alpha=0.7)
    axs[2].set_title("Turbulence Power Distribution")
    axs[2].set_xlabel("Turbulence Power")
    axs[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path
