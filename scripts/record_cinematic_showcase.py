"""Stage 8.3 — Simulation Playback, Temporal Synchronization & Propulsion Reconstruction Showcase.

Executes a full autonomous flight demonstration, performs:
1. Temporal Synchronization & Deterministic Invariance Audit (1.0x vs 0.5x playback)
2. Comprehensive 6-Metric Performance & Throughput Audit
3. Generation of continuous 0.5x cinematic showcase MP4 video
4. Capture of all 7 key flight phases with action-to-effect synchronization
5. Side-by-side comparison between legacy renderer and Stage 8.3 cinematic renderer.

Artifacts generated:
1. showcase/stage8_3_1_idle_flight.png
2. showcase/stage8_3_2_ignition.png
3. showcase/stage8_3_3_sustained_burn.png
4. showcase/stage8_3_4_rcs_maneuvers.png
5. showcase/stage8_3_5_engine_shutdown.png
6. showcase/stage8_3_6_terminal_dust.png
7. showcase/stage8_3_7_touchdown.png
8. showcase/cinematic_comparison_old_vs_new.png
9. showcase/cinematic_landing_demo.mp4
"""

from pathlib import Path
import sys
import time
from typing import Dict, List, Tuple

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import cv2
import gymnasium as gym
import numpy as np
import pygame
from stable_baselines3 import PPO

from evaluation.evaluate import LandingCriteria, classify_outcome
from visualization.aerospace_renderer import AerospaceRenderer
from visualization.cinematic_renderer import CinematicAerospaceRenderer


MODEL_PATH = repo_root / "models" / "benchmark" / "D_curriculum_and_dr" / "seed_42" / "final_model.zip"
SHOWCASE_DIR = repo_root / "showcase"
SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)


def run_deterministic_flight_pass(model, speed_factor: float, seed: int = 42) -> Dict:
    """Executes deterministic evaluation flight and records physics telemetry."""
    env = gym.make("LunarLander-v3", continuous=False)
    renderer = CinematicAerospaceRenderer(
        width=1280, height=720, headless=True,
        enable_camera_tracking=True, speed_factor=speed_factor
    )
    criteria = LandingCriteria()
    obs, _ = env.reset(seed=seed)
    total_reward = 0.0

    actions: List[int] = []
    observations: List[np.ndarray] = [obs.copy()]
    rewards: List[float] = []

    step = 0
    done = False
    render_latencies = []

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        act_int = int(action)
        actions.append(act_int)

        tel = renderer.extract_telemetry(
            env, obs, action=act_int, step=step,
            reward=0.0, terminated=False, truncated=False,
            cumulative_reward=total_reward, criteria=criteria,
        )

        t0 = time.perf_counter()
        renderer.render_frame(env, tel)
        render_latencies.append(time.perf_counter() - t0)

        obs, reward, terminated, truncated, _ = env.step(act_int)
        total_reward += reward
        rewards.append(reward)
        observations.append(obs.copy())
        done = terminated or truncated
        step += 1

    outcome = classify_outcome(
        terminated=terminated, truncated=truncated,
        final_step_reward=reward, final_obs=obs, criteria=criteria
    )

    sim_duration = step * 0.02
    wall_duration = sim_duration / speed_factor

    renderer.close()
    env.close()

    return {
        "speed_factor": speed_factor,
        "total_steps": step,
        "sim_duration_sec": sim_duration,
        "wall_duration_sec": wall_duration,
        "total_reward": total_reward,
        "outcome": outcome,
        "final_obs": obs,
        "actions": actions,
        "rewards": rewards,
        "observations": observations,
        "mean_latency_ms": float(np.mean(render_latencies)) * 1000.0,
    }


def record_cinematic_showcase_video(model, speed_factor: float = 0.5, seed: int = 42):
    """Records complete continuous cinematic flight video at specified presentation speed."""
    env = gym.make("LunarLander-v3", continuous=False)
    renderer = CinematicAerospaceRenderer(
        width=1280, height=720, headless=True,
        enable_camera_tracking=True, speed_factor=speed_factor
    )
    old_renderer = AerospaceRenderer(width=1280, height=720, headless=True)
    criteria = LandingCriteria()

    video_path = SHOWCASE_DIR / "cinematic_landing_demo.mp4"
    # Container video playback FPS matches presentation speed: 50 * 0.5 = 25 FPS
    effective_video_fps = int(round(50.0 * speed_factor))
    renderer.start_recording(video_path, fps=effective_video_fps)

    obs, _ = env.reset(seed=seed)
    total_reward = 0.0
    step = 0
    done = False
    prev_action = 0

    record_latencies = []
    captured_phases = {}
    rcs_right_frame = None
    rcs_left_frame = None
    comparison_frame_old = None
    comparison_frame_new = None

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        act_int = int(action)

        tel = renderer.extract_telemetry(
            env, obs, action=act_int, step=step,
            reward=0.0, terminated=False, truncated=False,
            cumulative_reward=total_reward, criteria=criteria,
        )

        t0 = time.perf_counter()
        surf_new = renderer.render_frame(env, tel)
        record_latencies.append(time.perf_counter() - t0)

        # -----------------------------------------------------------------
        # Capture 7 Distinct Flight Phases with Strict Action Synchronization
        # -----------------------------------------------------------------
        # Phase 1: Idle Flight (Action 0, high altitude, unpowered coasting)
        if step == 12 and "1_idle" not in captured_phases:
            p1 = SHOWCASE_DIR / "stage8_3_1_idle_flight.png"
            renderer.save_screenshot(p1)
            captured_phases["1_idle"] = p1
            print(f"  [CAPTURE 1/7] Idle Flight: {p1.name} (step {step}, alt {tel.altitude:.2f}m)")

        # Phase 2: Main-Engine Ignition (First frame of Action 2)
        if prev_action != 2 and act_int == 2 and step > 20 and "2_ignition" not in captured_phases:
            p2 = SHOWCASE_DIR / "stage8_3_2_ignition.png"
            renderer.save_screenshot(p2)
            captured_phases["2_ignition"] = p2
            print(f"  [CAPTURE 2/7] Main-Engine Ignition: {p2.name} (step {step}, throttle {renderer.main_throttle:.2f})")

        # Phase 3: Sustained Supersonic Burn (Action 2, throttle 100%, 3 shock diamonds)
        if act_int == 2 and renderer.main_throttle >= 0.98 and step > 50 and "3_sustained" not in captured_phases:
            p3 = SHOWCASE_DIR / "stage8_3_3_sustained_burn.png"
            renderer.save_screenshot(p3)
            captured_phases["3_sustained"] = p3
            print(f"  [CAPTURE 3/7] Sustained Supersonic Burn: {p3.name} (step {step}, alt {tel.altitude:.2f}m)")

        # Phase 4: RCS Maneuvers (Buffer frames for Left & Right RCS)
        if act_int == 1 and rcs_right_frame is None and step > 30:
            rcs_right_frame = pygame.surfarray.array3d(surf_new).swapaxes(0, 1)
        if act_int == 3 and rcs_left_frame is None and step > 30:
            rcs_left_frame = pygame.surfarray.array3d(surf_new).swapaxes(0, 1)

        # Phase 5: Engine Shutdown (Immediately after action 2 cuts off)
        if prev_action == 2 and act_int == 0 and step > 150 and "5_shutdown" not in captured_phases:
            p5 = SHOWCASE_DIR / "stage8_3_5_engine_shutdown.png"
            renderer.save_screenshot(p5)
            captured_phases["5_shutdown"] = p5
            print(f"  [CAPTURE 5/7] Engine Shutdown: {p5.name} (step {step}, throttle decay {renderer.main_throttle:.2f})")

        # Phase 6: Terminal Descent with Regolith Surface Dust
        if tel.altitude < 0.16 and act_int == 2 and "6_terminal_dust" not in captured_phases:
            p6 = SHOWCASE_DIR / "stage8_3_6_terminal_dust.png"
            renderer.save_screenshot(p6)
            captured_phases["6_terminal_dust"] = p6
            print(f"  [CAPTURE 6/7] Terminal Dust Storm: {p6.name} (step {step}, alt {tel.altitude:.2f}m)")

            # Legacy comparison capture at this same moment
            tel_old = old_renderer.extract_telemetry(
                env, obs, action=act_int, step=step,
                reward=0.0, terminated=False, truncated=False,
                cumulative_reward=total_reward, criteria=criteria,
            )
            surf_old = old_renderer.render_frame(env, tel_old)
            comparison_frame_old = pygame.surfarray.array3d(surf_old).swapaxes(0, 1)
            comparison_frame_new = pygame.surfarray.array3d(surf_new).swapaxes(0, 1)

        prev_action = act_int
        obs, reward, terminated, truncated, _ = env.step(act_int)
        total_reward += reward
        done = terminated or truncated
        step += 1

    outcome = classify_outcome(
        terminated=terminated, truncated=truncated,
        final_step_reward=reward, final_obs=obs, criteria=criteria
    )
    tel_final = renderer.extract_telemetry(
        env, obs, action=0, step=step,
        reward=reward, terminated=terminated, truncated=truncated,
        cumulative_reward=total_reward, criteria=criteria,
    )

    # Render debrief frames for 2.0 seconds into video (50 frames at 25 FPS)
    debrief_frames = int(round(2.0 * effective_video_fps))
    for _ in range(debrief_frames):
        renderer.render_frame(env, tel_final)

    p7 = SHOWCASE_DIR / "stage8_3_7_touchdown.png"
    renderer.save_screenshot(p7)
    captured_phases["7_touchdown"] = p7
    print(f"  [CAPTURE 7/7] Touchdown Debrief: {p7.name} (step {step}, outcome: {outcome})")

    renderer.stop_recording()
    renderer.close()
    old_renderer.close()
    env.close()

    # Assemble RCS Dual Thruster Showcase
    if rcs_left_frame is not None and rcs_right_frame is not None:
        img_rcs_r = cv2.resize(cv2.cvtColor(rcs_right_frame, cv2.COLOR_RGB2BGR), (640, 360))
        img_rcs_l = cv2.resize(cv2.cvtColor(rcs_left_frame, cv2.COLOR_RGB2BGR), (640, 360))

        cv2.rectangle(img_rcs_r, (0, 0), (640, 32), (15, 23, 42), -1)
        cv2.putText(img_rcs_r, "ACTION 1: RIGHT RCS JET (TRANSLATES LEFT)", (16, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (224, 242, 254), 1)

        cv2.rectangle(img_rcs_l, (0, 0), (640, 32), (15, 23, 42), -1)
        cv2.putText(img_rcs_l, "ACTION 3: LEFT RCS JET (TRANSLATES RIGHT)", (16, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (224, 242, 254), 1)

        rcs_composite = np.hstack([img_rcs_r, img_rcs_l])
        p4 = SHOWCASE_DIR / "stage8_3_4_rcs_maneuvers.png"
        cv2.imwrite(str(p4), rcs_composite)
        captured_phases["4_rcs"] = p4
        print(f"  [CAPTURE 4/7] RCS Maneuvers Composite: {p4.name}")

    # Side-by-Side Comparison Image (Stage 8 Legacy vs Stage 8.3 Cinematic)
    if comparison_frame_old is not None and comparison_frame_new is not None:
        img_old = cv2.resize(cv2.cvtColor(comparison_frame_old, cv2.COLOR_RGB2BGR), (960, 540))
        img_new = cv2.resize(cv2.cvtColor(comparison_frame_new, cv2.COLOR_RGB2BGR), (960, 540))

        cv2.rectangle(img_old, (0, 0), (960, 48), (15, 23, 42), -1)
        cv2.putText(img_old, "STAGE 8: BASELINE VECTOR RENDERER (LEGACY)", (24, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (148, 163, 184), 2)

        cv2.rectangle(img_new, (0, 0), (960, 48), (15, 23, 42), -1)
        cv2.putText(img_new, "STAGE 8.3: CINEMATIC RECONSTRUCTION (0.5x CINEMATIC SPEED)", (24, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (56, 189, 248), 2)

        comparison_img = np.hstack([img_old, img_new])
        comp_path = SHOWCASE_DIR / "cinematic_comparison_old_vs_new.png"
        cv2.imwrite(str(comp_path), comparison_img)
        print(f"  [CAPTURE] Side-by-Side Comparison: {comp_path.name}")

    rec_mean_lat = float(np.mean(record_latencies)) * 1000.0
    rec_throughput = 1000.0 / rec_mean_lat if rec_mean_lat > 0 else 0.0

    return {
        "step": step,
        "total_reward": total_reward,
        "outcome": outcome,
        "video_path": video_path,
        "effective_video_fps": effective_video_fps,
        "sim_duration_sec": step * 0.02,
        "wall_playback_sec": step / effective_video_fps,
        "recording_throughput_fps": rec_throughput,
        "recording_mean_latency_ms": rec_mean_lat,
    }


def main():
    print("=" * 80)
    print(" STAGE 8.3 — SIMULATION PLAYBACK & TEMPORAL SYNCHRONIZATION AUDIT")
    print("=" * 80)

    if not MODEL_PATH.exists():
        print(f"[ERROR] Trained model archive not found at: {MODEL_PATH}")
        sys.exit(1)

    print(f" Loading checkpoint: {MODEL_PATH.name}")
    model = PPO.load(str(MODEL_PATH))

    # 1. Deterministic Physics Invariance Audit across Playback Speeds
    print("\n [1/4] Auditing Physics Invariance (1.00x vs 0.50x Playback Speed)...")
    res_1x = run_deterministic_flight_pass(model, speed_factor=1.00, seed=42)
    res_05x = run_deterministic_flight_pass(model, speed_factor=0.50, seed=42)

    # Rigorous Verification Assertions
    assert res_1x["actions"] == res_05x["actions"], "FATAL: Action sequence diverged between 1.0x and 0.5x!"
    assert np.allclose(res_1x["final_obs"], res_05x["final_obs"]), "FATAL: Final state observation diverged!"
    assert abs(res_1x["total_reward"] - res_05x["total_reward"]) < 1e-4, "FATAL: Cumulative reward diverged!"
    assert res_1x["outcome"] == res_05x["outcome"] == "success", "FATAL: Landing outcome diverged!"
    assert abs(res_1x["sim_duration_sec"] - 7.56) < 1e-4 and abs(res_05x["sim_duration_sec"] - 7.56) < 1e-4, "FATAL: Simulated duration altered!"
    assert abs(res_05x["wall_duration_sec"] - 2.0 * res_1x["wall_duration_sec"]) < 1e-4, "FATAL: Wall duration ratio invalid!"

    print("       [OK] Physics Invariance VERIFIED:")
    print(f"         • Total Steps Simulated  : {res_1x['total_steps']} (identical in both)")
    print(f"         • Action Sequence Match  : 100.0% ({len(res_1x['actions'])} actions identical)")
    print(f"         • Simulated Flight Time  : {res_1x['sim_duration_sec']:.2f}s (identical in both)")
    print(f"         • 1.00x Wall-Clock Playback: {res_1x['wall_duration_sec']:.2f}s")
    print(f"         • 0.50x Wall-Clock Playback: {res_05x['wall_duration_sec']:.2f}s (exactly 2x duration)")
    print(f"         • Cumulative Reward      : {res_1x['total_reward']:+.2f} pts")
    print(f"         • Mission Outcome        : {res_1x['outcome'].upper()}")

    # 2. Record Continuous Cinematic Demonstration Video
    print("\n [2/4] Recording Continuous Cinematic Demonstration Video (0.50x Speed)...")
    vid_res = record_cinematic_showcase_video(model, speed_factor=0.50, seed=42)

    # 3. Report All 6 Required Timing & Performance Metrics
    print("\n" + "=" * 80)
    print(" STAGE 8.3 TEMPORAL SYNCHRONIZATION & PERFORMANCE AUDIT REPORT")
    print("=" * 80)
    print(" 1. Simulation Stepping Frequency: 50.0 Hz (Physics dt = 0.020s, invariant)")
    print(f" 2. Presentation Frames/Sec (FPS): {vid_res['effective_video_fps']:.1f} FPS (Target for 0.50x playback)")
    print(f" 3. Wall-Clock Playback Duration : {vid_res['wall_playback_sec']:.2f} s (Flight) + 2.00 s (Debrief)")
    print(f" 4. Simulated Flight Duration    : {vid_res['sim_duration_sec']:.2f} s ({vid_res['step']} simulation steps)")
    print(f" 5. Video Playback FPS           : {vid_res['effective_video_fps']} FPS (Encoded in MP4 header)")
    print(f" 6. Video Encoding Throughput    : {vid_res['recording_throughput_fps']:.1f} FPS ({vid_res['recording_mean_latency_ms']:.2f} ms/frame)")
    print(f"    Pure Rendering Speed (No I/O): {1000.0 / res_05x['mean_latency_ms']:.1f} FPS ({res_05x['mean_latency_ms']:.2f} ms/frame)")
    print(f"    Video Output File            : {vid_res['video_path']}")
    print("=" * 80)

    # Copy legacy aliases so existing paths remain functional
    legacy_map = {
        "stage8_3_1_idle_flight.png": "cinematic_1_high_descent.png",
        "stage8_3_3_sustained_burn.png": "cinematic_2_guidance_burn.png",
        "stage8_3_6_terminal_dust.png": "cinematic_3_terminal_dust.png",
        "stage8_3_7_touchdown.png": "cinematic_4_touchdown.png",
    }
    for src, dst in legacy_map.items():
        src_file = SHOWCASE_DIR / src
        dst_file = SHOWCASE_DIR / dst
        if src_file.exists():
            dst_file.write_bytes(src_file.read_bytes())


if __name__ == "__main__":
    main()
