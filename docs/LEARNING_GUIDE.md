# RepoMind Technical Learning & Interview Defense Guide

This guide is designed to help you deeply understand, explain, debug, and confidently defend RepoMind's architecture and engineering decisions during technical interviews.

---

## 1. The 30-Second Elevator Pitch

> *"RepoMind is a repository intelligence engine and full-stack web app: paste a GitHub link and ask questions that are answered with verified file:line citations. It combines static Python AST analysis, persistent SQLite FTS5 lexical indexing, and ChromaDB dense vector embeddings fused via Reciprocal Rank Fusion ($k=60$) to provide verifiable code search and grounded Q&A. It also builds NetworkX dependency graphs to calculate PageRank centrality and compute downstream blast-radius change impact, The hosted demo uses Groq for generation on a 512 MB free server; the same code runs fully offline with a local Ollama model."*

---

## 2. End-to-End Data Flow: Tracing a User Interaction

### Scenario: The user asks *"How does order checkout validate inventory?"*

```
1. Frontend (React 19 / Vite)
   └── User types question in AskView.tsx -> calls POST /api/repos/{id}/ask

2. FastAPI Backend (backend/routers/qa.py & backend/services/qa_service.py)
   └── Sanitizes repo ID and delegates to QAService.ask()

3. Two-Stage Hybrid Retrieval (repomind/hybrid.py)
   ├── Code-Aware Tokenizer:
   │   Tokenizes query into identifiers & sub-tokens: ["order", "checkout", "validate", "inventory"]
   ├── Stage 1A (Sparse):
   │   Executes BM25 query against SQLite FTS5 (fts_chunks) -> retrieves Top-20 sparse candidates
   ├── Stage 1B (Dense):
   │   Encodes query with all-MiniLM-L6-v2 -> searches ChromaDB cosine index -> retrieves Top-20 dense candidates
   └── Stage 2 (Fusion & Rerank):
       Computes Reciprocal Rank Fusion: RRF(d) = 1/(60 + rank_dense) + 1/(60 + rank_sparse)
       Sorts and returns top context chunks (orders.py lines 24-52: OrderService.checkout)

4. Evidence Assembly & Citation Verification (repomind/rag.py)
   ├── Binds retrieved code chunks with strict prompt boundaries
   ├── LLM or Deterministic Synthesizer outputs response referencing [orders.py:24-52]
   └── Citation Verifier:
       - Parses [orders.py:24-52] via regex
       - Queries SQLite files table to confirm orders.py exists
       - Verifies lines 24-52 fall within the actual chunk bounds
       - Computes a Groundedness Confidence Score (share of citations that verify)

5. Response Delivery (JSON to React UI)
   └── Frontend renders markdown answer, groundedness badge, and clickable file reference pills
```

---

## 3. Core Computer Science Algorithms Explained

### 3.1 Static Cyclomatic Complexity Calculation (`repomind/parser.py`)
- **Theory:** Cyclomatic complexity ($M$) measures the number of linearly independent paths through a program's source code:
  $$M = E - N + 2P$$
  In static AST analysis, this equals the count of predicate decision points plus 1.
- **Implementation:** `RepoMind` traverses the AST node of every function using `ast.walk()` and increments the count for:
  - Branching statements: `ast.If`, `ast.While`, `ast.For`, `ast.AsyncFor`
  - Exception handling: `ast.ExceptHandler`
  - Context managers & assertions: `ast.With`, `ast.AsyncWith`, `ast.Assert`
  - Short-circuit boolean operations: `len(node.values) - 1` for each `ast.BoolOp` (`and`, `or`)
- **Formula:**
  $$\text{Complexity} = 1 + \sum \text{Decision Points}$$

### 3.2 Reciprocal Rank Fusion ($k=60$) (`repomind/hybrid.py`)
- **Theory:** Combining sparse lexical scores (BM25) and dense semantic similarities (cosine) directly via weighted sum ($\alpha \cdot S_{bm25} + \beta \cdot S_{dense}$) is deeply flawed because:
  - BM25 scores are unbounded positive reals whose magnitude depends on document length and term frequency.
  - Cosine similarities range from $-1$ to $1$ (or $0$ to $1$).
  - Normalizing these scores requires ad-hoc heuristics that drift across codebases.
- **RRF Solution:** RRF relies purely on the **rank positions** of items in each result list:
  $$\text{Score}(d) = \sum_{m \in M} \frac{w_m}{k + \text{rank}_m(d)}$$
  We set the standard constant $k = 60$. An item ranked #1 in dense and #2 in sparse gets:
  $$\frac{1.0}{60 + 1} + \frac{1.0}{60 + 2} = \frac{1}{61} + \frac{1}{62} \approx 0.01639 + 0.01613 = 0.03252$$
  This rank-based scoring is invariant to scale differences and eliminates calibration issues.

### 3.3 Downstream Blast-Radius Analysis (`repomind/graph_builder.py`)
- **Theory:** When a developer edits a core file (e.g., `models.py`), what else can break?
- **Implementation:**
  1. Build a directed dependency graph $G = (V, E)$ where an edge $A \to B$ means "$A$ imports $B$".
  2. To find what depends on $B$, we invert the edges: $G_{rev} = (V, E_{rev})$ where $B \to A$.
  3. Execute Breadth-First Search (BFS) from the target node $B$ in $G_{rev}$:
     - Depth 1: Direct importers.
     - Depth 2+: Transitive downstream dependents.
  4. Augment with AST `symbol_calls` to identify specific functions calling methods inside the target.
  5. Combine with NetworkX **PageRank centrality** to determine system-wide criticality.

---

## 4. Top 15 Technical Interview Questions & Defensible Answers

### Q1: Why did you build a hybrid search engine instead of using a pure vector database?
**Answer:**
> *"Vector embeddings from models like `all-MiniLM-L6-v2` are excellent at capturing semantic intent (e.g., matching 'deduct product stock' to 'inventory validation'). However, pure vector databases frequently fail at exact code identifiers, error codes, and specific function names like `calculate_tax` or `StripeAdapter`. Conversely, sparse BM25 keyword search is exceptional at exact identifier matching but fails when the user asks conceptual questions using different terminology.*
>
> *By combining SQLite FTS5 (for exact BM25 keyword matching) and ChromaDB (for dense semantic vectors) using Reciprocal Rank Fusion ($k=60$), RepoMind aims to get the best of both. Honest caveat from my benchmark: on 20 natural-language questions, BM25 fusion actually lowered MRR from 0.70 to 0.56, because test files share vocabulary with the code they test. Adding a reranker brought it back to 0.70. My gold set doesn't yet include identifier-style queries, which is where keyword search should help most."*

### Q2: Why did you use Reciprocal Rank Fusion instead of a weighted sum of scores?
**Answer:**
> *"Dense cosine similarity ranges from -1 to 1, while BM25 scores are unbounded positive numbers that vary based on corpus statistics and chunk length. Trying to linearly combine them requires normalizing BM25 with min-max or sigmoid transformations, which are brittle and change whenever documents are added or removed.*
>
> *Reciprocal Rank Fusion bypasses score normalization entirely by operating on rank positions. The formula $1 / (k + rank)$ applies a smooth, monotonic decay where being ranked in the top 3 of both lists yields a higher score than being ranked #1 in one list and absent from the other. It is statistically robust and parameter-free across diverse codebases."*

### Q3: How do you prevent LLMs from hallucinating citations or fake code line numbers?
**Answer:**
> *"We implement a multi-layered verification strategy:*
> 1. *Strict System Prompting: Context chunks are formatted with explicit headers (`# File: orders.py (Lines 24-52)`), and the LLM is instructed to only assert claims with citations in the exact syntax `[file:start-end]`.*
> 2. *Deterministic Regex Parsing: When the LLM responds, `repomind/rag.py` parses all citations using regular expressions.*
> 3. *Grounding Validation against SQLite: Each citation is verified against the database. We check whether the file actually exists, whether the cited line range falls within the retrieved context chunks, and whether those lines exist in the file.*
> 4. *Confidence Scoring: A Groundedness Confidence Score is computed (ratio of valid citations to total citations). In the UI and CLI, unverified citations are explicitly flagged with warning badges.*
> 5. *Evidence-Only Fallback: When no LLM is configured (no Groq key, no Ollama), RepoMind returns the retrieved evidence with citations instead of generated prose, so there's nothing to hallucinate."*

### Q4: Why did you choose SQLite FTS5 instead of Elasticsearch or an external search engine?
**Answer:**
> *"RepoMind has to run on a laptop and on a 512 MB free-tier server, without extra infrastructure. Elasticsearch requires a JVM, hundreds of megabytes of resident memory, and background daemon management.*
>
> *SQLite is embedded in Python's standard library, requires zero background processes, runs in-process with sub-millisecond query latency, and its FTS5 extension provides high-performance BM25 indexing natively. Furthermore, using SQLite lets us store relational AST metadata (`files`, `functions`, `classes`, `symbol_calls`) and sparse text indices in a single local file with transactional ACID integrity."*

### Q5: How did you calculate cyclomatic complexity without executing the code?
**Answer:**
> *"We calculate it statically using Python's `ast` module. Cyclomatic complexity measures the number of decision points in a control flow graph plus one. By visiting the AST subtree for each function node, we count every branching construct (`If`, `While`, `For`, `AsyncFor`), exception handler (`ExceptHandler`), assertion (`Assert`), context manager (`With`), and boolean operator (`BoolOp`). This provides an exact, deterministic complexity score in microseconds without any runtime execution risk."*

### Q6: How does blast radius analysis work, and why is it useful?
**Answer:**
> *"When refactoring a function or module, developers need to know what downstream services might break. We construct a directed graph where an edge represents an import relationship. To find the blast radius, we invert the graph edges and perform a breadth-first search starting from the modified file.*
>
> *This identifies both direct importers (depth 1) and transitive dependents (depth 2+). We also cross-reference our AST `symbol_calls` table to show which specific functions call methods in the target, and display the target's PageRank centrality to convey how critical the module is to the overall architecture."*

### Q7: How does RepoMind maintain low memory usage on an 8 GB RAM laptop?
**Answer:**
> *"Memory discipline is maintained through three key decisions:*
> 1. *Lazy Loading: Heavy neural networks (`SentenceTransformer`) and ChromaDB vector indices are only instantiated when an embedding or vector search request occurs. CLI commands that only require AST parsing or SQLite queries never load PyTorch weights.*
> 2. *Persistent On-Disk Indices: FTS5 and ChromaDB persist on disk rather than in RAM. We do not rebuild BM25 indices in memory on every invocation.*
> 3. *Streaming AST Traversal: File discovery and AST parsing run iteratively, committing records to SQLite in transactions and releasing AST nodes to Python's garbage collector immediately."*

### Q8: What security considerations did you address for path handling and file viewing?
**Answer:**
> *"Ingested repositories must be treated as untrusted input. In `backend/security.py`, we implement `resolve_safe_path()` to prevent path traversal attacks. The function checks for null bytes, resolves canonical paths using `Path.resolve()`, and calls `relative_to()` on the repository root, which raises if the resolved path is outside it. The API turns that into `HTTP 403 Forbidden`, so `../` escapes and symlinks pointing outside the repo are blocked. When cloning, we also disable symlinks entirely (`core.symlinks=false`), skip files over 2 MB, and reject repos with more than 2,000 Python files."*

### Q9: How do you prevent Server-Side Request Forgery (SSRF) when cloning remote Git repositories?
**Answer:**
> *"`validate_git_url()` in `backend/security.py` accepts only `https://` URLs whose host is on an allow-list: github.com, gitlab.com or bitbucket.org. The allow-list is the real SSRF control, since internal services and cloud metadata IPs simply can't be named. It also requires a strict `owner/repo` path, which blocks shell metacharacters. The clone itself runs `git` as an argument list (no shell) with `--` before the URL, `GIT_TERMINAL_PROMPT=0` so it can't hang on a password prompt, a 60-second timeout, and `--depth 1`. On the public demo, clones are also rate-limited to 5 per IP per hour. I deliberately didn't do DNS-based IP filtering: with an allow-list it adds nothing, and DNS checks are prone to rebinding tricks anyway."*

### Q10: How did you evaluate the performance of your retrieval system?
**Answer:**
> *"I wrote 20 ground-truth questions about RepoMind's own code (`eval/gold.json`), each labelled with the file that answers it, and a script (`eval/run.py`) that measures Hit@5 and MRR@5 for several retrieval setups.*
>
> *Results: vector-only Hit@5 0.85 / MRR 0.70; hybrid RRF 0.80 / 0.56; hybrid plus the lexical reranker used in production 0.85 / 0.70 (Hit@1 0.60), at about 0.2 s per query. The surprise was that fusion hurt until reranking was added. That's why I treat the benchmark as a regression test: I re-run it after every retrieval change. It's small (20 questions, one repo), so I don't present it as a general score."*

### Q11: What are the fundamental limitations of static Python AST analysis?
**Answer:**
> *"Static AST analysis can only reason about syntax trees that are explicitly declared in the code. It cannot resolve dynamic runtime behavior such as `getattr(obj, func_name)()`, dictionary-based dispatch tables, runtime monkeypatching, or dynamic imports via `importlib.import_module()`. To mitigate this, RepoMind combines static AST symbols with full-text lexical indexing and vector search, so even if a relationship is dynamic, the code text remains searchable."*

### Q12: How does incremental vector synchronization work when code changes?
**Answer:**
> *"During indexing, RepoMind computes a SHA-256 hash for every file and stores it in SQLite. On subsequent runs, files whose hash has not changed are skipped. When a file is modified, its outdated chunk IDs are queried from SQLite and deleted from both ChromaDB and the SQLite `fts_chunks` table before newly parsed AST chunks are generated and upserted. Deleted files have their database records and vector chunks removed via cascading foreign keys."*

### Q13: Why did you separate the frontend and backend instead of rendering server-side templates with Jinja2?
**Answer:**
> *"Separating the system into a FastAPI backend and a Vite + React 19 frontend provides several key engineering benefits:*
> 1. *Clear API Contract: FastAPI automatically generates OpenAPI (Swagger) specifications, allowing typed frontend clients.*
> 2. *Interactive Client-Side State: Features like interactive dependency graphs, filterable symbol tables, and instant code tab switching require rich client-side interactivity that is cumbersome with server-rendered HTML.*
> 3. *Reusability: The backend API can serve both the React web application and external tools (such as IDE extensions or MCP servers) simultaneously."*

### Q14: How would you scale this architecture to a 10-million-line monorepo?
**Answer:**
> *"If scaling to a 10-million-line monorepo:*
> 1. *Distributed AST Parsing: Distribute parsing across a worker pool (e.g. Celery or multiprocessing) by sharding directories.*
> 2. *Distributed Vector Index: Replace embedded ChromaDB with a distributed vector index like Milvus or Qdrant with HNSW indexing.*
> 3. *Sharded FTS: Shard SQLite FTS5 by top-level package or migrate to Tantivy (a high-performance Rust-based Lucene alternative).*
> 4. *Language Server Protocol (LSP) / SCIP: Complement AST parsing with SCIP (Source Code Intelligence Protocol) indexers for multi-language cross-references."*

### Q15: What was the most challenging bug or edge case you encountered while building this?
**Answer:**
> *"One interesting edge case was handling relative imports in standalone sample packages. When parsing `from .database import db` in a root-level module, Python's `ast.ImportFrom` returns `level=1` and `module='database'`. Because the module is at the top level with no parent package dot, naive relative resolution returned `None` or an empty module name, disconnecting the dependency graph.*
>
> *We resolved this in `graph_builder.py` by implementing standard top-level fallback resolution and canonicalizing import paths so that internal modules correctly resolve into connected NetworkX graph edges regardless of relative import styling."*

---

## 5. Code File Reference Map

When reviewing or demonstrating the codebase, use this map:

| Feature / Subsystem | Primary Code File | Key Functions / Classes |
|---|---|---|
| **AST Parsing & Complexity** | `repomind/parser.py` | `ASTParser`, `visit_FunctionDef`, `_calc_complexity`, `_extract_calls` |
| **Database & FTS5** | `repomind/database.py` | `RepoDatabase`, `init_schema`, `upsert_file`, `search_fts` |
| **Symbol Chunking** | `repomind/chunking.py` | `SymbolChunker`, `chunk_file`, `_chunk_symbol` |
| **Embeddings (ChromaDB)** | `repomind/embedder.py` | `CodeEmbedder`, `embed_chunks`, `query_similar` |
| **Hybrid Search & RRF** | `repomind/hybrid.py` | `HybridRetriever`, `reciprocal_rank_fusion`, `code_aware_tokenize` |
| **Q&A & Citation Verifier** | `repomind/rag.py` | `RAGEngine`, `verify_citations`, `synthesize_answer` |
| **Dependency Graph & Impact** | `repomind/graph_builder.py` | `DependencyGraphBuilder`, `compute_blast_radius`, `find_cycles` |
| **Git Churn & Hotspots** | `repomind/git_analyzer.py` | `GitAnalyzer`, `calculate_hotspots`, `get_bus_factor` |
| **Evaluation Benchmark** | `repomind/evaluator.py` | `RetrievalEvaluator`, `run_benchmark` |
| **Backend REST Routers** | `backend/routers/*.py` | `repos.py`, `files.py`, `search.py`, `qa.py`, `graph.py`, `impact.py` |
| **Security & Path Guards** | `backend/security.py` | `resolve_safe_path`, `validate_git_url` |
| **React UI Views** | `frontend/src/views/*.py` | `OverviewView`, `FilesView`, `SymbolsView`, `AskView`, `GraphView` |
