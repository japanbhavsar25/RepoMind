import React, { useState } from 'react';
import {
  Bot,
  ExternalLink,
  FileCode,
  HelpCircle,
  ShieldCheck,
} from 'lucide-react';
import { askQuestion } from '../api';
import type { AskResponse } from '../types';

interface AskViewProps {
  repoId: string;
  onNavigateToFile?: (path: string) => void;
}

export const AskView: React.FC<AskViewProps> = ({ repoId, onNavigateToFile }) => {
  const [question, setQuestion] = useState('');
  const [useLlm, setUseLlm] = useState(true); // Falls back to evidence-only when no LLM is configured
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);

  const sampleQuestions = [
    'Where is password hashing implemented?',
    'How does order checkout validate inventory?',
    'What payment gateways are supported?',
    'Which background task is orphaned with no incoming imports?',
  ];

  const handleAsk = async (queryText?: string) => {
    const q = queryText || question;
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await askQuestion(q, repoId, useLlm);
      setResponse(res);
    } catch (err) {
      console.error('Ask error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header & Ask Box */}
      <div className="bg-slate-950 border border-slate-800 rounded-lg p-6 shadow-sm space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
            <Bot className="w-5 h-5 text-teal-400" />
            <span>Grounded Codebase Question Answering</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Answers are strictly grounded in retrieved AST chunks and verified against SQLite source coordinates.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
          className="space-y-3"
        >
          <div className="relative">
            <input
              type="text"
              placeholder="Ask a question about the repository..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-md pl-4 pr-24 py-3 text-sm text-slate-200 outline-none focus:border-teal-500 transition"
            />
            <button
              type="submit"
              disabled={loading}
              className="absolute right-2 top-2 px-4 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-50 text-slate-100 font-medium text-xs transition"
            >
              {loading ? 'Analyzing...' : 'Ask'}
            </button>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            {/* Quick Sample Questions */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-slate-500 font-medium">Try:</span>
              {sampleQuestions.map((sq) => (
                <button
                  key={sq}
                  type="button"
                  onClick={() => {
                    setQuestion(sq);
                    handleAsk(sq);
                  }}
                  className="px-2 py-0.5 rounded bg-slate-950 hover:bg-slate-700 border border-slate-800 text-[11px] text-slate-400 transition"
                >
                  {sq}
                </button>
              ))}
            </div>

            {/* Local LLM Toggle */}
            <label className="flex items-center space-x-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                className="w-3.5 h-3.5 text-teal-400 rounded bg-slate-950 border-slate-700 focus:ring-0 cursor-pointer"
              />
              <span className="text-xs text-slate-400">
                Generate AI answer <span className="text-slate-500">(Groq or local Ollama)</span>
              </span>
            </label>
          </div>
        </form>
      </div>

      {/* Answer & Evidence Display */}
      {response && (
        <div className="space-y-4">
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-semibold text-slate-200">
                  Groundedness & Citation Confidence:
                </span>
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-950/40 text-emerald-300 border border-emerald-800/40">
                  {Math.round(response.citation_confidence * 100)}% Verified
                </span>
              </div>

              <span className="text-xs text-slate-500 font-mono">
                Model: {response.model_used}
                {response.latency_ms != null && ` · ${(response.latency_ms / 1000).toFixed(1)}s`}
                {response.prompt_tokens != null &&
                  ` · ${response.prompt_tokens + (response.completion_tokens ?? 0)} tokens`}
              </span>
            </div>

            <div className="text-sm text-slate-200 leading-relaxed font-sans whitespace-pre-wrap">
              {response.answer}
            </div>
          </div>

          {/* Citations & Source Evidence Cards */}
          {response.citations.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-1.5 px-1">
                <FileCode className="w-3.5 h-3.5 text-teal-400" />
                <span>Supporting Source Evidence ({response.citations.length})</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {response.citations.map((cite, idx) => (
                  <div
                    key={idx}
                    className="bg-slate-950 border border-slate-800 rounded-md p-3.5 space-y-2 hover:border-slate-700 transition"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5 truncate">
                        <FileCode className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                        <span className="text-xs font-mono font-medium text-slate-200 truncate">
                          {cite.file_path}:{cite.line_start}-{cite.line_end}
                        </span>
                      </div>

                      <button
                        onClick={() => onNavigateToFile?.(cite.file_path)}
                        className="flex items-center space-x-1 text-[11px] text-teal-400 hover:text-teal-300 font-medium transition"
                      >
                        <span>Inspect</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>

                    <pre className="bg-[#0a0d14] border border-slate-800 rounded p-2 text-[11px] font-mono text-slate-500 overflow-x-auto whitespace-pre-wrap max-h-32">
                      {cite.snippet}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!response && !loading && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center space-y-2">
          <HelpCircle className="w-8 h-8 text-slate-500 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-300">Ask a Question with Verifiable Evidence</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            RepoMind indexes source files into symbol chunks, retrieves relevant context using weighted RRF, and verifies exact line-number citations.
          </p>
        </div>
      )}
    </div>
  );
};
