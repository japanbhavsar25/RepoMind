import React, { useState } from 'react';
import {
  FileCode,
  Flame,
  Search as SearchIcon,
  Sparkles,
} from 'lucide-react';
import { executeSearch } from '../api';
import type { SearchResponse } from '../types';

interface SearchViewProps {
  repoId: string;
  onNavigateToFile?: (path: string) => void;
}

export const SearchView: React.FC<SearchViewProps> = ({ repoId, onNavigateToFile }) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);

  const suggestions = [
    'calculate_tax',
    'StripeAdapter',
    'hash_token',
    'purge_expired_sessions',
    'AuthenticationService',
    'OrderService.checkout',
  ];

  const handleSearch = async (termToSearch?: string) => {
    const q = termToSearch || query;
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await executeSearch(q, repoId, 6);
      setResponse(res);
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getMatchBadge = (matchType: string) => {
    switch (matchType) {
      case 'hybrid':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-teal-950/40 text-teal-400 border border-teal-800/40">
            Hybrid RRF
          </span>
        );
      case 'fts5_sparse':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/40 text-amber-400 border border-amber-800/40">
            SQLite FTS5
          </span>
        );
      case 'symbol_exact':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
            Symbol AST Exact
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300">
            {matchType}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Search Header & Input */}
      <div className="bg-slate-950 border border-slate-800 rounded-lg p-6 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
            <SearchIcon className="w-5 h-5 text-teal-400" />
            <span>Hybrid Code & Identifier Search</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Combines SQLite FTS5 disk-based BM25 sparse matching with dense semantic embeddings via Reciprocal Rank Fusion.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSearch();
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <SearchIcon className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
            <input
              type="text"
              placeholder="Search functions, classes, snake_case, camelCase, or concepts..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-md pl-10 pr-4 py-2.5 text-sm text-slate-200 outline-none focus:border-teal-500 transition font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2.5 rounded-md bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-50 text-slate-100 font-medium text-sm transition shadow-md "
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>

        {/* Suggestion Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-[11px] text-slate-500 font-medium">Quick Suggestions:</span>
          {suggestions.map((sug) => (
            <button
              key={sug}
              onClick={() => {
                setQuery(sug);
                handleSearch(sug);
              }}
              className="px-2.5 py-1 rounded-md bg-slate-950 hover:bg-slate-700 border border-slate-800 text-[11px] font-mono text-slate-300 transition"
            >
              {sug}
            </button>
          ))}
        </div>
      </div>

      {/* Intent & Result Status Banner */}
      {response && (
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400">Query Intent:</span>
            <span
              className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                response.intent === 'code_identifier'
                  ? 'bg-amber-950/40/80 text-amber-300 border border-amber-800/40'
                  : 'bg-teal-950/80 text-teal-300 border border-teal-800/40'
              }`}
            >
              {response.intent === 'code_identifier' ? (
                <Flame className="w-3 h-3 text-amber-400" />
              ) : (
                <Sparkles className="w-3 h-3 text-teal-400" />
              )}
              <span>
                {response.intent === 'code_identifier'
                  ? 'Exact Identifier (Boosted Sparse BM25)'
                  : 'Natural Language (Semantic Balanced)'}
              </span>
            </span>
          </div>

          <span className="text-xs text-slate-500">
            {response.results.length} results of {response.total_candidates} candidates
          </span>
        </div>
      )}

      {/* Results List */}
      <div className="space-y-3">
        {response?.results.map((item, idx) => (
          <div
            key={item.chunk_id || idx}
            className="bg-slate-950 border border-slate-800 rounded-md p-4 space-y-3 hover:border-slate-700 transition"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
              <div className="flex items-center space-x-2 truncate">
                <FileCode className="w-4 h-4 text-teal-400 shrink-0" />
                <button
                  onClick={() => onNavigateToFile?.(item.file_path)}
                  className="font-mono text-xs font-semibold text-slate-200 hover:text-teal-400 transition truncate underline-offset-2 hover:underline"
                >
                  {item.file_path}
                </button>
                <span className="text-xs font-mono text-slate-500">
                  L{item.line_start}-{item.line_end}
                </span>
              </div>

              <div className="flex items-center space-x-2 shrink-0">
                {getMatchBadge(item.match_type)}
                <span className="text-xs font-mono text-slate-400">Score: {item.score}</span>
              </div>
            </div>

            {/* Code Snippet Box */}
            <pre className="bg-[#0a0d14] border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {item.snippet}
            </pre>
          </div>
        ))}

        {response && response.results.length === 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-md p-8 text-center text-slate-500 text-sm">
            No matching code chunks found for &quot;{response.query}&quot;
          </div>
        )}
      </div>
    </div>
  );
};
