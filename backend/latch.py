"""Terminal State Latch & Contact Classification Engine.

Guarantees:
1. Contact state tracking (airborne, single-leg contact, bounce, dual-leg touchdown).
2. Unstable contact and bounce recovery are preserved without premature propulsion cut.
3. Once a stable touchdown or environment termination occurs, propulsion is strictly zeroed.
4. Prevents post-landing thruster firing anomalies across both AI and human pilot modes.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class ContactMetrics:
    """Transient physical telemetry captured at the moment of first ground contact."""

    step: int
    sim_time: float
    vel_x: float
    vel_y: float
    tilt_rad: float
    contact_type: str  # "SINGLE_LEFT", "SINGLE_RIGHT", "DUAL"


class TerminalStateLatch:
    """Authoritative terminal-state latch and touchdown progression monitor."""

    def __init__(self, settle_budget_steps: int = 60):
        self.is_latched: bool = False
        self.latch_step: Optional[int] = None
        self.latch_reason: Optional[str] = None
        self.ground_settle_steps: int = 0
        self.settle_budget_steps: int = settle_budget_steps

        # Contact telemetry
        self.first_contact: Optional[ContactMetrics] = None
        self.touchdown_phase: str = "AIRBORNE"
        self.contact_type: str = "NONE"

    def check_and_update(
        self,
        obs: np.ndarray,
        terminated: bool,
        truncated: bool,
        step: int,
        altitude: Optional[float] = None,
        raw_vx: Optional[float] = None,
        raw_vy: Optional[float] = None,
        raw_angle: Optional[float] = None,
    ) -> bool:
        """Evaluates physical observation and updates contact/latch status.

        Returns:
            True if the terminal latch is engaged (propulsion must be zeroed), False otherwise.
        """
        if self.is_latched:
            return True

        # Extract kinematic features from Box2D observation vector
        # obs: [x, y, vx, vy, theta, ang_vel, left_contact, right_contact]
        leg_l = bool(obs[6] > 0.5)
        leg_r = bool(obs[7] > 0.5)
        vx = raw_vx if raw_vx is not None else float(obs[2] * 5.0)
        vy = raw_vy if raw_vy is not None else float(obs[3] * 5.0)
        theta = raw_angle if raw_angle is not None else float(obs[4])
        alt = altitude if altitude is not None else float(obs[1])

        # 1. Update contact type
        if leg_l and leg_r:
            self.contact_type = "DUAL"
        elif leg_l:
            self.contact_type = "SINGLE_LEFT"
        elif leg_r:
            self.contact_type = "SINGLE_RIGHT"
        else:
            self.contact_type = "NONE"

        # 2. Record initial ground contact event
        if (leg_l or leg_r) and self.first_contact is None:
            self.first_contact = ContactMetrics(
                step=step,
                sim_time=step * 0.02,
                vel_x=vx,
                vel_y=vy,
                tilt_rad=theta,
                contact_type=self.contact_type,
            )

        # 3. Environment Termination or Truncation (Highest Priority)
        if terminated or truncated:
            self.is_latched = True
            self.latch_step = step
            if truncated:
                self.latch_reason = "ENVIRONMENT_TRUNCATION"
                self.touchdown_phase = "TIMEOUT"
            else:
                self.latch_reason = "ENVIRONMENT_TERMINATION"
                # Check crash vs landing via boundary or contact state
                if abs(obs[0]) >= 1.0 or (self.first_contact and abs(self.first_contact.vel_y) > 3.0):
                    self.touchdown_phase = "CRASH"
                else:
                    self.touchdown_phase = "TOUCHDOWN_SETTLED"
            return True

        # 4. In-Flight Contact State Machine (Handling Bounce vs Settled Touchdown)
        if self.contact_type == "NONE":
            if self.first_contact is not None:
                # Leg touched previously but is now airborne -> Rebound / Bounce
                self.touchdown_phase = "BOUNCE"
            else:
                self.touchdown_phase = "AIRBORNE"
            return False

        # Single-leg contact at non-trivial velocity or tilt -> Unstable contact (do NOT latch)
        if self.contact_type in ("SINGLE_LEFT", "SINGLE_RIGHT"):
            if abs(vx) > 0.35 or abs(vy) > 0.25 or abs(theta) > 0.15:
                self.touchdown_phase = "UNSTABLE_CONTACT"
                return False  # Policy must retain control authority to recover/level

        # Dual-leg contact or very low energy single leg
        if (leg_l and leg_r and alt <= 0.08 and abs(vx) < 0.35 and abs(vy) < 0.35 and abs(theta) < 0.25) or (
            alt <= 0.025 and (leg_l or leg_r) and abs(vx) < 0.15 and abs(vy) < 0.15 and abs(theta) < 0.10
        ):
            self.is_latched = True
            self.latch_step = step
            self.latch_reason = "TOUCHDOWN_SETTLED"
            self.touchdown_phase = "SETTLED_TOUCHDOWN"
            return True

        self.touchdown_phase = "INITIAL_CONTACT"
        return False

    def filter_action(self, proposed_action: int) -> int:
        """Enforces zero propulsion if the terminal latch is active."""
        if self.is_latched:
            return 0
        return proposed_action
