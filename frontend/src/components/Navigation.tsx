import React from 'react';
import {
  BarChart3,
  Code,
  FolderTree,
  GitFork,
  Layers,
  MessageSquare,
  Network,
  Search,
} from 'lucide-react';

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

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  const tabs: Array<{ id: TabType; label: string; icon: React.ReactNode }> = [
    { id: 'overview', label: 'Overview', icon: <Layers className="w-4 h-4" /> },
    { id: 'files', label: 'File Explorer', icon: <FolderTree className="w-4 h-4" /> },
    { id: 'symbols', label: 'Symbols & AST', icon: <Code className="w-4 h-4" /> },
    { id: 'search', label: 'Code Search', icon: <Search className="w-4 h-4" /> },
    { id: 'ask', label: 'Ask RepoMind', icon: <MessageSquare className="w-4 h-4" /> },
    { id: 'graph', label: 'Dependency Graph', icon: <Network className="w-4 h-4" /> },
    { id: 'impact', label: 'Blast Radius', icon: <GitFork className="w-4 h-4" /> },
    { id: 'evaluation', label: 'Evaluation', icon: <BarChart3 className="w-4 h-4" /> },
  ];

  return (
    <nav className="border-b border-slate-800 bg-slate-900 px-6">
      <div className="max-w-7xl mx-auto flex space-x-1 overflow-x-auto scrollbar-none py-2">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition whitespace-nowrap ${
                isActive
                  ? 'bg-teal-600/20 text-teal-300 border border-teal-800/40'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
