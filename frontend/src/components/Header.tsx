import React, { useEffect, useState } from 'react';
import { ChevronDown, Moon, Plus, RefreshCw, Sun } from 'lucide-react';
import type { RepoInfo } from '../types';
import { Button } from './ui';

interface HeaderProps {
  repos: RepoInfo[];
  activeRepoId: string;
  onSelectRepo: (repoId: string) => void;
  onTriggerIndex: () => void;
  onOpenAddRepo: () => void;
  indexing: boolean;
}

type Theme = 'light' | 'dark';

function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === 'light' || set === 'dark') return set;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

const ThemeToggle: React.FC = () => {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  // Follow the OS theme until the person picks one themselves
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setTheme(currentTheme());
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try {
      localStorage.setItem('repomind-theme', next);
    } catch {
      // Storage can be blocked; the toggle still works for this visit.
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      className="p-2 rounded-md text-muted hover:text-ink hover:bg-sunk transition"
      aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      title={theme === 'dark' ? 'Light theme' : 'Dark theme'}
    >
      {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  );
};

export const Header: React.FC<HeaderProps> = ({
  repos,
  activeRepoId,
  onSelectRepo,
  onTriggerIndex,
  onOpenAddRepo,
  indexing,
}) => {
  return (
    <header className="bg-paper px-4 sm:px-6 pt-5 pb-3">
      <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="flex items-baseline gap-3">
          <span className="font-serif text-2xl font-semibold tracking-tight text-ink">
            RepoMind<span className="text-accent">.</span>
          </span>
          <span className="hidden md:inline text-sm text-subtle">Read any Python repo, with receipts.</span>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto min-w-0">
          <label className="relative flex-1 sm:flex-none min-w-0">
            <span className="sr-only">Repository</span>
            <select
              value={activeRepoId}
              onChange={(e) => onSelectRepo(e.target.value)}
              className="appearance-none w-full sm:w-72 truncate bg-surface border border-line-strong rounded-md pl-3 pr-8 py-2 text-sm font-medium text-ink outline-none focus:border-accent cursor-pointer"
            >
              {repos.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-subtle absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </label>

          <Button onClick={onOpenAddRepo} aria-label="Add a repository" title="Add a repository">
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Add repo</span>
          </Button>

          <Button
            variant="quiet"
            onClick={onTriggerIndex}
            disabled={indexing}
            title="Parse the selected repository again"
            aria-label={indexing ? 'Re-indexing' : 'Re-index repository'}
          >
            <RefreshCw className={`w-4 h-4 ${indexing ? 'animate-spin' : ''}`} />
            <span className="hidden lg:inline">{indexing ? 'Re-indexing…' : 'Re-index'}</span>
          </Button>

          <ThemeToggle />
        </div>
      </div>
    </header>
  );
};
