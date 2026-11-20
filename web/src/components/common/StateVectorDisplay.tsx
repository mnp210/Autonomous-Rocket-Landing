import React from 'react';

export interface StateVectorDisplayProps {
  label: string;
  vector: { x: number; y: number; z?: number };
  units?: string;
  coordinateSystem?: string;
  precision?: number;
  className?: string;
}

export const StateVectorDisplay: React.FC<StateVectorDisplayProps> = ({
  label,
  vector,
  units = 'm',
  coordinateSystem = 'BOX2D WORLD (2D)',
  precision = 2,
  className = '',
}) => {
  return (
    <div
      className={`p-2.5 rounded bg-[#101620] border border-slate-800/80 font-mono text-xs flex flex-col gap-1.5 ${className}`}
    >
      <div className="flex items-center justify-between text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
        <span>{label}</span>
        <span className="text-slate-500 text-[9px]">{coordinateSystem}</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <div className="flex items-center justify-between px-2 py-1 rounded bg-[#090D14] border border-slate-800/60">
          <span className="text-[10px] text-cyan-400 font-bold">X</span>
          <span className="font-bold tabular-nums text-slate-200">
            {vector.x >= 0 ? `+${vector.x.toFixed(precision)}` : vector.x.toFixed(precision)}
            <span className="text-[9px] text-slate-400 ml-1 font-normal">{units}</span>
          </span>
        </div>

        <div className="flex items-center justify-between px-2 py-1 rounded bg-[#090D14] border border-slate-800/60">
          <span className="text-[10px] text-emerald-400 font-bold">Y</span>
          <span className="font-bold tabular-nums text-slate-200">
            {vector.y >= 0 ? `+${vector.y.toFixed(precision)}` : vector.y.toFixed(precision)}
            <span className="text-[9px] text-slate-400 ml-1 font-normal">{units}</span>
          </span>
        </div>

        {vector.z !== undefined && (
          <div className="flex items-center justify-between px-2 py-1 rounded bg-[#090D14] border border-slate-800/60">
            <span className="text-[10px] text-indigo-400 font-bold">Z</span>
            <span className="font-bold tabular-nums text-slate-200">
              {vector.z >= 0 ? `+${vector.z.toFixed(precision)}` : vector.z.toFixed(precision)}
              <span className="text-[9px] text-slate-400 ml-1 font-normal">{units}</span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
