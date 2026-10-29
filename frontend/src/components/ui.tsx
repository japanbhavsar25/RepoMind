import React from 'react';

/** Small shared building blocks so every view speaks the same visual language. */

type ButtonVariant = 'primary' | 'secondary' | 'quiet';

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-ink border border-accent hover:brightness-110',
  secondary: 'bg-surface text-ink border border-line-strong hover:border-subtle',
  quiet: 'text-muted border border-transparent hover:text-ink hover:bg-sunk',
};

export const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'sm' | 'md' }
> = ({ variant = 'secondary', size = 'md', className = '', type = 'button', ...props }) => (
  <button
    type={type}
    {...props}
    className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition disabled:opacity-50 disabled:cursor-not-allowed ${
      size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-2 text-sm'
    } ${BUTTON_VARIANTS[variant]} ${className}`}
  />
);

export const inputClass =
  'w-full bg-surface border border-line-strong rounded-md px-3.5 py-2.5 text-sm text-ink placeholder:text-subtle outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition disabled:opacity-60';

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = '', children }) => (
  <div className={`bg-surface border border-line rounded-lg ${className}`}>{children}</div>
);

export const PageHeader: React.FC<{ title: React.ReactNode; children?: React.ReactNode; actions?: React.ReactNode }> = ({
  title,
  children,
  actions,
}) => (
  <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
    <div className="min-w-0">
      <h1 className="font-serif text-3xl sm:text-[2.1rem] leading-tight text-ink tracking-tight">{title}</h1>
      {children && <p className="mt-2 text-[15px] text-muted leading-relaxed max-w-2xl">{children}</p>}
    </div>
    {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
  </header>
);

export const SectionTitle: React.FC<{ children: React.ReactNode; aside?: React.ReactNode }> = ({ children, aside }) => (
  <div className="flex items-baseline justify-between gap-3 mb-3">
    <h2 className="font-serif text-xl text-ink">{children}</h2>
    {aside && <span className="text-xs text-subtle">{aside}</span>}
  </div>
);

export const Chip: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & { mono?: boolean }> = ({
  mono,
  className = '',
  ...props
}) => (
  <button
    type="button"
    {...props}
    className={`rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted hover:text-ink hover:border-line-strong transition text-left ${
      mono ? 'font-mono' : ''
    } ${className}`}
  />
);

export type Tone = 'neutral' | 'accent' | 'good' | 'warn' | 'bad';

const TONES: Record<Tone, string> = {
  neutral: 'bg-sunk text-muted',
  accent: 'bg-accent-soft text-accent',
  good: 'bg-good-soft text-good',
  warn: 'bg-warn-soft text-warn',
  bad: 'bg-bad-soft text-bad',
};

export const Tag: React.FC<{ tone?: Tone; className?: string; children: React.ReactNode }> = ({
  tone = 'neutral',
  className = '',
  children,
}) => (
  <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${TONES[tone]} ${className}`}>
    {children}
  </span>
);

export const Spinner: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <span
    aria-hidden
    className={`inline-block shrink-0 rounded-full border-2 border-current border-t-transparent animate-spin ${className}`}
  />
);

export const Notice: React.FC<{ tone?: 'info' | 'error'; children: React.ReactNode; action?: React.ReactNode }> = ({
  tone = 'info',
  children,
  action,
}) => (
  <div
    role={tone === 'error' ? 'alert' : 'status'}
    className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm leading-relaxed ${
      tone === 'error' ? 'border-bad/30 bg-bad-soft text-bad' : 'border-accent/25 bg-accent-soft text-ink'
    }`}
  >
    <div className="flex-1 min-w-0">{children}</div>
    {action}
  </div>
);

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-line bg-sunk p-0.5 text-xs">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`px-3 py-1 rounded font-medium transition ${
            value === o.value ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const CodeBlock: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <pre
    className={`bg-sunk border border-line rounded-md p-3 text-xs font-mono text-ink/85 leading-relaxed overflow-x-auto whitespace-pre-wrap ${className}`}
  >
    {children}
  </pre>
);

export const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="rounded-lg border border-dashed border-line-strong px-6 py-10 text-center text-sm text-muted">
    {children}
  </div>
);

export const Loading: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex items-center justify-center gap-3 py-20 text-sm text-muted">
    <Spinner className="w-4 h-4 text-accent" />
    <span>{children}</span>
  </div>
);
