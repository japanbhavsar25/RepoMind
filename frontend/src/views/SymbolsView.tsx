import React, { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
import { fetchSymbols } from '../api';
import type { SymbolInfo } from '../types';
import { Button, PageHeader, Segmented, Tag, inputClass, type Tone } from '../components/ui';
import { useFocusTrap } from '../useFocusTrap';

interface SymbolsViewProps {
  repoId: string;
  onNavigateToFile?: (path: string, line?: number) => void;
}

function complexity(cc: number): { label: string; tone: Tone } {
  if (cc <= 3) return { label: 'simple', tone: 'good' };
  if (cc <= 7) return { label: 'moderate', tone: 'warn' };
  return { label: 'complex', tone: 'bad' };
}

const ComplexityTag: React.FC<{ cc: number }> = ({ cc }) => {
  const c = complexity(cc);
  return (
    <Tag tone={c.tone}>
      {c.label} · {cc}
    </Tag>
  );
};

export const SymbolsView: React.FC<SymbolsViewProps> = ({ repoId, onNavigateToFile }) => {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState('');
  const [kindFilter, setKindFilter] = useState<'all' | 'function' | 'class'>('all');
  const [selectedSymbol, setSelectedSymbol] = useState<SymbolInfo | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetchSymbols(repoId, kindFilter === 'all' ? undefined : kindFilter)
      .then((res) => {
        if (isMounted) setSymbols(res.symbols);
      })
      .catch((err) => console.error('Failed to fetch symbols:', err))
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [repoId, kindFilter]);

  useEffect(() => {
    if (!selectedSymbol) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setSelectedSymbol(null);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedSymbol]);

  const dialogRef = useFocusTrap<HTMLDivElement>(selectedSymbol != null);

  const filtered = symbols.filter((s) => {
    const term = searchFilter.toLowerCase();
    return (
      s.name.toLowerCase().includes(term) ||
      (s.qualified_name && s.qualified_name.toLowerCase().includes(term)) ||
      s.file_path.toLowerCase().includes(term)
    );
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Every function and class">
        Pulled straight from the syntax tree. The complexity number counts the decision points in a function; higher
        means more paths to test.
      </PageHeader>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-subtle absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Filter by name or file…"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            aria-label="Filter symbols"
            className={`${inputClass} pl-9 py-2`}
          />
        </div>
        <Segmented
          value={kindFilter}
          onChange={setKindFilter}
          options={[
            { value: 'all', label: 'Everything' },
            { value: 'function', label: 'Functions' },
            { value: 'class', label: 'Classes' },
          ]}
        />
      </div>

      <div className="bg-surface border border-line rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-subtle">
                <th className="py-2.5 px-4 font-medium">Name</th>
                <th className="py-2.5 px-4 font-medium">File</th>
                <th className="py-2.5 px-4 font-medium">Lines</th>
                <th className="py-2.5 px-4 font-medium">Complexity</th>
                <th className="py-2.5 px-4 font-medium">What it says it does</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-muted">
                    Loading…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-muted">
                    Nothing matches &ldquo;{searchFilter}&rdquo;.
                  </td>
                </tr>
              ) : (
                filtered.map((s) => (
                  <tr
                    key={`${s.file_path}:${s.name}:${s.line_start}`}
                    onClick={() => setSelectedSymbol(s)}
                    className="hover:bg-sunk cursor-pointer transition"
                  >
                    <td className="py-2.5 px-4 font-mono text-[13px] text-ink whitespace-nowrap">
                      {/* A real button, so the details can be opened from the keyboard too */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSymbol(s);
                        }}
                        className="text-left rounded-sm hover:underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-accent"
                      >
                        <span className="text-subtle mr-1.5 text-[11px]">{s.kind === 'class' ? 'class' : 'def'}</span>
                        {s.qualified_name || s.name}
                      </button>
                    </td>
                    <td className="py-2.5 px-4 font-mono text-xs text-muted whitespace-nowrap">{s.file_path}</td>
                    <td className="py-2.5 px-4 font-mono text-xs text-subtle whitespace-nowrap tabular-nums">
                      {s.line_start}–{s.line_end}
                    </td>
                    <td className="py-2.5 px-4 whitespace-nowrap">
                      <ComplexityTag cc={s.complexity} />
                    </td>
                    <td className="py-2.5 px-4 text-muted truncate max-w-xs">
                      {s.docstring || <span className="text-subtle italic">no docstring</span>}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedSymbol && (
        <div
          className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedSymbol(null)}
        >
          <div
            ref={dialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={selectedSymbol.qualified_name || selectedSymbol.name}
            className="bg-surface border border-line rounded-xl max-w-xl w-full p-6 space-y-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-xs text-subtle">{selectedSymbol.kind === 'class' ? 'Class' : 'Function'}</p>
                <h3 className="font-mono text-lg text-ink break-all">
                  {selectedSymbol.qualified_name || selectedSymbol.name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedSymbol(null)}
                className="p-1 rounded-md text-subtle hover:text-ink hover:bg-sunk"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="text-subtle">File</dt>
              <dd className="font-mono text-ink break-all">{selectedSymbol.file_path}</dd>
              <dt className="text-subtle">Lines</dt>
              <dd className="font-mono text-ink">
                {selectedSymbol.line_start}–{selectedSymbol.line_end}
              </dd>
              <dt className="text-subtle">Complexity</dt>
              <dd>
                <ComplexityTag cc={selectedSymbol.complexity} />
              </dd>
            </dl>

            {selectedSymbol.docstring && (
              <blockquote className="border-l-2 border-line-strong pl-4 text-sm text-muted leading-relaxed whitespace-pre-wrap">
                {selectedSymbol.docstring}
              </blockquote>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <Button variant="quiet" onClick={() => setSelectedSymbol(null)}>
                Close
              </Button>
              {onNavigateToFile && (
                <Button
                  variant="primary"
                  onClick={() => {
                    onNavigateToFile(selectedSymbol.file_path, selectedSymbol.line_start);
                    setSelectedSymbol(null);
                  }}
                >
                  Open the file
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
