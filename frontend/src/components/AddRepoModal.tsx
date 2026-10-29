import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { browseFolder } from '../api';
import { Button, Notice, Segmented, Spinner, inputClass } from './ui';

interface AddRepoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string, path: string) => Promise<void>;
  onSubmitGitHub: (url: string) => Promise<void>;
  allowLocal?: boolean;
}

type AddMode = 'github' | 'local';

export const AddRepoModal: React.FC<AddRepoModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  onSubmitGitHub,
  allowLocal = true,
}) => {
  const [mode, setMode] = useState<AddMode>('github');
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const busy = loading || browsing;

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, busy, onClose]);

  if (!isOpen) return null;

  const handleBrowse = async () => {
    setBrowsing(true);
    setError(null);
    try {
      const res = await browseFolder(path.trim() || undefined);
      if (res.status === 'selected' && res.path) {
        setPath(res.path);
        // Suggest the folder's name as the repository name if none was typed
        if (!name.trim()) {
          const parts = res.path.replace(/\\/g, '/').split('/').filter(Boolean);
          const folderBase = parts[parts.length - 1];
          if (folderBase) {
            setName(folderBase);
          }
        }
      } else if (res.status === 'cancelled') {
        if (res.error) {
          setError(res.error);
        }
        // A plain cancel (no error) needs no message
      } else if (res.status === 'error' && res.error) {
        setError(res.error);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Couldn't open the folder picker.");
    } finally {
      setBrowsing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'github') {
      if (!url.trim()) {
        setError('Paste a link to a GitHub repository first.');
        return;
      }
      setLoading(true);
      setError(null);
      try {
        await onSubmitGitHub(url.trim());
        setUrl('');
        onClose();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Couldn't add that repository.");
      } finally {
        setLoading(false);
      }
      return;
    }
    if (!name.trim() || !path.trim()) {
      setError('Give it a name and a folder.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await onSubmit(name.trim(), path.trim());
      setName('');
      setPath('');
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Couldn't add that folder.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30"
      onClick={() => !busy && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-repo-title"
        className="w-full max-w-lg bg-surface border border-line rounded-xl shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 px-6 pt-6">
          <div>
            <h3 id="add-repo-title" className="font-serif text-2xl text-ink">
              Add a repository
            </h3>
            <p className="mt-1 text-sm text-muted">
              {mode === 'github'
                ? "Paste a link and RepoMind will download and read it."
                : 'Point RepoMind at a project folder on this machine.'}
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={busy}
            className="p-1 rounded-md text-subtle hover:text-ink hover:bg-sunk"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {allowLocal && (
            <Segmented
              value={mode}
              onChange={(m) => {
                setMode(m);
                setError(null);
              }}
              options={[
                { value: 'github', label: 'GitHub link' },
                { value: 'local', label: 'Folder on this computer' },
              ]}
            />
          )}

          {error && <Notice tone="error">{error}</Notice>}

          {mode === 'github' ? (
            <div>
              <label htmlFor="repo-url" className="block text-sm font-medium text-ink mb-1.5">
                Link
              </label>
              <input
                id="repo-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                disabled={loading}
                className={`${inputClass} font-mono`}
                autoFocus
              />
              <p className="mt-2 text-xs text-subtle leading-relaxed">
                Public repos only, and only the Python files get read. Downloading takes a few seconds; indexing keeps
                going in the background after this closes.
              </p>
            </div>
          ) : (
            <>
              <div>
                <label htmlFor="repo-name" className="block text-sm font-medium text-ink mb-1.5">
                  Name
                </label>
                <input
                  id="repo-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. payments-service"
                  disabled={loading}
                  className={inputClass}
                  autoFocus
                />
              </div>

              <div>
                <label htmlFor="repo-path" className="block text-sm font-medium text-ink mb-1.5">
                  Folder
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id="repo-path"
                    type="text"
                    value={path}
                    onChange={(e) => setPath(e.target.value)}
                    placeholder="D:\Projects\payments-service"
                    disabled={busy}
                    className={`${inputClass} font-mono`}
                  />
                  <Button onClick={handleBrowse} disabled={busy} title="Pick a folder">
                    {browsing ? <Spinner className="w-3.5 h-3.5" /> : 'Browse…'}
                  </Button>
                </div>
              </div>

              <p className="text-xs text-subtle leading-relaxed">
                Your files stay where they are and are never changed. RepoMind keeps its index separately in{' '}
                <code className="text-muted">.repomind_data/repos/</code>.
              </p>
            </>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button variant="quiet" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={busy || (mode === 'github' ? !url.trim() : !name.trim() || !path.trim())}
            >
              {loading ? (
                <>
                  <Spinner className="w-3.5 h-3.5" /> {mode === 'github' ? 'Downloading…' : 'Adding…'}
                </>
              ) : mode === 'github' ? (
                'Add and read it'
              ) : (
                'Add folder'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
