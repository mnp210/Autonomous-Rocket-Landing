# Stage 9.4.3 — AI Performance Analytics & Experiment Comparison: Analytics Specification

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.4.3  
**Document:** Metric Definitions, Statistical Methodology & Visualization Design  
**Status:** **AUTHORITATIVE & VERIFIED**  
**Author:** Engineering & Research Team  

---

## 1. Mathematical Definitions & Denominators

To prevent ambiguous or misleading claims, all analytical metrics are calculated using strict, mathematically defined denominators:

### 1.1 Outcome Rates (Denominator: All Completed Episodes $N_{\text{total}}$)
Every episode in evaluation or live flight terminates in exactly one physical outcome:
$$\text{Outcome} \in \{\text{SUCCESS}, \text{CRASH}, \text{TIMEOUT}, \text{OUT\_OF\_BOUNDS}\}$$

- **Success Rate ($S$):**
  $$S = \frac{N_{\text{success}}}{N_{\text{total}}} \times 100\%$$
- **Crash Rate ($C$):**
  $$C = \frac{N_{\text{crash}}}{N_{\text{total}}} \times 100\%$$
- **Timeout Rate ($T$):**
  $$T = \frac{N_{\text{timeout}}}{N_{\text{total}}} \times 100\%$$
- **Out-of-Bounds Rate ($O$):**
  $$O = \frac{N_{\text{out\_of\_bounds}}}{N_{\text{total}}} \times 100\%$$
- **Conservation of Total:** $S + C + T + O = 100.0\%$. Incomplete or in-progress episodes are excluded from the denominator.

### 1.2 Landing Quality Metrics (Denominator: Successful Landings Only $N_{\text{success}}$)
Calculated exclusively over flights that satisfied all strict physical landing criteria:
- **Mean Touchdown Offset ($|\bar{x}|$):**
  $$\bar{\epsilon}_x = \frac{1}{N_{\text{success}}} \sum_{i=1}^{N_{\text{success}}} |x_i| \quad (\text{Box2D units, target: } \le 0.25\text{ u})$$
- **Mean Resting Tilt ($|\bar{\theta}|$):**
  $$\bar{\theta}_{\text{rest}} = \frac{1}{N_{\text{success}}} \sum_{i=1}^{N_{\text{success}}} |\theta_i| \quad (\text{rad and deg, target: } \le 0.20\text{ rad})$$

### 1.3 Terminal Impact Kinematics (Denominator: All Episodes $N_{\text{total}}$)
Calculated over all attempts to quantify residual kinetic energy at termination:
- **Terminal Descent Velocity ($|\bar{v}_y|$):**
  $$\bar{v}_y = \frac{1}{N_{\text{total}}} \sum_{i=1}^{N_{\text{total}}} |v_{y, i}| \quad (\text{Box2D u/s})$$
- **Terminal Lateral Velocity ($|\bar{v}_x|$):**
  $$\bar{v}_x = \frac{1}{N_{\text{total}}} \sum_{i=1}^{N_{\text{total}}} |v_{x, i}| \quad (\text{Box2D u/s})$$

---

## 2. Statistical Methodology

### 2.1 Paired Student's $t$-Tests on Matched Seeds
Because training runs share matched random seeds (`42`, `123`, `999`), comparisons between paradigms are evaluated via Paired Two-Tailed Student's $t$-tests ($df = 2$):

$$t = \frac{\bar{d}}{s_d / \sqrt{N}}, \quad \text{where } d_i = X_{A, i} - X_{B, i}, \quad N = 3$$

### 2.2 Standardized Effect Sizes (Cohen's $d_z$)
To quantify the magnitude of experimental difference independent of small sample size:
$$d_z = \frac{\bar{d}}{s_d}$$
- Small: $|d_z| \ge 0.20$
- Medium: $|d_z| \ge 0.50$
- Large: $|d_z| \ge 0.80$ (Paradigm D vs A on nominal success: $d_z \approx 0.58$)

### 2.3 Holm-Bonferroni Family-Wise Error Rate Control
For a family of $m = 6$ pairwise comparisons, raw $p$-values are sorted ascendingly: $p_{(1)} \le p_{(2)} \le \dots \le p_{(m)}$. Each $p_{(k)}$ is tested against adjusted threshold $\alpha_k = \frac{\alpha}{m - k + 1}$:

| Rank ($k$) | Comparison | Multiplier ($m - k + 1$) | Threshold ($\alpha_k$) | Raw $p$ | Holm $p_{\text{adj}}$ | Significant at $\alpha = 0.05$? |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| 1 | B vs A [Reward] | 6 | $0.00833$ | $0.0145$ | **$0.0867$** | **No** ($p_{\text{adj}} > 0.05$) |
| 2 | B vs A [Success] | 5 | $0.01000$ | $0.0173$ | **$0.1038$** | **No** |
| 3 | C vs B [Success] | 4 | $0.01250$ | $0.0392$ | **$0.1960$** | **No** |
| 4 | D vs B [Success] | 3 | $0.01667$ | $0.0748$ | **$0.2992$** | **No** |
| 5 | D vs A [Success] | 2 | $0.02500$ | $0.4226$ | **$1.0000$** | **No** |
| 6 | D vs C [Success] | 1 | $0.05000$ | $0.4226$ | **$1.0000$** | **No** |

---

## 3. Visual Analytics & Component Specifications

The Stage 9.4.3 analytics interface organizes into five focused visual panels:

### 3.1 Outcome Distribution View (`OutcomeDistributionChart.tsx`)
Stacked/grouped horizontal percentage bars displaying:
- Green: Landing Success ($S$)
- Red: Structural Ground Crash ($C$)
- Yellow: Operational Timeout ($T$)
- Slate: Out of Bounds Disconnect ($O$)
- Explicit sample size labels ($N = 300$, $N = 1800$, or $N = 2400$).

### 3.2 Failure Mode Breakdown (`FailureAnalysisPanel.tsx`)
Detailed taxonomy of failure mechanisms:
1. **Severe Kinetic Impact ($v_y > 2.0\text{ u/s}$):** Structural body collision from inadequate deceleration burn.
2. **Attitude Loss / Rollover ($|\theta| > 0.20\text{ rad}$):** Unrecoverable aerodynamic tumble or single-leg trip.
3. **Lateral Helipad Miss ($|x| > 0.25\text{ u}$):** Lander missed target flags or drifted off pad.
4. **Energy Exhaustion / Timeout ($t \ge 1000\text{ steps}$):** Inability to converge before cutoff.

### 3.3 Four-Paradigm Comparative Workstation (`ParadigmComparisonView.tsx`)
Multi-paradigm comparative analysis table with:
- Nominal success rate vs In-Distribution mean.
- 95% Confidence Intervals with explicit $df = 2$ warnings.
- Resting tilt with the $N=1$ caveat prominently flagged for Paradigm B.
- Engine duty cycles (main throttle vs RCS side thrusters).

### 3.4 In-Distribution vs Out-of-Distribution Robustness (`EnvironmentalRobustnessView.tsx`)
Comparison across all 8 environmental test conditions:
- Radar / comparative bar breakdown across Nominal, Low G, Heavy G, Moderate Wind, Strong Wind, High Turbulence, OOD Extreme Combined, and OOD Microgravity Shear.
- Highlights zero-shot crosswind degradation in Paradigm A vs curriculum stabilization in Paradigm D.

### 3.5 Provenance & Live Session Cross-Check (`ProvenanceViewer.tsx`)
Side-by-side reconciliation between:
- **Historical Benchmark Baseline:** Verified $9,600$-episode dataset.
- **Current Session Live Episodes:** Ephemeral live-flight records accumulated during the active session.
