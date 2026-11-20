import React from 'react';

export interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  statusLabel?: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  statusLabel = 'AWAITING TELEMETRY',
  action,
  className = '',
}) => {
  return (
    <div
      className={`border border-dashed border-slate-800 rounded bg-[#090D14]/70 p-6 flex flex-col items-center justify-center text-center font-mono ${className}`}
    >
      <div className="w-10 h-10 rounded bg-[#101622] border border-slate-700/60 flex items-center justify-center text-slate-400 mb-3">
        {icon || (
          <svg
            className="w-5 h-5 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
        )}
      </div>

      <div className="inline-block px-2 py-0.5 mb-2 rounded bg-slate-900 border border-slate-700/60 text-[9px] font-bold tracking-widest text-slate-400 uppercase">
        {statusLabel}
      </div>

      <h3 className="text-xs font-bold text-slate-200 tracking-wider uppercase mb-1">
        {title}
      </h3>

      <p className="text-[11px] text-slate-400 max-w-sm mb-4 leading-relaxed font-normal">
        {description}
      </p>

      {action && <div>{action}</div>}
    </div>
  );
};
