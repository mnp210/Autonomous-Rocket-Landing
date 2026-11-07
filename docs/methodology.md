# Experimental Methodology & Research Architecture

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Environment:** Gymnasium `LunarLander-v3` (Box2D Physics)  
**Algorithm:** Proximal Policy Optimization (PPO, `MlpPolicy`)  
**License:** Apache License 2.0  

---

## 1. Research Motivation & Core Questions

Autonomous rocket landing is an underactuated, highly nonlinear flight control problem subject to severe aerodynamic disturbances, varying gravitational fields, and strict physical touchdown tolerances. Standard reinforcement learning agents trained in a single nominal simulator frequently overfit to fixed physics parameters and suffer catastrophic failure when exposed to environmental variations.

This research investigates two core questions:
1. **The Domain Randomization Question:** Does exposing an autonomous landing agent to broad stochastic distributions of environmental stressors (crosswind, turbulence, gravity shifts, lateral kinetic impulses) improve generalizability, or does it destabilize early policy exploration?
2. **The Curriculum Scaffolding Hypothesis:** Does progressive curriculum learning provide developmental stability that enables an agent to master attitude stabilization before navigating severe aerodynamic disturbances?

---

## 2. Reinforcement Learning Formulation

### A. State Space ($\mathcal{S} \subset \mathbb{R}^8$)
The state vector $s_t \in \mathbb{R}^8$ captures kinematic and ground sensor telemetry:
- $s_0 = x$: Horizontal coordinate normalized by viewport ($x = 0$ is helipad center).
- $s_1 = y$: Vertical coordinate normalized by viewport ($y = 0$ is helipad surface).
- $s_2 = v_x$: Horizontal linear velocity.
- $s_3 = v_y$: Vertical linear velocity.
- $s_4 = \theta$: Lander pitch attitude angle (radians, $\theta = 0$ upright).
- $s_5 = \dot{\theta}$: Angular velocity / roll spin rate.
- $s_6 \in \{0, 1\}$: Left landing leg ground contact boolean flag.
- $s_7 \in \{0, 1\}$: Right landing leg ground contact boolean flag.

### B. Action Space ($\mathcal{A} = \{0, 1, 2, 3\}$)
Discrete bang-bang thruster actuation:
- $a = 0$: Idle / coasting (no engine active).
- $a = 1$: Fire left orientation thruster (induces clockwise torque).
- $a = 2$: Fire main engine (induces upward vertical thrust $F \approx 20$).
- $a = 3$: Fire right orientation thruster (induces counter-clockwise torque).

### C. Policy Optimization (PPO)
We utilize Stable-Baselines3's implementation of Proximal Policy Optimization (PPO) with clipped surrogate objective:
$$L^{\text{CLIP}}(\theta) = \hat{\mathbb{E}}_t \left[ \min\left(r_t(\theta)\hat{A}_t, \, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon)\hat{A}_t\right) \right]$$
where $r_t(\theta) = \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{\text{old}}}(a_t|s_t)}$ and $\hat{A}_t$ is computed via Generalized Advantage Estimation (GAE-$\lambda$).

**Hyperparameters (Frozen across all benchmark paradigms):**
- Policy Architecture: 2-layer MLP (64 units/layer, `tanh` activations)
- Learning Rate: $\alpha = 3 \times 10^{-4}$ (constant)
- Horizon & Minibatch: $n_{\text{steps}} = 2048$, $\text{batch\_size} = 64$, $n_{\text{epochs}} = 10$
- Discount Factor: $\gamma = 0.99$
- GAE Parameter: $\lambda = 0.95$
- Clipping Parameter: $\epsilon = 0.20$
- Gradient Clipping: $\text{max\_grad\_norm} = 0.5$

---

## 3. Training Paradigms

| Paradigm Identifier | Paradigm Name | Environmental Dynamics | Stochastic Sampling | Scaffolding |
|:---|:---|:---|:---:|:---:|
| **`A_standard`** | Standard PPO (Control) | Fixed nominal physics ($g = -10$, no wind) | None | None |
| **`B_dr_only`** | PPO + Domain Randomization | Broad uniform distributions from step zero | Active | None |
| **`C_curriculum_only`**| PPO + Curriculum Learning | 5-stage progressive deterministic ladder | None | Automated ($\ge 70\%$) |
| **`D_curriculum_and_dr`**| PPO + Curriculum + DR | 5-stage progressive ladder + stochastic bounds | Active per stage | Automated ($\ge 70\%$) |

---

## 4. Curriculum Progression & Rollback Engine

The curriculum manager (`CurriculumManager`) monitors policy performance via periodic evaluation intervals ($20$ episodes every $10,000$ steps):

### Progression Rule
Advancement from stage $k$ to stage $k+1$ requires:
1. Minimum stage dwell time: $t_{\text{stage}} \ge 20,000$ timesteps.
2. Consecutive passing evaluations: $2$ consecutive evaluation intervals achieving physical landing success rate $\ge 70\%$.

### Rollback Protection Rule
If after advancing to stage $k \ge 1$, the policy's evaluation success rate collapses below $30\%$, the manager triggers an automatic rollback:
$$\text{Stage } k \longrightarrow \text{Stage } k-1$$
This mechanism prevents catastrophic forgetting and stabilizes exploration under severe stressors.

### The 5-Stage Ladder
- **Stage 0 (Standard):** Nominal physics ($g = -10.0 \text{ m/s}^2$, no wind).
- **Stage 1 (Moderate Gravity):** Gravity modulated $\in [-11.0, -9.0] \text{ m/s}^2$, zero wind.
- **Stage 2 (Mild Wind):** Gravity $\in [-11.0, -9.0]$, wind probability $0.6$, wind power $\in [5.0, 15.0]$, turbulence $\in [0.2, 1.0]$.
- **Stage 3 (High Wind & Turbulence):** Gravity $\in [-12.0, -8.0]$, wind probability $0.8$, wind power $\in [10.0, 20.0]$, turbulence $\in [0.5, 2.0]$.
- **Stage 4 (Combined Extreme Stressors):** Gravity $\in [-13.0, -7.0]$, wind probability $0.9$, wind power $\in [5.0, 25.0]$, turbulence $\in [0.5, 2.5]$, horizontal impulse kicks $\in [-150.0, 150.0]$ N$\cdot$s.

---

## 5. Domain Randomization Implementation

The domain randomization wrapper (`DomainRandomizationWrapper`) modulates Box2D physics on every episode reset:
- **Gravity:** Applied via `world.gravity = (0.0, sampled_g)`.
- **Aerodynamic Wind:** Modulated via `env.unwrapped.wind_power` and `env.unwrapped.turbulence_power`.
- **Initial Velocity Perturbations:** Modulated via Box2D linear impulses applied to the lander chassis at reset:
  `unwrapped.lander.ApplyLinearImpulse((impulse_x, 0.0), unwrapped.lander.worldCenter, True)`
  with linear velocity observations updated accordingly.

---

## 6. Decoupled Physical Landing Validation

Gymnasium's default termination awards $+100$ when the lander body comes to rest, even if resting on one leg or tilted severely. This research decouples physical landing validation from simulator rewards:

```python
@dataclass
class LandingCriteria:
    max_pad_offset_x: float = 0.25      # Lander center within helipad flags (|x| <= 0.25)
    max_touchdown_vx: float = 0.40      # Lateral drift limit (m/s scale)
    max_touchdown_vy: float = 0.40      # Vertical descent velocity limit (m/s scale)
    max_touchdown_tilt: float = 0.20    # Pitch angle limit (~11.5 degrees)
    max_touchdown_spin: float = 0.35    # Angular roll rate limit (rad/s)
    require_both_legs: bool = True      # Left AND right foot contact sensors engaged on pad
```

### Outcome Taxonomy
1. **`success`**: Both foot sensors contact pad, $|x| \le 0.25$, linear/angular velocities within limits, no $-100$ crash penalty.
2. **`crash`**: Exceeded velocity/attitude thresholds, single-leg landing gear failure, or chassis terrain impact.
3. **`out_of_bounds`**: Lateral displacement $|x| \ge 1.0$.
4. **`timeout`**: Truncated at $1,000$ steps without grounding.

---

## 7. Statistical Methodology

### A. Independent Units
Each training seed ($N = 3$: `[42, 123, 999]`) represents an independent training replicate. Evaluation episodes are **never** treated as independent statistical units to prevent pseudo-replication.

### B. Matched-Seed Paired $t$-Tests
Because all four paradigms were trained on the identical seed set, paired differences $d_i = y_{B,i} - y_{A,i}$ for seed $i \in \{42, 123, 999\}$ account for seed-level variance:
$$t = \frac{\bar{d}}{s_d / \sqrt{N}}, \quad \text{where } s_d = \sqrt{\frac{1}{N-1}\sum_{i=1}^N (d_i - \bar{d})^2}$$

### C. Effect Size (Cohen's $d_z$)
For matched pairs:
$$d_z = \frac{\bar{d}}{s_d}$$

### D. Family-Wise Error Rate Control (Holm-Bonferroni)
Across the complete family of $m = 6$ pairwise comparisons per primary metric:
1. Sort raw $p$-values: $p_{(1)} \le p_{(2)} \le \dots \le p_{(m)}$.
2. Holm comparison thresholds: $\alpha_{(k)} = \frac{0.05}{m - k + 1}$.
3. Step-down adjusted $p$-values:
   $$p_{\text{adj},(k)} = \min\left(1.0, \, \max_{j \le k}\left((m - j + 1) \cdot p_{(j)}\right)\right)$$
