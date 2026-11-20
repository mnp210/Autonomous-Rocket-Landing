import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

import {
  PARADIGM_BENCHMARKS,
  EVALUATION_CONDITIONS,
  PAIRWISE_HYPOTHESIS_TESTS,
  computeWilsonScoreInterval,
} from '../data/benchmarkData';
import { OutcomeDistributionChart } from '../components/dashboard/analytics/OutcomeDistributionChart';
import { FailureAnalysisPanel } from '../components/dashboard/analytics/FailureAnalysisPanel';
import { EnvironmentalRobustnessView } from '../components/dashboard/analytics/EnvironmentalRobustnessView';
import { ProvenanceViewer } from '../components/dashboard/analytics/ProvenanceViewer';

describe('Stage 9.4.3 AI Performance Analytics & Experiment Comparison', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  describe('Benchmark Data Integrity & Mathematical Foundations', () => {
    it('contains all 4 paradigms with 3 seeds each (N=3, df=2)', () => {
      const paradigms = Object.keys(PARADIGM_BENCHMARKS);
      expect(paradigms).toEqual(['A_standard', 'B_dr_only', 'C_curriculum_only', 'D_curriculum_and_dr']);

      paradigms.forEach((pKey) => {
        const p = PARADIGM_BENCHMARKS[pKey as keyof typeof PARADIGM_BENCHMARKS];
        expect(p.seeds).toHaveLength(3);
        expect(p.seeds).toEqual([42, 123, 999]);
        expect(p.total_eval_episodes).toBe(2400);
      });
    });

    it('satisfies strict outcome conservation (S + C + T + O = Total) across all scopes', () => {
      const paradigms = Object.values(PARADIGM_BENCHMARKS);

      paradigms.forEach((p) => {
        // Nominal (N=300)
        const nom = p.nominal_outcomes;
        expect(nom.total).toBe(300);
        expect(nom.success + nom.crash + nom.timeout + nom.out_of_bounds).toBe(300);

        // In-Distribution (N=1800)
        const id = p.id_outcomes;
        expect(id.total).toBe(1800);
        expect(id.success + id.crash + id.timeout + id.out_of_bounds).toBe(1800);

        // Out-of-Distribution (N=600)
        const ood = p.ood_outcomes;
        expect(ood.total).toBe(600);
        expect(ood.success + ood.crash + ood.timeout + ood.out_of_bounds).toBe(600);

        // Overall (N=2400)
        const all = p.overall_outcomes;
        expect(all.total).toBe(2400);
        expect(all.success + all.crash + all.timeout + all.out_of_bounds).toBe(2400);
      });
    });

    it('computes valid Wilson score confidence intervals', () => {
      const ciNormal = computeWilsonScoreInterval(186, 300, 0.95);
      expect(ciNormal.point).toBeCloseTo(62.0, 1);
      expect(ciNormal.lower).toBeGreaterThan(50.0);
      expect(ciNormal.upper).toBeLessThan(70.0);
      expect(ciNormal.lower).toBeLessThan(ciNormal.point);
      expect(ciNormal.point).toBeLessThan(ciNormal.upper);

      // Edge case: 0 successes
      const ciZero = computeWilsonScoreInterval(0, 100, 0.95);
      expect(ciZero.point).toBe(0);
      expect(ciZero.lower).toBe(0);
      expect(ciZero.upper).toBeGreaterThan(0);
      expect(ciZero.upper).toBeLessThan(5);

      // Edge case: 100% successes
      const ciFull = computeWilsonScoreInterval(100, 100, 0.95);
      expect(ciFull.point).toBe(100);
      expect(ciFull.lower).toBeGreaterThan(95);
      expect(ciFull.upper).toBe(100);
    });

    it('correctly flags Paradigm B sample size restriction (N=1 landing in nominal)', () => {
      const b = PARADIGM_BENCHMARKS.B_dr_only;
      expect(b.nominal_outcomes.success).toBe(1);
      expect(b.nominal_outcomes.timeout).toBe(292); // 97.3% perpetual hover
      expect(b.nominal_resting_sample_size).toBe(1);
      expect(b.nominal_resting_caveat).toBeDefined();
    });

    it('enforces Holm-Bonferroni correction and acknowledges df=2 non-significance', () => {
      const dVsA = PAIRWISE_HYPOTHESIS_TESTS.find(c => c.comparison === 'D_curriculum_and_dr_vs_A_standard');
      expect(dVsA).toBeDefined();
      expect(dVsA?.holm_adjusted_p_value).toBe(1.0);
      expect(dVsA?.significant).toBe(false);
      expect(dVsA?.verdict).toContain('df = 2');
    });
  });

  describe('OutcomeDistributionChart Component', () => {
    it('renders all four paradigms and switches evaluation scopes', () => {
      act(() => {
        root.render(<OutcomeDistributionChart />);
      });

      expect(container.textContent).toContain('EPISODE OUTCOME DISTRIBUTIONS');
      expect(container.textContent).toContain('A: Standard Baseline');
      expect(container.textContent).toContain('B: DR Only');
      expect(container.textContent).toContain('C: Curriculum Only');
      expect(container.textContent).toContain('D: Curriculum + DR');

      // Default view is nominal: Paradigm D has 186 successes (62.0%)
      expect(container.textContent).toContain('186');
      expect(container.textContent).toContain('62.0%');

      // Click In-Distribution scope filter button
      const buttons = container.querySelectorAll('button');
      const idButton = Array.from(buttons).find(b => b.textContent?.includes('IN-DIST'));
      expect(idButton).toBeDefined();

      act(() => {
        idButton?.click();
      });

      // Under In-Distribution (N=1800), Paradigm D has 698 successes (38.8%)
      expect(container.textContent).toContain('698');
      expect(container.textContent).toContain('38.8%');
    });
  });

  describe('FailureAnalysisPanel Component', () => {
    it('renders failure taxonomy categories and Paradigm B hover anomaly details', () => {
      act(() => {
        root.render(<FailureAnalysisPanel />);
      });

      expect(container.textContent).toContain('EMPIRICAL FAILURE TAXONOMY');
      expect(container.textContent).toContain('KINETIC COLLISION');
      expect(container.textContent).toContain('AERODYNAMIC ROLLOVER');
      expect(container.textContent).toContain('HORIZON CUTOFF / TIMEOUT');
      expect(container.textContent).toContain('LATERAL DISPLACEMENT');

      // Verify Paradigm B Case Study and Sample Size Warning
      expect(container.textContent).toContain('CASE STUDY: THE PARADIGM B \'PERPETUAL HOVER\' COLLAPSE');
      expect(container.textContent).toContain('292 / 300');
      expect(container.textContent).toContain('SAMPLE SIZE CAVEAT');
    });
  });

  describe('EnvironmentalRobustnessView Component', () => {
    it('renders 8 stress conditions with ID and OOD grouping and deltas', () => {
      act(() => {
        root.render(<EnvironmentalRobustnessView />);
      });

      expect(container.textContent).toContain('DISTRIBUTIONAL ROBUSTNESS EVALUATION');
      expect(container.textContent).toContain('IN-DIST');
      expect(container.textContent).toContain('OUT-OF-DIST');

      // Verify conditions
      EVALUATION_CONDITIONS.forEach(c => {
        expect(container.textContent).toContain(c.name);
      });

      // Verify Nominal anchor
      expect(container.textContent).toContain('Standard_Nominal');
      expect(container.textContent).toContain('62.0%');
      expect(container.textContent).toContain('59.3%');
      expect(container.textContent).toContain('54.7%');
      expect(container.textContent).toContain('0.3%');
    });
  });

  describe('ProvenanceViewer Component', () => {
    it('renders artifact provenance, live session separation, and hypothesis testing table', () => {
      act(() => {
        root.render(<ProvenanceViewer />);
      });

      // Provenance summary
      expect(container.textContent).toContain('EXPERIMENT PROVENANCE & BENCHMARK AUDIT TRAIL');
      expect(container.textContent).toContain('12 Production Runs');
      expect(container.textContent).toContain('6,000,000');
      expect(container.textContent).toContain('9,600 Verified Episodes');

      // Live Session vs Historical Separation
      expect(container.textContent).toContain('HISTORICAL BENCHMARK DATASET');
      expect(container.textContent).toContain('ACTIVE BROWSER SESSION EPISODES');

      // Hypothesis testing with Holm-Bonferroni
      expect(container.textContent).toContain('PAIRWISE HYPOTHESIS TESTING (HOLM-BONFERRONI FAMILY CONTROL)');
      expect(container.textContent).toContain('df = 2');
      expect(container.textContent).toContain('NO (p_adj > 0.05)');
      expect(container.textContent).toContain('SCIENTIFIC INTERPRETATION DIRECTIVE');
    });
  });
});
