import React, { useEffect, useRef } from 'react';

export type TabType =
  | 'overview'
  | 'files'
  | 'symbols'
  | 'search'
  | 'ask'
  | 'graph'
  | 'impact'
  | 'evaluation';

interface NavigationProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

const TABS: Array<{ id: TabType; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'ask', label: 'Ask' },
  { id: 'search', label: 'Search' },
  { id: 'files', label: 'Files' },
  { id: 'symbols', label: 'Symbols' },
  { id: 'graph', label: 'Dependencies' },
  { id: 'impact', label: 'Blast radius' },
  { id: 'evaluation', label: 'Benchmark' },
];

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  const activeRef = useRef<HTMLButtonElement>(null);

  // On narrow screens the strip scrolls: keep the current tab in view, so you can
  // see where you are (e.g. after a link from another tab jumps to Benchmark)
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [activeTab]);

  return (
    <nav className="bg-paper border-b border-line px-4 sm:px-6 sticky top-0 z-40" aria-label="Sections">
      <div className="relative max-w-6xl mx-auto">
        <div className="flex gap-5 sm:gap-7 overflow-x-auto [scrollbar-width:none]">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                ref={isActive ? activeRef : undefined}
                onClick={() => onTabChange(tab.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`relative py-3 text-sm whitespace-nowrap transition ${
                  isActive ? 'text-ink font-medium' : 'text-muted hover:text-ink'
                }`}
              >
                {tab.label}
                {isActive && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-accent" />}
              </button>
            );
          })}
        </div>
        {/* A fade at the right edge hints that more tabs are off-screen (phones only) */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-linear-to-l from-paper sm:hidden"
        />
      </div>
    </nav>
  );
};
