/** TypeScript definitions matching RepoMind FastAPI schemas. */

export interface RepoStats {
  files: number;
  functions: number;
  classes: number;
  imports: number;
}

export interface RepoInfo {
  id: string;
  name: string;
  path: string;
  is_sample: boolean;
  is_indexed: boolean;
  stats?: RepoStats;
}

export interface RepoListResponse {
  repos: RepoInfo[];
  active_repo_id: string;
}

export interface AddLocalRepoRequest {
  name: string;
  path: string;
}

export interface BrowseFolderResponse {
  status: 'selected' | 'cancelled' | 'error';
  path?: string | null;
  cancelled: boolean;
  error?: string | null;
}

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size: number;
  children?: FileNode[];
}

export interface FileTreeResponse {
  repo_id: string;
  root: FileNode;
  total_files: number;
}

export interface FileContentResponse {
  path: string;
  content: string;
  line_count: number;
  last_modified: number;
}

export interface SymbolInfo {
  name: string;
  kind: 'function' | 'class';
  qualified_name?: string;
  file_path: string;
  line_start: number;
  line_end: number;
  complexity: number;
  docstring?: string;
}

export interface SymbolListResponse {
  symbols: SymbolInfo[];
  total_count: number;
}

export interface SearchResultItem {
  chunk_id: string;
  file_path: string;
  snippet: string;
  line_start: number;
  line_end: number;
  score: number;
  match_type: string;
}

export interface SearchResponse {
  query: string;
  intent: string;
  results: SearchResultItem[];
  total_candidates: number;
}

export interface Citation {
  file_path: string;
  line_start: number;
  line_end: number;
  snippet: string;
  verified: boolean;
}

export interface AskResponse {
  question: string;
  answer: string;
  citations: Citation[];
  citation_confidence: number;
  intent: string;
  model_used: string;
  chunks_retrieved: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'internal' | 'external';
  pagerank: number;
  is_orphan: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: 'internal' | 'external';
}

export interface GraphDataResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  cycles: string[][];
  orphans: string[];
  pagerank_leaderboard: Array<{ file: string; score: number }>;
}

export interface CallerInfo {
  caller_file: string;
  caller_symbol: string;
  line_number: number;
}

export interface ImpactResponse {
  target: string;
  found: boolean;
  kind: string;
  direct_importers: string[];
  transitive_dependents: string[];
  pagerank: number;
  complexity: number;
  callers: CallerInfo[];
  limitations: string[];
}

export interface MetricScores {
  hit_rate_at_1: number;
  hit_rate_at_5: number;
  mrr_at_5: number;
  avg_latency_ms: number;
}

export interface EvaluationResponse {
  status: string;
  dataset_size: number;
  dense: MetricScores;
  sparse: MetricScores;
  hybrid: MetricScores;
}
