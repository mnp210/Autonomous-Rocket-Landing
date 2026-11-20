import React, { useEffect, useRef, useCallback } from 'react';
import type { TelemetryPoint } from '../../../services/telemetryStore';

export interface TrajectoryChartProps {
  points: TelemetryPoint[];
  className?: string;
}

export const TrajectoryChart: React.FC<TrajectoryChartProps> = ({ points, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Margins for scientific axes
    const margin = { top: 20, right: 25, bottom: 35, left: 45 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;

    // Clear background
    ctx.fillStyle = '#080B10';
    ctx.fillRect(0, 0, width, height);

    // Coordinate domain: X in [-2.5, 2.5] u, Y in [0.0, 1.8] u (or dynamic if vehicle exceeds)
    let minX = -2.5;
    let maxX = 2.5;
    let minY = 0.0;
    let maxY = 1.8;

    if (points.length > 0) {
      for (const p of points) {
        if (p.x < minX) minX = Math.floor(p.x * 2) / 2 - 0.5;
        if (p.x > maxX) maxX = Math.ceil(p.x * 2) / 2 + 0.5;
        if (p.alt > maxY) maxY = Math.ceil(p.alt * 2) / 2 + 0.2;
      }
    }

    const scaleX = (x: number) => margin.left + ((x - minX) / (maxX - minX)) * plotW;
    const scaleY = (y: number) => margin.top + plotH - ((y - minY) / (maxY - minY)) * plotH;

    // Draw Grid & Axes
    ctx.strokeStyle = '#1E293B';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);

    // Vertical grid lines (X)
    const xStep = (maxX - minX) > 6 ? 1.0 : 0.5;
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillStyle = '#64748B';
    ctx.textAlign = 'center';

    for (let x = Math.ceil(minX / xStep) * xStep; x <= maxX; x += xStep) {
      const px = scaleX(x);
      ctx.beginPath();
      ctx.moveTo(px, margin.top);
      ctx.lineTo(px, margin.top + plotH);
      ctx.stroke();

      ctx.fillText(x.toFixed(1), px, height - 12);
    }

    // Horizontal grid lines (Y)
    const yStep = (maxY - minY) > 3 ? 0.5 : 0.25;
    ctx.textAlign = 'right';

    for (let y = minY; y <= maxY; y += yStep) {
      const py = scaleY(y);
      ctx.beginPath();
      ctx.moveTo(margin.left, py);
      ctx.lineTo(margin.left + plotW, py);
      ctx.stroke();

      ctx.fillText(y.toFixed(2), margin.left - 6, py + 3);
    }
    ctx.setLineDash([]);

    // Axis labels
    ctx.fillStyle = '#94A3B8';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.fillText('HORIZONTAL OFFSET X (Box2D units)', margin.left + plotW / 2, height - 2);

    ctx.save();
    ctx.translate(12, margin.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('ALTITUDE / CLEARANCE Y (Box2D units)', 0, 0);
    ctx.restore();

    // Draw Landing Pad Surface Baseline & Strict Criteria Zone (|X| <= 0.25u)
    const padY = scaleY(0.0);
    const padLeft = scaleX(-1.5);
    const padRight = scaleX(1.5);
    const targetX = scaleX(0.0);
    const zoneLeft = scaleX(-0.25);
    const zoneRight = scaleX(0.25);

    // Pad surface bar
    ctx.strokeStyle = '#00F0FF';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padLeft, padY);
    ctx.lineTo(padRight, padY);
    ctx.stroke();

    // Strict Landing Target Zone (|x| <= 0.25u)
    ctx.fillStyle = 'rgba(0, 230, 118, 0.15)';
    ctx.fillRect(zoneLeft, margin.top, zoneRight - zoneLeft, plotH);
    ctx.strokeStyle = 'rgba(0, 230, 118, 0.5)';
    ctx.setLineDash([3, 3]);
    ctx.strokeRect(zoneLeft, margin.top, zoneRight - zoneLeft, plotH);
    ctx.setLineDash([]);

    // Pad centerline indicator
    ctx.strokeStyle = '#00E676';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(targetX, padY - 6);
    ctx.lineTo(targetX, padY + 6);
    ctx.stroke();

    // Plot Trajectory Path
    if (points.length >= 2) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#38BDF8';
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        const px = scaleX(pt.x);
        const py = scaleY(pt.alt);
        if (i === 0) {
          ctx.moveTo(px, py);
        } else {
          ctx.lineTo(px, py);
        }
      }
      ctx.stroke();

      // Start position marker (Diamond)
      const startPt = points[0];
      const sx = scaleX(startPt.x);
      const sy = scaleY(startPt.alt);
      ctx.fillStyle = '#64748B';
      ctx.beginPath();
      ctx.arc(sx, sy, 3, 0, Math.PI * 2);
      ctx.fill();

      // Current vehicle position (Glowing dot + attitude orientation line)
      const curPt = points[points.length - 1];
      const cx = scaleX(curPt.x);
      const cy = scaleY(curPt.alt);

      ctx.fillStyle = curPt.phase === 'TOUCHDOWN_DETECTED' ? '#00E676' : '#00F0FF';
      ctx.beginPath();
      ctx.arc(cx, cy, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // Attitude line
      const headingLen = 14;
      const hx = cx - Math.sin(curPt.angle) * headingLen;
      const hy = cy - Math.cos(curPt.angle) * headingLen;
      ctx.strokeStyle = '#FFB300';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(hx, hy);
      ctx.stroke();
    } else if (points.length === 1) {
      const curPt = points[0];
      const cx = scaleX(curPt.x);
      const cy = scaleY(curPt.alt);
      ctx.fillStyle = '#00F0FF';
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
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
          <span className="text-cyan-400 font-bold uppercase">TRAJECTORY TRACE Y(X)</span>
          <span className="text-slate-600">|</span>
          <span>SAMPLES: {points.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-emerald-400">■ CRITERIA: |X| ≤ 0.25u</span>
          <span className="text-slate-500">PAD: Y = 0.0u</span>
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
