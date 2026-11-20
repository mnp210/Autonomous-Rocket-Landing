import React from 'react';

export type StatusBadgeVariant = 'nominal' | 'warning' | 'critical' | 'info' | 'neutral';

export interface StatusBadgeProps {
  label: string;
  variant?: StatusBadgeVariant;
  size?: 'sm' | 'md';
  showDot?: boolean;
  dotPulse?: boolean;
  title?: string;
  className?: string;
}

const variantStyles: Record<
  StatusBadgeVariant,
  { badge: string; dot: string; glow: string }
> = {
  nominal: {
    badge: 'bg-emerald-950/60 text-emerald-400 border-emerald-500/40',
    dot: 'bg-emerald-400',
    glow: 'shadow-[0_0_6px_#00E676]',
  },
  warning: {
    badge: 'bg-amber-950/60 text-amber-400 border-amber-500/40',
    dot: 'bg-amber-400',
    glow: 'shadow-[0_0_6px_#FFB300]',
  },
  critical: {
    badge: 'bg-rose-950/60 text-rose-400 border-rose-500/40',
    dot: 'bg-rose-400',
    glow: 'shadow-[0_0_6px_#FF1744]',
  },
  info: {
    badge: 'bg-cyan-950/60 text-cyan-400 border-cyan-500/40',
    dot: 'bg-cyan-400',
    glow: 'shadow-[0_0_6px_rgba(0,240,255,0.5)]',
  },
  neutral: {
    badge: 'bg-slate-900/60 text-slate-400 border-slate-700/60',
    dot: 'bg-slate-400',
    glow: '',
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  label,
  variant = 'neutral',
  size = 'sm',
  showDot = false,
  dotPulse = false,
  title,
  className = '',
}) => {
  const styles = variantStyles[variant];
  const sizeClasses =
    size === 'sm'
      ? 'text-[10px] px-2 py-0.5 tracking-wider'
      : 'text-xs px-2.5 py-1 tracking-wider';

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 font-mono font-bold uppercase rounded border ${styles.badge} ${sizeClasses} select-none ${className}`}
    >
      {showDot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${styles.dot} ${styles.glow} ${
            dotPulse ? 'animate-pulse' : ''
          }`}
          aria-hidden="true"
        />
      )}
      <span>{label}</span>
    </span>
  );
};
