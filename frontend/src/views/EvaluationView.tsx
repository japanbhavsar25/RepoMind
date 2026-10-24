import React, { useEffect, useState } from 'react';
import {
  Award,
  CheckCircle2,
  Play,
  Sparkles,
} from 'lucide-react';
import { fetchEvaluation } from '../api';
import type { EvaluationResponse } from '../types';

interface EvaluationViewProps {
  repoId: string;
}

export const EvaluationView: React.FC<EvaluationViewProps> = ({ repoId }) => {
  const [data, setData] = useState<EvaluationResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const runBenchmark = async () => {
    setLoading(true);
    try {
      const res = await fetchEvaluation(repoId, 12);
      setData(res);
    } catch (err) {
      console.error('Failed to run benchmark:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runBenchmark();
  }, [repoId]);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="bg-slate-950 border border-slate-800 rounded-lg p-6 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-teal-500/10 border border-teal-800/40 text-teal-300 text-xs font-semibold mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Quantitative Information Retrieval Benchmark</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100">Dense vs. Sparse vs. Hybrid RRF Retrieval</h2>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Measures exact-hit accuracy and query latency across three retrieval strategies on the indexed codebase.
          </p>
        </div>

        <button
          onClick={runBenchmark}
          disabled={loading}
          className="flex items-center space-x-2 px-5 py-2.5 rounded-md bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-50 text-slate-100 font-medium text-xs transition shadow-md  shrink-0"
        >
          <Play className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Evaluating...' : 'Run Benchmark'}</span>
        </button>
      </div>

      {/* Benchmark Metric Cards Comparison */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Dense Card */}
          <div className="bg-slate-950 border border-slate-800 rounded-md p-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Dense-Only</span>
              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">ChromaDB</span>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-xs text-slate-500 block">Hit Rate @ 1</span>
                <span className="text-xl font-bold text-slate-200">
                  {(data.dense.hit_rate_at_1 * 100).toFixed(1)}%
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Hit Rate @ 5</span>
                <span className="text-xl font-bold text-slate-200">
                  {(data.dense.hit_rate_at_5 * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <span className="text-xs text-slate-400">MRR @ 5</span>
                <span className="text-xs font-mono font-bold text-slate-200">{data.dense.mrr_at_5.toFixed(3)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Avg Latency</span>
                <span className="text-xs font-mono text-slate-400">{data.dense.avg_latency_ms.toFixed(1)} ms</span>
              </div>
            </div>
          </div>

          {/* Sparse Card */}
          <div className="bg-slate-950 border border-slate-800 rounded-md p-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Sparse-Only</span>
              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">FTS5 / BM25</span>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-xs text-slate-500 block">Hit Rate @ 1</span>
                <span className="text-xl font-bold text-slate-200">
                  {(data.sparse.hit_rate_at_1 * 100).toFixed(1)}%
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Hit Rate @ 5</span>
                <span className="text-xl font-bold text-slate-200">
                  {(data.sparse.hit_rate_at_5 * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <span className="text-xs text-slate-400">MRR @ 5</span>
                <span className="text-xs font-mono font-bold text-slate-200">{data.sparse.mrr_at_5.toFixed(3)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Avg Latency</span>
                <span className="text-xs font-mono text-slate-400">{data.sparse.avg_latency_ms.toFixed(1)} ms</span>
              </div>
            </div>
          </div>

          {/* Hybrid RRF Card (Winner) */}
          <div className="bg-slate-900 border border-teal-600/40 rounded-md p-5 space-y-4 relative">
            <div className="absolute -top-3 right-4 px-2.5 py-0.5 rounded-full bg-teal-600 text-[10px] font-bold text-slate-100 uppercase tracking-wider shadow">
              Winner [BEST]
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-teal-300 uppercase tracking-wider">Hybrid RRF</span>
              <span className="text-[11px] px-2 py-0.5 rounded bg-teal-950/40 border border-teal-800/40 text-teal-300 font-mono">
                k=60 Fused
              </span>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-xs text-teal-400/80 block">Hit Rate @ 1</span>
                <span className="text-2xl font-extrabold text-emerald-400">
                  {(data.hybrid.hit_rate_at_1 * 100).toFixed(1)}%
                </span>
              </div>
              <div>
                <span className="text-xs text-teal-400/80 block">Hit Rate @ 5</span>
                <span className="text-2xl font-extrabold text-emerald-400">
                  {(data.hybrid.hit_rate_at_5 * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <span className="text-xs text-slate-300 font-medium">MRR @ 5</span>
                <span className="text-xs font-mono font-bold text-teal-300">{data.hybrid.mrr_at_5.toFixed(3)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Avg Latency</span>
                <span className="text-xs font-mono text-amber-300">{data.hybrid.avg_latency_ms.toFixed(1)} ms</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detailed Comparison Table */}
      {data && (
        <div className="bg-slate-950 border border-slate-800 rounded-md overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 bg-slate-900 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">
              Strategy Scorecard ({data.dataset_size} benchmark queries)
            </span>
          </div>

          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950 text-slate-400 text-[11px] font-semibold uppercase">
                <th className="py-3 px-4">Retrieval Strategy</th>
                <th className="py-3 px-4 text-right">Hit Rate @ 1</th>
                <th className="py-3 px-4 text-right">Hit Rate @ 5</th>
                <th className="py-3 px-4 text-right">MRR (Top 5)</th>
                <th className="py-3 px-4 text-right">Avg Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono">
              <tr className="hover:bg-slate-700/30">
                <td className="py-3 px-4 text-slate-300 font-sans">Dense-Only (ChromaDB all-MiniLM-L6-v2)</td>
                <td className="py-3 px-4 text-right">{(data.dense.hit_rate_at_1 * 100).toFixed(1)}%</td>
                <td className="py-3 px-4 text-right">{(data.dense.hit_rate_at_5 * 100).toFixed(1)}%</td>
                <td className="py-3 px-4 text-right">{data.dense.mrr_at_5.toFixed(3)}</td>
                <td className="py-3 px-4 text-right text-slate-400">{data.dense.avg_latency_ms.toFixed(1)} ms</td>
              </tr>
              <tr className="hover:bg-slate-700/30">
                <td className="py-3 px-4 text-slate-300 font-sans">Sparse-Only (SQLite FTS5 BM25)</td>
                <td className="py-3 px-4 text-right">{(data.sparse.hit_rate_at_1 * 100).toFixed(1)}%</td>
                <td className="py-3 px-4 text-right">{(data.sparse.hit_rate_at_5 * 100).toFixed(1)}%</td>
                <td className="py-3 px-4 text-right">{data.sparse.mrr_at_5.toFixed(3)}</td>
                <td className="py-3 px-4 text-right text-slate-400">{data.sparse.avg_latency_ms.toFixed(1)} ms</td>
              </tr>
              <tr className="bg-teal-950/20 font-bold hover:bg-teal-950/40">
                <td className="py-3 px-4 text-teal-300 font-sans flex items-center space-x-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>RepoMind Hybrid RRF (k=60 Weighted)</span>
                </td>
                <td className="py-3 px-4 text-right text-emerald-400">{(data.hybrid.hit_rate_at_1 * 100).toFixed(1)}%</td>
                <td className="py-3 px-4 text-right text-emerald-400">{(data.hybrid.hit_rate_at_5 * 100).toFixed(1)}%</td>
                <td className="py-3 px-4 text-right text-teal-300">{data.hybrid.mrr_at_5.toFixed(3)}</td>
                <td className="py-3 px-4 text-right text-amber-300">{data.hybrid.avg_latency_ms.toFixed(1)} ms</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Engineering Takeaways Box */}
      <div className="bg-slate-900 border border-slate-800 rounded-md p-5 space-y-3">
        <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
          <Award className="w-4 h-4 text-teal-400" />
          <span>Why Reciprocal Rank Fusion (RRF) Excels for Codebases</span>
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          Code search poses unique challenges: queries with exact identifiers (e.g. <code>calculate_tax</code> or <code>User.is_admin</code>)
          suffer from semantic distortion in dense vector embeddings, while natural-language concept questions (e.g. &quot;how is billing handled?&quot;)
          fail in lexical sparse search due to the vocabulary mismatch problem.
        </p>
        <p className="text-xs text-slate-300 leading-relaxed">
          RepoMind solves this by dynamically detecting query intent, scoring candidates across both SQLite FTS5 disk-based BM25
          and dense cosine vector similarity, and fusing them via Reciprocal Rank Fusion:
        </p>
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono text-[11px] text-teal-300 text-center">
          RRF_Score(d) = &sum; [ weight_r / (60 + rank_r(d)) ]
        </div>
      </div>
    </div>
  );
};
