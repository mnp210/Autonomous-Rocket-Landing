"""Interactive flight simulation visualizer and trajectory renderer.

Supports both modern 16:9 widescreen AerospaceRenderer and legacy Gymnasium fallback.
"""

from pathlib import Path
import sys
import time
from typing import Optional

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import gymnasium as gym
import pygame
from stable_baselines3 import PPO

from environments.lunar_lander import make_lunar_lander_env
from evaluation.evaluate import LandingCriteria, classify_outcome
from visualization.aerospace_renderer import AerospaceRenderer
from visualization.cinematic_renderer import CinematicAerospaceRenderer
from visualization.realistic3d_renderer import Realistic3DRenderer


DEFAULT_MODEL = repo_root / "models" / "benchmark" / "D_curriculum_and_dr" / "seed_42" / "final_model.zip"


def run_simulation(
    model_path: Optional[str] = None,
    episodes: int = 3,
    renderer_type: str = "3d",
    speed: float = 0.5,
):
    """Runs and renders the landing environment using trained policy or random baseline.

    Args:
        model_path: Path to trained PPO model archive (.zip).
        episodes: Number of episodes to simulate.
        renderer_type: '3d' (realistic Panda3D PBR), 'cinematic' (Pygame 2.5D tracking), 'aerospace' (16:9 fixed), or 'gymnasium' (legacy 4:3).
        speed: Playback speed multiplier (default: 0.5x cinematic).
    """
    model_file = Path(model_path) if model_path else DEFAULT_MODEL
    model = PPO.load(str(model_file)) if model_file.exists() else None

    is_custom = (renderer_type in ("3d", "cinematic", "aerospace"))
    gym_render_mode = None if is_custom else "human"

    env = gym.make("LunarLander-v3", render_mode=gym_render_mode, continuous=False)
    if renderer_type == "3d":
        renderer = Realistic3DRenderer(headless=False, speed_factor=speed)
    elif renderer_type == "cinematic":
        renderer = CinematicAerospaceRenderer(headless=False, enable_camera_tracking=True, speed_factor=speed)
    elif renderer_type == "aerospace":
        renderer = AerospaceRenderer(headless=False)
    else:
        renderer = None
    criteria = LandingCriteria()
    clock = pygame.time.Clock()

    print("=" * 80)
    print(" AEROSPACE SIMULATION RUNNER")
    print("=" * 80)
    print(f" Model    : {model_file.name if model else 'Random Actions'}")
    print(f" Renderer : {renderer_type.upper()}")
    print(f" Episodes : {episodes}")
    print("=" * 80)

    for ep in range(episodes):
        obs, _ = env.reset(seed=42 + ep)
        done = False
        step = 0
        total_reward = 0.0

        if renderer and hasattr(renderer, "reset"):
            tel_init = renderer.extract_telemetry(
                env, obs, action=0, step=0,
                reward=0.0, terminated=False, truncated=False,
                cumulative_reward=0.0, criteria=criteria,
            )
            if hasattr(renderer, "render_snapshot"):
                renderer.reset(initial_snapshot=tel_init)
            else:
                renderer.reset(initial_telemetry=tel_init)

        while not done:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    print("[INFO] Exiting simulation.")
                    if renderer:
                        renderer.close()
                    env.close()
                    return

            if model:
                action, _ = model.predict(obs, deterministic=True)
                act_int = int(action)
            else:
                act_int = int(env.action_space.sample())

            if renderer:
                tel = renderer.extract_telemetry(
                    env, obs, action=act_int, step=step,
                    reward=0.0, terminated=False, truncated=False,
                    cumulative_reward=total_reward, criteria=criteria,
                )
                renderer.render_frame(env, tel)

            obs, reward, terminated, truncated, _ = env.step(act_int)
            total_reward += reward
            done = terminated or truncated
            step += 1
            clock.tick(50)

        outcome = classify_outcome(
            terminated=terminated,
            truncated=truncated,
            final_step_reward=reward,
            final_obs=obs,
            criteria=criteria,
        )

        if renderer:
            tel_final = renderer.extract_telemetry(
                env, obs, action=0, step=step,
                reward=reward, terminated=terminated, truncated=truncated,
                cumulative_reward=total_reward, criteria=criteria,
            )
            hold_start = time.time()
            exit_debrief = False
            while time.time() - hold_start < 2.0:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        print("[INFO] Exiting simulation.")
                        if renderer:
                            renderer.close()
                        env.close()
                        return
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                        exit_debrief = True
                        break
                if exit_debrief:
                    break
                renderer.render_frame(env, tel_final)
                clock.tick(50)

        print(f"Episode {ep + 1} finished in {step} steps. Outcome: {outcome.upper()} | Reward: {total_reward:+.2f}")

    if renderer:
        renderer.close()
    env.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Visualize Rocket Landing Simulation")
    parser.add_argument("--model-path", type=str, default=None, help="Path to trained PPO model")
    parser.add_argument("--episodes", type=int, default=3, help="Number of episodes to simulate")
    parser.add_argument(
        "--renderer",
        type=str,
        default="3d",
        choices=["3d", "cinematic", "aerospace", "gymnasium"],
        help="Rendering backend: '3d' (realistic Panda3D PBR), 'cinematic' (Pygame 2.5D tracking), 'aerospace' (16:9 fixed), or 'gymnasium' (legacy 4:3)",
    )
    parser.add_argument("--speed", type=float, default=0.5, help="Playback speed multiplier (default: 0.5)")
    args = parser.parse_args()

    run_simulation(
        model_path=args.model_path,
        episodes=args.episodes,
        renderer_type=args.renderer,
        speed=args.speed,
    )
