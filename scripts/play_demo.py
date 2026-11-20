"""Interactive Demonstration and Test Flight Harness.

Allows the user to:
1. [AI Mode] Watch the trained PPO autonomous rocket landing agent fly and land in a real-time graphical Pygame window.
2. [Human Mode] Pilot the rocket manually using keyboard arrow keys (UP/LEFT/RIGHT or WASD) and test landing skills against the AI.
3. [Storm Mode] Test the AI under extreme turbulent crosswind conditions.

Usage:
    python scripts/play_demo.py --mode ai
    python scripts/play_demo.py --mode human
    python scripts/play_demo.py --mode storm
    python scripts/play_demo.py --mode ai --renderer gymnasium  # Fallback to legacy
"""

import argparse
from pathlib import Path
import subprocess
import sys
import time
from typing import Optional

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Auto-detect and switch to .venv python if invoked from system python
venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    sys.exit(subprocess.call([str(venv_python)] + sys.argv))

import gymnasium as gym
import numpy as np
import pygame
from stable_baselines3 import PPO

from environments.env_loader import make_environment
from evaluation.evaluate import LandingCriteria, classify_outcome
from visualization.aerospace_renderer import AerospaceRenderer
from visualization.cinematic_renderer import CinematicAerospaceRenderer
from visualization.realistic3d_renderer import Realistic3DRenderer


from backend.latch import TerminalStateLatch


DEFAULT_MODEL_PATH = repo_root / "models" / "benchmark" / "D_curriculum_and_dr" / "seed_42" / "final_model.zip"


def play_ai_flight(
    model_path: Path,
    enable_wind: bool = False,
    wind_power: float = 10.0,
    turbulence: float = 0.8,
    storm_severity: str = "moderate",
    policy_mode: str = "deterministic",
    base_seed: Optional[int] = 42,
    random_seeds: bool = False,
    episodes: int = 3,
    renderer_type: str = "3d",
    speed: float = 0.5,
    theme: str = "spaceport",
):
    """Watches the autonomous agent land in a rendered graphical window."""
    if not model_path.exists():
        print(f"[ERROR] Trained model file not found: {model_path}")
        return

    print("=" * 80)
    print(" LAUNCHING AUTONOMOUS AGENT DEMO")
    print("=" * 80)
    print(f" Model           : {model_path.name}")
    print(f" Policy Mode     : {policy_mode.upper()} ({'Stochastic Action Distribution' if policy_mode == 'stochastic' else 'Greedy Argmax (Reproducible)'})")
    print(f" Seed Mode       : {'Independent Random' if random_seeds else f'Sequential (Base: {base_seed})'}")
    print(f" Renderer        : {renderer_type.upper()}")
    if renderer_type == "3d":
        print(f" Visual Theme    : {theme.upper()}")
    print(f" Playback Speed  : {speed:.2f}x (Press 1=1.0x, 2=0.75x, 3=0.5x, 4=0.25x)")
    if enable_wind:
        print(f" Atmosphere      : STORM [{storm_severity.upper()}] (Wind: {wind_power:.1f} m/s, Turbulence: {turbulence:.2f})")
    else:
        print(f" Atmosphere      : NOMINAL CALM (Wind: 0.0 m/s)")
    print(f" Episodes        : {episodes}")
    print(" Close the window or press ESC to exit.")
    print("=" * 80)

    model = PPO.load(str(model_path))
    is_custom = (renderer_type in ("3d", "cinematic", "aerospace"))
    gym_render_mode = None if is_custom else "human"

    env = gym.make(
        "LunarLander-v3",
        render_mode=gym_render_mode,
        continuous=False,
        gravity=-10.0,
        enable_wind=enable_wind,
        wind_power=wind_power,
        turbulence_power=turbulence,
    )
    criteria = LandingCriteria()
    if renderer_type == "3d":
        renderer = Realistic3DRenderer(headless=False, speed_factor=speed, theme=theme)
    elif renderer_type == "cinematic":
        renderer = CinematicAerospaceRenderer(
            headless=False, enable_camera_tracking=True, speed_factor=speed
        )
    elif renderer_type == "aerospace":
        renderer = AerospaceRenderer(headless=False)
    else:
        renderer = None
    clock = pygame.time.Clock()

    for ep in range(episodes):
        if random_seeds or base_seed is None:
            ep_seed = int(np.random.randint(0, 1000000))
        else:
            ep_seed = base_seed + ep

        obs, _ = env.reset(seed=ep_seed)
        latch = TerminalStateLatch()
        done = False
        total_reward = 0.0
        step = 0
        print(f"\n--- Episode {ep + 1}/{episodes} [Seed: {ep_seed}] [Policy: {policy_mode.upper()}] Starting ---")

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
                    print("\n[INFO] Exiting simulation window.")
                    if renderer:
                        renderer.close()
                    env.close()
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(1.0)
                        print("[SPEED] 1.00x (Real-time)")
                    elif event.key == pygame.K_2 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(0.75)
                        print("[SPEED] 0.75x (Moderate)")
                    elif event.key == pygame.K_3 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(0.50)
                        print("[SPEED] 0.50x (Cinematic)")
                    elif event.key == pygame.K_4 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(0.25)
                        print("[SPEED] 0.25x (Slow-Motion)")
                    elif event.key == pygame.K_LEFTBRACKET and renderer and hasattr(renderer, "set_speed_factor"):
                        new_s = max(0.25, renderer.speed_factor - 0.25)
                        renderer.set_speed_factor(new_s)
                        print(f"[SPEED] Decreased to {new_s:.2f}x")
                    elif event.key == pygame.K_RIGHTBRACKET and renderer and hasattr(renderer, "set_speed_factor"):
                        new_s = min(1.0, renderer.speed_factor + 0.25)
                        renderer.set_speed_factor(new_s)
                        print(f"[SPEED] Increased to {new_s:.2f}x")

            # Check terminal state latch before deciding action
            is_latched = latch.check_and_update(obs, terminated=False, truncated=False, step=step)

            if is_latched:
                # Terminal latch engaged: halt policy predictions, zero propulsion immediately
                act_int = 0
            else:
                deterministic = (policy_mode == "deterministic")
                action, _ = model.predict(obs, deterministic=deterministic)
                act_int = int(action)

            if renderer:
                tel = renderer.extract_telemetry(
                    env, obs, action=act_int, step=step,
                    reward=0.0, terminated=False, truncated=False,
                    cumulative_reward=total_reward, criteria=criteria,
                )
                renderer.render_frame(env, tel)

            obs, reward, terminated, truncated, _ = env.step(act_int)
            total_reward += reward
            step += 1

            latch.check_and_update(obs, terminated=terminated, truncated=truncated, step=step)

            if terminated or truncated:
                done = True
            elif latch.is_latched:
                # If touching down and settled before Box2D body sleeps, allow up to 60 steps of pure zero-action idle settling
                latch.ground_settle_steps += 1
                if latch.ground_settle_steps >= 60:
                    terminated = True
                    done = True

            effective_speed = getattr(renderer, "speed_factor", speed) if renderer else speed
            clock.tick(max(10, int(round(50.0 * effective_speed))))

        # Final debrief frame with guaranteed zero propulsion
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
                reward=reward, terminated=True, truncated=False,
                cumulative_reward=total_reward, criteria=criteria,
            )
            # Render debrief for 2 seconds (or skip via SPACE/ESC)
            start_hold = time.time()
            exit_debrief = False
            while time.time() - start_hold < 2.0:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        print("\n[INFO] Exiting simulation window.")
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

        x, y, vx, vy, theta, theta_dot, leg_l, leg_r = obs
        print(f"Episode {ep + 1} Finished in {step} steps:")
        print(f"  • Final Outcome : >>> {outcome.upper()} <<<")
        print(f"  • Cumulative Rwd: {total_reward:+.2f}")
        print(f"  • Touchdown Pos : x={x:+.3f}, y={y:.3f}")
        print(f"  • Touchdown Vel : vx={vx:+.3f} m/s, vy={vy:+.3f} m/s")
        print(f"  • Body Tilt     : {theta * 57.2958:+.2f}°")

    if renderer:
        renderer.close()
    env.close()
    print("\n[INFO] Autonomous demo completed.")


def play_human_flight(
    episodes: int = 3,
    renderer_type: str = "3d",
    speed: float = 0.5,
    theme: str = "spaceport",
):
    """Allows human user to pilot the rocket using keyboard controls."""
    print("=" * 80)
    print(" MANUAL PILOT MODE: FLY THE ROCKET YOURSELF!")
    print("=" * 80)
    print(f" Renderer       : {renderer_type.upper()}")
    if renderer_type == "3d":
        print(f" Visual Theme   : {theme.upper()}")
    print(f" Playback Speed : {speed:.2f}x (Press 1=1.0x, 2=0.75x, 3=0.5x, 4=0.25x)")
    print(" CONTROLS:")
    print("   • UP ARROW    or [ W ] : Fire Main Engine (Upward Thrust)")
    print("   • LEFT ARROW  or [ A ] : Fire Left Thruster (Tilt Rocket Right)")
    print("   • RIGHT ARROW or [ D ] : Fire Right Thruster (Tilt Rocket Left)")
    print("   • NO KEYS              : Coast (Thrusters Idle)")
    print("   • [ 1 / 2 / 3 / 4 ]    : Speed: 1.0x / 0.75x / 0.5x / 0.25x")
    print("   • [ ESC ]              : Quit to Menu")
    print("=" * 80)
    print(" Landing Goal: Touch down softly on the yellow flags at (x=0, y=0) with dual leg contact!")
    print("=" * 80)

    is_custom = (renderer_type in ("3d", "cinematic", "aerospace"))
    gym_render_mode = None if is_custom else "human"
    env = gym.make("LunarLander-v3", render_mode=gym_render_mode, continuous=False)
    criteria = LandingCriteria()
    if renderer_type == "3d":
        renderer = Realistic3DRenderer(headless=False, speed_factor=speed, theme=theme)
    elif renderer_type == "cinematic":
        renderer = CinematicAerospaceRenderer(
            headless=False, enable_camera_tracking=True, speed_factor=speed
        )
    elif renderer_type == "aerospace":
        renderer = AerospaceRenderer(headless=False)
    else:
        renderer = None
    clock = pygame.time.Clock()

    for ep in range(episodes):
        obs, _ = env.reset(seed=100 + ep)
        latch = TerminalStateLatch()
        done = False
        total_reward = 0.0
        step = 0
        print(f"\n--- Pilot Flight {ep + 1}/{episodes} — READY FOR TAKEOFF! ---")

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
                    print("\n[INFO] Exiting pilot flight.")
                    if renderer:
                        renderer.close()
                    env.close()
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(1.0)
                        print("[SPEED] 1.00x (Real-time)")
                    elif event.key == pygame.K_2 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(0.75)
                        print("[SPEED] 0.75x (Moderate)")
                    elif event.key == pygame.K_3 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(0.50)
                        print("[SPEED] 0.50x (Cinematic)")
                    elif event.key == pygame.K_4 and renderer and hasattr(renderer, "set_speed_factor"):
                        renderer.set_speed_factor(0.25)
                        print("[SPEED] 0.25x (Slow-Motion)")

            # Check terminal latch before taking user input
            is_latched = latch.check_and_update(obs, terminated=False, truncated=False, step=step)

            if is_latched:
                # Terminal latch engaged: override user input, zero thrusters on ground
                action = 0
            else:
                keys = pygame.key.get_pressed()
                action = 0  # Default NO-OP

                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    action = 2  # Main Engine
                elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    action = 1  # Left Orientation Thruster
                elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    action = 3  # Right Orientation Thruster

            if renderer:
                tel = renderer.extract_telemetry(
                    env, obs, action=action, step=step,
                    reward=0.0, terminated=False, truncated=False,
                    cumulative_reward=total_reward, criteria=criteria,
                )
                renderer.render_frame(env, tel)

            obs, reward, terminated, truncated, _ = env.step(action)
            total_reward += reward
            step += 1

            latch.check_and_update(obs, terminated=terminated, truncated=truncated, step=step)

            if terminated or truncated:
                done = True
            elif latch.is_latched:
                latch.ground_settle_steps += 1
                if latch.ground_settle_steps >= 60:
                    terminated = True
                    done = True

            if step % 50 == 0:
                x, y, vx, vy, theta, _, leg_l, leg_r = obs
                print(f"  Step {step:3d} | Alt: {y:.2f} | Speed: vx={vx:+.2f}, vy={vy:+.2f} | Tilt: {theta*57.3:+.1f}°")

            effective_speed = getattr(renderer, "speed_factor", speed) if renderer else speed
            clock.tick(max(10, int(round(50.0 * effective_speed))))

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
                reward=reward, terminated=True, truncated=False,
                cumulative_reward=total_reward, criteria=criteria,
            )
            # Render debrief for 2 seconds (or skip via SPACE/ESC)
            start_hold = time.time()
            exit_debrief = False
            while time.time() - start_hold < 2.0:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        print("\n[INFO] Exiting pilot flight.")
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

        x, y, vx, vy, theta, _, leg_l, leg_r = obs
        print(f"\nFlight {ep + 1} Result:")
        print(f"  • Flight Outcome: >>> {outcome.upper()} <<<")
        print(f"  • Total Score   : {total_reward:+.2f}")
        print(f"  • Final Altitude: {y:.3f}")
        print(f"  • Descent Speed : vy={vy:+.3f} m/s (Limit: <= 0.40)")
        print(f"  • Pitch Angle   : {theta * 57.2958:+.2f}° (Limit: <= 11.5°)")
        print(f"  • Landing Pad   : x={x:+.3f} (Limit: |x| <= 0.25)")

    if renderer:
        renderer.close()
    env.close()
    print("\n[INFO] Pilot session concluded.")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Rocket Landing Demo & Interactive Test")
    parser.add_argument(
        "--mode",
        type=str,
        default="ai",
        choices=["ai", "human", "storm"],
        help="Flight mode: 'ai' (autonomous agent), 'human' (manual keyboard pilot), 'storm' (turbulent crosswind AI)",
    )
    parser.add_argument(
        "--renderer",
        type=str,
        default="3d",
        choices=["3d", "cinematic", "aerospace", "gymnasium"],
        help="Rendering presentation: '3d' (realistic Panda3D PBR), 'cinematic' (Pygame 2.5D tracking), 'aerospace' (16:9 fixed), or 'gymnasium' (legacy 4:3)",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default="spaceport",
        choices=["spaceport", "lunar"],
        help="Visual theme for 3D renderer: 'spaceport' (daylight terrestrial launchpad matching reference) or 'lunar' (deep space)",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=str(DEFAULT_MODEL_PATH),
        help="Path to trained PPO model archive (.zip)",
    )
    parser.add_argument(
        "--policy-mode",
        type=str,
        default="deterministic",
        choices=["deterministic", "stochastic"],
        help="PPO action prediction mode: 'deterministic' (greedy argmax, reproducible) or 'stochastic' (samples categorical distribution for behavioural diversity)",
    )
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Shorthand flag to enable stochastic policy prediction mode",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed for reproducible episodes (default: 42)",
    )
    parser.add_argument(
        "--random-seeds",
        action="store_true",
        help="Generate independent unconstrained random seeds for each demonstration episode",
    )
    parser.add_argument(
        "--storm-severity",
        type=str,
        default="moderate",
        choices=["moderate", "severe", "extreme"],
        help="Atmospheric disturbance tier for storm mode: 'moderate' (10 m/s wind, 0.8 turb - standard test), 'severe' (15 m/s wind, 1.2 turb), 'extreme' (20 m/s wind, 2.0 turb - physical limit stress-test)",
    )
    parser.add_argument(
        "--wind",
        type=float,
        default=None,
        help="Custom wind disturbance magnitude for storm mode (overrides --storm-severity, range: 0.0-25.0)",
    )
    parser.add_argument(
        "--turbulence",
        type=float,
        default=None,
        help="Custom turbulence rotational torque for storm mode (overrides --storm-severity, range: 0.0-2.5)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=3,
        help="Number of flights to execute (default: 3)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=0.5,
        choices=[0.25, 0.5, 0.75, 1.0],
        help="Presentation playback speed: 1.0 (real-time), 0.75 (moderate), 0.5 (cinematic default), 0.25 (slow-motion)",
    )
    args = parser.parse_args()

    model_path = Path(args.model_path)

    policy_mode = "stochastic" if args.stochastic else args.policy_mode

    storm_presets = {
        "moderate": (10.0, 0.8),
        "severe": (15.0, 1.2),
        "extreme": (20.0, 2.0),
    }
    preset_wind, preset_turb = storm_presets.get(args.storm_severity, (10.0, 0.8))
    wind_power = args.wind if args.wind is not None else preset_wind
    turbulence = args.turbulence if args.turbulence is not None else preset_turb

    if args.mode == "ai":
        play_ai_flight(
            model_path=model_path,
            enable_wind=False,
            policy_mode=policy_mode,
            base_seed=args.seed,
            random_seeds=args.random_seeds,
            episodes=args.episodes,
            renderer_type=args.renderer,
            speed=args.speed,
            theme=args.theme,
        )
    elif args.mode == "storm":
        play_ai_flight(
            model_path=model_path,
            enable_wind=True,
            wind_power=wind_power,
            turbulence=turbulence,
            storm_severity=args.storm_severity if args.wind is None else f"custom ({wind_power:.1f}m/s)",
            policy_mode=policy_mode,
            base_seed=args.seed,
            random_seeds=args.random_seeds,
            episodes=args.episodes,
            renderer_type=args.renderer,
            speed=args.speed,
            theme=args.theme,
        )
    elif args.mode == "human":
        play_human_flight(episodes=args.episodes, renderer_type=args.renderer, speed=args.speed, theme=args.theme)


if __name__ == "__main__":
    main()
