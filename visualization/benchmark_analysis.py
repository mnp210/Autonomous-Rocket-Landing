"""Visualization suite for benchmarking controlled training, robustness, and statistical evaluation.

Generates:
  1. Success rate comparison bar chart with 95% Student's t error bars (ID vs OOD).
  2. Multi-condition environmental stress radar / grouped bar chart.
  3. Landing stability and control effort comparison (touchdown velocities, tilt, thruster duty cycles).
  4. Seed variation distribution strip/box plot.
  5. Multi-seed training curve progression with shaded confidence bands.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import matplotlib.pyplot as plt
import numpy as np


def plot_benchmark_success_rates(
    paradigm_analyses: Dict[str, Dict[str, Any]],
    save_path: Union[str, Path] = "benchmark_success_rates.png",
    title: str = "Empirical Landing Success Rates (95% CI across Independent Seeds)",
) -> Path:
    """Generates grouped bar chart of landing success rates with 95% confidence intervals."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    paradigms = list(paradigm_analyses.keys())
    x = np.arange(len(paradigms))
    width = 0.35

    id_means = [paradigm_analyses[p]["in_distribution"]["success_rate_ci"]["mean"] * 100 for p in paradigms]
    id_errors = [paradigm_analyses[p]["in_distribution"]["success_rate_ci"]["margin_of_error"] * 100 for p in paradigms]

    ood_means = [paradigm_analyses[p]["out_of_distribution"]["success_rate_ci"]["mean"] * 100 for p in paradigms]
    ood_errors = [paradigm_analyses[p]["out_of_distribution"]["success_rate_ci"]["margin_of_error"] * 100 for p in paradigms]

    fig, ax = plt.subplots(figsize=(10, 6))

    rects1 = ax.bar(x - width/2, id_means, width, yerr=id_errors, capsize=6,
                    label="In-Distribution (ID)", color="#1f77b4", alpha=0.85, edgecolor="black")
    rects2 = ax.bar(x + width/2, ood_means, width, yerr=ood_errors, capsize=6,
                    label="Out-of-Distribution (OOD)", color="#ff7f0e", alpha=0.85, edgecolor="black")

    ax.set_ylabel("Landing Success Rate (%)", fontweight="bold", fontsize=11)
    ax.set_title(title, fontweight="bold", fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("_", " \n") for p in paradigms], fontsize=10)
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path


def plot_id_vs_ood_matrix(
    paradigm_analyses: Dict[str, Dict[str, Any]],
    save_path: Union[str, Path] = "id_vs_ood_matrix.png",
    title: str = "Detailed Multi-Condition Performance Matrix",
) -> Path:
    """Generates condition-by-condition comparison of landing success rate across all 8 stress tests."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    paradigms = list(paradigm_analyses.keys())
    first_p = paradigms[0]
    conditions = list(paradigm_analyses[first_p]["conditions"].keys())

    x = np.arange(len(conditions))
    n_p = len(paradigms)
    total_w = 0.8
    bar_w = total_w / n_p

    fig, ax = plt.subplots(figsize=(14, 6))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for idx, p_name in enumerate(paradigms):
        means = [
            paradigm_analyses[p_name]["conditions"][c]["success_rate_ci"]["mean"] * 100
            for c in conditions
        ]
        errors = [
            paradigm_analyses[p_name]["conditions"][c]["success_rate_ci"]["margin_of_error"] * 100
            for c in conditions
        ]
        offset = (idx - n_p / 2 + 0.5) * bar_w
        ax.bar(
            x + offset, means, bar_w, yerr=errors, capsize=4,
            label=p_name.replace("_", " "), color=colors[idx % len(colors)], alpha=0.85, edgecolor="black"
        )

    ax.set_ylabel("Landing Success Rate (%)", fontweight="bold")
    ax.set_title(title, fontweight="bold", fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in conditions], fontsize=9)
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="upper right")

    # Divider between ID and OOD
    ood_idx = None
    for i, c in enumerate(conditions):
        if paradigm_analyses[first_p]["conditions"][c]["category"] == "out_of_distribution":
            ood_idx = i
            break
    if ood_idx is not None:
        ax.axvline(ood_idx - 0.5, color="red", linestyle="--", linewidth=1.5, alpha=0.8)
        ax.text(ood_idx - 0.4, 98, "OUT-OF-DISTRIBUTION ->", color="red", fontweight="bold", fontsize=9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path


def plot_landing_stability_and_effort(
    paradigm_analyses: Dict[str, Dict[str, Any]],
    save_path: Union[str, Path] = "landing_stability_effort.png",
) -> Path:
    """Generates multi-panel plot comparing landing velocity, tilt, and actuator duty cycles."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    paradigms = list(paradigm_analyses.keys())
    x = np.arange(len(paradigms))

    # Aggregate ID stats for stability metrics
    first_p = paradigms[0]
    id_cond_names = [
        c for c, data in paradigm_analyses[first_p]["conditions"].items()
        if data["category"] == "in_distribution"
    ]

    mean_vy = []
    mean_tilt = []
    main_efforts = []
    side_efforts = []

    for p in paradigms:
        p_vy = [paradigm_analyses[p]["conditions"][c]["mean_landing_vy_ci"]["mean"] for c in id_cond_names]
        p_tilt = [paradigm_analyses[p]["conditions"][c]["mean_tilt_rad_ci"]["mean"] for c in id_cond_names]
        p_main = [paradigm_analyses[p]["conditions"][c]["main_engine_frequency_ci"]["mean"] * 100 for c in id_cond_names]
        p_side = [paradigm_analyses[p]["conditions"][c]["side_thruster_frequency_ci"]["mean"] * 100 for c in id_cond_names]

        mean_vy.append(float(np.mean(p_vy)))
        mean_tilt.append(float(np.degrees(np.mean(p_tilt))))
        main_efforts.append(float(np.mean(p_main)))
        side_efforts.append(float(np.mean(p_side)))

    fig, axs = plt.subplots(1, 3, figsize=(15, 5))

    # 1. Terminal Descent Velocity (All episodes)
    axs[0].bar(x, mean_vy, color="#d62728", alpha=0.8, edgecolor="black")
    axs[0].set_xticks(x)
    axs[0].set_xticklabels([p.replace("_", " \n") for p in paradigms], fontsize=9)
    axs[0].set_ylabel("Terminal Vertical Velocity |Vy| (m/s)", fontweight="bold")
    axs[0].set_title("Terminal Impact Velocity (All Episodes)")
    axs[0].grid(True, alpha=0.3, axis="y")

    # 2. Terminal Tilt Angle (All episodes)
    axs[1].bar(x, mean_tilt, color="#ff7f0e", alpha=0.8, edgecolor="black")
    axs[1].set_xticks(x)
    axs[1].set_xticklabels([p.replace("_", " \n") for p in paradigms], fontsize=9)
    axs[1].set_ylabel("Terminal Pitch Angle (degrees)", fontweight="bold")
    axs[1].set_title("Terminal Tilt (All Episodes)")
    axs[1].grid(True, alpha=0.3, axis="y")

    # 3. Control Effort (Main vs Side Thruster Duty Cycles)
    width = 0.35
    axs[2].bar(x - width/2, main_efforts, width, label="Main Engine %", color="#1f77b4", alpha=0.8, edgecolor="black")
    axs[2].bar(x + width/2, side_efforts, width, label="Side Thrusters %", color="#9467bd", alpha=0.8, edgecolor="black")
    axs[2].set_xticks(x)
    axs[2].set_xticklabels([p.replace("_", " \n") for p in paradigms], fontsize=9)
    axs[2].set_ylabel("Actuator Active Duty Cycle (%)", fontweight="bold")
    axs[2].set_title("Control Effort & Energy Expenditure")
    axs[2].set_ylim(0, 100)
    axs[2].grid(True, alpha=0.3, axis="y")
    axs[2].legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path


def plot_seed_variance_distribution(
    paradigm_analyses: Dict[str, Dict[str, Any]],
    save_path: Union[str, Path] = "seed_variance_distribution.png",
) -> Path:
    """Generates scatter/strip plot showing variation across individual random seeds."""
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    paradigms = list(paradigm_analyses.keys())

    for idx, p in enumerate(paradigms):
        raw_successes = [s * 100 for s in paradigm_analyses[p]["in_distribution"]["raw_seed_successes"]]
        x_jitter = np.random.normal(idx, 0.04, size=len(raw_successes))
        ax.scatter(x_jitter, raw_successes, s=90, label=p.replace("_", " "), alpha=0.9, edgecolors="black", zorder=4)

        # Plot mean line
        mean_val = paradigm_analyses[p]["in_distribution"]["success_rate_ci"]["mean"] * 100
        ax.hlines(mean_val, idx - 0.25, idx + 0.25, colors="black", linewidth=2.5, zorder=5)

    ax.set_xticks(range(len(paradigms)))
    ax.set_xticklabels([p.replace("_", " \n") for p in paradigms], fontsize=10)
    ax.set_ylabel("In-Distribution Success Rate (%)", fontweight="bold")
    ax.set_title("Cross-Seed Reproducibility & Variance Distribution", fontweight="bold")
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    return save_path
