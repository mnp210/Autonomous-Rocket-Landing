# Technical Limitations & Future Research Scope

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.6  
**License:** Apache License 2.0  

---

## 1. Simulation & Physical Modeling Limitations

This application is an algorithmic research study in deep reinforcement learning, not a certified aerospace engineering flight simulator.

| Characteristic | Implemented Modeling Reality | Real-World Rocket Dynamics |
| :--- | :--- | :--- |
| **Coordinate Space** | **2D Planar Simulation** ($x, y, \theta$); 3D view is visual presentation only. | Full 6-DOF (Degrees of Freedom: pitch, yaw, roll, surge, sway, heave). |
| **Propulsion Actuation** | **Discrete Actions** (0: Coast, 1: Left RCS, 2: Main Thruster, 3: Right RCS). | Continuous throttle percentage ($40\%–100\%$) and continuous gimbal angle ($\pm 5^\circ$). |
| **Aerodynamics** | Simplified drag forces and rotational turbulence. | Compressible supersonic flow, shockwave interaction, plume-induced separation, aerothermal heating. |
| **Mass & Inertia** | Constant vehicle mass and rigid-body inertia. | High mass depletion ($>80\%$ propellant consumed), shifting center-of-gravity, propellant slosh. |
| **Ground Dynamics** | Spring-damper footpads with friction latch. | Ground effect backpressure, regolith ejection, landing leg crush core deformation. |

---

## 2. Experimental & Statistical Limitations

1. **Replicate Sample Size ($N = 3$ Seeds):**
   - The production study evaluated 3 matched random seeds (`42`, `123`, `999`).
   - While 9,600 evaluation episodes were executed, seed-level hypothesis tests have only **$df = 2$ degrees of freedom**.
   - Under conservative Holm-Bonferroni multiplicity correction, differences between Paradigm D and Standard PPO do not achieve $p < 0.05$. Results must be interpreted as **exploratory empirical evidence** rather than definitive mathematical proof.
2. **Out-of-Distribution (OOD) Generalization Boundary:**
   - Under hurricane crosswinds ($30\text{ m/s}$) and combined microgravity shears, landing success rates for all trained policies drop to $0\%–4.7\%$.
   - Pure domain randomization without curriculum collapses early ($0.3\%$ nominal success), while curriculum training without disturbance exposure overfits ($1.7\%$ OOD success).

---

## 3. High-Priority Future Research Directions

1. **Continuous Action Spaces:**
   - Transition to continuous Deep Deterministic Policy Gradient (DDPG) or Soft Actor-Critic (SAC) to control continuous engine throttling and vectoring gimbal angles.
2. **Fuel-Optimal Trajectory Guidance:**
   - Incorporate propellant mass depletion and convex optimization baselines (G-FOLD) for hybrid RL-optimal guidance comparison.
3. **6-DOF Simulation Engine:**
   - Upgrade the physics backend to a 3D rigid-body engine (e.g. MuJoCo or Isaac Gym) to investigate roll-yaw coupling and true 3D spatial drift.
4. **Expanded Seed Study ($N \ge 10$):**
   - Conduct higher-volume compute runs to establish statistical significance under Holm-Bonferroni corrections.
