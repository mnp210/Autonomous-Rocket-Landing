# Gymnasium LunarLander-v3 Specification

## 1. Overview
`LunarLander-v3` is a standard 2D robotics simulation environment within Gymnasium simulating rocket trajectory guidance and soft touchdown dynamics. It is governed by Box2D rigid-body 2D physics.

The primary objective is to navigate the lander from the top of the viewport to a designated landing pad at coordinates $(0, 0)$ without crashing, maintaining safe orientation, and minimizing fuel expenditure.

---

## 2. Observation Space
The observation space is a continuous vector with shape `(8,)` in `Box(-inf, inf, (8,), float32)`.

| Index | Name | Physical Quantity | Typical Range | Description |
|:---:|:---|:---|:---:|:---|
| **0** | `x` | Horizontal position | $[-1.5, 1.5]$ | Horizontal displacement from center. The landing pad is located at $x = 0$. |
| **1** | `y` | Vertical position / altitude | $[0.0, 1.5]$ | Altitude above the ground plane. Surface ground level is around $y = 0$. |
| **2** | `vx` | Linear horizontal velocity | $[-5.0, 5.0]$ | Velocity in the horizontal direction. |
| **3** | `vy` | Linear vertical velocity | $[-5.0, 5.0]$ | Velocity in the vertical direction (negative is descending). |
| **4** | `theta` | Angular position / tilt | $[-\pi, \pi]$ | Body orientation angle in radians. $0$ is upright. |
| **5** | `theta_dot` | Angular velocity | $[-10.0, 10.0]$ | Rate of change of body angle (rotational speed). |
| **6** | `leg_left_contact` | Boolean flag (0.0 or 1.0) | $\{0.0, 1.0\}$ | $1.0$ if left landing leg is in contact with the ground, else $0.0$. |
| **7** | `leg_right_contact` | Boolean flag (0.0 or 1.0) | $\{0.0, 1.0\}$ | $1.0$ if right landing leg is in contact with the ground, else $0.0$. |

---

## 3. Action Space

### Discrete Action Space (Default: `Discrete(4)`)
In standard discrete mode, the lander possesses 4 discrete actions:

| Action ID | Action Name | Actuator Description |
|:---:|:---|:---|
| **0** | `Do Nothing` | All thrusters are idle (free-fall / ballistic flight). |
| **1** | `Fire Left Thruster` | Fires the left attitude control thruster to impart clockwise torque (rolls rocket right). |
| **2** | `Fire Main Engine` | Fires the main central rocket engine to provide upward thrust counteracting gravity. |
| **3** | `Fire Right Thruster` | Fires the right attitude control thruster to impart counter-clockwise torque (rolls rocket left). |

*(Note: Continuous action space mode `Box(-1.0, 1.0, (2,), float32)` is also supported by Gymnasium when initialized with `continuous=True`, where action `[0]` throttles main engine and action `[1]` controls lateral roll thrust).*

---

## 4. Reward System
The environment reward signal is structured as follows:
- **Approach & Alignment**: Moving closer to the landing pad coordinates $(0, 0)$ and reducing speed increases reward (+100 to +140 range over a full descent).
- **Attitude Alignment**: Tilting away from vertical ($0$ angle) incurs a penalty.
- **Leg Ground Contact**: Each landing leg touching the ground yields $+10$ points.
- **Engine Usage Cost**:
  - Main engine firing incurs $-0.3$ points per frame.
  - Side thruster firing incurs $-0.03$ points per frame.
- **Terminal Rewards**:
  - Safe touchdown inside landing pad: $+100$ bonus points.
  - Crash landing / destruction: $-100$ penalty.

An episode is widely considered **solved** when an agent consistently achieves an average cumulative reward of $\ge 200$ over 100 consecutive episodes.

---

## 5. Episode Termination & Truncation Conditions
An episode finishes when any of the following conditions is satisfied:

1. **Termination (`terminated = True`)**:
   - The lander crashes into terrain or body contact occurs (destruction).
   - The lander comes to rest safely on the landing pad (linear & angular velocities near zero with legs touching down).
   - The lander flies out of the horizontal physical viewport bounds ($|x| > 1.0$).
2. **Truncation (`truncated = True`)**:
   - Step limit reached (default `max_episode_steps = 1000` under the standard `TimeLimit` wrapper).

---

## 6. Rendering Modes
Supported Gymnasium render modes:
- `None`: Headless mode for high-throughput training.
- `'human'`: Displays interactive Pygame simulation window at standard frame rate.
- `'rgb_array'`: Returns an `np.ndarray` of shape `(H, W, 3)` containing rendered pixel frames for video recording and telemetry visualization.
