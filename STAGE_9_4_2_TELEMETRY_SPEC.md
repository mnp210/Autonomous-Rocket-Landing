# Stage 9.4.2 — Live Flight Telemetry & Engineering Visualization: Telemetry Specification

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.4.2  
**Document:** Telemetry Availability Matrix, Coordinate Conventions & Units Specification  
**Status:** **AUTHORITATIVE & VERIFIED**  

---

## 1. Verified Telemetry Availability Matrix

Every metric displayed on the Research & Engineering Dashboard must trace directly to an authoritative field in the Gymnasium/Box2D simulation or FastAPI WebSocket stream.

| Subsystem / Metric | Backend Source Field | Actual Physical Unit | Stream Cadence | Availability Status | Notes & Constraints |
|:---|:---|:---:|:---:|:---:|:---|
| **Horizontal Position** | `kinematics.pos_x` | Box2D units (`u`) | $50\text{ Hz}$ | **VERIFIED** | Relative to helipad center ($X=0.0$). Viewport span is $\approx \pm 10.0\text{ u}$. |
| **Vertical Body Position** | `kinematics.pos_y` | Box2D units (`u`) | $50\text{ Hz}$ | **VERIFIED** | Center of mass vertical coordinate in world space. |
| **Footpad Clearance / Altitude**| `kinematics.altitude` | Box2D units (`u`) | $50\text{ Hz}$ | **VERIFIED** | Calibrated clearance: $\max(0, Y_{\text{lander}} - Y_{\text{pad}} - 0.592)$. $0.0\text{ u}$ = flush ground contact. **NOT meters**. |
| **Horizontal Velocity** | `kinematics.vel_x` | Box2D units/sec (`u/s`) | $50\text{ Hz}$ | **VERIFIED** | Linear velocity in X. Positive = right drift, negative = left drift. |
| **Vertical Velocity** | `kinematics.vel_y` | Box2D units/sec (`u/s`) | $50\text{ Hz}$ | **VERIFIED** | Linear velocity in Y. Negative = descent (sink rate), positive = ascent. |
| **Body Attitude Angle** | `kinematics.angle` | Radians (`rad`) | $50\text{ Hz}$ | **VERIFIED** | $0.0 = \text{upright}$. Positive = counter-clockwise tilt. Displays in rad and degrees ($^\circ$). |
| **Body Angular Velocity** | `kinematics.ang_vel` | Radians/sec (`rad/s`) | $50\text{ Hz}$ | **VERIFIED** | Rotational velocity $\dot{\theta}$. |
| **Commanded Discrete Action** | `propulsion.action` | Enum $\{0, 1, 2, 3\}$ | $50\text{ Hz}$ | **VERIFIED** | 0=Coast, 1=Left RCS, 2=Main Engine, 3=Right RCS. Filtered through terminal latch. |
| **Main Engine Actuator State** | `propulsion.throttle` | Fraction $[0.0, 1.0]$ | $50\text{ Hz}$ | **VERIFIED** | $1.0$ when action 2 executed and not latched; $0.0$ otherwise. |
| **RCS Port (Left) Thruster** | `propulsion.rcs_left` | Fraction $[0.0, 1.0]$ | $50\text{ Hz}$ | **VERIFIED** | $1.0$ when action 1 active; generates clockwise torque. |
| **RCS Stbd (Right) Thruster**| `propulsion.rcs_right`| Fraction $[0.0, 1.0]$ | $50\text{ Hz}$ | **VERIFIED** | $1.0$ when action 3 active; generates counter-clockwise torque. |
| **Left Footpad Contact** | `landing_gear.left_contact` | Boolean | $50\text{ Hz}$ | **VERIFIED** | Direct Box2D sensor reading from `legs[0].ground_contact`. |
| **Right Footpad Contact** | `landing_gear.right_contact`| Boolean | $50\text{ Hz}$ | **VERIFIED** | Direct Box2D sensor reading from `legs[1].ground_contact`. |
| **Aerodynamic Wind Force** | `atmosphere.wind_force` | Force units | $50\text{ Hz}$ | **VERIFIED** | Applied horizontal wind force vector. |
| **Aerodynamic Turbulence** | `atmosphere.turbulence` | Torque units | $50\text{ Hz}$ | **VERIFIED** | Applied rotational turbulence torque. |
| **Step Reward** | `lifecycle.step_reward` | Dimensionless float | $50\text{ Hz}$ | **VERIFIED** | Instantaneous Gymnasium reward for step $t$. |
| **Cumulative Episode Reward**| `lifecycle.cumulative_reward`| Dimensionless float | $50\text{ Hz}$ | **VERIFIED** | Total accumulated return $R = \sum_{t=0}^k r_t$. |
| **Simulation Step & Time** | `lifecycle.step`, `sim_time` | Integer / Seconds | $50\text{ Hz}$ | **VERIFIED** | $t = \text{step} \times 0.02\text{ s}$. 50 Hz authoritative. |
| **Touchdown Phase** | `lifecycle.touchdown_phase` | Enum string | $50\text{ Hz}$ | **VERIFIED** | `AIRBORNE`, `TERMINAL_APPROACH`, `TOUCHDOWN_DETECTED`. |
| **Terminal Outcome** | `lifecycle.outcome` | String (`SUCCESS`, `CRASH`, `TIMEOUT`) | On terminal step | **VERIFIED** | Classified by physical touchdown criteria via `classify_outcome()`. |
| **First Impact Telemetry** | `impact.impact_vel_x/y/tilt`| `u/s` and `rad` | On contact | **VERIFIED** | Captured at initial contact by `TerminalStateLatch`. |

---

## 2. Explicitly Unavailable / Non-Existent Fields (Zero-Fabrication Policy)

The following metrics **do not exist** in the authoritative simulation and are strictly **prohibited** from being estimated, fabricated, or displayed as measured telemetry:

| Prohibited / Unavailable Metric | Reason for Unavailability | Architectural Mandate |
|:---|:---|:---|
| **SI Meters ($m$) Calibration** | Box2D coordinates are dimensionless simulation units ($\sim 20 \times 13.3$). | All distances must be labeled `units` or `u`. Never label Box2D units as meters. |
| **Propellant Mass / Fuel Quantity** | LunarLander-v3 does not model variable propellant mass depletion. | Do not draw fuel gauges, fuel percentages, or remaining delta-V meters. |
| **Engine Chamber Pressure / Temperature**| No thermodynamic rocket cycle model exists in Box2D. | Do not fabricate temperature dials, combustion chamber gauges, or heat bars. |
| **Actuator Gimbal Angle** | Lander uses a fixed main engine axis with RCS thrusters for attitude control. | Do not display imaginary gimbal deflection degrees. |
| **3D Roll and Pitch Euler Angles** | Box2D is strictly a 2D planar physics engine ($X, Y, \theta_z$). | Do not invent roll ($\phi$) or pitch ($\psi$) angles. Attitude is strictly planar angle $\theta$. |
| **Ideal Braking Curve Baseline** | No analytic closed-form curve exists in the baseline repository. | Chart 2 plots purely measured data and physical thresholds ($v_y \le -0.40\text{ u/s}$). |

---

## 3. Coordinate Conventions & Physical Thresholds

### 3.1 Coordinate Frames
- **Landing Target Center:** $X = 0.000\text{ u}$, $Y = 0.000\text{ u}$ (Pad surface).
- **Horizontal Axis ($X$):**
  - Origin: Helipad centerline.
  - Positive ($+X$): East / Starboard (right).
  - Negative ($-X$): West / Port (left).
  - Helipad Boundary: $|X| \le 1.50\text{ u}$ (visual pad width $\approx 4.0\text{ u}$).
  - Strict Landing Criterion: $|X| \le 0.25\text{ u}$ (lander center between helipad flags).
- **Vertical Axis ($Y$):**
  - Ground Reference: $Y = 0.000\text{ u}$ (Helipad surface).
  - Body Center of Mass at Rest: $Y \approx 1.083\text{ u}$ (due to landing gear leg extension).
  - Footpad Ground Clearance (`altitude`): $Y_{\text{clearance}} = \max(0, Y_{\text{lander}} - Y_{\text{pad}} - 0.592)$. At rest on pad, $\text{clearance} = 0.00\text{ u}$.
- **Attitude Angle ($\theta$):**
  - Origin: Upright vertical flight ($\theta = 0.000\text{ rad} = 0.0^\circ$).
  - Positive ($+\theta$): Counter-clockwise tilt (tilting left).
  - Negative ($-\theta$): Clockwise tilt (tilting right).
  - Strict Landing Criterion: $|\theta| \le 0.20\text{ rad}$ ($\approx 11.46^\circ$).

### 3.2 Dynamic Velocity Thresholds
- **Vertical Descent Rate ($v_y$):**
  - $v_y \ge -0.40\text{ u/s}$: **Nominal Touchdown Zone** (Strict landing acceptance).
  - $-0.40 > v_y \ge -1.00\text{ u/s}$: **Safe Controlled Descent**.
  - $-1.00 > v_y \ge -2.00\text{ u/s}$: **Caution / High Sink Rate**.
  - $v_y < -2.00\text{ u/s}$: **Danger / Terminal Impact Hazard**.
- **Horizontal Drift Velocity ($v_x$):**
  - $|v_x| \le 0.40\text{ u/s}$: **Nominal Touchdown Zone** (Strict landing acceptance).
  - $0.40 < |v_x| \le 0.80\text{ u/s}$: **Acceptable Lateral Drift**.
  - $|v_x| > 0.80\text{ u/s}$: **Excessive Shear Warning**.
- **Angular Velocity ($\dot{\theta}$):**
  - $|\dot{\theta}| \le 0.35\text{ rad/s}$: **Nominal Touchdown Zone** (Strict landing acceptance).
  - $|\dot{\theta}| > 0.35\text{ rad/s}$: **Excessive Tumble Rate**.

---

## 4. Sampling & Buffering Policy

1. **Authoritative Input Stream:** $50\text{ Hz}$ ($20\text{ ms}$ tick intervals) delivered via WebSocket `SIMULATION_STEP` packets.
2. **Telemetry History Buffer:**
   - Ring buffer sized to $N = 1500$ points (covering up to $30\text{ seconds}$ at $50\text{ Hz}$, well exceeding the $1000$-step maximum episode cutoff).
   - Each data point stores: `{ step, time, x, y, alt, vx, vy, angle, ang_vel, reward, cum_reward, action, throttle, phase }`.
3. **Chart Rendering Cadence:**
   - Visual chart repainting is decoupled from the $50\text{ Hz}$ React tree using dedicated HTML5 Canvas renderers.
   - Canvas repaints are throttled to requestAnimationFrame / ~20 Hz or on-demand, preventing high React re-rendering costs.
4. **Lifecycle Scoping:**
   - When `episode_id` changes or a `reset` control ack is received, the current history buffer is transferred to the episode log archive, and the active trace resets cleanly.
   - Data points from different episodes are **never mixed**.
