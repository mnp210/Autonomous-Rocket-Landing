import React from 'react';

export type TelemetryStatus = 'nominal' | 'warning' | 'critical' | 'info' | 'muted';

export interface TelemetryReadoutProps {
  label: string;
  value: string | number;
  unit?: string;
  status?: TelemetryStatus;
  subtext?: string;
  auxValue?: string | number;
  auxLabel?: string;
  className?: string;
}

const statusColors: Record<TelemetryStatus, { text: string; bg: string; border: string }> = {
  nominal: {
    text: 'text-emerald-400',
    bg: 'bg-emerald-950/20',
    border: 'border-emerald-800/40',
  },
  warning: {
    text: 'text-amber-400',
    bg: 'bg-amber-950/20',
    border: 'border-amber-800/40',
  },
  critical: {
    text: 'text-rose-400',
    bg: 'bg-rose-950/20',
    border: 'border-rose-800/40',
  },
  info: {
    text: 'text-cyan-400',
    bg: 'bg-cyan-950/20',
    border: 'border-cyan-800/40',
  },
  muted: {
    text: 'text-slate-300',
    bg: 'bg-slate-900/40',
    border: 'border-slate-800/60',
  },
};

export const TelemetryReadout: React.FC<TelemetryReadoutProps> = ({
  label,
  value,
  unit,
  status = 'muted',
  subtext,
  auxValue,
  auxLabel,
  className = '',
}) => {
  const colors = statusColors[status];

  return (
    <div
      className={`p-2.5 rounded border ${colors.bg} ${colors.border} transition-colors flex flex-col justify-between font-mono ${className}`}
    >
      <div className="flex items-center justify-between text-[10px] tracking-wider text-slate-400 uppercase font-semibold">
        <span>{label}</span>
        {auxLabel && auxValue !== undefined && (
          <span className="text-slate-500 text-[9px] tabular-nums">
            {auxLabel}: {auxValue}
          </span>
        )}
      </div>

      <div className="mt-1 flex items-baseline justify-between gap-1">
        <div className="flex items-baseline gap-1">
          <span className={`text-lg font-bold tabular-nums tracking-tight ${colors.text}`}>
            {value}
          </span>
          {unit && (
            <span className="text-[11px] text-slate-400 font-normal">{unit}</span>
          )}
        </div>

        {subtext && (
          <span className={`text-[10px] font-semibold uppercase ${colors.text}`}>
            {subtext}
          </span>
        )}
      </div>
    </div>
  );
};
