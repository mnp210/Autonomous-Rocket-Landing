import React, { useEffect, useRef, useCallback } from 'react';
import type { TelemetryPoint } from '../../../services/telemetryStore';

export interface RewardChartProps {
  points: TelemetryPoint[];
  className?: string;
}

export const RewardChart: React.FC<RewardChartProps> = ({ points, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    const margin = { top: 20, right: 25, bottom: 35, left: 50 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;

    ctx.fillStyle = '#080B10';
    ctx.fillRect(0, 0, width, height);

    // Domain: X = Time in [0.0, 10.0]s; Y = Cumulative Reward in [-100, 280]
    let minT = 0.0;
    let maxT = 10.0;
    let minR = -50.0;
    let maxR = 250.0;

    if (points.length > 0) {
      for (const p of points) {
        if (p.time > maxT) maxT = Math.ceil(p.time * 2) / 2 + 1.0;
        if (p.cumReward < minR) minR = Math.floor(p.cumReward / 50) * 50 - 25;
        if (p.cumReward > maxR) maxR = Math.ceil(p.cumReward / 50) * 50 + 25;
      }
    }

    const scaleX = (t: number) => margin.left + ((t - minT) / (maxT - minT)) * plotW;
    const scaleY = (r: number) => margin.top + plotH - ((r - minR) / (maxR - minR)) * plotH;

    // Grid lines
    ctx.strokeStyle = '#1E293B';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillStyle = '#64748B';

    // Vertical grid (Time)
    const tStep = (maxT - minT) > 15 ? 5.0 : (maxT - minT) > 8 ? 2.0 : 1.0;
    ctx.textAlign = 'center';
    for (let t = minT; t <= maxT; t += tStep) {
      const px = scaleX(t);
      ctx.beginPath();
      ctx.moveTo(px, margin.top);
      ctx.lineTo(px, margin.top + plotH);
      ctx.stroke();

      ctx.fillText(`${t.toFixed(1)}s`, px, height - 12);
    }

    // Horizontal grid (Reward)
    const rStep = (maxR - minR) > 300 ? 100 : 50;
    ctx.textAlign = 'right';
    for (let r = Math.ceil(minR / rStep) * rStep; r <= maxR; r += rStep) {
      const py = scaleY(r);
      ctx.beginPath();
      ctx.moveTo(margin.left, py);
      ctx.lineTo(margin.left + plotW, py);
      ctx.stroke();

      ctx.fillText(r.toFixed(0), margin.left - 6, py + 3);
    }
    ctx.setLineDash([]);

    // Zero Reward Baseline
    const zeroY = scaleY(0.0);
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, zeroY);
    ctx.lineTo(margin.left + plotW, zeroY);
    ctx.stroke();

    // Axis labels
    ctx.fillStyle = '#94A3B8';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.fillText('SIMULATION TIME t (Seconds, 50 Hz)', margin.left + plotW / 2, height - 2);

    ctx.save();
    ctx.translate(12, margin.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('CUMULATIVE RETURN R(t)', 0, 0);
    ctx.restore();

    // Plot Step Reward Area/Bars (subtle)
    if (points.length >= 2) {
      ctx.fillStyle = 'rgba(56, 189, 248, 0.15)';
      ctx.beginPath();
      ctx.moveTo(scaleX(points[0].time), zeroY);

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        ctx.lineTo(scaleX(pt.time), scaleY(pt.cumReward));
      }
      ctx.lineTo(scaleX(points[points.length - 1].time), zeroY);
      ctx.closePath();
      ctx.fill();

      // Main Cumulative Reward Trace
      ctx.lineWidth = 2;
      const latestReward = points[points.length - 1].cumReward;
      ctx.strokeStyle = latestReward >= 200 ? '#00E676' : latestReward >= 0 ? '#38BDF8' : '#FF1744';
      ctx.beginPath();

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        const px = scaleX(pt.time);
        const py = scaleY(pt.cumReward);

        if (i === 0) {
          ctx.moveTo(px, py);
        } else {
          ctx.lineTo(px, py);
        }
      }
      ctx.stroke();

      // Current point
      const curPt = points[points.length - 1];
      const cx = scaleX(curPt.time);
      const cy = scaleY(curPt.cumReward);

      ctx.fillStyle = curPt.cumReward >= 200 ? '#00E676' : curPt.cumReward >= 0 ? '#38BDF8' : '#FF1744';
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [points]);

  useEffect(() => {
    drawChart();
  }, [drawChart]);

  const latestReturn = points.length > 0 ? points[points.length - 1].cumReward : 0.0;

  return (
    <div className={`relative w-full h-full flex flex-col font-mono ${className}`}>
      <div className="flex items-center justify-between px-2 py-1 bg-[#101622] border-b border-slate-800 text-[10px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="text-cyan-400 font-bold uppercase">REWARD PROGRESSION R(t)</span>
          <span className="text-slate-600">|</span>
          <span>SAMPLES: {points.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={latestReturn >= 200 ? 'text-emerald-400 font-bold' : latestReturn >= 0 ? 'text-cyan-300' : 'text-rose-400'}>
            CURRENT RETURN: {latestReturn >= 0 ? `+${latestReturn.toFixed(1)}` : latestReturn.toFixed(1)}
          </span>
        </div>
      </div>

      <div className="flex-1 w-full min-h-[180px] relative">
        <canvas
          ref={canvasRef}
          width={480}
          height={240}
          className="w-full h-full block bg-[#080B10]"
        />
      </div>
    </div>
  );
};
