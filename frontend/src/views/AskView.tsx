import React, { useEffect, useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { askQuestion, fetchSymbols } from '../api';
import type { AskResponse, SymbolInfo } from '../types';
import { Button, Chip, CodeBlock, Notice, PageHeader, Spinner, Tag, type Tone } from '../components/ui';

const ECOMMERCE_SAMPLE_QUESTIONS = [
  'Where is password hashing implemented?',
  'How does order checkout validate inventory?',
  'What payment gateways are supported?',
  'Which background task is orphaned with no incoming imports?',
];

const GENERIC_QUESTIONS = [
  'What are the main modules and what does each do?',
  'Where is error handling implemented?',
];

/** Build starter questions from a repo's own public classes and most complex functions. */
function suggestionsFromSymbols(symbols: SymbolInfo[]): string[] {
  // Skip private names, tests, and packaging/tooling scripts (setup.py etc.)
  const isPublic = (s: SymbolInfo) =>
    !s.name.startsWith('_') &&
    !/(^|\/)(tests?|docs|examples)\//.test(s.file_path) &&
    !/(^|\/)(setup|conftest|noxfile|tasks)\.py$/.test(s.file_path);
  const classes = symbols
    .filter((s) => s.kind === 'class' && isPublic(s))
    .sort((a, b) => Number(Boolean(b.docstring)) - Number(Boolean(a.docstring)))
    .slice(0, 2)
    .map((s) => `What is the ${s.name} class responsible for?`);
  const functions = symbols
    .filter((s) => s.kind === 'function' && isPublic(s) && !s.name.startsWith('test'))
    .sort((a, b) => b.complexity - a.complexity)
    .slice(0, 2)
    .map((s) => `How does ${s.name} work?`);
  const picked = [...classes, ...functions];
  return picked.length > 0 ? picked : GENERIC_QUESTIONS;
}

// Matches citations like [pkg/module.py:12-40] or [module.py:7] inside an answer.
const CITATION_RE = /\[([^\]\s]+\.py):(\d+)(?:-(\d+))?\]/g;

/** Render answer text with clickable citations and `inline code`. */
function renderAnswer(text: string, onOpen?: (path: string) => void): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(CITATION_RE)) {
    const idx = m.index ?? 0;
    out.push(...renderInlineCode(text.slice(last, idx), out.length));
    const [, path, start, end] = m;
    out.push(
      <button
        key={`c${idx}`}
        type="button"
        onClick={() => onOpen?.(path)}
        className="font-mono text-[0.8em] px-1 py-px rounded bg-accent-soft text-accent hover:underline underline-offset-2 align-baseline"
        title={`Open ${path}`}
      >
        {path.split('/').pop()}:{start}
        {end && end !== start ? `–${end}` : ''}
      </button>,
    );
    last = idx + m[0].length;
  }
  out.push(...renderInlineCode(text.slice(last), out.length));
  return out;
}

/** Render **bold** and `inline code`, the only markdown the model reliably uses. */
function renderInlineCode(text: string, keyBase: number): React.ReactNode[] {
  return text.split(/(\*\*[^\n]+?\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
      <strong key={`${keyBase}-b${i}`} className="font-semibold">
        {renderCode(part.slice(2, -2).trim(), `${keyBase}-b${i}`)}
      </strong>
    ) : (
      <React.Fragment key={`${keyBase}-t${i}`}>{renderCode(part, `${keyBase}-${i}`)}</React.Fragment>
    ),
  );
}

function renderCode(text: string, keyBase: string): React.ReactNode[] {
  return text.split(/(`[^`\n]+`)/g).map((part, i) =>
    part.startsWith('`') && part.endsWith('`') && part.length > 2 ? (
      <code key={`${keyBase}-${i}`} className="px-1 py-px rounded bg-sunk text-ink">
        {part.slice(1, -1)}
      </code>
    ) : (
      part
    ),
  );
}

function verifiedTone(pct: number): Tone {
  if (pct >= 90) return 'good';
  if (pct >= 60) return 'warn';
  return 'bad';
}

interface AskViewProps {
  repoId: string;
  onNavigateToFile?: (path: string) => void;
}

export const AskView: React.FC<AskViewProps> = ({ repoId, onNavigateToFile }) => {
  const [question, setQuestion] = useState('');
  const [useLlm, setUseLlm] = useState(true); // Falls back to evidence-only when no LLM is configured
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [symbolQuestions, setSymbolQuestions] = useState<string[]>([]);
  const sampleQuestions = repoId === 'ecommerce_sample' ? ECOMMERCE_SAMPLE_QUESTIONS : symbolQuestions;

  useEffect(() => {
    if (repoId === 'ecommerce_sample') return;
    let cancelled = false;
    fetchSymbols(repoId)
      .then((res) => !cancelled && setSymbolQuestions(suggestionsFromSymbols(res.symbols)))
      .catch(() => !cancelled && setSymbolQuestions(GENERIC_QUESTIONS));
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  const handleAsk = async (queryText?: string) => {
    const q = queryText || question;
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await askQuestion(q, repoId, useLlm);
      setResponse(res);
    } catch (err) {
      console.error('Ask error:', err);
      setError(err instanceof Error ? err.message : 'Something went wrong while answering.');
    } finally {
      setLoading(false);
    }
  };

  const verifiedPct = response ? Math.round(response.citation_confidence * 100) : 0;
  const tokens =
    response?.prompt_tokens != null ? response.prompt_tokens + (response.completion_tokens ?? 0) : null;

  return (
    <div className="max-w-3xl space-y-8">
      <PageHeader title="Ask about this code">
        RepoMind finds the functions and classes related to your question, answers using only those, and then checks
        every line reference it gives you.
      </PageHeader>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk();
        }}
        className="space-y-4"
      >
        <div className="bg-surface border border-line-strong rounded-lg focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 transition">
          <textarea
            rows={2}
            placeholder="e.g. Where do we check that a user is allowed to do this?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
            aria-label="Your question"
            className="block w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[15px] text-ink placeholder:text-subtle outline-none"
          />
          <div className="flex flex-wrap items-center justify-between gap-3 px-3 pb-3 pt-1">
            <label className="flex items-center gap-2 text-xs text-muted cursor-pointer select-none pl-1">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                className="w-3.5 h-3.5 accent-[var(--accent)] cursor-pointer"
              />
              Write an answer (otherwise just show the matching code)
            </label>
            <Button type="submit" variant="primary" disabled={loading || !question.trim()}>
              {loading ? (
                <>
                  <Spinner className="w-3.5 h-3.5" /> Reading the code…
                </>
              ) : (
                'Ask'
              )}
            </Button>
          </div>
        </div>

        {sampleQuestions.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-subtle mr-1">Not sure what to ask? Try</span>
            {sampleQuestions.map((sq) => (
              <Chip
                key={sq}
                onClick={() => {
                  setQuestion(sq);
                  handleAsk(sq);
                }}
              >
                {sq}
              </Chip>
            ))}
          </div>
        )}
      </form>

      {error && <Notice tone="error">{error}</Notice>}

      {response && (
        <article className="space-y-8">
          <div className="bg-surface border border-line rounded-lg p-6 sm:p-7">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-5">
              <Tag tone={verifiedTone(verifiedPct)}>{verifiedPct}% of citations verified</Tag>
              <span className="text-xs text-subtle font-mono">
                {response.model_used}
                {response.latency_ms != null && ` · ${(response.latency_ms / 1000).toFixed(1)}s`}
                {tokens != null && ` · ${tokens.toLocaleString()} tokens`}
              </span>
            </div>
            <div className="text-[15px] text-ink leading-[1.75] whitespace-pre-wrap">
              {renderAnswer(response.answer, onNavigateToFile)}
            </div>
          </div>

          {response.citations.length > 0 && (
            <section>
              <h2 className="font-serif text-xl text-ink mb-1">Where this comes from</h2>
              <p className="text-sm text-muted mb-4">
                The {response.citations.length === 1 ? 'snippet' : `${response.citations.length} snippets`} the answer
                is based on.
              </p>
              <ol className="space-y-4">
                {response.citations.map((cite, idx) => (
                  <li key={idx} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-mono text-ink truncate">
                        <span className="text-subtle mr-2">{idx + 1}.</span>
                        {cite.file_path}
                        <span className="text-subtle">
                          :{cite.line_start}–{cite.line_end}
                        </span>
                      </span>
                      <button
                        onClick={() => onNavigateToFile?.(cite.file_path)}
                        className="shrink-0 inline-flex items-center gap-0.5 text-xs text-accent hover:underline underline-offset-2"
                      >
                        Open file <ArrowUpRight className="w-3 h-3" />
                      </button>
                    </div>
                    <CodeBlock className="max-h-40 overflow-y-auto">{cite.snippet}</CodeBlock>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </article>
      )}

      {!response && !loading && !error && (
        <ol className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4 border-t border-line text-sm">
          {[
            ['Find', 'It searches by name and by meaning to pull the most relevant functions and classes.'],
            ['Answer', 'The model is only shown those snippets and is told to cite each claim.'],
            ['Check', 'Every file:line it cites is matched against the parsed source. You see the score.'],
          ].map(([title, body], i) => (
            <li key={title}>
              <span className="font-serif text-2xl text-accent">{i + 1}</span>
              <p className="mt-1 font-medium text-ink">{title}</p>
              <p className="mt-1 text-muted leading-relaxed">{body}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
};
