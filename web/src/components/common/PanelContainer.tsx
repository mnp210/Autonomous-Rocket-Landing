import React from 'react';

export interface PanelContainerProps {
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  actionSlot?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  headerClassName?: string;
  contentClassName?: string;
}

export const PanelContainer: React.FC<PanelContainerProps> = ({
  title,
  subtitle,
  badge,
  actionSlot,
  children,
  className = '',
  headerClassName = '',
  contentClassName = '',
}) => {
  return (
    <section
      className={`bg-[#0D1117] border border-slate-800/80 rounded flex flex-col font-mono text-slate-200 overflow-hidden ${className}`}
    >
      {/* Panel Header */}
      <div
        className={`bg-[#101622] border-b border-slate-800/90 px-3.5 py-2 flex items-center justify-between gap-2 select-none ${headerClassName}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-1 h-3.5 bg-cyan-400 rounded-xs" aria-hidden="true" />
          <div className="truncate">
            <h2 className="text-xs font-bold tracking-wider text-slate-100 uppercase truncate">
              {title}
            </h2>
            {subtitle && (
              <p className="text-[10px] text-slate-400 truncate tracking-normal font-normal">
                {subtitle}
              </p>
            )}
          </div>
          {badge && <div className="ml-1 shrink-0">{badge}</div>}
        </div>

        {actionSlot && <div className="flex items-center gap-1.5 shrink-0">{actionSlot}</div>}
      </div>

      {/* Panel Body */}
      <div className={`p-3 flex-1 flex flex-col ${contentClassName}`}>{children}</div>
    </section>
  );
};
