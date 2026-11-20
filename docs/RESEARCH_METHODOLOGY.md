# Research Methodology & Experimental Design

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.6  
**License:** Apache License 2.0  

---

## 1. Problem Formulation & Research Questions

Autonomous pinpoint rocket landing requires solving a non-linear, underactuated optimal control problem under severe atmospheric disturbances. Reinforcement learning policies often overfit to nominal conditions, failing catastrophically when exposed to unmodeled crosswinds or gravity anomalies.

This research investigates three core questions:
1. **Curriculum Hypothesis:** Does developmental task scaffolding prevent early policy exploration collapse?
2. **Domain Randomization Boundary:** Can an agent trained under stochastic disturbance distributions maintain nominal precision while rejecting high-velocity aerodynamic shears?
3. **Decoupled Verification:** How do policies perform when evaluated against strict kinematic landing criteria rather than cumulative simulator reward bonuses?

---

## 2. Experimental Paradigms

Four distinct training regimes were evaluated across 3 matched random seeds (`42`, `123`, `999`), totaling **12 independent training runs** and **6,000,000 timesteps**:

| Paradigm | Identifier | Training Physics | Disturbance Sampling | Progression Logic |
| :--- | :--- | :--- | :---: | :--- |
| **A** | `A_standard` | Fixed nominal physics ($g = -10.0\text{ m/s}^2$, zero wind) | Deterministic | Fixed throughout (Control) |
| **B** | `B_dr_only` | Full domain randomization from step zero | Active | Uncurriculated |
| **C** | `C_curriculum_only` | Progressive 4-stage task ladder in nominal physics | None | Rolling success rate $\ge 70\%$ |
| **D** | `D_curriculum_and_dr` | Progressive 4-stage task ladder with expanding DR bounds | Active | Rolling success rate $\ge 70\%$ |

All models share identical PPO hyperparameters:
- Network Architecture: MLP ($[64, 64]$ hidden units, Tanh activations)
- Learning Rate: $3 \times 10^{-4}$
- Rollout Horizon ($n_{\text{steps}}$): $2,048$
- Batch Size: $64$
- Discount Factor ($\gamma$): $0.99$
- GAE Parameter ($\lambda$): $0.95$
- Clipping Range ($\epsilon$): $0.20$
- Total Steps per Run: $500,000$

---

## 3. Curriculum Learning & Domain Randomization Schedules

### Curriculum Ladder (Paradigms C & D):
- **Stage 1 (Hover & Vertical Descent):** Initial altitude $y \in [1.0, 1.2]$, horizontal displacement $|x| \le 0.1$, zero initial tilt.
- **Stage 2 (Lateral Offset & Translation):** Initial displacement $|x| \in [0.2, 0.5]$, initial horizontal velocity $|v_x| \le 0.2$.
- **Stage 3 (Attitude Recovery):** Initial pitch tilt $\theta \in [-0.2, 0.2]\text{ rad}$ ($\pm 11.5^\circ$), initial angular rate $|\dot{\theta}| \le 0.3\text{ rad/s}$.
- **Stage 4 (Full Envelope Flight):** High altitude $y \in [1.2, 1.5]$, arbitrary initial tilt and lateral velocity.

### Domain Randomization Bounds (Paradigm D):
- **Gravity Acceleration:** $g \in [-13.0, -7.0]\text{ m/s}^2$
- **Persistent Crosswind:** $w_{\text{force}} \in [-20.0, 20.0]\text{ units}$
- **Rotational Turbulence:** $\tau_{\text{turb}} \in [-2.0, 2.0]\text{ units}$
- **Booster Mass Variation:** $m_{\text{scale}} \in [0.85, 1.15]$

---

## 4. Aeronautical Landing Criteria

Rather than relying on the simulator's $+100$ body-rest bonus, touchdowns are evaluated against strict kinematic boundaries:

```python
@dataclass
class LandingCriteria:
    max_pad_offset_x: float = 0.25      # Lander center within helipad flags (|x| <= 0.25)
    max_touchdown_vx: float = 0.40      # Lateral drift limit (units/s)
    max_touchdown_vy: float = 0.40      # Vertical descent speed limit (units/s)
    max_touchdown_tilt: float = 0.20    # Pitch angle limit (~11.5 degrees)
    max_touchdown_spin: float = 0.35    # Angular rate limit (rad/s)
    require_both_legs: bool = True      # Both foot sensors engaged on the pad
```

Touchdown outcomes are classified into:
1. **Successful Landing:** Both legs in contact on the pad surface within velocity and tilt boundaries, held stable for $\ge 0.3\text{ s}$.
2. **Hard Landing / Crash:** Kinetic limits exceeded, or body collision detected before stabilization.
3. **Rollover:** Lander touched down with excessive tilt ($> 11.5^\circ$), tipping onto its side.
4. **Timeout / Out-of-Bounds:** Episode reached 1,200 steps or drifted outside simulated airspace.

---

## 5. Statistical Rigor & Hypothesis Testing

1. **Independent Units of Analysis:**
   - The 3 matched random seeds (`42`, `123`, `999`) serve as independent experimental replicates. Individual evaluation episodes are not treated as independent units to prevent pseudo-replication.
2. **Paired Comparisons:**
   - Matched-seed Student's paired $t$-tests ($df = 2$) compare paradigm differences.
3. **Multiplicity Correction:**
   - The family of $m = 6$ pairwise comparisons is controlled using the **Holm-Bonferroni step-down procedure** at overall family-wise error rate $\alpha = 0.05$.
4. **Binomial Confidence Intervals:**
   - Success proportions are reported with 95% **Wilson score intervals** to ensure coverage accuracy near extreme boundaries without Gaussian approximation artifacts.
