import React, { useState } from 'react';
import { AlertCircle, FolderOpen, FolderPlus, Link2, Loader2, X } from 'lucide-react';
import { browseFolder } from '../api';

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

  if (!isOpen) return null;

  const handleBrowse = async () => {
    setBrowsing(true);
    setError(null);
    try {
      const res = await browseFolder(path.trim() || undefined);
      if (res.status === 'selected' && res.path) {
        setPath(res.path);
        // Automatically suggest folder basename as repository name if name is empty
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
        // If regular user cancellation (res.error is null), cleanly do nothing
      } else if (res.status === 'error' && res.error) {
        setError(res.error);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to open native folder picker.');
      }
    } finally {
      setBrowsing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'github') {
      if (!url.trim()) {
        setError('Please paste a GitHub repository link.');
        return;
      }
      setLoading(true);
      setError(null);
      try {
        await onSubmitGitHub(url.trim());
        setUrl('');
        onClose();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to add repository.');
      } finally {
        setLoading(false);
      }
      return;
    }
    if (!name.trim() || !path.trim()) {
      setError('Please provide both a repository name and a folder path.');
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
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to register repository.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40  animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-lg shadow-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-lg bg-teal-500/10 border border-teal-800/40 text-teal-400">
              <FolderPlus className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-100 text-base">Add Repository</h3>
              <p className="text-xs text-slate-400">
                {mode === 'github' ? 'Clone a public GitHub repository' : 'Register an offline codebase on your machine'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-700 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {allowLocal && (
          <div className="grid grid-cols-2 gap-1 p-1 rounded-md bg-slate-950 border border-slate-800">
            {(['github', 'local'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                disabled={loading || browsing}
                className={`flex items-center justify-center space-x-1.5 py-1.5 rounded text-xs font-medium transition ${
                  mode === m ? 'bg-slate-800 text-slate-100' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {m === 'github' ? <Link2 className="w-3.5 h-3.5" /> : <FolderOpen className="w-3.5 h-3.5" />}
                <span>{m === 'github' ? 'GitHub link' : 'Local folder'}</span>
              </button>
            ))}
          </div>
          )}

          {error && (
            <div className="p-3.5 rounded-md bg-red-950/40 border border-red-800/60 flex items-start space-x-2.5 text-red-300 text-xs">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-400 mt-0.5" />
              <div className="flex-1">{error}</div>
            </div>
          )}

          {mode === 'github' ? (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Repository Link
              </label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                disabled={loading}
                className="w-full px-3.5 py-2.5 rounded-md bg-slate-950 border border-slate-800 text-slate-200 text-sm font-mono focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition placeholder:text-slate-600 disabled:opacity-60"
                autoFocus
              />
              <p className="mt-1.5 text-[11px] text-slate-500">
                Public repositories only. Python files are analyzed. Downloading takes seconds; indexing then continues in the background.
              </p>
            </div>
          ) : (
          <>
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Repository Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Payment Gateway Service"
              disabled={loading}
              className="w-full px-3.5 py-2.5 rounded-md bg-slate-950 border border-slate-800 text-slate-200 text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition placeholder:text-slate-600"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Local Folder Path
            </label>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="e.g. D:\Projects\payment_service or C:\Users\user\code"
                disabled={loading || browsing}
                className="flex-1 px-3.5 py-2.5 rounded-md bg-slate-950 border border-slate-800 text-slate-200 text-sm font-mono focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition placeholder:text-slate-600 disabled:opacity-60"
              />
              <button
                type="button"
                onClick={handleBrowse}
                disabled={loading || browsing}
                className="flex items-center space-x-1.5 px-3.5 py-2.5 rounded-md bg-slate-800 hover:bg-slate-700 active:bg-slate-600 disabled:opacity-50 text-xs font-medium text-slate-200 hover:text-slate-100 border border-slate-700 transition shadow-sm whitespace-nowrap cursor-pointer disabled:cursor-not-allowed"
                title="Open native Windows folder selection dialog"
              >
                {browsing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-400" />
                    <span>Browsing...</span>
                  </>
                ) : (
                  <>
                    <FolderOpen className="w-3.5 h-3.5 text-teal-400" />
                    <span>Browse Folder</span>
                  </>
                )}
              </button>
            </div>
            <p className="mt-1.5 text-[11px] text-slate-500">
              Click &ldquo;Browse Folder&rdquo; to select a folder from your computer, or type the path directly.
            </p>
          </div>

          <div className="p-3 rounded-md bg-slate-900 border border-slate-800 text-xs text-slate-400 space-y-1">
            <span className="font-semibold text-slate-300">🔒 100% Local & Isolated:</span>
            <p>
              Your source code is never copied or modified. RepoMind only reads the AST symbols and stores an isolated SQLite index in <code className="text-teal-300 font-mono text-[10px]">.repomind_data/repos/</code>.
            </p>
          </div>
          </>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={loading || browsing}
              className="px-4 py-2 rounded-md text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || browsing || (mode === 'github' ? !url.trim() : !name.trim() || !path.trim())}
              className="flex items-center space-x-2 px-4 py-2 rounded-md bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-50 text-xs font-semibold text-slate-100 shadow-lg  transition cursor-pointer disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>{mode === 'github' ? 'Cloning...' : 'Registering...'}</span>
                </>
              ) : (
                <>
                  <FolderPlus className="w-3.5 h-3.5" />
                  <span>{mode === 'github' ? 'Clone & Analyze' : 'Register & Select'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
