import React, { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { fetchGraph, fetchImpact } from '../api';
import type { ImpactResponse } from '../types';
import { Button, Chip, Empty, Notice, PageHeader, SectionTitle, Spinner, inputClass } from '../components/ui';

interface ImpactViewProps {
  repoId: string;
  initialTarget?: string;
  onNavigateToFile?: (path: string) => void;
}

const FileList: React.FC<{ files: string[]; onOpen?: (path: string) => void }> = ({ files, onOpen }) => (
  <ul className="divide-y divide-line border-y border-line">
    {files.map((f) => (
      <li key={f}>
        <button
          onClick={() => onOpen?.(f)}
          className="w-full text-left py-2 px-1 font-mono text-[13px] text-ink hover:text-accent truncate"
        >
          {f}
        </button>
      </li>
    ))}
  </ul>
);

export const ImpactView: React.FC<ImpactViewProps> = ({ repoId, initialTarget, onNavigateToFile }) => {
  const [target, setTarget] = useState(initialTarget ?? '');
  const [impact, setImpact] = useState<ImpactResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const runImpact = async (t: string) => {
    if (!t.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchImpact(t.trim(), repoId);
      setImpact(res);
    } catch (err) {
      console.error('Failed to compute impact:', err);
      setError(err instanceof Error ? err.message : 'Could not work out the impact.');
    } finally {
      setLoading(false);
    }
  };

  // Suggest this repo's most depended-on files; start with the top one if nothing was picked
  useEffect(() => {
    let cancelled = false;
    setImpact(null);
    if (initialTarget) {
      setTarget(initialTarget);
      runImpact(initialTarget);
    }
    fetchGraph(repoId)
      .then((g) => {
        if (cancelled) return;
        const top = g.pagerank_leaderboard.slice(0, 5).map((p) => p.file);
        setSuggestions(top);
        if (!initialTarget && top[0]) {
          setTarget(top[0]);
          runImpact(top[0]);
        }
      })
      .catch(() => !cancelled && setSuggestions([]));
    return () => {
      cancelled = true;
    };
  }, [initialTarget, repoId]);

  const direct = impact?.direct_importers ?? [];
  const indirect = (impact?.transitive_dependents ?? []).filter((f) => !direct.includes(f));
  const total = impact?.transitive_dependents.length ?? 0;

  return (
    <div className="max-w-4xl space-y-8">
      <PageHeader title="What breaks if I change this?">
        Pick a file or a function. RepoMind follows the imports backwards to find everything that relies on it, directly
        or through other files.
      </PageHeader>

      <div className="space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runImpact(target);
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-subtle absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="models.py, or a function name"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              aria-label="File or function"
              className={`${inputClass} pl-10 font-mono`}
            />
          </div>
          <Button type="submit" variant="primary" disabled={loading || !target.trim()}>
            {loading ? 'Checking…' : 'Check'}
          </Button>
        </form>

        {suggestions.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-subtle mr-1">Most depended-on</span>
            {suggestions.map((st) => (
              <Chip
                key={st}
                mono
                onClick={() => {
                  setTarget(st);
                  runImpact(st);
                }}
              >
                {st}
              </Chip>
            ))}
          </div>
        )}
      </div>

      {error && <Notice tone="error">{error}</Notice>}

      {loading && !impact && (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Spinner className="w-4 h-4 text-accent" /> Following the imports…
        </p>
      )}

      {impact && (
        <article className={`space-y-10 transition-opacity ${loading ? 'opacity-50' : ''}`}>
          <div className="border-l-4 border-accent pl-5 py-1">
            <p className="font-serif text-2xl sm:text-[1.7rem] leading-snug text-ink">
              {total === 0 ? (
                <>
                  Nothing else in the project depends on <code className="text-accent">{impact.target}</code>.
                </>
              ) : (
                <>
                  Changing <code className="text-accent">{impact.target}</code> could affect{' '}
                  <span className="text-accent">
                    {total} {total === 1 ? 'file' : 'files'}
                  </span>
                  .
                </>
              )}
            </p>
            <p className="mt-2 text-sm text-muted">
              {direct.length} import it directly, {indirect.length} through other files. Graph importance{' '}
              <span className="font-mono">{impact.pagerank.toFixed(3)}</span>, highest complexity{' '}
              <span className="font-mono">{impact.complexity}</span>.
            </p>
          </div>

          {total > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <section>
                <SectionTitle aside={String(direct.length)}>Import it directly</SectionTitle>
                {direct.length > 0 ? (
                  <FileList files={direct} onOpen={onNavigateToFile} />
                ) : (
                  <p className="text-sm text-muted">None.</p>
                )}
              </section>
              <section>
                <SectionTitle aside={String(indirect.length)}>Depend on it through other files</SectionTitle>
                {indirect.length > 0 ? (
                  <FileList files={indirect} onOpen={onNavigateToFile} />
                ) : (
                  <p className="text-sm text-muted">None.</p>
                )}
              </section>
            </div>
          )}

          {impact.callers.length > 0 && (
            <section>
              <SectionTitle aside={String(impact.callers.length)}>Places that call it</SectionTitle>
              <ul className="divide-y divide-line border-y border-line">
                {impact.callers.map((c, idx) => (
                  <li key={idx} className="flex items-center justify-between gap-3 py-2 px-1 text-[13px] font-mono">
                    <button
                      onClick={() => onNavigateToFile?.(c.caller_file)}
                      className="min-w-0 truncate text-left hover:text-accent"
                    >
                      <span className="text-muted">{c.caller_file}</span>
                      <span className="text-subtle"> · </span>
                      <span className="text-ink">{c.caller_symbol}</span>
                    </button>
                    <span className="text-xs text-subtle shrink-0">line {c.line_number}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {impact.limitations.length > 0 && (
            <aside className="rounded-lg bg-sunk px-5 py-4 text-sm">
              <p className="font-medium text-ink mb-2">Keep in mind</p>
              <ul className="list-disc pl-5 space-y-1 text-muted marker:text-subtle">
                {impact.limitations.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </aside>
          )}
        </article>
      )}

      {!impact && !loading && !error && suggestions.length === 0 && (
        <Empty>Type a file or function name above to see what depends on it.</Empty>
      )}
    </div>
  );
};
