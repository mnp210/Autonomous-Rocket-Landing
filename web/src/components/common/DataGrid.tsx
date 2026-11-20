import React from 'react';

export interface DataGridItem {
  label: string;
  value: React.ReactNode;
  unit?: string;
  status?: 'nominal' | 'warning' | 'critical' | 'info' | 'muted';
  tooltip?: string;
}

export interface DataGridProps {
  items: DataGridItem[];
  columns?: 1 | 2 | 3 | 4;
  className?: string;
}

const statusTextColors: Record<string, string> = {
  nominal: 'text-emerald-400',
  warning: 'text-amber-400',
  critical: 'text-rose-400',
  info: 'text-cyan-400',
  muted: 'text-slate-300',
};

export const DataGrid: React.FC<DataGridProps> = ({
  items,
  columns = 2,
  className = '',
}) => {
  const colClass = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3',
    4: 'grid-cols-2 sm:grid-cols-4',
  }[columns];

  return (
    <div className={`grid ${colClass} gap-2 font-mono text-xs ${className}`}>
      {items.map((item, index) => {
        const textColor = item.status ? statusTextColors[item.status] : 'text-slate-200';
        return (
          <div
            key={index}
            title={item.tooltip}
            className="flex items-center justify-between p-2 rounded bg-[#101620] border border-slate-800/80"
          >
            <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
              {item.label}
            </span>
            <div className="flex items-baseline gap-1">
              <span className={`font-bold tabular-nums ${textColor}`}>{item.value}</span>
              {item.unit && <span className="text-[10px] text-slate-400 font-normal">{item.unit}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
};
