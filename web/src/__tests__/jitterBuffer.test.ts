import { describe, it, expect } from 'vitest';
import { JitterBuffer } from '../services/jitterBuffer';
import type { SimulationSnapshotPayload } from '../types/protocol';

function createMockSnapshot(step: number, posX: number, posY: number, angle: number): SimulationSnapshotPayload {
  return {
    protocol_version: '1.0.0',
    session_id: 'test-session-123',
    episode_id: 1,
    kinematics: {
      pos_x: posX,
      pos_y: posY,
      vel_x: 0.0,
      vel_y: -1.0,
      angle: angle,
      ang_vel: 0.0,
      altitude: posY,
    },
    propulsion: {
      action: 0,
      throttle: 0.0,
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
      step,
      sim_time: step * 0.02,
      touchdown_phase: 'AIRBORNE',
      step_reward: 0.5,
      cumulative_reward: 10.0,
      terminated: false,
      truncated: false,
      outcome: null,
    },
    impact: {},
  };
}

describe('JitterBuffer', () => {
  it('returns null on empty buffer', () => {
    const jb = new JitterBuffer();
    expect(jb.getInterpolatedSnapshot()).toBeNull();
    expect(jb.length).toBe(0);
  });

  it('returns exact snapshot when buffer contains only one frame', () => {
    const jb = new JitterBuffer();
    const s1 = createMockSnapshot(0, 0.0, 10.0, 0.0);
    jb.push(s1);

    const interp = jb.getInterpolatedSnapshot();
    expect(interp).not.toBeNull();
    expect(interp?.kinematics.pos_y).toBe(10.0);
    expect(interp?.lifecycle.step).toBe(0);
  });

  it('interpolates positions smoothly between two frames', () => {
    const jb = new JitterBuffer();
    const s0 = createMockSnapshot(0, 0.0, 10.0, 0.0);
    const s1 = createMockSnapshot(1, 2.0, 8.0, 0.2);

    jb.push(s0);
    // Push second snapshot
    jb.push(s1);

    expect(jb.length).toBe(2);
    const interp = jb.getInterpolatedSnapshot();
    expect(interp).not.toBeNull();
    // Interp values must be bounded between s0 and s1
    expect(interp!.kinematics.pos_x).toBeGreaterThanOrEqual(0.0);
    expect(interp!.kinematics.pos_x).toBeLessThanOrEqual(2.0);
    expect(interp!.kinematics.pos_y).toBeGreaterThanOrEqual(8.0);
    expect(interp!.kinematics.pos_y).toBeLessThanOrEqual(10.0);
  });

  it('correctly interpolates angular wrap-around across +/- PI', () => {
    const jb = new JitterBuffer();
    // Angle wraps from 3.10 rad to -3.10 rad (shortest path is over the boundary, not through 0)
    const s0 = createMockSnapshot(0, 0.0, 5.0, 3.10);
    const s1 = createMockSnapshot(1, 0.0, 4.9, -3.10);

    jb.push(s0);
    jb.push(s1);

    const interp = jb.getInterpolatedSnapshot();
    expect(interp).not.toBeNull();
    // Shortest angular difference between 3.10 and -3.10 is ~0.083 radians
    expect(Math.abs(interp!.kinematics.angle)).toBeGreaterThan(3.0);
  });

  it('clears buffer on clear() call', () => {
    const jb = new JitterBuffer();
    jb.push(createMockSnapshot(0, 0, 10, 0));
    jb.push(createMockSnapshot(1, 0, 9, 0));
    expect(jb.length).toBe(2);

    jb.clear();
    expect(jb.length).toBe(0);
    expect(jb.getInterpolatedSnapshot()).toBeNull();
  });
});
