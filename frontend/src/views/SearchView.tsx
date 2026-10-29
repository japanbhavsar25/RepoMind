import React, { useEffect, useState } from 'react';
import { Search as SearchIcon } from 'lucide-react';
import { executeSearch, fetchSymbols } from '../api';
import type { SearchResponse } from '../types';
import { Button, Chip, CodeBlock, Empty, Notice, PageHeader, Tag, inputClass, type Tone } from '../components/ui';

const ECOMMERCE_SUGGESTIONS = [
  'calculate_tax',
  'StripeAdapter',
  'hash_token',
  'purge_expired_sessions',
  'where are passwords hashed',
];

const MATCH_LABELS: Record<string, { label: string; tone: Tone; hint: string }> = {
  hybrid: { label: 'name + meaning', tone: 'accent', hint: 'Found by both keyword and semantic search' },
  fts5_sparse: { label: 'keyword', tone: 'warn', hint: 'Found by keyword search' },
  symbol_exact: { label: 'exact name', tone: 'good', hint: 'The symbol name matches exactly' },
};

interface SearchViewProps {
  repoId: string;
  onNavigateToFile?: (path: string) => void;
}

export const SearchView: React.FC<SearchViewProps> = ({ repoId, onNavigateToFile }) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [symbolSuggestions, setSymbolSuggestions] = useState<string[]>([]);
  const suggestions = repoId === 'ecommerce_sample' ? ECOMMERCE_SUGGESTIONS : symbolSuggestions;

  // For other repos, suggest a few of their own public names
  useEffect(() => {
    if (repoId === 'ecommerce_sample') return;
    let cancelled = false;
    fetchSymbols(repoId)
      .then((res) => {
        if (cancelled) return;
        const names = res.symbols
          .filter((s) => !s.name.startsWith('_') && !/(^|\/)tests?\//.test(s.file_path))
          .sort((a, b) => b.complexity - a.complexity)
          .map((s) => s.name);
        setSymbolSuggestions([...new Set(names)].slice(0, 5));
      })
      .catch(() => !cancelled && setSymbolSuggestions([]));
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  const handleSearch = async (termToSearch?: string) => {
    const q = termToSearch || query;
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await executeSearch(q, repoId, 6);
      setResponse(res);
    } catch (err) {
      console.error('Search error:', err);
      setError(err instanceof Error ? err.message : 'Search failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-8">
      <PageHeader title="Search the code">
        Type a name like <code className="text-ink">calculate_tax</code> or describe what you're after in plain words.
        Both work.
      </PageHeader>

      <div className="space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSearch();
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <SearchIcon className="w-4 h-4 text-subtle absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Function, class, or an idea…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search query"
              className={`${inputClass} pl-10`}
            />
          </div>
          <Button type="submit" variant="primary" disabled={loading || !query.trim()}>
            {loading ? 'Searching…' : 'Search'}
          </Button>
        </form>

        {suggestions.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-subtle mr-1">For example</span>
            {suggestions.map((sug) => (
              <Chip
                key={sug}
                mono={!sug.includes(' ')}
                onClick={() => {
                  setQuery(sug);
                  handleSearch(sug);
                }}
              >
                {sug}
              </Chip>
            ))}
          </div>
        )}
      </div>

      {error && <Notice tone="error">{error}</Notice>}

      {response && (
        <section className="space-y-5">
          <p className="text-sm text-muted border-b border-line pb-3">
            {response.intent === 'code_identifier'
              ? 'That looks like a name, so exact matches are ranked first.'
              : 'That reads like a description, so results are matched by meaning as well as keywords.'}{' '}
            <span className="text-subtle">
              Showing {response.results.length} of {response.total_candidates} candidates.
            </span>
          </p>

          {response.results.length === 0 ? (
            <Empty>Nothing matched &ldquo;{response.query}&rdquo;. Try a different name or a broader description.</Empty>
          ) : (
            <ol className="space-y-6">
              {response.results.map((item, idx) => {
                const match = MATCH_LABELS[item.match_type] ?? {
                  label: item.match_type,
                  tone: 'neutral' as Tone,
                  hint: '',
                };
                return (
                  <li key={item.chunk_id || idx} className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <button
                        onClick={() => onNavigateToFile?.(item.file_path)}
                        className="font-mono text-sm text-ink hover:text-accent hover:underline underline-offset-2 truncate text-left"
                      >
                        {item.file_path}
                        <span className="text-subtle">
                          :{item.line_start}–{item.line_end}
                        </span>
                      </button>
                      <span className="flex items-center gap-2" title={match.hint}>
                        <Tag tone={match.tone}>{match.label}</Tag>
                        <span className="text-[11px] font-mono text-subtle">score {item.score}</span>
                      </span>
                    </div>
                    <CodeBlock className="max-h-64 overflow-y-auto">{item.snippet}</CodeBlock>
                  </li>
                );
              })}
            </ol>
          )}
        </section>
      )}
    </div>
  );
};
