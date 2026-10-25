import { useCallback, useEffect, useState } from 'react';
import { Header } from './components/Header';
import { AddRepoModal } from './components/AddRepoModal';
import { Navigation, type TabType } from './components/Navigation';
import { OverviewView } from './views/OverviewView';
import { FilesView } from './views/FilesView';
import { SymbolsView } from './views/SymbolsView';
import { SearchView } from './views/SearchView';
import { AskView } from './views/AskView';
import { GraphView } from './views/GraphView';
import { ImpactView } from './views/ImpactView';
import { EvaluationView } from './views/EvaluationView';
import { addGitHubRepo, addLocalRepo, fetchHealth, fetchRepos, triggerIndex } from './api';
import type { RepoInfo } from './types';
import { AlertCircle, CheckCircle2, HardDrive, ShieldCheck } from 'lucide-react';

export default function App() {
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [activeRepoId, setActiveRepoId] = useState<string>('');
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [selectedFilePath, setSelectedFilePath] = useState<string | undefined>(undefined);
  const [impactTarget, setImpactTarget] = useState<string | undefined>(undefined);
  const [indexing, setIndexing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [waking, setWaking] = useState(false);
  const [isAddRepoOpen, setIsAddRepoOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Start hidden; enabled once the backend confirms it's a local (non-public) install
  const [localReposEnabled, setLocalReposEnabled] = useState(false);

  const loadRepos = useCallback(async () => {
    // Free hosting sleeps when idle and takes ~1 minute to wake, so keep
    // retrying for a while (showing a "waking up" message) before giving up.
    const deadline = Date.now() + 150_000;
    setError(null);
    try {
      for (;;) {
        try {
          const data = await fetchRepos();
          setRepos(data.repos);
          if (data.repos.length > 0) {
            setActiveRepoId((prev) => {
              if (prev && data.repos.some((r: RepoInfo) => r.id === prev)) {
                return prev;
              }
              return data.active_repo_id || data.repos[0].id;
            });
          }
          // Server is up: ask whether local-folder repos are allowed (off on the public demo)
          fetchHealth()
            .then((h) => setLocalReposEnabled(h.local_repos_enabled ?? true))
            .catch(() => {});
          return;
        } catch (err) {
          if (Date.now() > deadline) {
            console.error('Failed to load repositories:', err);
            setError('Could not connect to the RepoMind backend. Press Retry in a moment.');
            return;
          }
          setWaking(true);
          await new Promise((resolve) => setTimeout(resolve, 4000));
        }
      }
    } finally {
      setWaking(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRepos();
  }, [loadRepos]);

  const handleSelectRepo = (repoId: string) => {
    setActiveRepoId(repoId);
    setSelectedFilePath(undefined);
    setImpactTarget(undefined);
  };

  const handleTriggerIndex = async () => {
    if (!activeRepoId) return;
    setIndexing(true);
    try {
      await triggerIndex(activeRepoId);
      await loadRepos();
    } catch (err) {
      console.error('Indexing failed:', err);
      setError('Indexing request failed. Inspect backend terminal logs.');
    } finally {
      setIndexing(false);
    }
  };

  const handleNavigateToFile = (path: string) => {
    setSelectedFilePath(path);
    setActiveTab('files');
  };

  const handleSelectImpactTarget = (target: string) => {
    setImpactTarget(target);
    setActiveTab('impact');
  };

  const handleAddLocalRepo = async (name: string, path: string) => {
    await registerAndIndex(await addLocalRepo(name, path));
  };

  const handleAddGitHubRepo = async (url: string) => {
    await registerAndIndex(await addGitHubRepo(url));
  };

  const registerAndIndex = async (newRepo: RepoInfo) => {
    const name = newRepo.name;
    setError(null);
    // Refresh repo list
    const data = await fetchRepos();
    setRepos(data.repos);
    setActiveRepoId(newRepo.id);
    setSelectedFilePath(undefined);
    setImpactTarget(undefined);

    // Automatically trigger indexing for the newly registered repository
    if (newRepo.is_indexed) return;
    setIndexing(true);
    try {
      await triggerIndex(newRepo.id);
      const refreshed = await fetchRepos();
      setRepos(refreshed.repos);
    } catch (idxErr) {
      console.error('Initial indexing failed:', idxErr);
      setError(`Repository '${name}' registered, but initial indexing encountered an issue: ${idxErr instanceof Error ? idxErr.message : String(idxErr)}`);
    } finally {
      setIndexing(false);
    }
  };

  const currentRepo = repos.find((r) => r.id === activeRepoId);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-teal-500/30 selection:text-teal-200">
      {/* Global Header */}
      <Header
        repos={repos}
        activeRepoId={activeRepoId}
        onSelectRepo={handleSelectRepo}
        onTriggerIndex={handleTriggerIndex}
        onOpenAddRepo={() => setIsAddRepoOpen(true)}
        indexing={indexing}
      />

      {/* Add Repository Modal */}
      <AddRepoModal
        isOpen={isAddRepoOpen}
        onClose={() => setIsAddRepoOpen(false)}
        onSubmit={handleAddLocalRepo}
        onSubmitGitHub={handleAddGitHubRepo}
        allowLocal={localReposEnabled}
      />

      {/* Navigation tabs */}
      <Navigation activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main content body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 sm:p-8">
        {error && (
          <div className="mb-6 bg-red-950/40 border border-red-800/60 rounded-md p-4 flex items-start space-x-3 text-red-300 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold">Backend Connection Issue:</span> {error}
            </div>
            <button
              onClick={loadRepos}
              className="text-xs px-2.5 py-1 rounded bg-red-900/60 hover:bg-red-800 text-slate-100 font-medium"
            >
              Retry
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 text-slate-400 space-y-3">
            <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm">
              {waking ? 'Waking up the server…' : 'Connecting to the RepoMind engine…'}
            </p>
            {waking && (
              <p className="text-xs text-slate-500 max-w-sm text-center">
                The free demo server sleeps when nobody is using it. It takes about a minute to start —
                thanks for waiting!
              </p>
            )}
          </div>
        ) : (
          <>
            {activeTab === 'overview' && (
              <OverviewView repo={currentRepo} onNavigate={setActiveTab} />
            )}

            {activeTab === 'files' && (
              <FilesView repoId={activeRepoId} initialPath={selectedFilePath} />
            )}

            {activeTab === 'symbols' && (
              <SymbolsView repoId={activeRepoId} />
            )}

            {activeTab === 'search' && (
              <SearchView repoId={activeRepoId} onNavigateToFile={handleNavigateToFile} />
            )}

            {activeTab === 'ask' && (
              <AskView repoId={activeRepoId} onNavigateToFile={handleNavigateToFile} />
            )}

            {activeTab === 'graph' && (
              <GraphView repoId={activeRepoId} onSelectTarget={handleSelectImpactTarget} />
            )}

            {activeTab === 'impact' && (
              <ImpactView
                repoId={activeRepoId}
                initialTarget={impactTarget || 'models.py'}
                onNavigateToFile={handleNavigateToFile}
              />
            )}

            {activeTab === 'evaluation' && (
              <EvaluationView repoId={activeRepoId} />
            )}
          </>
        )}
      </main>

      {/* Global Footer */}
      <footer className="border-t border-slate-800 bg-slate-950/90 px-6 py-4 mt-auto text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-4">
            <span className="flex items-center space-x-1.5 text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Engine Status: Online</span>
            </span>
            <span className="flex items-center space-x-1.5 text-slate-400">
              <HardDrive className="w-3.5 h-3.5" />
              <span>100% Local-First Storage</span>
            </span>
            <span className="flex items-center space-x-1.5 text-slate-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Strict Path Traversal Protection</span>
            </span>
          </div>

          <div className="flex items-center space-x-3 text-slate-400">
            <span className="font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-[11px]">
              API: 127.0.0.1:8001
            </span>
            <span>•</span>
            <span>RepoMind</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
