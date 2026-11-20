import React, { useEffect, useRef, useCallback } from 'react';
import type { TelemetryPoint } from '../../../services/telemetryStore';

export interface AttitudeChartProps {
  points: TelemetryPoint[];
  className?: string;
}

export const AttitudeChart: React.FC<AttitudeChartProps> = ({ points, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    const margin = { top: 20, right: 35, bottom: 35, left: 50 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;

    ctx.fillStyle = '#080B10';
    ctx.fillRect(0, 0, width, height);

    // Domain: X = Time in [0.0, 10.0]s; Y = Pitch in [-25°, +25°]
    let minT = 0.0;
    let maxT = 10.0;
    let minPitch = -25.0;
    let maxPitch = 25.0;

    if (points.length > 0) {
      for (const p of points) {
        if (p.time > maxT) maxT = Math.ceil(p.time * 2) / 2 + 1.0;
        if (p.angleDeg < minPitch) minPitch = Math.floor(p.angleDeg / 10) * 10 - 5;
        if (p.angleDeg > maxPitch) maxPitch = Math.ceil(p.angleDeg / 10) * 10 + 5;
      }
    }

    const scaleX = (t: number) => margin.left + ((t - minT) / (maxT - minT)) * plotW;
    const scaleY = (deg: number) => margin.top + plotH - ((deg - minPitch) / (maxPitch - minPitch)) * plotH;

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

    // Horizontal grid (Pitch Degrees)
    const pStep = (maxPitch - minPitch) > 60 ? 20 : 10;
    ctx.textAlign = 'right';
    for (let deg = Math.ceil(minPitch / pStep) * pStep; deg <= maxPitch; deg += pStep) {
      const py = scaleY(deg);
      ctx.beginPath();
      ctx.moveTo(margin.left, py);
      ctx.lineTo(margin.left + plotW, py);
      ctx.stroke();

      ctx.fillText(`${deg > 0 ? '+' : ''}${deg.toFixed(0)}°`, margin.left - 6, py + 3);
    }
    ctx.setLineDash([]);

    // Zero Pitch Baseline (Upright Flight)
    const zeroY = scaleY(0.0);
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, zeroY);
    ctx.lineTo(margin.left + plotW, zeroY);
    ctx.stroke();

    // Strict Landing Limit Thresholds: ±0.20 rad (±11.46°)
    const posLimitY = scaleY(11.46);
    const negLimitY = scaleY(-11.46);

    ctx.strokeStyle = 'rgba(255, 179, 0, 0.7)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);

    ctx.beginPath();
    ctx.moveTo(margin.left, posLimitY);
    ctx.lineTo(margin.left + plotW, posLimitY);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(margin.left, negLimitY);
    ctx.lineTo(margin.left + plotW, negLimitY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Limit label
    ctx.fillStyle = '#FFB300';
    ctx.font = '9px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('CRITERIA LIMIT: +11.5° (0.20 rad)', margin.left + 8, posLimitY - 4);
    ctx.fillText('CRITERIA LIMIT: -11.5° (-0.20 rad)', margin.left + 8, negLimitY + 11);

    // Axis labels
    ctx.fillStyle = '#94A3B8';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.fillText('SIMULATION TIME t (Seconds, 50 Hz)', margin.left + plotW / 2, height - 2);

    ctx.save();
    ctx.translate(12, margin.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('PITCH ANGLE θ (Degrees / Radians)', 0, 0);
    ctx.restore();

    // Plot Attitude Angle Trace
    if (points.length >= 2) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#00F0FF';
      ctx.beginPath();

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        const px = scaleX(pt.time);
        const py = scaleY(pt.angleDeg);

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
      const cy = scaleY(curPt.angleDeg);

      ctx.fillStyle = Math.abs(curPt.angleDeg) <= 11.46 ? '#00E676' : '#FF1744';
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [points]);

  useEffect(() => {
    drawChart();
  }, [drawChart]);

  const latestPitchDeg = points.length > 0 ? points[points.length - 1].angleDeg : 0.0;
  const latestPitchRad = points.length > 0 ? points[points.length - 1].angle : 0.0;
  const isUpright = Math.abs(latestPitchDeg) <= 11.46;

  return (
    <div className={`relative w-full h-full flex flex-col font-mono ${className}`}>
      <div className="flex items-center justify-between px-2 py-1 bg-[#101622] border-b border-slate-800 text-[10px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="text-cyan-400 font-bold uppercase">ATTITUDE STABILIZATION θ(t)</span>
          <span className="text-slate-600">|</span>
          <span>SAMPLES: {points.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={isUpright ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
            PITCH: {latestPitchDeg >= 0 ? `+${latestPitchDeg.toFixed(1)}°` : `${latestPitchDeg.toFixed(1)}°`} ({latestPitchRad >= 0 ? `+${latestPitchRad.toFixed(3)}` : latestPitchRad.toFixed(3)} rad)
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
