import React from 'react';
import { Database, Plus, RefreshCw, ShieldCheck } from 'lucide-react';
import type { RepoInfo } from '../types';

interface HeaderProps {
  repos: RepoInfo[];
  activeRepoId: string;
  onSelectRepo: (repoId: string) => void;
  onTriggerIndex: () => void;
  onOpenAddRepo: () => void;
  indexing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  repos,
  activeRepoId,
  onSelectRepo,
  onTriggerIndex,
  onOpenAddRepo,
  indexing,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-950 sticky top-0 z-50 px-4 sm:px-6 py-3">
      {/* Wraps onto two rows on phones: brand on top, repo picker + actions below */}
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-md bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-200">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <span className="font-semibold text-base text-slate-100 tracking-tight">RepoMind</span>
            <p className="hidden sm:block text-xs text-slate-500">Code intelligence</p>
          </div>
        </div>

        {/* Repository selector & actions */}
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto min-w-0">
          <div className="flex items-center space-x-2 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 flex-1 sm:flex-none min-w-0">
            <Database className="w-4 h-4 text-slate-400 flex-shrink-0" />
            <select
              value={activeRepoId}
              onChange={(e) => onSelectRepo(e.target.value)}
              aria-label="Repository"
              className="bg-transparent text-sm text-slate-200 outline-none cursor-pointer pr-2 font-medium w-full sm:max-w-xs truncate"
            >
              {repos.map((r) => (
                <option key={r.id} value={r.id} className="bg-slate-900 text-slate-200">
                  {r.name} {r.is_sample ? '(Sample)' : ''}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={onOpenAddRepo}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-700 border border-slate-800 hover:border-slate-700 text-sm font-medium text-slate-200 hover:text-slate-100 transition shadow-sm flex-shrink-0"
            title="Add a repository"
            aria-label="Add repository"
          >
            <Plus className="w-4 h-4 text-teal-400" />
            <span className="hidden sm:inline">Add Repo</span>
          </button>

          <button
            onClick={onTriggerIndex}
            disabled={indexing}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-50 text-sm font-medium text-slate-100 transition shadow-sm flex-shrink-0"
            title="Re-index the selected repository"
            aria-label={indexing ? 'Indexing' : 'Index repository'}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${indexing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{indexing ? 'Indexing...' : 'Index Repo'}</span>
          </button>

          <div className="hidden lg:flex items-center space-x-1 px-2.5 py-1 rounded-md bg-emerald-950/40 border border-emerald-800/40 text-emerald-400 text-xs font-medium">
            <ShieldCheck className="w-3.5 h-3.5 mr-1" />
            <span>Cited answers</span>
          </div>
        </div>
      </div>
    </header>
  );
};
