import React, { useRef } from 'react';

export interface TabItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

export interface TabNavigationProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  size?: 'sm' | 'md';
  ariaLabel?: string;
  className?: string;
}

export const TabNavigation: React.FC<TabNavigationProps> = ({
  tabs,
  activeTab,
  onChange,
  size = 'md',
  ariaLabel = 'Navigation Tabs',
  className = '',
}) => {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = index;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      nextIndex = (index + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      nextIndex = (index - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = tabs.length - 1;
    }

    if (nextIndex !== index) {
      tabRefs.current[nextIndex]?.focus();
      onChange(tabs[nextIndex].id);
    }
  };

  const isSmall = size === 'sm';

  return (
    <nav
      role="tablist"
      aria-label={ariaLabel}
      className={`inline-flex items-center gap-1 bg-[#090D14] border border-slate-800/90 rounded p-1 font-mono ${className}`}
    >
      {tabs.map((tab, idx) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            ref={(el) => {
              tabRefs.current[idx] = el;
            }}
            role="tab"
            aria-selected={isActive}
            aria-controls={`tabpanel-${tab.id}`}
            id={`tab-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            type="button"
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={`flex items-center gap-2 rounded font-bold uppercase transition-all select-none focus:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 ${
              isSmall ? 'text-[10px] px-2.5 py-1' : 'text-xs px-3.5 py-1.5'
            } ${
              isActive
                ? 'bg-cyan-950/80 border border-cyan-400 text-cyan-300 shadow-[0_0_8px_rgba(0,240,255,0.3)]'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
            }`}
          >
            {tab.icon && <span className="shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                className={`text-[9px] px-1.5 py-0.2 rounded font-normal ${
                  isActive ? 'bg-cyan-900/80 text-cyan-200' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
};
