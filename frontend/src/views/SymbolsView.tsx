import React, { useEffect, useState } from 'react';
import {
  Code,
  FileCode,
  Filter,
  Layers,
  Search,
  X,
} from 'lucide-react';
import { fetchSymbols } from '../api';
import type { SymbolInfo } from '../types';

interface SymbolsViewProps {
  repoId: string;
}

export const SymbolsView: React.FC<SymbolsViewProps> = ({ repoId }) => {
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

  const filtered = symbols.filter((s) => {
    const term = searchFilter.toLowerCase();
    return (
      s.name.toLowerCase().includes(term) ||
      (s.qualified_name && s.qualified_name.toLowerCase().includes(term)) ||
      s.file_path.toLowerCase().includes(term)
    );
  });

  const getComplexityBadge = (cc: number) => {
    if (cc <= 3) {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
          CC {cc}
        </span>
      );
    }
    if (cc <= 7) {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-950/40 text-amber-400 border border-amber-800/40">
          CC {cc}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-950/40 text-rose-400 border border-rose-800/40">
        CC {cc} (High)
      </span>
    );
  };

  return (
    <div className="space-y-4">
      {/* Top Filter Bar */}
      <div className="bg-slate-950 border border-slate-800 rounded-md p-4 flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Filter symbols by name or file..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 outline-none focus:border-teal-500 transition"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <div className="flex space-x-1 bg-slate-950 border border-slate-800 rounded-lg p-1">
            <button
              onClick={() => setKindFilter('all')}
              className={`px-3 py-1 rounded text-xs font-medium transition ${
                kindFilter === 'all' ? 'bg-teal-600 text-slate-100' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All ({symbols.length})
            </button>
            <button
              onClick={() => setKindFilter('function')}
              className={`px-3 py-1 rounded text-xs font-medium transition ${
                kindFilter === 'function' ? 'bg-teal-600 text-slate-100' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Functions
            </button>
            <button
              onClick={() => setKindFilter('class')}
              className={`px-3 py-1 rounded text-xs font-medium transition ${
                kindFilter === 'class' ? 'bg-teal-600 text-slate-100' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Classes
            </button>
          </div>
        </div>
      </div>

      {/* Symbols Table */}
      <div className="bg-slate-950 border border-slate-800 rounded-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4">Symbol Name</th>
                <th className="py-3 px-4">Kind</th>
                <th className="py-3 px-4">File Location</th>
                <th className="py-3 px-4">Lines</th>
                <th className="py-3 px-4">Complexity</th>
                <th className="py-3 px-4">Docstring</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-xs">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    Loading extracted AST symbols...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No symbols found matching your filter criteria
                  </td>
                </tr>
              ) : (
                filtered.map((s) => (
                  <tr
                    key={`${s.file_path}:${s.name}:${s.line_start}`}
                    onClick={() => setSelectedSymbol(s)}
                    className="hover:bg-slate-700 cursor-pointer transition"
                  >
                    <td className="py-3 px-4 font-mono font-medium text-teal-300">
                      {s.qualified_name || s.name}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium ${
                          s.kind === 'function'
                            ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/40'
                            : 'bg-purple-950/40 text-purple-400 border border-purple-800/40'
                        }`}
                      >
                        {s.kind === 'function' ? (
                          <Code className="w-3 h-3" />
                        ) : (
                          <Layers className="w-3 h-3" />
                        )}
                        <span>{s.kind}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400">{s.file_path}</td>
                    <td className="py-3 px-4 font-mono text-slate-500">
                      L{s.line_start}-{s.line_end}
                    </td>
                    <td className="py-3 px-4">{getComplexityBadge(s.complexity)}</td>
                    <td className="py-3 px-4 text-slate-400 truncate max-w-xs">
                      {s.docstring || <span className="text-slate-500 italic">None</span>}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Modal / Drawer */}
      {selectedSymbol && (
        <div className="fixed inset-0 bg-black/40  flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-xl w-full p-6 space-y-4 shadow-lg">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center space-x-2">
                <FileCode className="w-5 h-5 text-teal-400" />
                <h3 className="text-base font-bold text-slate-100 font-mono">
                  {selectedSymbol.qualified_name || selectedSymbol.name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedSymbol(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-500 block">File Path</span>
                <span className="font-mono text-slate-200">{selectedSymbol.file_path}</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-500 block">Line Span</span>
                <span className="font-mono text-slate-200">
                  Lines {selectedSymbol.line_start} to {selectedSymbol.line_end}
                </span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-500 block">Symbol Kind</span>
                <span className="capitalize text-slate-200 font-semibold">{selectedSymbol.kind}</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-500 block">Cyclomatic Complexity</span>
                <div className="mt-1">{getComplexityBadge(selectedSymbol.complexity)}</div>
              </div>
            </div>

            {selectedSymbol.docstring && (
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-400">Docstring</span>
                <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 font-sans leading-relaxed">
                  {selectedSymbol.docstring}
                </div>
              </div>
            )}

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setSelectedSymbol(null)}
                className="px-4 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-slate-100 text-xs font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
