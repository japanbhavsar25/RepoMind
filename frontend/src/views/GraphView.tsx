import React, { useEffect, useState } from 'react';
import { fetchGraph } from '../api';
import type { GraphDataResponse } from '../types';
import { Card, Loading, PageHeader, Segmented, SectionTitle, Tag } from '../components/ui';

interface GraphViewProps {
  repoId: string;
  onSelectTarget?: (target: string) => void;
}

export const GraphView: React.FC<GraphViewProps> = ({ repoId, onSelectTarget }) => {
  const [data, setData] = useState<GraphDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState<'all' | 'internal' | 'external'>('internal');

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
    return <Loading>Working out which files depend on which…</Loading>;
  }

  const leaders = data?.pagerank_leaderboard ?? [];
  const topScore = leaders[0]?.score || 1;
  const cycles = data?.cycles ?? [];
  const orphans = data?.orphans ?? [];

  return (
    <div className="space-y-10">
      <PageHeader title="How the files depend on each other">
        Built from every <code className="text-ink">import</code> statement. {data?.nodes.length ?? 0} modules and
        libraries, connected by {data?.edges.length ?? 0} imports.
      </PageHeader>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-10">
        <section className="lg:col-span-3">
          <SectionTitle aside="ranked by PageRank">The files everything leans on</SectionTitle>
          <p className="text-sm text-muted mb-4 leading-relaxed">
            The more (and more important) files import something, the higher it ranks. Changes here travel furthest.
            Click one to see what it would affect.
          </p>
          <ol className="space-y-1">
            {leaders.map((item, idx) => (
              <li key={item.file}>
                <button
                  onClick={() => onSelectTarget?.(item.file)}
                  className="group w-full grid grid-cols-[1.5rem_1fr_auto] items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-surface transition"
                >
                  <span className="text-xs text-subtle tabular-nums">{idx + 1}</span>
                  <span className="min-w-0">
                    <span className="block font-mono text-[13px] text-ink truncate group-hover:text-accent">
                      {item.file}
                    </span>
                    <span className="mt-1.5 block h-1 rounded-full bg-sunk overflow-hidden">
                      <span
                        className="block h-full rounded-full bg-accent/70"
                        style={{ width: `${Math.max(4, (item.score / topScore) * 100)}%` }}
                      />
                    </span>
                  </span>
                  <span className="font-mono text-xs text-subtle tabular-nums">{item.score.toFixed(3)}</span>
                </button>
              </li>
            ))}
          </ol>
        </section>

        <div className="lg:col-span-2 space-y-8">
          <section>
            <SectionTitle>Import loops</SectionTitle>
            {cycles.length > 0 ? (
              <ul className="space-y-2">
                {cycles.map((cyc, idx) => (
                  <li key={idx} className="rounded-md bg-bad-soft text-bad px-3 py-2 text-xs font-mono leading-relaxed">
                    {cyc.join(' → ')} → {cyc[0]}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">None. No two files import each other in a circle.</p>
            )}
          </section>

          <section>
            <SectionTitle>Files nobody imports</SectionTitle>
            <p className="text-sm text-muted mb-3 leading-relaxed">
              These don't import other project files and nothing imports them. Usually scripts or entry points, but
              sometimes dead code.
            </p>
            {orphans.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {orphans.map((orph) => (
                  <button
                    key={orph}
                    onClick={() => onSelectTarget?.(orph)}
                    className="rounded bg-warn-soft text-warn px-2 py-0.5 text-xs font-mono hover:underline underline-offset-2"
                  >
                    {orph}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">None found.</p>
            )}
          </section>
        </div>
      </div>

      <section>
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-3">
          <div>
            <h2 className="font-serif text-xl text-ink">Every import</h2>
            <p className="text-sm text-muted">{filteredEdges.length} shown</p>
          </div>
          <Segmented
            value={filterType}
            onChange={setFilterType}
            options={[
              { value: 'internal', label: 'Within the project' },
              { value: 'external', label: 'Libraries' },
              { value: 'all', label: 'All' },
            ]}
          />
        </div>

        <Card className="overflow-hidden">
          <div className="overflow-auto max-h-[28rem]">
            <table className="w-full text-left text-sm border-collapse">
              <thead className="sticky top-0 bg-surface border-b border-line text-xs text-subtle">
                <tr>
                  <th className="py-2.5 px-4 font-medium">File</th>
                  <th className="py-2.5 px-4 font-medium">imports</th>
                  <th className="py-2.5 px-4 font-medium" />
                  <th className="py-2.5 px-4" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line font-mono text-[13px]">
                {filteredEdges.map((e, idx) => (
                  <tr key={idx} className="hover:bg-sunk/60">
                    <td className="py-2 px-4 text-ink whitespace-nowrap">{e.source}</td>
                    <td className="py-2 px-4 text-muted whitespace-nowrap">{e.target}</td>
                    <td className="py-2 px-4">
                      {e.type !== 'internal' && <Tag className="font-sans">library</Tag>}
                    </td>
                    <td className="py-2 px-4 text-right">
                      <button
                        onClick={() => onSelectTarget?.(e.target)}
                        className="font-sans text-xs text-accent hover:underline underline-offset-2 whitespace-nowrap"
                      >
                        What depends on this?
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>
    </div>
  );
};
