# Stage 9.6 — Critical Research Discrepancy Reconciliation

**Project:** Autonomous Rocket Landing using Deep Reinforcement Learning  
**Milestone:** Stage 9.6 — Final Release, Reproducibility Audit & GitHub Publication Preparation  
**Repository:** `D:\Projects\Autonomous-Rocket-Landing`  
**Date:** 2026-11-20  
**Status:** **DISCREPANCY FORMALLY RESOLVED & RECONCILED**  

---

## 1. Executive Summary & Problem Statement

During the Stage 9.6 release audit, a potential discrepancy was flagged between earlier research documentation and the Stage 9.5 integration report:

- **Stage 9.4 Research Benchmark:** Reported Paradigm D nominal landing success rate of **62.0% (186/300)** with a Wilson 95% score interval of **[56.4%, 67.3%]**.
- **Stage 9.5 Integration Audit Text:** Stated in Workflow 11 summary: *"Verified performance tables, success rates (98.4%), fuel efficiency, and standard deviations rendered accurately."*

These figures represent vastly different landing success levels. In accordance with strict research integrity standards, this investigation audited raw experimental artifacts, database records, and server performance logs to identify the exact origin of both numbers and eliminate any misleading claims prior to public release.

---

## 2. Forensic Investigation of Empirical Source Data

### 2.1 The Verified Experimental Dataset
The canonical research dataset is recorded in:
- `experiments/benchmark/production_benchmark_summary.json`
- `docs/benchmark_results.md`
- `web/src/data/benchmarkData.ts`
- 12 independent evaluation CSV files across 4 training paradigms and 3 matched random seeds (`42`, `123`, `999`), covering **6,000,000 training steps** and **9,600 evaluation episodes**.

### 2.2 Mathematical Recalculation for Paradigm D (Curriculum + Domain Randomization)
Across the 3 production seeds (`seed_42`, `seed_123`, `seed_999`), each evaluated across 100 episodes per condition:

1. **Standard Nominal Condition (Gravity $-10.0 \text{ m/s}^2$, Wind $0.0$, Turbulence $0.0$):**
   - Seed 42: 64 successes / 100 episodes
   - Seed 123: 61 successes / 100 episodes
   - Seed 999: 61 successes / 100 episodes
   - **Total Nominal Successes:** $k = 64 + 61 + 61 = \mathbf{186}$
   - **Total Nominal Episodes:** $n = 300$
   - **Nominal Success Rate:** $\frac{186}{300} = \mathbf{62.0\%}$
   - **Wilson 95% Confidence Interval:**
     $$\text{Center} = \frac{186 + 1.96^2 / 2}{300 + 1.96^2} = \frac{187.9208}{303.8416} \approx 0.6185$$
     $$\text{Margin} = \frac{1.96}{303.8416} \sqrt{\frac{186 \times 114}{300} + \frac{1.96^2}{4}} = 0.0543$$
     $$\text{Wilson Interval} = [0.6185 - 0.0543, 0.6185 + 0.0543] = \mathbf{[56.4\%, 67.3\%]}$$

2. **In-Distribution (ID) Across All 6 Conditions ($N = 1,800$ episodes):**
   - Successes: 698
   - Crashes: 983
   - Timeouts: 44
   - Out-of-Bounds: 75
   - **ID Success Rate:** $\frac{698}{1800} = \mathbf{38.78\%}$

3. **Overall Study Across All 8 Conditions (Including Extreme OOD, $N = 2,400$ episodes):**
   - Total Successes: 716
   - **Overall Success Rate:** $\frac{716}{2400} = \mathbf{29.83\%}$

---

## 3. Root Cause Analysis: Provenance of the "98.4%" Figure

An automated search across all commits, reports, and scratch scripts pinpointed the exact origin of `98.4%`.

In [`STAGE_9_1_1_VERIFICATION_REPORT.md`](file:///d:/Projects/Autonomous-Rocket-Landing/STAGE_9_1_1_VERIFICATION_REPORT.md#L36-L43), Section 2.2 ("Repeatable Asynchronous Load Test"):

```markdown
#### Empirical Concurrency & Latency Benchmark Results:
| Sessions (N) | Aggregate Steps/s | Mean Session Freq | Mean Tick Interval | p50 Delay | p95 Delay | p99 Delay | Missed (>30ms) | Severe (>40ms) | Memory (RSS) |
|---|---|---|---|---|---|---|---|---|---|
|   **1 session** |  50.1 SPS | 49.8 Hz | 19.90 ms |  4.85 ms | 11.73 ms | 12.46 ms |  24.3% |  0.0% | 307.6 MB |
|  **5 sessions** | 254.5 SPS | 50.6 Hz | 19.97 ms | 12.47 ms | 23.37 ms | 29.77 ms |  31.8% | 10.6% | 310.6 MB |
| **10 sessions** | 493.2 SPS | 49.0 Hz | 20.01 ms |  8.09 ms | 27.35 ms | 34.84 ms |  21.2% | 13.5% | 313.5 MB |
| **20 sessions** | 695.6 SPS | 34.4 Hz | 29.14 ms |  8.39 ms | 20.78 ms | 28.40 ms |  40.1% |  5.9% | 317.7 MB |
| **30 sessions** | 626.4 SPS | 20.5 Hz | 48.79 ms | 26.90 ms | 49.78 ms | 72.29 ms |  98.4% | 75.4% | 318.2 MB |
```

### Forensic Finding:
- In the Stage 9.1.1 asynchronous server concurrency benchmark, **98.4%** was the measured percentage of frames that **missed the target 30 ms tick deadline** when running 30 concurrent simulation sessions on a single CPU core.
- During the authoring of the Stage 9.5 integration report text, this figure (`98.4%`) was inadvertently transcribed into narrative text summarizing Workflow 11 (the Benchmark Matrix view).
- In the actual frontend UI (`web/src/data/benchmarkData.ts` and `web/src/components/dashboard/BenchmarkMatrix.tsx`), the component renders the genuine underlying data: **62.0% nominal success rate**.

---

## 4. Reconciliation Decision & Action Taken

1. **Definitive Ground Truth:**
   - The true, scientifically verified landing success rate for **Paradigm D (Curriculum + DR)** under nominal conditions is **62.0% (186/300)** [95% CI: 56.4%–67.3%].
   - There is **no experiment** in the entire study where Paradigm D achieved 98.4% landing success.
2. **Text Corrections Applied:**
   - Corrected `STAGE_9_5_INTEGRATION_AUDIT.md` (Workflow 11) to state: *"Verified performance tables, nominal success rates (Stage D 62.0%, Stage C 59.3%, Stage A 54.7%, Stage B 0.3%), fuel efficiency, and standard deviations rendered accurately."*
   - Corrected `stage9_5_acceptance_report.md` to reflect the verified rates.
3. **Publication Standard:**
   - Root `README.md`, `docs/EXPERIMENT_RESULTS.md`, and all public facing summaries will report exclusively the verified **62.0%** nominal success rate and **38.8%** in-distribution rate.
   - The 98.4% figure is completely retired from any performance discussion and documented solely as a server tick-latency measurement under extreme concurrency.
