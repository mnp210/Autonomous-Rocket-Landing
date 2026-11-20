import type {
  EpisodeCompletePayload,
  FlightMode,
  SimulationSnapshotPayload,
} from '../types/protocol';

export interface TelemetryPoint {
  step: number;
  time: number;
  x: number;
  y: number;
  alt: number;
  vx: number;
  vy: number;
  angle: number;
  angleDeg: number;
  angVel: number;
  stepReward: number;
  cumReward: number;
  action: number;
  throttle: number;
  phase: string;
}

export interface CompletedEpisodeRecord {
  episode_id: number;
  mode: FlightMode;
  total_steps: number;
  total_sim_time: number;
  final_clearance: number;
  impact_vel_x?: number | null;
  impact_vel_y?: number | null;
  impact_tilt_deg?: number | null;
  cumulative_reward: number;
  outcome: string;
}

const MAX_POINTS = 1500;
const MAX_COMPLETED_EPISODES = 50;

export class TelemetryStore {
  private activePoints: TelemetryPoint[] = [];
  private completedEpisodes: CompletedEpisodeRecord[] = [];
  private listeners: Set<() => void> = new Set();
  private chartsPaused: boolean = false;
  private currentEpisodeId: number | null = null;
  private lastRecordedStep: number = -1;

  public pushSnapshot(snap: SimulationSnapshotPayload, flightMode: FlightMode = 'ai') {
    // Detect new episode boundary
    if (this.currentEpisodeId !== null && snap.episode_id !== this.currentEpisodeId) {
      this.resetActiveEpisode();
    }
    this.currentEpisodeId = snap.episode_id;

    // Prevent duplicate entries for the same step
    if (snap.lifecycle.step === this.lastRecordedStep && this.activePoints.length > 0) {
      return;
    }
    this.lastRecordedStep = snap.lifecycle.step;

    const point: TelemetryPoint = {
      step: snap.lifecycle.step,
      time: snap.lifecycle.sim_time,
      x: snap.kinematics.pos_x,
      y: snap.kinematics.pos_y,
      alt: snap.kinematics.altitude,
      vx: snap.kinematics.vel_x,
      vy: snap.kinematics.vel_y,
      angle: snap.kinematics.angle,
      angleDeg: snap.kinematics.angle * 57.2957795,
      angVel: snap.kinematics.ang_vel,
      stepReward: snap.lifecycle.step_reward,
      cumReward: snap.lifecycle.cumulative_reward,
      action: snap.propulsion.action,
      throttle: snap.propulsion.throttle,
      phase: snap.lifecycle.touchdown_phase,
    };

    if (this.activePoints.length >= MAX_POINTS) {
      this.activePoints.shift();
    }
    this.activePoints.push(point);

    // If episode just ended and outcome is known, archive it if not already recorded
    if (
      (snap.lifecycle.terminated || snap.lifecycle.truncated) &&
      snap.lifecycle.outcome
    ) {
      this.recordTerminalOutcome(snap, flightMode);
    }

    if (!this.chartsPaused) {
      this.notifyListeners();
    }
  }

  public pushEpisodeComplete(complete: EpisodeCompletePayload, flightMode: FlightMode) {
    const existing = this.completedEpisodes.find((e) => e.episode_id === complete.episode_id);
    if (existing) {
      return;
    }

    const record: CompletedEpisodeRecord = {
      episode_id: complete.episode_id,
      mode: flightMode,
      total_steps: complete.total_steps,
      total_sim_time: complete.total_sim_time,
      final_clearance: complete.final_clearance,
      impact_vel_x: complete.impact_vel_x,
      impact_vel_y: complete.impact_vel_y,
      impact_tilt_deg: complete.impact_tilt_deg,
      cumulative_reward: complete.cumulative_reward,
      outcome: complete.outcome,
    };

    this.completedEpisodes.unshift(record);
    if (this.completedEpisodes.length > MAX_COMPLETED_EPISODES) {
      this.completedEpisodes.pop();
    }

    this.notifyListeners();
  }

  private recordTerminalOutcome(snap: SimulationSnapshotPayload, flightMode: FlightMode) {
    const existing = this.completedEpisodes.find((e) => e.episode_id === snap.episode_id);
    if (existing) return;

    const record: CompletedEpisodeRecord = {
      episode_id: snap.episode_id,
      mode: flightMode,
      total_steps: snap.lifecycle.step,
      total_sim_time: snap.lifecycle.sim_time,
      final_clearance: snap.kinematics.altitude,
      impact_vel_x: snap.impact.impact_vel_x,
      impact_vel_y: snap.impact.impact_vel_y,
      impact_tilt_deg:
        snap.impact.impact_tilt !== null && snap.impact.impact_tilt !== undefined
          ? snap.impact.impact_tilt * 57.2957795
          : null,
      cumulative_reward: snap.lifecycle.cumulative_reward,
      outcome: snap.lifecycle.outcome || (snap.lifecycle.terminated ? 'SUCCESS' : 'TIMEOUT'),
    };

    this.completedEpisodes.unshift(record);
    if (this.completedEpisodes.length > MAX_COMPLETED_EPISODES) {
      this.completedEpisodes.pop();
    }
  }

  public resetActiveEpisode() {
    this.activePoints = [];
    this.lastRecordedStep = -1;
    this.notifyListeners();
  }

  public clearAll() {
    this.activePoints = [];
    this.completedEpisodes = [];
    this.lastRecordedStep = -1;
    this.currentEpisodeId = null;
    this.notifyListeners();
  }

  public getActivePoints(): TelemetryPoint[] {
    return this.activePoints;
  }

  public getCompletedEpisodes(): CompletedEpisodeRecord[] {
    return this.completedEpisodes;
  }

  public setChartsPaused(paused: boolean) {
    this.chartsPaused = paused;
    if (!paused) {
      this.notifyListeners();
    }
  }

  public isChartsPaused(): boolean {
    return this.chartsPaused;
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notifyListeners() {
    for (const listener of this.listeners) {
      listener();
    }
  }
}

// Global singleton instance for application-wide telemetry distribution
export const globalTelemetryStore = new TelemetryStore();
