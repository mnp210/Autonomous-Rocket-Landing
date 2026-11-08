"""Deterministic evaluation module for Autonomous Rocket Landing.

Evaluates trained policies against LunarLander-v3, computes statistical benchmarks
(mean/median reward, success rate, crash rate, length, std), distinguishes true physical
outcomes using strict aeronautical touchdown criteria, instruments reward components
(original, shaping, energy penalties), and exports results to JSON and CSV.
"""

from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import gymnasium as gym
import numpy as np
from stable_baselines3 import PPO

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from environments.env_loader import make_environment
from rewards.reward_config import RewardConfig, load_reward_config
from rewards.reward_wrapper import RocketRewardShapingWrapper


@dataclass
class LandingCriteria:
    """Configurable physical touchdown criteria for autonomous rocket landing.

    Physical rationale:
        - max_pad_offset_x: The landing pad is located at x=0 with width ~0.4 (-0.2 to +0.2).
          The lander center must reside over the designated pad surface.
        - max_touchdown_vx: Excessive horizontal shear can snap landing gear or cause lateral tipping.
        - max_touchdown_vy: High descent rate creates excessive kinetic impact force leading to structural failure.
        - max_touchdown_tilt: Steep angles cause the rocket to topple over onto its main chassis.
        - max_touchdown_spin: Angular roll rate at ground contact must be minimal to prevent cartwheeling.
        - require_both_legs: Both landing leg foot contact sensors must register solid contact with the pad surface.
    """
    max_pad_offset_x: float = 0.25      # Pad boundary threshold (|x| <= 0.25)
    max_touchdown_vx: float = 0.40      # Lateral drift speed limit (m/s)
    max_touchdown_vy: float = 0.40      # Vertical descent speed limit (m/s)
    max_touchdown_tilt: float = 0.20    # Max tilt angle (rad, ~11.5 degrees)
    max_touchdown_spin: float = 0.35    # Max angular velocity (rad/s)
    require_both_legs: bool = True       # Left and right leg contact flags == 1.0


def classify_outcome(
    terminated: bool,
    truncated: bool,
    final_step_reward: float,
    final_obs: np.ndarray,
    criteria: Optional[LandingCriteria] = None,
) -> str:
    """Classifies episode outcome using strict physical criteria.

    Distinguishes Gymnasium's native termination/reward signals from the project's
    strict physical landing success metric.

    Outcomes:
        - 'success': Safely grounded within pad boundaries meeting all kinematic limits.
        - 'crash': Collision with terrain, severe kinetic impact, or chassis collapse.
        - 'out_of_bounds': Flown beyond viewport boundaries (|x| >= 1.0).
        - 'timeout': Maximum episode timesteps reached without landing or crashing.
    """
    crit = criteria or LandingCriteria()

    if truncated and not terminated:
        return "timeout"

    if terminated:
        x_dist = abs(final_obs[0])
        y_alt = float(final_obs[1])
        vx = abs(final_obs[2])
        vy = abs(final_obs[3])
        tilt = abs(final_obs[4])
        spin = abs(final_obs[5])
        left_leg = bool(final_obs[6] > 0.5)
        right_leg = bool(final_obs[7] > 0.5)

        # Check physical conditions
        legs_ok = (left_leg and right_leg) if crit.require_both_legs else (left_leg or right_leg)
        pos_ok = (x_dist <= crit.max_pad_offset_x)
        vel_ok = (vx <= crit.max_touchdown_vx and vy <= crit.max_touchdown_vy)
        att_ok = (tilt <= crit.max_touchdown_tilt and spin <= crit.max_touchdown_spin)
        not_crash_reward = (final_step_reward > -50.0)

        # Strict physical landing validation
        if legs_ok and pos_ok and vel_ok and att_ok and not_crash_reward:
            return "success"
        elif final_step_reward >= 80.0 and legs_ok and pos_ok and vel_ok and att_ok:
            # Safe rest bonus awarded by simulator within valid boundaries with required leg contact
            return "success"
        elif x_dist >= 1.0:
            return "out_of_bounds"
        else:
            return "crash"

    return "unknown"


def evaluate_policy(
    model: PPO,
    env: gym.Env,
    n_episodes: int = 100,
    deterministic: bool = True,
    render: bool = False,
    seed: Optional[int] = 42,
    record_trajectory: bool = False,
    criteria: Optional[LandingCriteria] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Runs deterministic evaluation across multiple episodes.

    Args:
        model: Trained PPO policy.
        env: Gymnasium evaluation environment.
        n_episodes: Total number of test episodes.
        deterministic: Whether to use greedy deterministic actions.
        render: Whether to visualize rollouts (human render mode).
        seed: Initial random seed.
        record_trajectory: Whether to preserve full step trajectory transitions.
        criteria: Custom physical landing criteria.

    Returns:
        Tuple containing summary metrics dictionary and list of per-episode record dicts.
    """
    crit = criteria or LandingCriteria()
    episode_records: List[Dict[str, Any]] = []
    first_episode_trajectory: List[Dict[str, Any]] = []

    for ep in range(n_episodes):
        ep_seed = seed + ep if seed is not None else None
        obs, info = env.reset(seed=ep_seed)
        done = False

        total_combined_reward = 0.0
        total_orig_reward = 0.0
        total_shaping_reward = 0.0
        total_energy_penalty = 0.0
        step_count = 0
        last_step_reward = 0.0

        main_engine_steps = 0
        side_thruster_steps = 0
        idle_steps = 0

        while not done:
            action, _states = model.predict(obs, deterministic=deterministic)
            action_int = int(action)
            next_obs, reward, terminated, truncated, info = env.step(action_int)

            step_reward = float(reward)
            total_combined_reward += step_reward
            last_step_reward = step_reward
            step_count += 1

            # Actuator accounting
            if action_int == 2:
                main_engine_steps += 1
            elif action_int in (1, 3):
                side_thruster_steps += 1
            else:
                idle_steps += 1

            # Decompose reward if wrapper is present
            if "reward_components" in info:
                comps = info["reward_components"]
                orig_r = float(comps.get("original_reward", step_reward))
                shape_r = float(comps.get("shaping_reward", 0.0))
                energy_pen = float(comps.get("energy_penalty", 0.0))
            else:
                orig_r = step_reward
                shape_r = 0.0
                energy_pen = 0.0

            total_orig_reward += orig_r
            total_shaping_reward += shape_r
            total_energy_penalty += energy_pen

            if ep == 0 and record_trajectory:
                first_episode_trajectory.append({
                    "step": step_count,
                    "obs": np.array(obs, copy=True),
                    "action": action_int,
                    "reward": step_reward,
                    "reward_components": {
                        "original_reward": orig_r,
                        "shaping_reward": shape_r,
                        "energy_penalty": energy_pen,
                        "combined_reward": step_reward,
                    },
                })

            obs = next_obs
            done = terminated or truncated

        outcome = classify_outcome(
            terminated=terminated,
            truncated=truncated,
            final_step_reward=last_step_reward,
            final_obs=obs,
            criteria=crit,
        )

        record = {
            "episode": ep + 1,
            "cumulative_reward": round(total_combined_reward, 3),
            "original_reward": round(total_orig_reward, 3),
            "shaping_reward": round(total_shaping_reward, 3),
            "energy_penalty": round(total_energy_penalty, 3),
            "episode_length": step_count,
            "outcome": outcome,
            "main_engine_ratio": round(main_engine_steps / max(1, step_count), 4),
            "side_thruster_ratio": round(side_thruster_steps / max(1, step_count), 4),
            "final_x": round(float(obs[0]), 4),
            "final_y": round(float(obs[1]), 4),
            "final_vx": round(float(obs[2]), 4),
            "final_vy": round(float(obs[3]), 4),
            "final_tilt_rad": round(float(obs[4]), 4),
            "final_spin_rad_s": round(float(obs[5]), 4),
            "left_leg_contact": float(obs[6]),
            "right_leg_contact": float(obs[7]),
            "final_step_reward": round(last_step_reward, 2),
        }
        episode_records.append(record)

    # Compute aggregate statistical metrics
    rewards = [rec["cumulative_reward"] for rec in episode_records]
    orig_rewards = [rec["original_reward"] for rec in episode_records]
    lengths = [rec["episode_length"] for rec in episode_records]
    main_ratios = [rec["main_engine_ratio"] for rec in episode_records]
    side_ratios = [rec["side_thruster_ratio"] for rec in episode_records]
    final_vx_list = [abs(rec["final_vx"]) for rec in episode_records]
    final_vy_list = [abs(rec["final_vy"]) for rec in episode_records]
    final_tilt_list = [abs(rec["final_tilt_rad"]) for rec in episode_records]
    final_spin_list = [abs(rec["final_spin_rad_s"]) for rec in episode_records]
    final_x_list = [abs(rec["final_x"]) for rec in episode_records]

    success_count = sum(1 for rec in episode_records if rec["outcome"] == "success")
    crash_count = sum(1 for rec in episode_records if rec["outcome"] in ("crash", "out_of_bounds"))
    timeout_count = sum(1 for rec in episode_records if rec["outcome"] == "timeout")

    metrics: Dict[str, Any] = {
        "n_episodes": n_episodes,
        "mean_episode_reward": round(float(np.mean(rewards)), 3),
        "median_episode_reward": round(float(np.median(rewards)), 3),
        "reward_std": round(float(np.std(rewards)), 3),
        "min_episode_reward": round(float(np.min(rewards)), 3),
        "max_episode_reward": round(float(np.max(rewards)), 3),
        "mean_original_reward": round(float(np.mean(orig_rewards)), 3),
        "mean_episode_length": round(float(np.mean(lengths)), 2),
        "landing_success_rate": round(success_count / n_episodes, 4),
        "crash_rate": round(crash_count / n_episodes, 4),
        "timeout_rate": round(timeout_count / n_episodes, 4),
        "success_count": success_count,
        "crash_count": crash_count,
        "timeout_count": timeout_count,
        "mean_landing_vx": round(float(np.mean(final_vx_list)), 4),
        "mean_landing_vy": round(float(np.mean(final_vy_list)), 4),
        "mean_absolute_tilt_rad": round(float(np.mean(final_tilt_list)), 4),
        "mean_absolute_spin_rad_s": round(float(np.mean(final_spin_list)), 4),
        "mean_pad_offset_x": round(float(np.mean(final_x_list)), 4),
        "main_engine_frequency": round(float(np.mean(main_ratios)), 4),
        "side_thruster_frequency": round(float(np.mean(side_ratios)), 4),
    }

    if record_trajectory:
        metrics["sample_trajectory"] = first_episode_trajectory

    return metrics, episode_records


def save_evaluation_artifacts(
    metrics: Dict[str, Any],
    records: List[Dict[str, Any]],
    output_dir: Union[str, Path],
    filename_prefix: str = "evaluation",
) -> Tuple[Path, Path]:
    """Saves metrics to JSON and episode records to CSV."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    json_path = out_path / f"{filename_prefix}_metrics.json"
    csv_path = out_path / f"{filename_prefix}_episodes.csv"

    # Save JSON summary (omit full raw trajectory from JSON summary)
    metrics_to_dump = {k: v for k, v in metrics.items() if k != "sample_trajectory"}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics_to_dump, f, indent=2)

    # Save CSV records
    if records:
        fieldnames = list(records[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    return json_path, csv_path


def run_evaluation(
    model_path: Union[str, Path],
    n_episodes: int = 50,
    deterministic: bool = True,
    render_mode: Optional[str] = None,
    output_dir: Optional[Union[str, Path]] = None,
    reward_config: Optional[Union[RewardConfig, Dict[str, Any], str]] = None,
    seed: int = 42,
    record_trajectory: bool = False,
    criteria: Optional[LandingCriteria] = None,
) -> Dict[str, Any]:
    """Top-level evaluation runner."""
    model = PPO.load(str(model_path))
    env = make_environment(
        env_id="LunarLander-v3",
        continuous=False,
        render_mode=render_mode,
        reward_config=reward_config,
    )

    try:
        metrics, records = evaluate_policy(
            model=model,
            env=env,
            n_episodes=n_episodes,
            deterministic=deterministic,
            render=bool(render_mode == "human"),
            seed=seed,
            record_trajectory=record_trajectory,
            criteria=criteria,
        )

        if output_dir is not None:
            json_file, csv_file = save_evaluation_artifacts(metrics, records, output_dir)
            metrics["saved_json"] = str(json_file)
            metrics["saved_csv"] = str(csv_file)

        return metrics
    finally:
        env.close()
