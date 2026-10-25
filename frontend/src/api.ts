/** API Client for communicating with the RepoMind FastAPI backend. */

import type {
  AskResponse,
  BrowseFolderResponse,
  EvaluationResponse,
  FileContentResponse,
  FileTreeResponse,
  GraphDataResponse,
  ImpactResponse,
  RepoInfo,
  RepoListResponse,
  SearchResponse,
  SymbolListResponse,
} from './types';

// Same-origin by default (dev proxy / single container). When the UI is hosted
// separately (e.g. Vercel), VITE_API_URL points at the backend (e.g. Render).
const BASE_URL = `${(import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')}/api`;

export async function fetchHealth(): Promise<{
  status: string;
  version: string;
  fts5_enabled: boolean;
  local_repos_enabled?: boolean;
}> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchRepos(): Promise<RepoListResponse> {
  const res = await fetch(`${BASE_URL}/repos`);
  if (!res.ok) throw new Error(`Failed to load repositories: ${res.statusText}`);
  return res.json();
}

export async function selectRepo(repoId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/repos/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_id: repoId }),
  });
  if (!res.ok) throw new Error(`Failed to switch repository: ${res.statusText}`);
}

export async function addLocalRepo(name: string, path: string): Promise<RepoInfo> {
  const res = await fetch(`${BASE_URL}/repos/local`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, path }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to add repository: ${res.statusText}`);
  }
  return res.json();
}

export async function addGitHubRepo(url: string): Promise<RepoInfo> {
  const res = await fetch(`${BASE_URL}/repos/github`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to add repository: ${res.statusText}`);
  }
  return res.json();
}

export async function browseFolder(initialPath?: string): Promise<BrowseFolderResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 125000);
  try {
    const res = await fetch(`${BASE_URL}/repos/browse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_path: initialPath || null }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to open folder picker (${res.statusText})`);
    }
    return res.json();
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      return {
        status: 'cancelled',
        path: null,
        cancelled: true,
        error: 'Folder picker request timed out',
      };
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function triggerIndex(repoId: string): Promise<{ files_indexed: number; duration_seconds: number }> {
  const res = await fetch(`${BASE_URL}/repos/index?repo_id=${encodeURIComponent(repoId)}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Indexing failed: ${res.statusText}`);
  return res.json();
}

export async function fetchFileTree(repoId: string): Promise<FileTreeResponse> {
  const res = await fetch(`${BASE_URL}/files/tree?repo_id=${encodeURIComponent(repoId)}`);
  if (!res.ok) throw new Error(`Failed to fetch file tree: ${res.statusText}`);
  return res.json();
}

export async function fetchFileContent(path: string, repoId: string): Promise<FileContentResponse> {
  const res = await fetch(`${BASE_URL}/files/content?path=${encodeURIComponent(path)}&repo_id=${encodeURIComponent(repoId)}`);
  if (!res.ok) throw new Error(`Failed to fetch file content: ${res.statusText}`);
  return res.json();
}

export async function fetchSymbols(repoId: string, kind?: 'function' | 'class'): Promise<SymbolListResponse> {
  const url = kind 
    ? `${BASE_URL}/symbols?repo_id=${encodeURIComponent(repoId)}&kind=${kind}`
    : `${BASE_URL}/symbols?repo_id=${encodeURIComponent(repoId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch symbols: ${res.statusText}`);
  return res.json();
}

export async function executeSearch(query: string, repoId: string, topK: number = 5): Promise<SearchResponse> {
  const res = await fetch(`${BASE_URL}/search?repo_id=${encodeURIComponent(repoId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
  return res.json();
}

export async function askQuestion(question: string, repoId: string, useLlm: boolean = true): Promise<AskResponse> {
  const res = await fetch(`${BASE_URL}/ask?repo_id=${encodeURIComponent(repoId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: 5, use_llm: useLlm }),
  });
  if (!res.ok) throw new Error(`Q&A failed: ${res.statusText}`);
  return res.json();
}

export async function fetchGraph(repoId: string): Promise<GraphDataResponse> {
  const res = await fetch(`${BASE_URL}/graph?repo_id=${encodeURIComponent(repoId)}`);
  if (!res.ok) throw new Error(`Failed to fetch graph: ${res.statusText}`);
  return res.json();
}

export async function fetchImpact(target: string, repoId: string): Promise<ImpactResponse> {
  const res = await fetch(`${BASE_URL}/impact/${encodeURIComponent(target)}?repo_id=${encodeURIComponent(repoId)}`);
  if (!res.ok) throw new Error(`Failed to fetch impact analysis: ${res.statusText}`);
  return res.json();
}

export async function fetchEvaluation(repoId: string, maxSamples: number = 10): Promise<EvaluationResponse> {
  const res = await fetch(`${BASE_URL}/evaluate?repo_id=${encodeURIComponent(repoId)}&max_samples=${maxSamples}`);
  if (!res.ok) throw new Error(`Failed to run evaluation: ${res.statusText}`);
  return res.json();
}
