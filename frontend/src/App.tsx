import { Fragment, useCallback, useEffect, useState } from 'react';
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
import { API_HOST, addGitHubRepo, addLocalRepo, fetchHealth, fetchRepos, triggerIndex } from './api';
import type { RepoInfo } from './types';
import { Button, Notice, Spinner } from './components/ui';

export default function App() {
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [activeRepoId, setActiveRepoId] = useState<string>('');
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [selectedFilePath, setSelectedFilePath] = useState<string | undefined>(undefined);
  const [impactTarget, setImpactTarget] = useState<string | undefined>(undefined);
  const [indexing, setIndexing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [waking, setWaking] = useState(false);
  const [indexingRepoName, setIndexingRepoName] = useState<string | null>(null);
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
            setError("Couldn't reach the RepoMind server. Give it a moment, then try again.");
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
      setError('Re-indexing failed. The server log should say why.');
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
    // Wait only for the clone; indexing can take minutes on a small server, so it
    // continues in the background (with a progress banner) after the modal closes.
    const newRepo = await addGitHubRepo(url);
    void registerAndIndex(newRepo);
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
    setIndexingRepoName(name);
    try {
      await triggerIndex(newRepo.id);
      const refreshed = await fetchRepos();
      setRepos(refreshed.repos);
    } catch (idxErr) {
      console.error('Initial indexing failed:', idxErr);
      setError(`Added ${name}, but indexing it failed: ${idxErr instanceof Error ? idxErr.message : String(idxErr)}`);
    } finally {
      setIndexing(false);
      setIndexingRepoName(null);
    }
  };

  const currentRepo = repos.find((r) => r.id === activeRepoId);

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col">
      <Header
        repos={repos}
        activeRepoId={activeRepoId}
        onSelectRepo={handleSelectRepo}
        onTriggerIndex={handleTriggerIndex}
        onOpenAddRepo={() => setIsAddRepoOpen(true)}
        indexing={indexing}
        canReindex={localReposEnabled}
      />

      <AddRepoModal
        isOpen={isAddRepoOpen}
        onClose={() => setIsAddRepoOpen(false)}
        onSubmit={handleAddLocalRepo}
        onSubmitGitHub={handleAddGitHubRepo}
        allowLocal={localReposEnabled}
      />

      <Navigation activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-10 min-w-0 space-y-6">
        {indexingRepoName && (
          <Notice>
            <span className="font-medium">Indexing {indexingRepoName}…</span>{' '}
            <span className="text-muted">
              Reading every Python file and building the search index. On the free demo server this can take a few
              minutes, so feel free to look around in the meantime.
            </span>
          </Notice>
        )}

        {error && (
          <Notice
            tone="error"
            action={
              <Button size="sm" onClick={loadRepos}>
                Try again
              </Button>
            }
          >
            {error}
          </Notice>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-28 text-center">
            <Spinner className="w-6 h-6 text-accent" />
            <p className="mt-5 font-serif text-2xl text-ink">
              {waking ? 'Waking the server up…' : 'Connecting…'}
            </p>
            {waking && (
              <p className="mt-2 text-sm text-muted max-w-sm leading-relaxed">
                The demo runs on a free server that naps when nobody's around. It usually takes about a minute to get
                going. Thanks for your patience.
              </p>
            )}
          </div>
        ) : (
          // Keyed by repo: switching repos remounts the views, so no old results or
          // late replies from the previous repo can show up under the new one
          <Fragment key={activeRepoId}>
            {activeTab === 'overview' && (
              <OverviewView repo={currentRepo} onNavigate={setActiveTab} />
            )}

            {activeTab === 'files' && (
              <FilesView repoId={activeRepoId} initialPath={selectedFilePath} />
            )}

            {activeTab === 'symbols' && (
              <SymbolsView repoId={activeRepoId} onNavigateToFile={handleNavigateToFile} />
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
                initialTarget={impactTarget}
                onNavigateToFile={handleNavigateToFile}
              />
            )}

            {activeTab === 'evaluation' && (
              <EvaluationView repoId={activeRepoId} />
            )}
          </Fragment>
        )}
      </main>

      <footer className="border-t border-line px-4 sm:px-6 py-6 mt-12 text-xs text-subtle">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
          <p>
            RepoMind is a side project by Japan Bhavsar.{' '}
            <a
              href="https://github.com/japanbhavsar25/RepoMind"
              target="_blank"
              rel="noreferrer"
              className="text-muted underline underline-offset-2 hover:text-accent"
            >
              Read the source on GitHub
            </a>
            .
          </p>
          <p className="font-mono truncate max-w-full">server: {API_HOST}</p>
        </div>
      </footer>
    </div>
  );
}
