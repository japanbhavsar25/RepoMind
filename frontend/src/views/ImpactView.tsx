import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Code2,
  FileCode,
  GitFork,
  Search,
  ShieldAlert,
} from 'lucide-react';
import { fetchImpact } from '../api';
import type { ImpactResponse } from '../types';

interface ImpactViewProps {
  repoId: string;
  initialTarget?: string;
  onNavigateToFile?: (path: string) => void;
}

export const ImpactView: React.FC<ImpactViewProps> = ({
  repoId,
  initialTarget = 'models.py',
  onNavigateToFile,
}) => {
  const [target, setTarget] = useState(initialTarget);
  const [impact, setImpact] = useState<ImpactResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialTarget) {
      setTarget(initialTarget);
      runImpact(initialTarget);
    }
  }, [initialTarget, repoId]);

  const runImpact = async (t: string) => {
    if (!t.trim()) return;
    setLoading(true);
    try {
      const res = await fetchImpact(t.trim(), repoId);
      setImpact(res);
    } catch (err) {
      console.error('Failed to compute impact:', err);
    } finally {
      setLoading(false);
    }
  };

  const sampleTargets = ['models.py', 'database.py', 'auth.py', 'calculate_tax', 'hash_token'];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Target Search Box */}
      <div className="bg-slate-950 border border-slate-800 rounded-lg p-6 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
            <GitFork className="w-5 h-5 text-teal-400" />
            <span>Downstream Blast-Radius & Change-Impact Analyzer</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Calculates transitive downstream dependents using reverse BFS graph traversal and maps AST caller-callee relationships.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            runImpact(target);
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
            <input
              type="text"
              placeholder="Enter module file (e.g. models.py) or function name..."
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-md pl-10 pr-4 py-2.5 text-sm font-mono text-slate-200 outline-none focus:border-teal-500 transition"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2.5 rounded-md bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-50 text-slate-100 font-medium text-sm transition shadow-md "
          >
            {loading ? 'Analyzing...' : 'Analyze Impact'}
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-[11px] text-slate-500 font-medium">Quick Targets:</span>
          {sampleTargets.map((st) => (
            <button
              key={st}
              onClick={() => {
                setTarget(st);
                runImpact(st);
              }}
              className="px-2.5 py-1 rounded bg-slate-950 hover:bg-slate-700 border border-slate-800 text-[11px] font-mono text-slate-300 transition"
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Impact Result Cards */}
      {impact && (
        <div className="space-y-5">
          {/* Metrics summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
              <span className="text-xs text-slate-400 block">Transitive Blast Radius</span>
              <span className="text-2xl font-bold text-rose-400 mt-1 block">
                {impact.transitive_dependents.length} files
              </span>
              <span className="text-[11px] text-slate-500">Downstream modules affected</span>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
              <span className="text-xs text-slate-400 block">Direct Importers</span>
              <span className="text-2xl font-bold text-amber-400 mt-1 block">
                {impact.direct_importers.length} files
              </span>
              <span className="text-[11px] text-slate-500">Immediate dependencies</span>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
              <span className="text-xs text-slate-400 block">PageRank Centrality</span>
              <span className="text-2xl font-bold text-teal-400 mt-1 block font-mono">
                {impact.pagerank.toFixed(4)}
              </span>
              <span className="text-[11px] text-slate-500">Graph importance score</span>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
              <span className="text-xs text-slate-400 block">Max Complexity</span>
              <span className="text-2xl font-bold text-emerald-400 mt-1 block">
                CC {impact.complexity}
              </span>
              <span className="text-[11px] text-slate-500">Cyclomatic decision points</span>
            </div>
          </div>

          {/* Transitive Downstream Dependents List */}
          <div className="bg-slate-950 border border-slate-800 rounded-md p-5 space-y-3">
            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              <h3 className="text-sm font-bold text-slate-100">
                Transitive Downstream Dependents ({impact.transitive_dependents.length})
              </h3>
            </div>
            <p className="text-xs text-slate-400">
              Modifying <code>{impact.target}</code> has a direct or indirect propagation risk to the following modules:
            </p>

            {impact.transitive_dependents.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 pt-1">
                {impact.transitive_dependents.map((dep) => (
                  <button
                    key={dep}
                    onClick={() => onNavigateToFile?.(dep)}
                    className="flex items-center space-x-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800 hover:border-teal-500 text-left text-xs font-mono text-slate-200 transition"
                  >
                    <ArrowRight className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                    <span className="truncate">{dep}</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 bg-slate-950 p-3 rounded-lg border border-slate-800">
                Zero downstream dependents. This component can be safely modified without transitive side effects on internal modules.
              </div>
            )}
          </div>

          {/* AST Direct Callers */}
          {impact.callers.length > 0 && (
            <div className="bg-slate-950 border border-slate-800 rounded-md p-5 space-y-3">
              <div className="flex items-center space-x-2">
                <Code2 className="w-4 h-4 text-teal-400" />
                <h3 className="text-sm font-bold text-slate-100">
                  AST Caller Invocations ({impact.callers.length})
                </h3>
              </div>
              <p className="text-xs text-slate-400">
                Direct function and method calls extracted from AST Call nodes:
              </p>

              <div className="space-y-1.5 pt-1">
                {impact.callers.map((c, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-slate-950 p-2 rounded-lg border border-slate-800 text-xs font-mono"
                  >
                    <div className="flex items-center space-x-2">
                      <FileCode className="w-3.5 h-3.5 text-slate-500" />
                      <span className="text-slate-300">{c.caller_file}</span>
                      <span className="text-slate-500">::</span>
                      <span className="text-teal-400 font-semibold">{c.caller_symbol}</span>
                    </div>
                    <span className="text-slate-500">Line {c.line_number}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Static Analysis Limitations Box */}
          <div className="bg-slate-900 border border-slate-800 rounded-md p-4 space-y-2">
            <h4 className="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span>Static Analysis Boundaries & Disclosures</span>
            </h4>
            <ul className="text-xs text-slate-400 space-y-1 pl-4 list-disc">
              {impact.limitations.map((lim, idx) => (
                <li key={idx}>{lim}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
