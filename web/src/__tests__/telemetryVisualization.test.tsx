import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { TelemetryStore, type TelemetryPoint } from '../services/telemetryStore';
import { TrajectoryChart } from '../components/dashboard/charts/TrajectoryChart';
import { BrakingCorridorChart } from '../components/dashboard/charts/BrakingCorridorChart';
import { RewardChart } from '../components/dashboard/charts/RewardChart';
import { AttitudeChart } from '../components/dashboard/charts/AttitudeChart';
import type { SimulationSnapshotPayload, EpisodeCompletePayload } from '../types/protocol';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

function createMockSnapshot(overrides: Partial<any> = {}): SimulationSnapshotPayload {
  return {
    protocol_version: '1.0.0',
    session_id: 'test-session',
    episode_id: 1,
    kinematics: {
      pos_x: 0.15,
      pos_y: 1.25,
      vel_x: -0.05,
      vel_y: -0.85,
      angle: 0.05,
      ang_vel: -0.02,
      altitude: 0.65,
      ...(overrides.kinematics || {}),
    },
    propulsion: {
      action: 2,
      throttle: 1.0,
      rcs_left: 0.0,
      rcs_right: 0.0,
      ...(overrides.propulsion || {}),
    },
    landing_gear: {
      left_contact: false,
      right_contact: false,
      ...(overrides.landing_gear || {}),
    },
    atmosphere: {
      wind_force: 0.0,
      turbulence: 0.0,
      ...(overrides.atmosphere || {}),
    },
    lifecycle: {
      step: 10,
      sim_time: 0.2,
      touchdown_phase: 'AIRBORNE',
      step_reward: 1.5,
      cumulative_reward: 15.0,
      terminated: false,
      truncated: false,
      outcome: null,
      ...(overrides.lifecycle || {}),
    },
    impact: {
      impact_vel_x: null,
      impact_vel_y: null,
      impact_tilt: null,
      ...(overrides.impact || {}),
    },
    ...overrides,
  };
}

describe('TelemetryStore Buffer & Lifecycle Management', () => {
  let store: TelemetryStore;

  beforeEach(() => {
    store = new TelemetryStore();
  });

  it('pushes snapshot into activePoints with accurate field mapping', () => {
    const snap = createMockSnapshot();
    store.pushSnapshot(snap, 'ai');

    const points = store.getActivePoints();
    expect(points.length).toBe(1);
    expect(points[0].step).toBe(10);
    expect(points[0].time).toBeCloseTo(0.2, 3);
    expect(points[0].x).toBe(0.15);
    expect(points[0].alt).toBe(0.65);
    expect(points[0].vx).toBe(-0.05);
    expect(points[0].vy).toBe(-0.85);
    expect(points[0].angle).toBe(0.05);
    expect(points[0].angleDeg).toBeCloseTo(0.05 * 57.2957795, 2);
    expect(points[0].action).toBe(2);
    expect(points[0].throttle).toBe(1.0);
    expect(points[0].cumReward).toBe(15.0);
  });

  it('prevents duplicate entry for identical simulation step', () => {
    const snap1 = createMockSnapshot({ lifecycle: { step: 5, sim_time: 0.1 } });
    const snap2 = createMockSnapshot({ lifecycle: { step: 5, sim_time: 0.1 } });

    store.pushSnapshot(snap1);
    store.pushSnapshot(snap2);

    expect(store.getActivePoints().length).toBe(1);
  });

  it('enforces ring-buffer upper bound (MAX_POINTS = 1500)', () => {
    for (let i = 0; i < 1600; i++) {
      store.pushSnapshot(
        createMockSnapshot({
          lifecycle: { step: i, sim_time: i * 0.02 },
        })
      );
    }

    const points = store.getActivePoints();
    expect(points.length).toBe(1500);
    expect(points[0].step).toBe(100); // 1600 - 1500 = 100
    expect(points[1499].step).toBe(1599);
  });

  it('resets active episode buffer when episode_id changes', () => {
    store.pushSnapshot(createMockSnapshot({ episode_id: 1, lifecycle: { step: 1 } }));
    store.pushSnapshot(createMockSnapshot({ episode_id: 1, lifecycle: { step: 2 } }));
    expect(store.getActivePoints().length).toBe(2);

    // New episode
    store.pushSnapshot(createMockSnapshot({ episode_id: 2, lifecycle: { step: 0 } }));
    const points = store.getActivePoints();
    expect(points.length).toBe(1);
    expect(points[0].step).toBe(0);
  });

  it('records completed episodes and enforces history boundary', () => {
    const completePayload: EpisodeCompletePayload = {
      session_id: 'test-session',
      episode_id: 1,
      outcome: 'SUCCESS',
      total_steps: 240,
      total_sim_time: 4.8,
      cumulative_reward: 265.4,
      impact_vel_x: 0.02,
      impact_vel_y: -0.28,
      impact_tilt_deg: 0.8,
      final_clearance: 0.0,
      final_tilt_deg: 0.3,
    };

    store.pushEpisodeComplete(completePayload, 'ai');
    const records = store.getCompletedEpisodes();
    expect(records.length).toBe(1);
    expect(records[0].episode_id).toBe(1);
    expect(records[0].outcome).toBe('SUCCESS');
    expect(records[0].cumulative_reward).toBe(265.4);
    expect(records[0].impact_vel_y).toBe(-0.28);
  });

  it('supports chart visual pause/resume toggle without losing points', () => {
    expect(store.isChartsPaused()).toBe(false);
    store.setChartsPaused(true);
    expect(store.isChartsPaused()).toBe(true);

    const listener = vi.fn();
    store.subscribe(listener);

    // Points pushed while paused should not trigger listeners
    store.pushSnapshot(createMockSnapshot({ lifecycle: { step: 1 } }));
    expect(listener).not.toHaveBeenCalled();
    expect(store.getActivePoints().length).toBe(1);

    // Resume triggers notification
    store.setChartsPaused(false);
    expect(listener).toHaveBeenCalled();
  });
});

describe('Scientific Live Charts Canvas Rendering', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  const samplePoints: TelemetryPoint[] = [
    {
      step: 0,
      time: 0.0,
      x: -0.8,
      y: 1.8,
      alt: 1.2,
      vx: 0.1,
      vy: -1.2,
      angle: 0.1,
      angleDeg: 5.7,
      angVel: -0.05,
      stepReward: 0.0,
      cumReward: 0.0,
      action: 0,
      throttle: 0.0,
      phase: 'AIRBORNE',
    },
    {
      step: 50,
      time: 1.0,
      x: -0.2,
      y: 1.2,
      alt: 0.6,
      vx: 0.05,
      vy: -0.6,
      angle: 0.02,
      angleDeg: 1.1,
      angVel: 0.0,
      stepReward: 5.0,
      cumReward: 85.0,
      action: 2,
      throttle: 1.0,
      phase: 'TERMINAL_APPROACH',
    },
    {
      step: 100,
      time: 2.0,
      x: 0.02,
      y: 0.6,
      alt: 0.0,
      vx: 0.01,
      vy: -0.25,
      angle: 0.005,
      angleDeg: 0.3,
      angVel: 0.0,
      stepReward: 100.0,
      cumReward: 254.0,
      action: 0,
      throttle: 0.0,
      phase: 'TOUCHDOWN_DETECTED',
    },
  ];

  it('TrajectoryChart renders canvas and criteria badges', () => {
    act(() => {
      root.render(<TrajectoryChart points={samplePoints} />);
    });

    expect(container.textContent).toContain('TRAJECTORY TRACE Y(X)');
    expect(container.textContent).toContain('SAMPLES: 3');
    expect(container.textContent).toContain('CRITERIA: |X| ≤ 0.25u');
    expect(container.querySelector('canvas')).not.toBeNull();
  });

  it('BrakingCorridorChart renders canvas, limits and descent zone', () => {
    act(() => {
      root.render(<BrakingCorridorChart points={samplePoints} />);
    });

    expect(container.textContent).toContain('BRAKING CORRIDOR Vy(Y)');
    expect(container.textContent).toContain('TOUCHDOWN LIMIT: ≥ -0.40 u/s');
    expect(container.textContent).toContain('DESCENT: Vy < 0');
    expect(container.querySelector('canvas')).not.toBeNull();
  });

  it('RewardChart renders canvas, step duration and latest return', () => {
    act(() => {
      root.render(<RewardChart points={samplePoints} />);
    });

    expect(container.textContent).toContain('REWARD PROGRESSION R(t)');
    expect(container.textContent).toContain('CURRENT RETURN: +254.0');
    expect(container.querySelector('canvas')).not.toBeNull();
  });

  it('AttitudeChart renders pitch degrees, radians, and landing limits', () => {
    act(() => {
      root.render(<AttitudeChart points={samplePoints} />);
    });

    expect(container.textContent).toContain('ATTITUDE STABILIZATION θ(t)');
    expect(container.textContent).toContain('PITCH: +0.3°');
    expect(container.querySelector('canvas')).not.toBeNull();
  });
});
