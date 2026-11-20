"""Stage 8.4 — Realistic 3D Showcase and Demonstration Video Generator.

Executes a deterministic flight of the trained PPO autonomous landing agent,
records physical snapshots into SnapshotTimeline, generates 60 FPS continuous
3D demonstration video, captures the 9 flight phase milestone screenshots,
and benchmarks 3D rendering throughput on RTX 3050 Ti hardware.
"""

import math
import os
from pathlib import Path
import shutil
import sys
import time
from typing import List, Tuple

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# On Windows, PyTorch's c10.dll must be pre-loaded before Panda3D OpenGL runtime
try:
    import torch
except Exception:
    pass

import cv2
import gymnasium as gym
import numpy as np
from stable_baselines3 import PPO

from evaluation.evaluate import LandingCriteria, classify_outcome
from visualization.realistic3d_renderer import Realistic3DRenderer
from visualization.timeline import SimulationSnapshot, SnapshotTimeline, capture_snapshot_from_env


DEFAULT_MODEL = repo_root / "models" / "benchmark" / "D_curriculum_and_dr" / "seed_42" / "final_model.zip"
ARTIFACTS_DIR = Path(r"C:\Users\lnami\.gemini\antigravity\brain\2e707fdc-b6f8-4deb-9783-ae412d4e1706")
SHOWCASE_DIR = repo_root / "showcase"


def record_3d_showcase(
    model_path: Path = DEFAULT_MODEL,
    speed_factor: float = 0.5,
    video_fps: int = 30,
    seed: int = 42,
) -> None:
    """Executes deterministic autonomous landing flight and records 3D showcase video and phase captures."""
    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    if ARTIFACTS_DIR.exists():
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(" STAGE 8.4 — REALISTIC 3D SHOWCASE & BENCHMARK SUITE")
    print("=" * 80)
    print(f" Model Archive   : {model_path.relative_to(repo_root)}")
    print(f" Playback Speed  : {speed_factor:.2f}x (Deterministic Interpolation)")
    print(f" Target Video FPS: {video_fps} FPS")
    print(f" Environment Seed: {seed}")
    print("=" * 80)

    # 1. Run Physical Simulation and Record Timeline (Pure Box2D - zero rendering)
    print("[1/4] Simulating autonomous flight with PPO policy...")
    t_sim_start = time.perf_counter()
    env = gym.make("LunarLander-v3", continuous=False, gravity=-10.0, render_mode=None)
    model = PPO.load(str(model_path))
    criteria = LandingCriteria()

    obs, _ = env.reset(seed=seed)
    timeline = SnapshotTimeline(dt=0.02)
    step = 0
    total_reward = 0.0
    done = False

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        act_int = int(action)

        snap = capture_snapshot_from_env(
            env=env,
            obs=obs,
            action=act_int,
            step=step,
            reward=0.0,
            cumulative_reward=total_reward,
            terminated=False,
            truncated=False,
        )
        timeline.add_snapshot(snap)

        obs, reward, terminated, truncated, _ = env.step(act_int)
        total_reward += reward
        step += 1
        done = terminated or truncated

    outcome = classify_outcome(
        terminated=terminated,
        truncated=truncated,
        final_step_reward=reward,
        final_obs=obs,
        criteria=criteria,
    ).upper()

    final_snap = capture_snapshot_from_env(
        env=env,
        obs=obs,
        action=0,
        step=step,
        reward=reward,
        cumulative_reward=total_reward,
        terminated=terminated,
        truncated=truncated,
        outcome=outcome,
    )
    timeline.add_snapshot(final_snap)
    env.close()

    t_sim_end = time.perf_counter()
    sim_wall_dur = t_sim_end - t_sim_start
    total_sim_time = timeline.total_sim_time
    total_steps = len(timeline)
    print(f"[OK] Simulation completed: {total_steps} steps | Sim Time: {total_sim_time:.2f}s | Outcome: {outcome} | Wall: {sim_wall_dur:.3f}s")

    # 2. Initialize Realistic 3D Renderer
    print("[2/4] Initializing Panda3D Hardware PBR Offscreen Renderer...")
    renderer = Realistic3DRenderer(headless=True, width=1280, height=720, speed_factor=speed_factor)
    if len(timeline) > 0 and timeline.get_snapshot(0).terrain_coords:
        renderer.update_terrain_from_coords(timeline.get_snapshot(0).terrain_coords)

    # 3. Render 3D Video & Capture 9 Phase Screenshots
    presentation_duration = total_sim_time / speed_factor
    # Add 2.5 seconds post-touchdown debrief hold
    debrief_hold_sec = 2.5
    total_pres_duration = presentation_duration + debrief_hold_sec
    total_frames = int(round(total_pres_duration * video_fps))

    video_path = SHOWCASE_DIR / "realistic3d_landing_demo.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, video_fps, (1280, 720))

    print(f"[3/4] Rendering {total_frames} frames ({total_pres_duration:.2f}s @ {video_fps} FPS)...")
    phase_captures = {
        "realistic3d_1_high_altitude_approach": False,
        "realistic3d_2_guidance_burn_ignition": False,
        "realistic3d_3_sustained_deceleration": False,
        "realistic3d_4_rcs_attitude_correction": False,
        "realistic3d_5_engine_cutoff": False,
        "realistic3d_6_terminal_regolith_dust": False,
        "realistic3d_7_first_gear_contact": False,
        "realistic3d_8_dual_gear_contact": False,
        "realistic3d_9_settled_touchdown_debrief": False,
    }

    t_render_start = time.perf_counter()
    frame_times = []

    for f_idx in range(total_frames):
        f_start = time.perf_counter()
        pres_t = f_idx / float(video_fps)

        if pres_t <= presentation_duration:
            snap_cur = timeline.sample_interpolated(pres_t, speed_factor=speed_factor)
        else:
            # Debrief hold frame
            snap_cur = final_snap

        rgb_frame = renderer.render_snapshot(snap_cur)
        bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
        writer.write(bgr_frame)

        # Detect and capture milestone phases
        # Phase 1: High altitude approach (early descent, alt > 5.0)
        if not phase_captures["realistic3d_1_high_altitude_approach"] and snap_cur.sim_time >= 0.8 and snap_cur.altitude > 4.0:
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_1_high_altitude_approach.png"))
            phase_captures["realistic3d_1_high_altitude_approach"] = True
            print("  [CAP] Captured Phase 1: High Altitude Approach")

        # Phase 2: Guidance burn ignition (main throttle firing)
        if not phase_captures["realistic3d_2_guidance_burn_ignition"] and snap_cur.throttle > 0.8 and snap_cur.altitude > 3.0:
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_2_guidance_burn_ignition.png"))
            phase_captures["realistic3d_2_guidance_burn_ignition"] = True
            print("  [CAP] Captured Phase 2: Guidance Burn Ignition")

        # Phase 3: Sustained deceleration (braking at mid altitude)
        if not phase_captures["realistic3d_3_sustained_deceleration"] and snap_cur.throttle > 0.9 and 1.5 < snap_cur.altitude < 2.8:
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_3_sustained_deceleration.png"))
            phase_captures["realistic3d_3_sustained_deceleration"] = True
            print("  [CAP] Captured Phase 3: Sustained Deceleration")

        # Phase 4: RCS attitude correction (RCS active at mid altitude)
        if not phase_captures["realistic3d_4_rcs_attitude_correction"] and (snap_cur.rcs_left > 0.5 or snap_cur.rcs_right > 0.5) and snap_cur.altitude < 6.0:
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_4_rcs_attitude_correction.png"))
            phase_captures["realistic3d_4_rcs_attitude_correction"] = True
            print("  [CAP] Captured Phase 4: RCS Attitude Correction")

        # Phase 5: Engine cutoff (throttle cut near ground)
        if not phase_captures["realistic3d_5_engine_cutoff"] and phase_captures["realistic3d_3_sustained_deceleration"] and snap_cur.throttle < 0.1 and snap_cur.altitude < 1.2:
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_5_engine_cutoff.png"))
            phase_captures["realistic3d_5_engine_cutoff"] = True
            print("  [CAP] Captured Phase 5: Engine Cutoff")

        # Phase 6: Terminal regolith dust (low altitude with dust ejecta)
        if not phase_captures["realistic3d_6_terminal_regolith_dust"] and snap_cur.altitude < 0.6:
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_6_terminal_regolith_dust.png"))
            phase_captures["realistic3d_6_terminal_regolith_dust"] = True
            print("  [CAP] Captured Phase 6: Terminal Regolith Dust")

        # Phase 7: First gear contact (one leg touching)
        if not phase_captures["realistic3d_7_first_gear_contact"] and (snap_cur.left_contact or snap_cur.right_contact):
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_7_first_gear_contact.png"))
            phase_captures["realistic3d_7_first_gear_contact"] = True
            print("  [CAP] Captured Phase 7: First Gear Contact")

        # Phase 8: Dual gear contact (both legs on pad)
        if not phase_captures["realistic3d_8_dual_gear_contact"] and (snap_cur.left_contact and snap_cur.right_contact):
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_8_dual_gear_contact.png"))
            phase_captures["realistic3d_8_dual_gear_contact"] = True
            print("  [CAP] Captured Phase 8: Dual Gear Contact")

        # Phase 9: Settled touchdown with debrief card
        if not phase_captures["realistic3d_9_settled_touchdown_debrief"] and pres_t >= presentation_duration + 1.0:
            renderer.save_screenshot(str(SHOWCASE_DIR / "realistic3d_9_settled_touchdown_debrief.png"))
            phase_captures["realistic3d_9_settled_touchdown_debrief"] = True
            print("  [CAP] Captured Phase 9: Settled Touchdown & Debrief")

        f_end = time.perf_counter()
        frame_times.append(f_end - f_start)

        if (f_idx + 1) % 60 == 0 or (f_idx + 1) == total_frames:
            pct = (f_idx + 1) / total_frames * 100.0
            fps_cur = 1.0 / np.mean(frame_times[-30:])
            print(f"    Frame {f_idx + 1:4d}/{total_frames} ({pct:5.1f}%) | Throughput: {fps_cur:.1f} FPS")

    writer.release()
    renderer.close()

    t_render_end = time.perf_counter()
    total_render_sec = t_render_end - t_render_start
    avg_fps = total_frames / total_render_sec
    mean_frame_ms = np.mean(frame_times) * 1000.0
    p95_frame_ms = np.percentile(frame_times, 95) * 1000.0

    print(f"[OK] Video recorded to {video_path} ({os.path.getsize(video_path) / (1024 * 1024):.2f} MB)")
    print(f"[PERF] Average Render Throughput : {avg_fps:.1f} FPS")
    print(f"[PERF] Frame Time Mean / P95     : {mean_frame_ms:.2f} ms / {p95_frame_ms:.2f} ms")

    # 4. Copy Artifacts
    print("[4/4] Copying showcase video and screenshots to artifact directory...")
    files_to_copy = [
        "realistic3d_landing_demo.mp4",
        "realistic3d_1_high_altitude_approach.png",
        "realistic3d_2_guidance_burn_ignition.png",
        "realistic3d_3_sustained_deceleration.png",
        "realistic3d_4_rcs_attitude_correction.png",
        "realistic3d_5_engine_cutoff.png",
        "realistic3d_6_terminal_regolith_dust.png",
        "realistic3d_7_first_gear_contact.png",
        "realistic3d_8_dual_gear_contact.png",
        "realistic3d_9_settled_touchdown_debrief.png",
    ]

    for fname in files_to_copy:
        src = SHOWCASE_DIR / fname
        if src.exists() and ARTIFACTS_DIR.exists():
            dst = ARTIFACTS_DIR / fname
            shutil.copy2(src, dst)
            print(f"  [CP] -> {fname}")

    print("\n[SUCCESS] Stage 8.4 3D Showcase generation complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record Stage 8.4 Realistic 3D Showcase")
    parser.add_argument("--model-path", type=str, default=str(DEFAULT_MODEL), help="Path to trained PPO model")
    parser.add_argument("--speed", type=float, default=0.5, help="Playback speed multiplier (0.5 for cinematic)")
    parser.add_argument("--fps", type=int, default=30, help="Output video frame rate")
    parser.add_argument("--seed", type=int, default=42, help="Simulation seed")
    args = parser.parse_args()

    record_3d_showcase(
        model_path=Path(args.model_path),
        speed_factor=args.speed,
        video_fps=args.fps,
        seed=args.seed,
    )
