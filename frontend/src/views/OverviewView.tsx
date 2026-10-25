import React from 'react';
import { AlertTriangle, CheckCircle2, Code2, FileCode2, GitFork, HelpCircle, Network, Search } from 'lucide-react';
import type { RepoInfo } from '../types';
import type { TabType } from '../components/Navigation';

interface OverviewViewProps {
  repo?: RepoInfo;
  onNavigate: (tab: TabType) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({ repo, onNavigate }) => {
  const stats = repo?.stats || { files: 0, functions: 0, classes: 0, imports: 0 };

  if (!repo) {
    return (
      <div className="max-w-2xl space-y-4">
        <h1 className="text-xl font-semibold text-slate-100">Repository overview</h1>
        <p className="text-sm text-slate-400 leading-relaxed">
          Select an indexed repository from the header, or add a GitHub repository to begin. RepoMind parses Python ASTs,
          builds a dependency graph, and indexes symbols for search and grounded Q&amp;A.
        </p>
        <div className="flex gap-2">
          <button onClick={() => onNavigate('search')} className="px-3 py-1.5 text-sm rounded border border-slate-700 hover:bg-slate-800 text-slate-200">
            Search
          </button>
          <button onClick={() => onNavigate('ask')} className="px-3 py-1.5 text-sm rounded bg-teal-600 hover:bg-teal-500 text-slate-100">
            Ask
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide">Repository</p>
          <h1 className="text-xl font-semibold text-slate-100">{repo.name}</h1>
          <p className="text-xs text-slate-400 font-mono mt-1">{repo.id}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => onNavigate('ask')} className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded bg-teal-600 hover:bg-teal-500 text-slate-100">
            <HelpCircle className="w-3.5 h-3.5" /> Ask
          </button>
          <button onClick={() => onNavigate('search')} className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded border border-slate-700 hover:bg-slate-800 text-slate-200">
            <Search className="w-3.5 h-3.5" /> Search
          </button>
          <button onClick={() => onNavigate('graph')} className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded border border-slate-700 hover:bg-slate-800 text-slate-200">
            <Network className="w-3.5 h-3.5" /> Graph
          </button>
        </div>
      </header>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-slate-700 border border-slate-800 rounded overflow-hidden">
        <Stat label="Files" value={stats.files} icon={<FileCode2 className="w-3.5 h-3.5" />} />
        <Stat label="Functions" value={stats.functions} icon={<Code2 className="w-3.5 h-3.5" />} />
        <Stat label="Classes" value={stats.classes} icon={<Code2 className="w-3.5 h-3.5" />} />
        <Stat label="Import edges" value={stats.imports} icon={<GitFork className="w-3.5 h-3.5" />} />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div className="border border-slate-800 rounded p-4 space-y-2">
          <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Guarantees
          </h2>
          <ul className="text-xs text-slate-400 space-y-1.5 leading-relaxed">
            <li>Every answer cites exact file:line ranges, checked against the parsed source.</li>
            <li>
              Parsing, indexing and search run on the RepoMind server. Only the few retrieved snippets are sent
              to the LLM (Groq in this online demo, or a local Ollama model when self-hosted).
            </li>
            <li>Repository code is parsed with Python&apos;s AST — never executed.</li>
          </ul>
        </div>
        <div className="border border-slate-800 rounded p-4 space-y-2">
          <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Limits
          </h2>
          <ul className="text-xs text-slate-400 space-y-1.5 leading-relaxed">
            <li>Static analysis only — dynamic calls and reflection are not inferred.</li>
            <li>Python files only; other languages are skipped.</li>
            <li>Abstains when retrieved chunks lack evidence.</li>
          </ul>
        </div>
      </section>
    </div>
  );
};

const Stat: React.FC<{ label: string; value: number; icon: React.ReactNode }> = ({ label, value, icon }) => (
  <div className="bg-slate-950 p-3 flex items-center gap-3">
    <span className="text-slate-500">{icon}</span>
    <div>
      <div className="text-lg font-semibold text-slate-100 tabular-nums">{value}</div>
      <div className="text-xs text-slate-400">{label}</div>
    </div>
  </div>
);
