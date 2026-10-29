# RepoMind Retrieval Eval

Chunks: 502 | k=5 | reranker: lexical | embeddings: onnx

| Setup | Slice | n | Hit@1 | Hit@5 | MRR@5 |
|---|---|---|---|---|---|
| vector | all | 35 | 0.66 | 0.91 | 0.78 |
| vector | identifier | 15 | 0.80 | 1.00 | 0.89 |
| vector | natural | 20 | 0.55 | 0.85 | 0.70 |
| hybrid | all | 35 | 0.57 | 0.89 | 0.70 |
| hybrid | identifier | 15 | 0.80 | 1.00 | 0.90 |
| hybrid | natural | 20 | 0.40 | 0.80 | 0.56 |
| hybrid+rerank | all | 35 | 0.77 | 0.91 | 0.83 |
| hybrid+rerank | identifier | 15 | 1.00 | 1.00 | 1.00 |
| hybrid+rerank | natural | 20 | 0.60 | 0.85 | 0.70 |

## Per-question results (hybrid+rerank, the live demo setup)

| Kind | Question | Expected | Top-3 got | Rank |
|---|---|---|---|---|
| natural | how does prune of deleted files work? | repomind/database.py | repomind/database.py,tests/test_cli.py,tests/test_database.py | 1 |
| natural | where are relative imports resolved? | repomind/parser.py | repomind/parser.py,tests/test_parsers.py,repomind/parser.py | 1 |
| natural | how are functions extracted with qualified names? | repomind/parser.py | tests/test_parsers.py,repomind/parser.py,repomind/database.py | 2 |
| natural | how is SHA hash used to skip unchanged files? | repomind/parser.py,repomind/cli.py | repomind/cli.py,repomind/parser.py,tests/test_cli.py | 1 |
| natural | what tables exist in SQLite storage? | repomind/database.py | backend/services/repo_manager.py,repomind/evaluator.py,tests/test_v2_features.py | - |
| natural | how does upsert on file path work? | repomind/database.py | tests/test_database.py,tests/test_v2_features.py,tests/test_local_repo.py | 4 |
| natural | which embedding model converts code to vectors? | repomind/embedder.py | repomind/embedder.py,tests/conftest.py,repomind/embedder.py | 1 |
| natural | how are code chunks built for ChromaDB? | repomind/rag.py,repomind/chunking.py | repomind/cli.py,repomind/rag.py,repomind/rag.py | 2 |
| natural | what are the 5 steps of ask RAG pipeline? | repomind/rag.py | repomind/rag.py,repomind/rag.py,repomind/rag.py | 1 |
| natural | how does Ollama client send prompts? | repomind/llm.py | repomind/llm.py,repomind/llm.py,backend/services/qa_service.py | 1 |
| natural | how is dependency graph built from imports? | repomind/graph_builder.py | repomind/graph_builder.py,repomind/cli.py,repomind/graph_builder.py | 1 |
| natural | how is PageRank used for important files? | repomind/graph_builder.py | backend/services/graph_service.py,repomind/git_analyzer.py,repomind/graph_builder.py | 3 |
| natural | how are orphan files and cycles detected? | repomind/graph_builder.py | backend/routers/graph.py,tests/test_graph_builder.py,tests/test_github_repo.py | - |
| natural | how are git hotspots and ghost files found? | repomind/git_analyzer.py | repomind/git_analyzer.py,tests/test_github_repo.py,repomind/git_analyzer.py | 1 |
| natural | what sections are in the HTML report? | repomind/report.py | repomind/report.py,repomind/report.py,repomind/report.py | 1 |
| natural | how are Python files found while skipping venv? | repomind/utils.py | repomind/cli.py,repomind/parser.py,tests/test_parsers.py | - |
| natural | which CLI commands exist for index and search? | repomind/cli.py | repomind/cli.py,repomind/cli.py,repomind/cli.py | 1 |
| natural | how are citations formatted with file and lines? | repomind/rag.py | repomind/rag.py,repomind/parser.py,backend/services/qa_service.py | 1 |
| natural | how does chunk overlap handle long functions? | repomind/chunking.py | tests/test_chunking.py,repomind/mcp_server.py,repomind/chunking.py | 3 |
| natural | how are external vs internal imports distinguished? | repomind/graph_builder.py | repomind/graph_builder.py,repomind/graph_builder.py,tests/test_graph_builder.py | 1 |
| identifier | where is verify_citations defined? | repomind/rag.py | repomind/rag.py,repomind/rag.py,tests/test_v2_features.py | 1 |
| identifier | compute_blast_radius | repomind/graph_builder.py | repomind/graph_builder.py,repomind/graph_builder.py,backend/services/graph_service.py | 1 |
| identifier | what does rrf_fuse do with the k parameter? | repomind/hybrid.py | repomind/hybrid.py,tests/test_hybrid.py,tests/test_v2_features.py | 1 |
| identifier | how does _resolve_from_module handle dots? | repomind/parser.py | repomind/parser.py,backend/security.py,tests/test_parsers.py | 1 |
| identifier | search_fts query escaping | repomind/database.py | repomind/database.py,tests/test_v2_features.py,backend/routers/search.py | 1 |
| identifier | split_identifier camelCase handling | repomind/utils.py | repomind/utils.py,repomind/utils.py,tests/test_v2_features.py | 1 |
| identifier | what does graph_context_for_files return? | repomind/graphrag.py | repomind/graphrag.py,backend/routers/graph.py,repomind/rag.py | 1 |
| identifier | validate_git_url | backend/security.py | backend/security.py,backend/services/repo_manager.py,tests/test_github_repo.py | 1 |
| identifier | _enforce_github_rate_limit | backend/routers/repos.py | backend/routers/repos.py,tests/test_public_mode.py,tests/test_public_mode.py | 1 |
| identifier | GroqClient.generate | repomind/llm.py | repomind/llm.py,repomind/llm.py,repomind/llm.py | 1 |
| identifier | _OnnxModel BATCH_SIZE | repomind/embedder.py | repomind/embedder.py,repomind/embedder.py,repomind/embedder.py | 1 |
| identifier | RepoMindMCPServer.handle_tool_call | repomind/mcp_server.py | repomind/mcp_server.py,repomind/mcp_server.py,repomind/mcp_server.py | 1 |
| identifier | get_ghost_files | repomind/git_analyzer.py | repomind/git_analyzer.py,repomind/database.py,backend/routers/files.py | 1 |
| identifier | detect_query_intent | repomind/hybrid.py | repomind/hybrid.py,tests/test_v2_features.py,backend/services/search_service.py | 1 |
| identifier | where is prune_paths called? | repomind/database.py,repomind/cli.py | repomind/database.py,tests/test_database.py,repomind/database.py | 1 |
