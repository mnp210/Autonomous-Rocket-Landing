/**
 * Coordinate Mapping and Physics Transformation for the Three.js 3D Presentation Layer.
 *
 * Maps authoritative Box2D 2D simulation coordinates (pos_x, altitude, angle, velocities)
 * onto a 3D visualization plane where:
 * - X is horizontal lateral position relative to landing pad center (pad at X=0).
 * - Y is vertical altitude / clearance above the pad surface (pad surface at Y=0).
 * - Z is visual depth (vehicle centerline at Z=0; depth used strictly for spatial composition).
 * - Rotation is planar around the Z-axis (rotation.z = angle).
 *
 * NOTE: Box2D simulation coordinates remain authoritative. No physical Z dynamics
 * or unverified conversions are fabricated.
 */

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface VelocityVectorResult {
  vector: Vector3D;
  speed: number;
  color: string;
  isSafeSink: boolean;
}

export interface TouchdownEstimate {
  predX: number;
  tGo: number;
  isSafe: boolean;
}

/**
 * Visual offset from the procedural booster model origin (center of mass)
 * to the bottom contact plane of the deployed landing gear footpads.
 *
 * Arithmetic derivation from procedural geometry in boosterModel.ts:
 * - Booster fuselage height: 1.38u (origin centered at y = 0.0)
 * - Leg attachment point on fuselage: y = -1.38 * 0.35 = -0.483u
 * - Footpad mesh local center inside leg assembly: y = -0.58u
 * - Footpad box geometry height: 0.04u (half-thickness = 0.02u)
 * - Footpad bottom contact plane: -0.483 + (-0.58) - 0.02 = -1.083u
 *
 * Therefore, when the footpads touch the pad surface (world Y = 0.0),
 * the vehicle center of mass must be positioned at world Y = +1.083u.
 *
 * NOTE: This is a purely presentation-layer visual offset. Box2D physics,
 * coordinate definitions, and PPO model observations remain strictly untouched.
 */
export const BOOSTER_FOOTPAD_OFFSET = 1.083;

/**
 * Maps authoritative Box2D planar coordinates to Three.js world coordinates.
 * Sanitizes non-finite inputs to safe defaults.
 *
 * @param posX Horizontal position relative to pad center (X=0)
 * @param altitude Calibrated footpad clearance above pad surface (Box2D units)
 * @param includeFootpadOffset If true (default), adds visual footpad offset so
 *        footpads meet the pad surface at altitude = 0.0.
 */
export function mapSimulationTo3DPosition(
  posX: number,
  altitude: number,
  includeFootpadOffset: boolean = true
): Vector3D {
  const safeX = Number.isFinite(posX) ? posX : 0.0;
  const safeAlt = Number.isFinite(altitude) ? Math.max(0.0, altitude) : 0.0;
  const yOffset = includeFootpadOffset ? BOOSTER_FOOTPAD_OFFSET : 0.0;
  return {
    x: safeX,
    y: safeAlt + yOffset,
    z: 0.0,
  };
}

/**
 * Maps Box2D body angle (radians, counter-clockwise) to Three.js Z-axis Euler rotation.
 * Sanitizes non-finite inputs to safe defaults.
 */
export function mapSimulationRotation(angleRad: number): number {
  return Number.isFinite(angleRad) ? angleRad : 0.0;
}

/**
 * Computes instantaneous velocity vector and danger threshold color.
 * Sanitizes non-finite velocity components to zero.
 */
export function computeVelocityVector(velX: number, velY: number): VelocityVectorResult {
  const safeVelX = Number.isFinite(velX) ? velX : 0.0;
  const safeVelY = Number.isFinite(velY) ? velY : 0.0;
  const speed = Math.sqrt(safeVelX * safeVelX + safeVelY * safeVelY);
  const isSafeSink = Math.abs(safeVelY) <= 1.0;

  let color = '#00E676'; // Safe (<= 1.0 u/s)
  if (Math.abs(safeVelY) > 2.0) {
    color = '#FF1744'; // Danger (> 2.0 u/s)
  } else if (Math.abs(safeVelY) > 1.0) {
    color = '#FFB300'; // Caution (1.0 to 2.0 u/s)
  }

  return {
    vector: {
      x: safeVelX,
      y: safeVelY,
      z: 0.0,
    },
    speed,
    color,
    isSafeSink,
  };
}

/**
 * Computes projected touchdown point on the pad given current descent trajectory.
 * 
 * NOTE: This estimate is a simplified open-loop linear kinematic projection for visual
 * situational awareness only. It is NOT an authoritative state or trajectory calculation
 * from the Box2D physics simulation.
 * Strict guards protect against non-finite inputs, upward/stalled motion, and division by zero.
 */
export function computeEstimatedTouchdown(
  posX: number,
  altitude: number,
  velX: number,
  velY: number,
  padHalfWidth: number = 1.5
): TouchdownEstimate | null {
  if (
    !Number.isFinite(posX) ||
    !Number.isFinite(altitude) ||
    !Number.isFinite(velX) ||
    !Number.isFinite(velY)
  ) {
    return null;
  }

  if (velY >= -0.05 || altitude <= 0.05) {
    return null;
  }

  const absVelY = Math.abs(velY);
  if (absVelY < 1e-4) {
    return null;
  }

  const tGo = altitude / absVelY;
  if (!Number.isFinite(tGo) || tGo < 0 || tGo > 600) {
    return null;
  }

  const predX = posX + velX * tGo;
  if (!Number.isFinite(predX)) {
    return null;
  }

  const isSafe = Math.abs(predX) <= padHalfWidth;

  return {
    predX,
    tGo,
    isSafe,
  };
}

/**
 * Determines whether propulsion should be strictly disabled.
 * Zero plumes on coast (action 0), cutoff (throttle <= 0), or terminal state latch.
 */
export function isPropulsionCutoff(
  terminated: boolean,
  truncated: boolean,
  throttle: number
): boolean {
  return terminated || truncated || throttle <= 0.0;
}

/**
 * Computes camera target and eye positions for follow vs overview modes.
 */
export function computeCameraTargets(
  mode: 'follow' | 'overview',
  posX: number,
  altitude: number
): { eye: Vector3D; target: Vector3D } {
  if (mode === 'overview') {
    // Wide overview capturing entire launchpad, towers, and spaceport
    return {
      eye: { x: 0.0, y: 7.0, z: 24.0 },
      target: { x: 0.0, y: 3.5, z: 0.0 },
    };
  }

  // Follow Mode: Cinematic elevated tracking camera
  // As altitude decreases, eye smoothly drops and draws closer for dramatic touchdown view
  const targetY = Math.max(0.5, altitude);
  const camElev = Math.max(2.5, altitude * 0.45 + 1.8);
  const camDistZ = Math.max(7.5, altitude * 0.65 + 6.0);

  return {
    eye: {
      x: posX * 0.45,
      y: targetY + camElev,
      z: camDistZ,
    },
    target: {
      x: posX * 0.75,
      y: targetY * 0.8,
      z: 0.0,
    },
  };
}
