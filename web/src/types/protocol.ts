/**
 * Strict TypeScript protocol definitions mirroring backend/schemas.py.
 * Ground-truth Box2D physics telemetry and WebSocket client/server message schemas.
 */

// =============================================================================
// Protocol Enums
// =============================================================================

export type ClientMessageType =
  | 'SESSION_INIT'
  | 'INPUT_ACTION'
  | 'CONTROL_CMD'
  | 'HEARTBEAT_PING';

export type ServerMessageType =
  | 'SESSION_READY'
  | 'SIMULATION_STEP'
  | 'CONTROL_ACK'
  | 'EPISODE_COMPLETE'
  | 'HEARTBEAT_PONG'
  | 'ERROR';

export type FlightMode = 'ai' | 'human' | 'storm';
export type PolicyMode = 'deterministic' | 'stochastic';
export type StormSeverity = 'moderate' | 'severe' | 'extreme';
export type EpisodeOutcome = 'SUCCESS' | 'CRASH' | 'TIMEOUT';

// =============================================================================
// Authoritative 2D Simulation Snapshot Schemas
// =============================================================================

export interface Kinematics2D {
  /** Horizontal position relative to pad centerline (Box2D distance units) */
  pos_x: number;
  /** Vertical coordinate of lander body center (Box2D distance units) */
  pos_y: number;
  /** Horizontal linear velocity (Box2D units/sec) */
  vel_x: number;
  /** Vertical linear velocity (Box2D units/sec) */
  vel_y: number;
  /** Lander body angle (radians, positive = counter-clockwise, 0 = upright) */
  angle: number;
  /** Angular velocity (radians/sec) */
  ang_vel: number;
  /** Calibrated vertical ground clearance of footpads above pad (0.0 = flush contact) */
  altitude: number;
}

export interface PropulsionState {
  /** Discrete action executed: 0=Coast, 1=Left RCS, 2=Main Engine, 3=Right RCS */
  action: 0 | 1 | 2 | 3;
  /** Main engine throttle intensity (0.0 to 1.0) */
  throttle: number;
  /** Left RCS thruster firing intensity (0.0 or 1.0) */
  rcs_left: number;
  /** Right RCS thruster firing intensity (0.0 or 1.0) */
  rcs_right: number;
}

export interface LandingGearState {
  /** Left footpad Box2D physical ground contact */
  left_contact: boolean;
  /** Right footpad Box2D physical ground contact */
  right_contact: boolean;
}

export interface AtmosphereState {
  /** Instantaneous horizontal aerodynamic wind force applied to lander */
  wind_force: number;
  /** Instantaneous turbulence torque applied to lander */
  turbulence: number;
}

export interface LifecycleState {
  /** Simulation step count */
  step: number;
  /** Authoritative simulation elapsed time in seconds (step * 0.02) */
  sim_time: number;
  /** Flight phase description (e.g. 'AIRBORNE', 'TOUCHDOWN', 'SETTLED') */
  touchdown_phase: string;
  /** Instantaneous Gymnasium step reward */
  step_reward: number;
  /** Cumulative episode reward */
  cumulative_reward: number;
  /** Environment termination flag (landing bonus or crash penalty) */
  terminated: boolean;
  /** Environment truncation flag (1000 step time limit) */
  truncated: boolean;
  /** Outcome classification if terminated or truncated */
  outcome?: EpisodeOutcome | string | null;
}

export interface ImpactTelemetry {
  impact_vel_x?: number | null;
  impact_vel_y?: number | null;
  impact_tilt?: number | null;
}

export interface SimulationSnapshotPayload {
  protocol_version: string;
  session_id: string;
  episode_id: number;
  kinematics: Kinematics2D;
  propulsion: PropulsionState;
  landing_gear: LandingGearState;
  atmosphere: AtmosphereState;
  lifecycle: LifecycleState;
  impact: ImpactTelemetry;
}

// =============================================================================
// Server Response Payloads
// =============================================================================

export interface SessionReadyPayload {
  session_id: string;
  dt: number;
  mode: FlightMode;
  policy_mode: PolicyMode;
  seed: number;
  /** Helipad coordinates: [x1, x2, y] in Box2D units */
  helipad_bounds: [number, number, number];
  /** Terrain profile polygon vertices: [x, y][] */
  terrain: [number, number][];
}

export interface EpisodeCompletePayload {
  session_id: string;
  episode_id: number;
  outcome: EpisodeOutcome | string;
  total_steps: number;
  total_sim_time: number;
  cumulative_reward: number;
  impact_vel_x?: number | null;
  impact_vel_y?: number | null;
  impact_tilt_deg?: number | null;
  final_clearance: number;
  final_tilt_deg: number;
}

export interface HeartbeatPongPayload {
  ping_timestamp: number;
  server_timestamp: number;
}

export interface ErrorPayload {
  code:
    | 'MALFORMED_JSON'
    | 'MISSING_TYPE'
    | 'UNSUPPORTED_TYPE'
    | 'VALIDATION_ERROR'
    | 'NO_SESSION'
    | 'SESSION_EXPIRED'
    | 'SESSION_TAKEOVER'
    | 'INVALID_MODE'
    | 'EPISODE_TERMINATED'
    | 'STALE_STEP'
    | 'SERVER_CAPACITY_EXCEEDED'
    | string;
  message: string;
}

export interface ControlAckPayload {
  command: string;
  status?: string;
  seed?: number;
  speed?: number;
  [key: string]: unknown;
}

// =============================================================================
// Server Message Envelopes
// =============================================================================

export interface ServerSessionReadyMessage {
  type: 'SESSION_READY';
  payload: SessionReadyPayload;
}

export interface ServerSimulationStepMessage {
  type: 'SIMULATION_STEP';
  payload: SimulationSnapshotPayload;
}

export interface ServerEpisodeCompleteMessage {
  type: 'EPISODE_COMPLETE';
  payload: EpisodeCompletePayload;
}

export interface ServerPongMessage {
  type: 'HEARTBEAT_PONG';
  payload: HeartbeatPongPayload;
}

export interface ServerErrorMessage {
  type: 'ERROR';
  payload: ErrorPayload;
}

export interface ServerControlAckMessage {
  type: 'CONTROL_ACK';
  payload: ControlAckPayload;
}

export type ServerWebSocketMessage =
  | ServerSessionReadyMessage
  | ServerSimulationStepMessage
  | ServerEpisodeCompleteMessage
  | ServerPongMessage
  | ServerErrorMessage
  | ServerControlAckMessage;

// =============================================================================
// Client Request Messages
// =============================================================================

export interface SessionInitPayload {
  session_id?: string | null;
  mode: FlightMode;
  policy_mode?: PolicyMode;
  seed?: number | null;
  storm_severity?: StormSeverity;
  wind?: number | null;
  turbulence?: number | null;
}

export interface InputActionPayload {
  step: number;
  action: 0 | 1 | 2 | 3;
  client_timestamp: number;
}

export interface ControlCmdPayload {
  command: 'pause' | 'resume' | 'reset' | 'set_speed';
  value?: number | null;
}

export interface HeartbeatPingPayload {
  timestamp: number;
}

export interface ClientInitMessage {
  type: 'SESSION_INIT';
  payload: SessionInitPayload;
}

export interface ClientInputMessage {
  type: 'INPUT_ACTION';
  payload: InputActionPayload;
}

export interface ClientControlMessage {
  type: 'CONTROL_CMD';
  payload: ControlCmdPayload;
}

export interface ClientPingMessage {
  type: 'HEARTBEAT_PING';
  payload: HeartbeatPingPayload;
}

export type ClientWebSocketMessage =
  | ClientInitMessage
  | ClientInputMessage
  | ClientControlMessage
  | ClientPingMessage;
