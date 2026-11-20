/**
 * Client-Side Jitter Buffer for smooth 60 FPS Canvas rendering.
 *
 * Buffers incoming 50 Hz WebSocket snapshots and performs presentation-only
 * interpolation. Never mutates, modifies, or feeds interpolated values back
 * into the physics engine or action space.
 */

import type { SimulationSnapshotPayload } from '../types/protocol';

interface BufferedFrame {
  snapshot: SimulationSnapshotPayload;
  receivedAt: number; // performance.now()
}

export class JitterBuffer {
  private buffer: BufferedFrame[] = [];
  private maxBufferSize: number = 20;
  private renderDelayMs: number = 40; // 2 simulation ticks (40 ms) buffering for jitter absorption

  /**
   * Pushes a new server snapshot into the buffer.
   */
  public push(snapshot: SimulationSnapshotPayload): void {
    const now = performance.now();
    this.buffer.push({ snapshot, receivedAt: now });

    // Enforce buffer bounds to prevent memory accumulation
    if (this.buffer.length > this.maxBufferSize) {
      this.buffer.shift();
    }
  }

  /**
   * Clears the jitter buffer (e.g. on episode reset or session switch).
   */
  public clear(): void {
    this.buffer = [];
  }

  /**
   * Returns the count of buffered snapshots.
   */
  public get length(): number {
    return this.buffer.length;
  }

  /**
   * Retrieves an interpolated snapshot for smooth rendering at renderTimestamp.
   * If insufficient frames exist, returns the most recent frame directly.
   */
  public getInterpolatedSnapshot(now: number = performance.now()): SimulationSnapshotPayload | null {
    if (this.buffer.length === 0) {
      return null;
    }

    if (this.buffer.length === 1) {
      return this.buffer[0].snapshot;
    }

    const targetTime = now - this.renderDelayMs;

    // If targetTime is older than our oldest frame, return oldest frame
    if (targetTime <= this.buffer[0].receivedAt) {
      return this.buffer[0].snapshot;
    }

    // If targetTime is newer than our latest frame, return latest frame
    const latest = this.buffer[this.buffer.length - 1];
    if (targetTime >= latest.receivedAt) {
      return latest.snapshot;
    }

    // Find the two frames bounding targetTime
    let prevIndex = 0;
    for (let i = 0; i < this.buffer.length - 1; i++) {
      if (this.buffer[i].receivedAt <= targetTime && targetTime <= this.buffer[i + 1].receivedAt) {
        prevIndex = i;
        break;
      }
    }

    const f0 = this.buffer[prevIndex];
    const f1 = this.buffer[prevIndex + 1];

    const span = f1.receivedAt - f0.receivedAt;
    const alpha = span > 0 ? Math.min(1.0, Math.max(0.0, (targetTime - f0.receivedAt) / span)) : 1.0;

    return this.interpolateSnapshots(f0.snapshot, f1.snapshot, alpha);
  }

  /**
   * Interpolates continuous kinematic states between two snapshots.
   * Discrete states (contact flags, actuator choices, termination) take the values of f1.
   */
  private interpolateSnapshots(
    s0: SimulationSnapshotPayload,
    s1: SimulationSnapshotPayload,
    alpha: number
  ): SimulationSnapshotPayload {
    const k0 = s0.kinematics;
    const k1 = s1.kinematics;

    // Linear interpolation helper
    const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

    // Shortest angular distance interpolation
    let angleDiff = k1.angle - k0.angle;
    while (angleDiff > Math.PI) angleDiff -= 2 * Math.PI;
    while (angleDiff < -Math.PI) angleDiff += 2 * Math.PI;
    const interpAngle = k0.angle + angleDiff * alpha;

    return {
      ...s1,
      kinematics: {
        pos_x: lerp(k0.pos_x, k1.pos_x, alpha),
        pos_y: lerp(k0.pos_y, k1.pos_y, alpha),
        vel_x: lerp(k0.vel_x, k1.vel_x, alpha),
        vel_y: lerp(k0.vel_y, k1.vel_y, alpha),
        angle: interpAngle,
        ang_vel: lerp(k0.ang_vel, k1.ang_vel, alpha),
        altitude: lerp(k0.altitude, k1.altitude, alpha),
      },
      // Discrete propulsion, gear, and lifecycle properties take the target state s1
      propulsion: s1.propulsion,
      landing_gear: s1.landing_gear,
      atmosphere: s1.atmosphere,
      lifecycle: s1.lifecycle,
      impact: s1.impact,
    };
  }
}
