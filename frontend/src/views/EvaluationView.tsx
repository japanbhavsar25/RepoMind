import React, { useEffect, useState } from 'react';
import { fetchEvaluation } from '../api';
import type { EvaluationResponse, MetricScores } from '../types';
import { Button, Card, Loading, PageHeader, Spinner } from '../components/ui';

interface EvaluationViewProps {
  repoId: string;
}

type Strategy = 'dense' | 'sparse' | 'hybrid';

const STRATEGIES: Array<{ key: Strategy; name: string; how: string }> = [
  { key: 'dense', name: 'By meaning', how: 'Embeddings (all-MiniLM-L6-v2 in ChromaDB)' },
  { key: 'sparse', name: 'By keyword', how: 'BM25 full-text search in SQLite' },
  { key: 'hybrid', name: 'Both, combined', how: 'Reciprocal Rank Fusion of the two, then reranked (what Ask and Search use)' },
];

const METRICS: Array<{ key: keyof MetricScores; label: string; hint: string; format: (v: number) => string; lowerIsBetter?: boolean }> = [
  { key: 'hit_rate_at_1', label: 'Right file first', hint: 'Hit rate @1', format: (v) => `${Math.round(v * 100)}%` },
  { key: 'hit_rate_at_5', label: 'Right file in top 5', hint: 'Hit rate @5', format: (v) => `${Math.round(v * 100)}%` },
  { key: 'mrr_at_5', label: 'Rank quality', hint: 'MRR @5, 1.0 is perfect', format: (v) => v.toFixed(2) },
  { key: 'avg_latency_ms', label: 'Avg time', hint: 'Per query', format: (v) => `${v.toFixed(0)} ms`, lowerIsBetter: true },
];

export const EvaluationView: React.FC<EvaluationViewProps> = ({ repoId }) => {
  const [data, setData] = useState<EvaluationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runBenchmark = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchEvaluation(repoId, 12);
      setData(res);
    } catch (err) {
      console.error('Failed to run benchmark:', err);
      setError(err instanceof Error ? err.message : 'The benchmark failed to run.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runBenchmark();
  }, [repoId]);

  const best = (metric: (typeof METRICS)[number]) => {
    if (!data) return null;
    const values = STRATEGIES.map((s) => data[s.key][metric.key]);
    return metric.lowerIsBetter ? Math.min(...values) : Math.max(...values);
  };

  return (
    <div className="max-w-4xl space-y-10">
      <PageHeader
        title="How good is the search, really?"
        actions={
          <Button onClick={runBenchmark} disabled={loading}>
            {loading ? (
              <>
                <Spinner className="w-3.5 h-3.5" /> Running…
              </>
            ) : (
              'Run it again'
            )}
          </Button>
        }
      >
        Each test question has a known right answer: hand-written ones where they exist, topped up with &ldquo;where is
        X implemented?&rdquo; for this repo's documented functions. Then each search method is checked on whether it
        brings back the right file.
        {data && ` This run used ${data.dataset_size} questions.`}
      </PageHeader>

      {error && <p className="text-sm text-bad">{error}</p>}

      {!data && loading && <Loading>Running the benchmark…</Loading>}

      {data && (
        <Card className={`overflow-hidden transition-opacity ${loading ? 'opacity-50' : ''}`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-3 px-5 font-medium text-xs text-subtle">Search method</th>
                  {METRICS.map((m) => (
                    <th key={m.key} className="py-3 px-4 text-right whitespace-nowrap">
                      <span className="block text-xs font-medium text-ink">{m.label}</span>
                      <span className="block text-[11px] font-normal text-subtle">{m.hint}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {STRATEGIES.map((s) => (
                  <tr key={s.key} className={s.key === 'hybrid' ? 'bg-accent-soft/40' : ''}>
                    <td className="py-3.5 px-5">
                      <span className="block font-medium text-ink">{s.name}</span>
                      <span className="block text-xs text-subtle">{s.how}</span>
                    </td>
                    {METRICS.map((m) => {
                      const v = data[s.key][m.key];
                      const isBest = v === best(m);
                      return (
                        <td
                          key={m.key}
                          className={`py-3.5 px-4 text-right font-mono tabular-nums ${
                            isBest ? 'text-ink font-semibold' : 'text-muted'
                          }`}
                        >
                          {m.format(v)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-5 py-2.5 border-t border-line text-xs text-subtle">Bold marks the best result in each column.</p>
        </Card>
      )}

      <section className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-6 text-sm text-muted leading-relaxed">
        <div className="space-y-3">
          <h2 className="font-serif text-xl text-ink">Why combine two kinds of search?</h2>
          <p>
            Keyword search is great when you know the name: <code className="text-ink">calculate_tax</code> is either
            there or it isn't. It falls apart on questions like &ldquo;how is billing handled?&rdquo; when the code never
            uses the word &ldquo;billing&rdquo;.
          </p>
          <p>
            Embedding search is the opposite. It gets the gist of a question but can blur exact names together. Neither
            wins everywhere, so RepoMind runs both and merges the rankings.
          </p>
        </div>
        <div className="space-y-3">
          <h2 className="font-serif text-xl text-ink">How the merge works</h2>
          <p>
            Each result gets points from each list based on its position, so something ranked well by both rises to the
            top. The 60 keeps any single list from dominating.
          </p>
          <p className="rounded-md bg-sunk px-4 py-3 font-mono text-[13px] text-ink">
            score(d) = &sum; weight / (60 + rank(d))
          </p>
          <p className="text-xs text-subtle">
            A small benchmark like this is a regression check, not a general score.
          </p>
        </div>
      </section>
    </div>
  );
};
