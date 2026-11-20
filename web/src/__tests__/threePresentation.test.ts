import { describe, it, expect } from 'vitest';
import {
  mapSimulationTo3DPosition,
  mapSimulationRotation,
  computeVelocityVector,
  computeEstimatedTouchdown,
  isPropulsionCutoff,
  computeCameraTargets,
  BOOSTER_FOOTPAD_OFFSET,
} from '../three/coordinateMapping';
import { createBoosterModel, updateBoosterModel } from '../three/boosterModel';
import type { SimulationSnapshotPayload } from '../types/protocol';

describe('Three.js 3D Coordinate Mapping & Presentation Logic', () => {
  it('maps authoritative Box2D simulation position to 3D world coordinates correctly with footpad offset', () => {
    // Pad center touchdown: posX = 0, altitude = 0
    // With visual footpad offset, vehicle center of mass sits at y = 1.083u so deployed footpads touch pad at y = 0.0
    const padPos = mapSimulationTo3DPosition(0.0, 0.0);
    expect(padPos.x).toBe(0.0);
    expect(padPos.y).toBeCloseTo(BOOSTER_FOOTPAD_OFFSET, 3);
    expect(padPos.z).toBe(0.0); // Centerline depth strictly 0

    // Without visual footpad offset (raw altitude)
    const rawPos = mapSimulationTo3DPosition(0.0, 0.0, false);
    expect(rawPos.y).toBe(0.0);

    // Apogee flight position: posX = -2.5, altitude = 11.8
    const flightPos = mapSimulationTo3DPosition(-2.5, 11.8);
    expect(flightPos.x).toBe(-2.5);
    expect(flightPos.y).toBeCloseTo(11.8 + BOOSTER_FOOTPAD_OFFSET, 3);
    expect(flightPos.z).toBe(0.0);

    // Negative altitude (ground penetration) clamped to pad baseline + offset
    const clampedPos = mapSimulationTo3DPosition(1.2, -0.4);
    expect(clampedPos.y).toBeCloseTo(0.0 + BOOSTER_FOOTPAD_OFFSET, 3);
  });

  it('maps Box2D body angle to Three.js planar Z-axis rotation', () => {
    // Counter-clockwise angle in radians
    const angleRad = 0.35;
    expect(mapSimulationRotation(angleRad)).toBe(0.35);

    const negativeAngle = -0.785; // ~ -45 deg
    expect(mapSimulationRotation(negativeAngle)).toBe(-0.785);
  });

  it('computes 3D velocity vectors and danger threshold colors accurately', () => {
    // 1. Safe descent: Vy = -0.8 u/s
    const safeVel = computeVelocityVector(0.2, -0.8);
    expect(safeVel.speed).toBeCloseTo(Math.sqrt(0.2 * 0.2 + 0.8 * 0.8), 3);
    expect(safeVel.color).toBe('#00E676');
    expect(safeVel.isSafeSink).toBe(true);

    // 2. Caution descent: Vy = -1.6 u/s
    const cautionVel = computeVelocityVector(0.0, -1.6);
    expect(cautionVel.color).toBe('#FFB300');
    expect(cautionVel.isSafeSink).toBe(false);

    // 3. Danger sink rate: Vy = -2.8 u/s
    const dangerVel = computeVelocityVector(-0.5, -2.8);
    expect(dangerVel.color).toBe('#FF1744');
    expect(dangerVel.isSafeSink).toBe(false);
  });

  it('computes projected touchdown intercept position accurately', () => {
    // Descending at altitude 6.0u, sink rate 2.0 u/s -> tGo = 3.0s
    // Lateral drift 0.2 u/s from posX = -0.3u -> predX = -0.3 + (0.2 * 3.0) = +0.3u (safe on pad)
    const estSafe = computeEstimatedTouchdown(-0.3, 6.0, 0.2, -2.0, 1.5);
    expect(estSafe).not.toBeNull();
    expect(estSafe?.tGo).toBeCloseTo(3.0, 3);
    expect(estSafe?.predX).toBeCloseTo(0.3, 3);
    expect(estSafe?.isSafe).toBe(true);

    // Lateral drift 1.0 u/s from posX = 1.0u -> predX = 1.0 + (1.0 * 3.0) = +4.0u (diverging off pad)
    const estOffPad = computeEstimatedTouchdown(1.0, 6.0, 1.0, -2.0, 1.5);
    expect(estOffPad).not.toBeNull();
    expect(estOffPad?.predX).toBeCloseTo(4.0, 3);
    expect(estOffPad?.isSafe).toBe(false);

    // Ascending vehicle (Vy >= 0) or vehicle settled on pad should return null
    expect(computeEstimatedTouchdown(0.0, 5.0, 0.1, 0.5)).toBeNull();
    expect(computeEstimatedTouchdown(0.0, 0.02, 0.0, -0.5)).toBeNull();
  });

  it('strictly enforces propulsion cutoff and terminal state latch', () => {
    // Active thrust during nominal flight
    expect(isPropulsionCutoff(false, false, 1.0)).toBe(false);

    // Neutral / Coasting action (throttle = 0)
    expect(isPropulsionCutoff(false, false, 0.0)).toBe(true);

    // Terminal touchdown latch (terminated = true)
    expect(isPropulsionCutoff(true, false, 1.0)).toBe(true);

    // Flight timeout / truncation (truncated = true)
    expect(isPropulsionCutoff(false, true, 1.0)).toBe(true);
  });

  it('computes camera eye and target targets for follow and overview modes', () => {
    // Overview mode returns fixed wide perspective of spaceport
    const overview = computeCameraTargets('overview', 0.0, 5.0);
    expect(overview.eye.z).toBe(24.0);
    expect(overview.target.x).toBe(0.0);
    expect(overview.target.y).toBe(3.5);

    // Follow mode dynamically frames vehicle and pad
    const followHigh = computeCameraTargets('follow', 1.0, 12.0);
    const followLow = computeCameraTargets('follow', 0.2, 0.5);

    // When near ground, camera is significantly closer in Z and lower in elevation
    expect(followLow.eye.z).toBeLessThan(followHigh.eye.z);
    expect(followLow.eye.y).toBeLessThan(followHigh.eye.y);
  });

  it('updates procedural 3D booster model actuators, plumes and contact sensors', () => {
    const booster = createBoosterModel('high');
    expect(booster.root).toBeDefined();

    const mockSnapshot: SimulationSnapshotPayload = {
      protocol_version: '1.0.0',
      session_id: 'test-session',
      episode_id: 1,
      kinematics: {
        pos_x: 0.5,
        pos_y: 6.0,
        vel_x: 0.1,
        vel_y: -1.2,
        angle: 0.05,
        ang_vel: 0.02,
        altitude: 5.4,
      },
      propulsion: {
        action: 2, // Main Engine
        throttle: 1.0,
        rcs_left: 0.0,
        rcs_right: 0.0,
      },
      landing_gear: {
        left_contact: false,
        right_contact: false,
      },
      atmosphere: {
        wind_force: 0.0,
        turbulence: 0.0,
      },
      lifecycle: {
        step: 120,
        sim_time: 2.4,
        touchdown_phase: 'TERMINAL_DESCENT',
        step_reward: 0.5,
        cumulative_reward: 45.2,
        terminated: false,
        truncated: false,
        outcome: null,
      },
      impact: {},
    };

    // 1. Nominal braking burn
    updateBoosterModel(booster, mockSnapshot, 'high');
    expect(booster.root.position.x).toBe(0.5);
    expect(booster.root.position.y).toBeCloseTo(5.4 + BOOSTER_FOOTPAD_OFFSET, 3);
    expect(booster.mainPlumeGroup.visible).toBe(true);
    expect(booster.plumeLight.intensity).toBeGreaterThan(0);
    expect(booster.rcsLeftMesh.visible).toBe(false);

    // 2. First leg contact (left leg only): verifies independent contact sensor mapping
    mockSnapshot.landing_gear.left_contact = true;
    mockSnapshot.landing_gear.right_contact = false;
    updateBoosterModel(booster, mockSnapshot, 'high');
    expect(booster.leftFootpadMat.emissive.getHex()).toBe(0x00E676);
    expect(booster.rightFootpadMat.emissive.getHex()).toBe(0x000000);

    // 3. Dual leg contact: both illuminate, but propulsion does NOT cut off until terminal latch
    mockSnapshot.landing_gear.right_contact = true;
    updateBoosterModel(booster, mockSnapshot, 'high');
    expect(booster.leftFootpadMat.emissive.getHex()).toBe(0x00E676);
    expect(booster.rightFootpadMat.emissive.getHex()).toBe(0x00E676);
    expect(booster.mainPlumeGroup.visible).toBe(true); // Still firing until terminated!

    // 4. Terminal touchdown latch -> propulsion must immediately shut down
    mockSnapshot.lifecycle.terminated = true;
    mockSnapshot.propulsion.throttle = 0.0;
    mockSnapshot.propulsion.action = 0;

    updateBoosterModel(booster, mockSnapshot, 'high');
    expect(booster.mainPlumeGroup.visible).toBe(false);
    expect(booster.plumeLight.intensity).toBe(0);
    // Footpads maintain physical contact illumination
    expect(booster.leftFootpadMat.emissive.getHex()).toBe(0x00E676);
    expect(booster.rightFootpadMat.emissive.getHex()).toBe(0x00E676);
  });

  it('supports low-power quality preset with optimized draw configuration', () => {
    const boosterLow = createBoosterModel('low');
    expect(boosterLow.root).toBeDefined();

    // Verify low-power updates successfully without error
    updateBoosterModel(boosterLow, null, 'low');
    expect(boosterLow.mainPlumeGroup.visible).toBe(false);
  });

  it('safely handles NaN, Infinity, and malformed telemetry without crashing', () => {
    // 1. Position mapping with NaNs / Infinities
    const nanPos = mapSimulationTo3DPosition(NaN, Infinity, false);
    expect(nanPos.x).toBe(0.0);
    expect(nanPos.y).toBe(0.0);
    expect(nanPos.z).toBe(0.0);

    const nanPosWithOffset = mapSimulationTo3DPosition(NaN, Infinity);
    expect(nanPosWithOffset.x).toBe(0.0);
    expect(nanPosWithOffset.y).toBeCloseTo(BOOSTER_FOOTPAD_OFFSET, 3);

    // 2. Rotation mapping with NaN
    expect(mapSimulationRotation(NaN)).toBe(0.0);
    expect(mapSimulationRotation(-Infinity)).toBe(0.0);

    // 3. Velocity vector with NaNs
    const nanVel = computeVelocityVector(NaN, -Infinity);
    expect(nanVel.vector.x).toBe(0.0);
    expect(nanVel.vector.y).toBe(0.0);
    expect(nanVel.speed).toBe(0.0);
    expect(nanVel.color).toBe('#00E676');
    expect(nanVel.isSafeSink).toBe(true);

    // 4. Touchdown predictor with invalid/extreme inputs
    expect(computeEstimatedTouchdown(NaN, 5.0, 0.1, -1.0)).toBeNull();
    expect(computeEstimatedTouchdown(0.0, NaN, 0.1, -1.0)).toBeNull();
    expect(computeEstimatedTouchdown(0.0, 5.0, NaN, -1.0)).toBeNull();
    expect(computeEstimatedTouchdown(0.0, 5.0, 0.1, NaN)).toBeNull();
    // Near-zero sink rate (< 1e-4) to prevent division by zero
    expect(computeEstimatedTouchdown(0.0, 5.0, 0.1, -0.00001)).toBeNull();
    // Runaway altitude / extreme tGo (> 600s)
    expect(computeEstimatedTouchdown(0.0, 100000.0, 0.1, -0.1)).toBeNull();
  });

  it('updates booster model cleanly when telemetry contains non-finite values', () => {
    const booster = createBoosterModel('high');
    const corruptedSnapshot: SimulationSnapshotPayload = {
      protocol_version: '1.0.0',
      session_id: 'corrupt-session',
      episode_id: 2,
      kinematics: {
        pos_x: NaN,
        pos_y: NaN,
        vel_x: NaN,
        vel_y: NaN,
        angle: NaN,
        ang_vel: NaN,
        altitude: NaN,
      },
      propulsion: {
        action: 0,
        throttle: NaN,
        rcs_left: NaN,
        rcs_right: NaN,
      },
      landing_gear: {
        left_contact: false,
        right_contact: false,
      },
      atmosphere: {
        wind_force: 0.0,
        turbulence: 0.0,
      },
      lifecycle: {
        step: 1,
        sim_time: 0.02,
        touchdown_phase: 'APPROACH',
        step_reward: 0.0,
        cumulative_reward: 0.0,
        terminated: false,
        truncated: false,
        outcome: null,
      },
      impact: {},
    };

    expect(() => {
      updateBoosterModel(booster, corruptedSnapshot, 'high');
    }).not.toThrow();

    // Booster position should have fallen back to finite values
    expect(Number.isFinite(booster.root.position.x)).toBe(true);
    expect(Number.isFinite(booster.root.position.y)).toBe(true);
    expect(Number.isFinite(booster.root.rotation.z)).toBe(true);
  });
});
