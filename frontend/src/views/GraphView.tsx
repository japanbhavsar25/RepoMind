import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Award,
  CheckCircle,
  ExternalLink,
  GitFork,
  Network,
  Share2,
} from 'lucide-react';
import { fetchGraph } from '../api';
import type { GraphDataResponse } from '../types';

interface GraphViewProps {
  repoId: string;
  onSelectTarget?: (target: string) => void;
}

export const GraphView: React.FC<GraphViewProps> = ({ repoId, onSelectTarget }) => {
  const [data, setData] = useState<GraphDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState<'all' | 'internal' | 'external'>('all');

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetchGraph(repoId)
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch((err) => console.error('Failed to load graph:', err))
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [repoId]);

  const filteredEdges = data?.edges.filter((e) => {
    if (filterType === 'internal') return e.type === 'internal';
    if (filterType === 'external') return e.type === 'external';
    return true;
  }) || [];

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-400">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-sm font-medium">Analyzing dependency graph & calculating PageRank...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Total Nodes</span>
            <Network className="w-4 h-4 text-teal-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-100">{data?.nodes.length || 0}</div>
          <p className="text-xs text-slate-500 mt-1">Modules & libraries</p>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Import Edges</span>
            <GitFork className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-100">{data?.edges.length || 0}</div>
          <p className="text-xs text-slate-500 mt-1">Directed dependencies</p>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Circular Cycles</span>
            <Share2 className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-100">{data?.cycles.length || 0}</div>
          <p className="text-xs text-slate-500 mt-1">Mutual import loops</p>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-md p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Orphan Files</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-100">{data?.orphans.length || 0}</div>
          <p className="text-xs text-slate-500 mt-1">Isolated components</p>
        </div>
      </div>

      {/* PageRank Leaderboard & Cycles Alert */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* PageRank Leaderboard */}
        <div className="bg-slate-950 border border-slate-800 rounded-md p-5 space-y-3">
          <div className="flex items-center space-x-2">
            <Award className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold text-slate-100">PageRank Criticality Leaderboard</h3>
          </div>
          <p className="text-xs text-slate-400">
            Files with high PageRank scores represent core architectural dependencies relied on by other modules.
          </p>

          <div className="space-y-2 pt-1">
            {data?.pagerank_leaderboard.map((item, idx) => (
              <div
                key={item.file}
                onClick={() => onSelectTarget?.(item.file)}
                className="flex items-center justify-between bg-slate-950 p-2.5 rounded-lg border border-slate-800 hover:border-teal-400 cursor-pointer transition text-xs"
              >
                <div className="flex items-center space-x-2">
                  <span className="w-5 text-center font-bold text-slate-500">#{idx + 1}</span>
                  <span className="font-mono text-slate-200">{item.file}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-teal-400 font-semibold">{item.score.toFixed(4)}</span>
                  <ExternalLink className="w-3 h-3 text-slate-500" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cycles & Orphans */}
        <div className="space-y-4">
          {/* Circular Dependencies */}
          <div className="bg-slate-950 border border-slate-800 rounded-md p-5 space-y-3">
            <div className="flex items-center space-x-2">
              <Share2 className="w-4 h-4 text-rose-400" />
              <h3 className="text-sm font-bold text-slate-100">Circular Dependencies</h3>
            </div>
            {data?.cycles && data.cycles.length > 0 ? (
              <div className="space-y-2">
                {data.cycles.map((cyc, idx) => (
                  <div key={idx} className="bg-rose-950/40 border border-rose-800/40 p-2.5 rounded-lg text-xs font-mono text-rose-300">
                    Cycle #{idx + 1}: {cyc.join(' -> ')}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 p-3 rounded-lg">
                <CheckCircle className="w-4 h-4 shrink-0" />
                <span>Zero circular dependency cycles detected in this codebase.</span>
              </div>
            )}
          </div>

          {/* Orphan Modules */}
          <div className="bg-slate-950 border border-slate-800 rounded-md p-5 space-y-3">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-bold text-slate-100">Orphan Modules</h3>
            </div>
            <p className="text-xs text-slate-400">
              Files with zero incoming and zero outgoing internal imports (often dead code or standalone entrypoints).
            </p>
            {data?.orphans && data.orphans.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {data.orphans.map((orph) => (
                  <button
                    key={orph}
                    onClick={() => onSelectTarget?.(orph)}
                    className="px-2.5 py-1 rounded bg-amber-950/40 border border-amber-800/40 text-amber-300 font-mono text-xs hover:bg-amber-900/40 transition"
                  >
                    {orph}
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500">No orphan modules found.</div>
            )}
          </div>
        </div>
      </div>

      {/* Dependency Edge Table */}
      <div className="bg-slate-950 border border-slate-800 rounded-md overflow-hidden space-y-3 p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-100">Recorded Dependency Edges ({filteredEdges.length})</h3>
            <p className="text-xs text-slate-400">Extracted from AST `import` and `from ... import` statements.</p>
          </div>

          <div className="flex space-x-1 bg-slate-950 border border-slate-800 rounded-lg p-1 text-xs">
            <button
              onClick={() => setFilterType('all')}
              className={`px-3 py-1 rounded font-medium transition ${
                filterType === 'all' ? 'bg-teal-600 text-slate-100' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilterType('internal')}
              className={`px-3 py-1 rounded font-medium transition ${
                filterType === 'internal' ? 'bg-teal-600 text-slate-100' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Internal Only
            </button>
            <button
              onClick={() => setFilterType('external')}
              className={`px-3 py-1 rounded font-medium transition ${
                filterType === 'external' ? 'bg-teal-600 text-slate-100' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              External
            </button>
          </div>
        </div>

        <div className="overflow-x-auto max-h-96 scrollbar-thin">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="sticky top-0 bg-slate-900 border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="py-2.5 px-4">Source File</th>
                <th className="py-2.5 px-4">Target Dependency</th>
                <th className="py-2.5 px-4">Edge Type</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono">
              {filteredEdges.map((e, idx) => (
                <tr key={idx} className="hover:bg-slate-700/30 transition">
                  <td className="py-2.5 px-4 text-slate-200">{e.source}</td>
                  <td className="py-2.5 px-4 text-teal-300">{e.target}</td>
                  <td className="py-2.5 px-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        e.type === 'internal'
                          ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/40'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {e.type}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-right">
                    <button
                      onClick={() => onSelectTarget?.(e.target)}
                      className="text-xs text-teal-400 hover:text-teal-300 font-sans"
                    >
                      Blast Radius
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
