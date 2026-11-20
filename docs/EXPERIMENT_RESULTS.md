# Empirical Experiment Results & Statistical Analysis

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.6  
**License:** Apache License 2.0  
**Data Scope:** 12 Production Runs (4 Paradigms $\times$ 3 Seeds: `42`, `123`, `999`), 6,000,000 Steps, 9,600 Evaluation Episodes  

---

## 1. Executive Performance Summary

All 12 production models were evaluated across the exact same 8 test environments (100 episodes per condition per model, totaling 800 episodes per model and 2,400 episodes per paradigm).

| Paradigm | Nominal Success Rate ($N=300$) | In-Distribution (ID) Mean Success ($N=1,800$) | Out-of-Distribution (OOD) Mean Success ($N=600$) | Overall Study Success ($N=2,400$) | Mean Resting Tilt (Landings Only) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **A_standard** (Control) | $54.7\%$ [49.0%, 60.2%] | $31.2\% \pm 18.3\%$ | $2.0\% \pm 1.2\%$ | $23.9\%$ | $0.75^\circ$ ($N=164$) |
| **B_dr_only** | $0.3\%$ [0.06%, 1.9%] | $1.2\% \pm 1.3\%$ | $0.0\% \pm 0.0\%$ | $0.9\%$ | $0.06^\circ$ ($N=1$) |
| **C_curriculum_only** | $59.3\%$ [53.7%, 64.7%] | $34.4\% \pm 30.5\%$ | $1.7\% \pm 0.8\%$ | $26.3\%$ | $0.87^\circ$ ($N=178$) |
| **D_curriculum_and_dr** | **$62.0\%$ [56.4%, 67.3%]** | **$38.8\% \pm 48.2\%$** | **$3.0\% \pm 1.4\%$** | **$29.8\%$** | **$0.58^\circ$ ($N=186$)** |

*Note: Bracketed ranges represent 95% Wilson score confidence intervals. Standard deviations represent inter-seed variation ($N=3$).*

---

## 2. In-Distribution (ID) vs. Out-of-Distribution (OOD) Breakdown

| Environmental Condition | Stress Category | Gravity ($g$) | Wind ($w$) | Turbulence | A_standard | B_dr_only | C_curriculum | D_curriculum_dr |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standard_Nominal** | In-Distribution | $-10.0$ | $0.0$ | $0.0$ | $54.7\%$ | $0.3\%$ | $59.3\%$ | **$62.0\%$** |
| **Low_Gravity** | In-Distribution | $-7.5$ | $0.0$ | $0.0$ | $50.3\%$ | $1.3\%$ | $53.0\%$ | **$57.3\%$** |
| **Heavy_Gravity** | In-Distribution | $-12.5$ | $0.0$ | $0.0$ | $45.0\%$ | $0.7\%$ | $41.3\%$ | **$47.7\%$** |
| **Moderate_Wind** | In-Distribution | $-10.0$ | $15.0$ | $1.0$ | $15.7\%$ | $2.0\%$ | $28.0\%$ | **$26.7\%$** |
| **Strong_Wind** | In-Distribution | $-10.0$ | $22.0$ | $1.5$ | $7.3\%$ | $1.7\%$ | $14.7\%$ | **$16.0\%$** |
| **High_Turbulence** | In-Distribution | $-10.0$ | $12.0$ | $2.5$ | $9.0\%$ | $1.3\%$ | $10.3\%$ | **$12.7\%$** |
| **OOD_Extreme_Combined**| Out-of-Distribution | $-15.0$ | $30.0$ | $3.5$ | $1.3\%$ | $0.0\%$ | $1.0\%$ | **$1.3\%$** |
| **OOD_Microgravity_Shear**| Out-of-Distribution | $-4.5$ | $28.0$ | $3.0$ | $2.7\%$ | $0.0\%$ | $2.3\%$ | **$4.7\%$** |

---

## 3. Terminal Impact Kinematics & Touchdown Attitude

### A. The Denominator Reality
In Box2D `LunarLander-v3`, once a lander achieves a successful landing on the helipad and the body comes to complete rest (`not self.lander.awake`), linear and angular velocities decay to zero ($v_x = 0, v_y = 0, \dot{\theta} = 0$).

Reported terminal velocities in benchmark tables represent **terminal impact kinematics averaged across all 300 nominal episodes** (including crashes, tip-overs, and timeouts):

| Paradigm | Total Nominal Episodes | Landings ($k$) | Crashes / Timeouts | Terminal $|v_x|$ (All Episodes) | Terminal $|v_y|$ (All Episodes) | Main Engine Duty | Side Thruster Duty |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A_standard** | 300 | 164 ($54.7\%$) | 136 ($45.3\%$) | $0.0139\text{ m/s}$ | $0.0072\text{ m/s}$ | $45.6\%$ | $32.2\%$ |
| **B_dr_only** | 300 | 1 ($0.3\%$) | 299 ($99.7\%$) | $0.0559\text{ m/s}$ | $0.0416\text{ m/s}$ | $57.0\%$ | $33.3\%$ |
| **C_curriculum_only** | 300 | 178 ($59.3\%$) | 122 ($40.7\%$) | $0.0094\text{ m/s}$ | $0.0060\text{ m/s}$ | $47.2\%$ | $33.9\%$ |
| **D_curriculum_and_dr** | 300 | 186 ($62.0\%$) | 114 ($38.0\%$) | **$0.0074\text{ m/s}$** | **$0.0050\text{ m/s}$** | $48.3\%$ | $32.3\%$ |

*Audit Note: Paradigm B achieved only a single landing ($N=1$). Comparative stability claims for Paradigm B cannot be supported due to sample size deficiency.*

---

## 4. Hypothesis Testing & Statistical Significance ($N = 3$ Seeds)

Family of $m = 6$ pairwise comparisons evaluated with matched-seed Student's paired $t$-tests ($df = 2$). Adjusted $p$-values computed via Holm-Bonferroni correction ($\alpha = 0.05$):

| Comparison Pair | Mean Difference | $t$-statistic | Raw $p$-value | Holm Multiplier | Adjusted $p$-value | Verdict ($\alpha = 0.05$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **D vs B** | $+37.56\%$ | $3.351$ | $0.0787$ | 6 | $0.4720$ | Not Significant |
| **C vs B** | $+33.22\%$ | $8.452$ | $0.0137$ | 5 | $0.0686$ | Not Significant |
| **A vs B** | $+30.00\%$ | $2.846$ | $0.1045$ | 4 | $0.4180$ | Not Significant |
| **D vs A** | $+7.56\%$ | $0.812$ | $0.5015$ | 3 | $1.0000$ | Not Significant |
| **D vs C** | $+4.34\%$ | $0.347$ | $0.7618$ | 2 | $1.0000$ | Not Significant |
| **C vs A** | $+3.22\%$ | $0.231$ | $0.8389$ | 1 | $1.0000$ | Not Significant |

### Methodological Interpretation:
Under rigorous Holm-Bonferroni correction, **no comparison achieves statistical significance at $\alpha = 0.05$**. This occurs because evaluating 3 random seeds yields only $df = 2$ degrees of freedom. While Paradigm D demonstrates strong empirical gains ($d_z \approx 0.58$ effect size over Standard PPO), these findings must be interpreted as **exploratory empirical evidence** rather than definitive mathematical proof.
