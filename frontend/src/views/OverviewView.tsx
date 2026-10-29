import React from 'react';
import { ArrowRight } from 'lucide-react';
import type { RepoInfo } from '../types';
import type { TabType } from '../components/Navigation';
import { Button, PageHeader } from '../components/ui';

interface OverviewViewProps {
  repo?: RepoInfo;
  onNavigate: (tab: TabType) => void;
}

const STARTING_POINTS: Array<{ tab: TabType; title: string; body: string }> = [
  {
    tab: 'ask',
    title: 'Ask a question',
    body: 'Plain English is fine. You get an answer plus the exact lines it was based on.',
  },
  {
    tab: 'graph',
    title: 'See how it fits together',
    body: 'Which files everything leans on, import loops, and files nothing uses.',
  },
  {
    tab: 'impact',
    title: 'Check before you change',
    body: 'Pick a file or function and see everything that could break if you touch it.',
  },
];

export const OverviewView: React.FC<OverviewViewProps> = ({ repo, onNavigate }) => {
  const stats = repo?.stats || { files: 0, functions: 0, classes: 0, imports: 0 };

  if (!repo) {
    return (
      <div className="max-w-2xl space-y-5">
        <PageHeader title="Nothing to look at yet">
          Pick a repository from the menu at the top, or add a public GitHub repo. RepoMind will read its Python files,
          map how they connect, and then you can ask it questions.
        </PageHeader>
        <Button variant="primary" onClick={() => onNavigate('ask')}>
          Go to Ask
        </Button>
      </div>
    );
  }

  const numbers: Array<[number, string]> = [
    [stats.files, 'Python files'],
    [stats.functions, 'functions'],
    [stats.classes, 'classes'],
    [stats.imports, 'import links'],
  ];

  return (
    <div className="space-y-12">
      <div className="space-y-6">
        <PageHeader
          title={repo.name}
          actions={
            <Button variant="primary" onClick={() => onNavigate('ask')}>
              Ask about it <ArrowRight className="w-4 h-4" />
            </Button>
          }
        >
          Here's what RepoMind found after reading this repository.
        </PageHeader>

        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-y-5 border-y border-line py-5">
          {numbers.map(([value, label]) => (
            <div key={label} className="sm:border-l sm:border-line sm:pl-6 sm:first:border-l-0 sm:first:pl-0">
              <dt className="sr-only">{label}</dt>
              <dd className="font-serif text-4xl text-ink tabular-nums">{value.toLocaleString()}</dd>
              <dd className="mt-1 text-sm text-muted">{label}</dd>
            </div>
          ))}
        </dl>
      </div>

      <section>
        <h2 className="font-serif text-xl text-ink mb-4">Where to start</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {STARTING_POINTS.map((p) => (
            <button
              key={p.tab}
              onClick={() => onNavigate(p.tab)}
              className="group text-left bg-surface border border-line rounded-lg p-5 hover:border-accent/60 transition"
            >
              <span className="flex items-center justify-between font-medium text-ink">
                {p.title}
                <ArrowRight className="w-4 h-4 text-subtle group-hover:text-accent group-hover:translate-x-0.5 transition" />
              </span>
              <span className="block mt-1.5 text-sm text-muted leading-relaxed">{p.body}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8 text-sm leading-relaxed">
        <div>
          <h2 className="font-serif text-xl text-ink mb-3">What you can count on</h2>
          <ul className="space-y-2.5 text-muted list-disc pl-5 marker:text-subtle">
            <li>
              Answers point to specific <code className="text-ink">file:line</code> ranges, and each one is checked
              against the real source before you see it.
            </li>
            <li>
              The heavy lifting happens on the RepoMind server. Only the handful of snippets relevant to your question
              go to the language model (Groq here, or a local Ollama model if you run it yourself).
            </li>
            <li>Code is read, never run.</li>
          </ul>
        </div>
        <div>
          <h2 className="font-serif text-xl text-ink mb-3">What it can't do (yet)</h2>
          <ul className="space-y-2.5 text-muted list-disc pl-5 marker:text-subtle">
            <li>It only reads Python. Other languages are skipped.</li>
            <li>
              It works from the code as written, so anything decided at runtime (dynamic imports, reflection) is
              invisible to it.
            </li>
            <li>If it can't find enough evidence, it says so instead of guessing.</li>
          </ul>
        </div>
      </section>
    </div>
  );
};
