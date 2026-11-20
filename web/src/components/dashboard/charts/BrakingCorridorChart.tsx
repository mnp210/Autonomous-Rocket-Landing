import React, { useEffect, useRef, useCallback } from 'react';
import type { TelemetryPoint } from '../../../services/telemetryStore';

export interface BrakingCorridorChartProps {
  points: TelemetryPoint[];
  className?: string;
}

export const BrakingCorridorChart: React.FC<BrakingCorridorChartProps> = ({
  points,
  className = '',
}) => {
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

    // Domain: X = Altitude in [0.0, 1.8] u; Y = Velocity Vy in [-2.5, 0.5] u/s
    let minX = 0.0;
    let maxX = 1.8;
    let minY = -2.5;
    let maxY = 0.5;

    if (points.length > 0) {
      for (const p of points) {
        if (p.alt > maxX) maxX = Math.ceil(p.alt * 2) / 2 + 0.2;
        if (p.vy < minY) minY = Math.floor(p.vy * 2) / 2 - 0.5;
        if (p.vy > maxY) maxY = Math.ceil(p.vy * 2) / 2 + 0.2;
      }
    }

    const scaleX = (x: number) => margin.left + ((x - minX) / (maxX - minX)) * plotW;
    const scaleY = (y: number) => margin.top + plotH - ((y - minY) / (maxY - minY)) * plotH;

    // Grid lines
    ctx.strokeStyle = '#1E293B';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillStyle = '#64748B';

    // Vertical grid (Altitude X)
    const xStep = (maxX - minX) > 3 ? 0.5 : 0.25;
    ctx.textAlign = 'center';
    for (let x = minX; x <= maxX; x += xStep) {
      const px = scaleX(x);
      ctx.beginPath();
      ctx.moveTo(px, margin.top);
      ctx.lineTo(px, margin.top + plotH);
      ctx.stroke();

      ctx.fillText(x.toFixed(2), px, height - 12);
    }

    // Horizontal grid (Velocity Y)
    const yStep = (maxY - minY) > 4 ? 1.0 : 0.5;
    ctx.textAlign = 'right';
    for (let y = Math.ceil(minY / yStep) * yStep; y <= maxY; y += yStep) {
      const py = scaleY(y);
      ctx.beginPath();
      ctx.moveTo(margin.left, py);
      ctx.lineTo(margin.left + plotW, py);
      ctx.stroke();

      ctx.fillText(y.toFixed(1), margin.left - 6, py + 3);
    }
    ctx.setLineDash([]);

    // Zero Velocity Baseline (Hover threshold)
    const zeroY = scaleY(0.0);
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, zeroY);
    ctx.lineTo(margin.left + plotW, zeroY);
    ctx.stroke();

    // Strict Landing Criterion Touchdown Limit (-0.40 u/s)
    const limitY = scaleY(-0.4);
    ctx.strokeStyle = 'rgba(0, 230, 118, 0.8)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(margin.left, limitY);
    ctx.lineTo(margin.left + plotW, limitY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Criterion threshold tag
    ctx.fillStyle = '#00E676';
    ctx.textAlign = 'left';
    ctx.font = '9px ui-monospace, monospace';
    ctx.fillText('CRITERION LIMIT: -0.40 u/s', margin.left + 8, limitY - 4);

    // Axis labels
    ctx.fillStyle = '#94A3B8';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.fillText('FOOTPAD CLEARANCE Y (Box2D units)', margin.left + plotW / 2, height - 2);

    ctx.save();
    ctx.translate(12, margin.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('VERTICAL VELOCITY Vy (Box2D u/s)', 0, 0);
    ctx.restore();

    // Plot Braking Curve
    if (points.length >= 2) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#00F0FF';
      ctx.beginPath();

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        const px = scaleX(pt.alt);
        const py = scaleY(pt.vy);

        if (i === 0) {
          ctx.moveTo(px, py);
        } else {
          ctx.lineTo(px, py);
        }
      }
      ctx.stroke();

      // Current point
      const curPt = points[points.length - 1];
      const cx = scaleX(curPt.alt);
      const cy = scaleY(curPt.vy);

      ctx.fillStyle = Math.abs(curPt.vy) <= 0.4 ? '#00E676' : Math.abs(curPt.vy) <= 1.0 ? '#38BDF8' : '#FF1744';
      ctx.beginPath();
      ctx.arc(cx, cy, 4.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [points]);

  useEffect(() => {
    drawChart();
  }, [drawChart]);

  return (
    <div className={`relative w-full h-full flex flex-col font-mono ${className}`}>
      <div className="flex items-center justify-between px-2 py-1 bg-[#101622] border-b border-slate-800 text-[10px] text-slate-400">
        <div className="flex items-center gap-2">
          <span className="text-cyan-400 font-bold uppercase">BRAKING CORRIDOR Vy(Y)</span>
          <span className="text-slate-600">|</span>
          <span>SAMPLES: {points.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-emerald-400">TOUCHDOWN LIMIT: ≥ -0.40 u/s</span>
          <span className="text-slate-500">DESCENT: Vy &lt; 0</span>
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
