"""Pydantic schemas for the WebSocket protocol and authoritative simulation snapshots."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Protocol Enums
# =============================================================================

class ClientMessageType(str, Enum):
    SESSION_INIT = "SESSION_INIT"
    INPUT_ACTION = "INPUT_ACTION"
    CONTROL_CMD = "CONTROL_CMD"
    HEARTBEAT_PING = "HEARTBEAT_PING"


class ServerMessageType(str, Enum):
    SESSION_READY = "SESSION_READY"
    SIMULATION_STEP = "SIMULATION_STEP"
    CONTROL_ACK = "CONTROL_ACK"
    EPISODE_COMPLETE = "EPISODE_COMPLETE"
    HEARTBEAT_PONG = "HEARTBEAT_PONG"
    ERROR = "ERROR"


class FlightMode(str, Enum):
    AI = "ai"
    HUMAN = "human"
    STORM = "storm"


class PolicyMode(str, Enum):
    DETERMINISTIC = "deterministic"
    STOCHASTIC = "stochastic"


class StormSeverity(str, Enum):
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


# =============================================================================
# Client Payload Schemas
# =============================================================================

class SessionInitPayload(BaseModel):
    """Configuration requested when initializing or reconnecting to a simulation session."""

    session_id: Optional[str] = Field(default=None, description="Optional session UUID for reconnection attempts")
    mode: FlightMode = FlightMode.AI
    policy_mode: PolicyMode = PolicyMode.DETERMINISTIC
    seed: Optional[int] = Field(default=None, ge=0, le=2_147_483_647)
    storm_severity: StormSeverity = StormSeverity.MODERATE
    wind: Optional[float] = Field(default=None, ge=0.0, le=25.0)
    turbulence: Optional[float] = Field(default=None, ge=0.0, le=2.5)


class InputActionPayload(BaseModel):
    """Discrete manual pilot input from the client with strict validation."""

    step: int = Field(ge=0, description="Client perceived simulation step number")
    action: int = Field(strict=True, ge=0, le=3, description="0=Coast, 1=Left RCS, 2=Main Engine, 3=Right RCS (strictly integer 0-3)")
    client_timestamp: float = Field(description="Client wall-clock time in seconds")


class ControlCmdPayload(BaseModel):
    """Control flow commands (pause, resume, reset, set_speed)."""

    command: Literal["pause", "resume", "reset", "set_speed"]
    value: Optional[float] = Field(default=None, ge=0.1, le=2.0, description="Optional parameter, e.g. speed factor")


class HeartbeatPingPayload(BaseModel):
    """Heartbeat keepalive and latency probe."""

    timestamp: float


# =============================================================================
# Discriminated Client Messages
# =============================================================================

class ClientInitMessage(BaseModel):
    type: Literal[ClientMessageType.SESSION_INIT] = ClientMessageType.SESSION_INIT
    payload: SessionInitPayload


class ClientInputMessage(BaseModel):
    type: Literal[ClientMessageType.INPUT_ACTION] = ClientMessageType.INPUT_ACTION
    payload: InputActionPayload


class ClientControlMessage(BaseModel):
    type: Literal[ClientMessageType.CONTROL_CMD] = ClientMessageType.CONTROL_CMD
    payload: ControlCmdPayload


class ClientPingMessage(BaseModel):
    type: Literal[ClientMessageType.HEARTBEAT_PING] = ClientMessageType.HEARTBEAT_PING
    payload: HeartbeatPingPayload


ClientWebSocketMessage = Union[
    ClientInitMessage,
    ClientInputMessage,
    ClientControlMessage,
    ClientPingMessage,
]


# =============================================================================
# Authoritative Snapshot & Telemetry Schemas (Ground Truth 2D Physics)
# =============================================================================

class Kinematics2D(BaseModel):
    """Planar Box2D kinematics relative to the landing target.
    
    NOTE: All positions and distances are expressed in Box2D simulation coordinate
    units (where the viewport spans ~20 units horizontally and ~13.3 units vertically).
    They are NOT calibrated to real-world SI meters. 'altitude' is calibrated so that
    0.0 represents zero vertical ground clearance of the landing gear footpads
    above the pad surface.
    """

    pos_x: float = Field(description="Horizontal position relative to pad center (Box2D distance units)")
    pos_y: float = Field(description="Vertical coordinate of body center (Box2D distance units)")
    vel_x: float = Field(description="Horizontal linear velocity (Box2D units/s)")
    vel_y: float = Field(description="Vertical linear velocity (Box2D units/s)")
    angle: float = Field(description="Lander body angle (radians, positive=counter-clockwise)")
    ang_vel: float = Field(description="Angular velocity (rad/s)")
    altitude: float = Field(description="Calibrated ground clearance of footpads above pad surface (Box2D units)")


class PropulsionState(BaseModel):
    """Actual actuator commands executed in the physics timestep."""

    action: int = Field(ge=0, le=3, description="Discrete action integer (0-3)")
    throttle: float = Field(ge=0.0, le=1.0, description="Main engine thrust intensity (0.0 to 1.0)")
    rcs_left: float = Field(ge=0.0, le=1.0, description="Left RCS thruster status")
    rcs_right: float = Field(ge=0.0, le=1.0, description="Right RCS thruster status")


class LandingGearState(BaseModel):
    """Direct Box2D physical ground contact sensor readings."""

    left_contact: bool
    right_contact: bool


class AtmosphereState(BaseModel):
    """Current atmospheric aerodynamic disturbances."""

    wind_force: float = Field(description="Instantaneous horizontal wind force applied to lander")
    turbulence: float = Field(description="Instantaneous turbulence torque applied to lander")


class LifecycleState(BaseModel):
    """Simulation step, rewards, and episode termination progression."""

    step: int = Field(ge=0)
    sim_time: float = Field(ge=0.0, description="Physical simulation time in seconds (step * 0.02)")
    touchdown_phase: str = Field(description="Flight phase or touchdown status")
    step_reward: float = Field(description="Instantaneous Gymnasium step reward")
    cumulative_reward: float = Field(description="Episode cumulative reward")
    terminated: bool = Field(description="Environment termination flag")
    truncated: bool = Field(description="Environment truncation flag (time limit)")
    outcome: Optional[str] = Field(default=None, description="SUCCESS, CRASH, TIMEOUT, etc.")


class ImpactTelemetry(BaseModel):
    """Transient physical state captured at the initial ground impact moment."""

    impact_vel_x: Optional[float] = None
    impact_vel_y: Optional[float] = None
    impact_tilt: Optional[float] = None


class SimulationSnapshotPayload(BaseModel):
    """Complete, versioned physical snapshot streamed every simulation step."""

    protocol_version: str = "1.0.0"
    session_id: str
    episode_id: int
    kinematics: Kinematics2D
    propulsion: PropulsionState
    landing_gear: LandingGearState
    atmosphere: AtmosphereState
    lifecycle: LifecycleState
    impact: ImpactTelemetry


# =============================================================================
# Server Response Messages
# =============================================================================

class SessionReadyPayload(BaseModel):
    """Environment geometry, parameters, and metadata sent after initialization."""

    session_id: str
    dt: float = 0.02
    mode: FlightMode
    policy_mode: PolicyMode
    seed: int
    helipad_bounds: Tuple[float, float, float]  # (x1, x2, y)
    terrain: List[Tuple[float, float]]


class EpisodeCompletePayload(BaseModel):
    """Final debrief metrics sent when an episode ends."""

    session_id: str
    episode_id: int
    outcome: str
    total_steps: int
    total_sim_time: float
    cumulative_reward: float
    impact_vel_x: Optional[float] = None
    impact_vel_y: Optional[float] = None
    impact_tilt_deg: Optional[float] = None
    final_clearance: float
    final_tilt_deg: float


class HeartbeatPongPayload(BaseModel):
    ping_timestamp: float
    server_timestamp: float


class ErrorPayload(BaseModel):
    code: str
    message: str


class ServerSessionReadyMessage(BaseModel):
    type: Literal[ServerMessageType.SESSION_READY] = ServerMessageType.SESSION_READY
    payload: SessionReadyPayload


class ServerSimulationStepMessage(BaseModel):
    type: Literal[ServerMessageType.SIMULATION_STEP] = ServerMessageType.SIMULATION_STEP
    payload: SimulationSnapshotPayload


class ServerEpisodeCompleteMessage(BaseModel):
    type: Literal[ServerMessageType.EPISODE_COMPLETE] = ServerMessageType.EPISODE_COMPLETE
    payload: EpisodeCompletePayload


class ServerPongMessage(BaseModel):
    type: Literal[ServerMessageType.HEARTBEAT_PONG] = ServerMessageType.HEARTBEAT_PONG
    payload: HeartbeatPongPayload


class ServerErrorMessage(BaseModel):
    type: Literal[ServerMessageType.ERROR] = ServerMessageType.ERROR
    payload: ErrorPayload


class ServerControlAckMessage(BaseModel):
    type: Literal[ServerMessageType.CONTROL_ACK] = ServerMessageType.CONTROL_ACK
    payload: Dict[str, Any]


ServerWebSocketMessage = Union[
    ServerSessionReadyMessage,
    ServerSimulationStepMessage,
    ServerEpisodeCompleteMessage,
    ServerPongMessage,
    ServerErrorMessage,
    ServerControlAckMessage,
]
