# RepoMind Retrieval Eval

Chunks: 131 | k=5 | vector hit@5=0.850 MRR=0.742 | hybrid hit@5=0.950 MRR=0.717

| Question | Expected | Top-3 got | Rank |
|---|---|---|---|
| how does prune of deleted files work? | repomind/database.py | repomind/database.py,repomind/cli.py,tests/test_database.py | 1 |
| where are relative imports resolved? | repomind/parser.py | repomind/parser.py,tests/test_parsers.py,repomind/parser.py | 1 |
| how are functions extracted with qualified names? | repomind/parser.py | repomind/parser.py,tests/test_parsers.py,tests/test_parsers.py | 1 |
| how is SHA hash used to skip unchanged files? | repomind/parser.py,repomind/cli.py | repomind/parser.py,tests/test_parsers.py,repomind/parser.py | 1 |
| what tables exist in SQLite storage? | repomind/database.py | repomind/rag.py,repomind/database.py,repomind/database.py | 2 |
| how does upsert on file path work? | repomind/database.py | tests/test_database.py,repomind/database.py,repomind/database.py | 2 |
| which embedding model converts code to vectors? | repomind/embedder.py | repomind/embedder.py,repomind/embedder.py,repomind/embedder.py | 1 |
| how are code chunks built for ChromaDB? | repomind/rag.py,repomind/chunking.py | repomind/embedder.py,repomind/rag.py,repomind/rag.py | 2 |
| what are the 5 steps of ask RAG pipeline? | repomind/rag.py | repomind/rag.py,repomind/rag.py,repomind/cli.py | 1 |
| how does Ollama client send prompts? | repomind/llm.py | repomind/llm.py,repomind/llm.py,repomind/llm.py | 1 |
| how is dependency graph built from imports? | repomind/graph_builder.py | repomind/graph_builder.py,repomind/graph_builder.py,repomind/graph_builder.py | 1 |
| how is PageRank used for important files? | repomind/graph_builder.py | repomind/graph_builder.py,repomind/graph_builder.py,tests/test_graph_builder.py | 1 |
| how are orphan files and cycles detected? | repomind/graph_builder.py | repomind/git_analyzer.py,tests/test_cli.py,tests/test_database.py | - |
| how are git hotspots and ghost files found? | repomind/git_analyzer.py | repomind/git_analyzer.py,repomind/git_analyzer.py,repomind/git_analyzer.py | 1 |
| what sections are in the HTML report? | repomind/report.py | repomind/report.py,repomind/cli.py,repomind/report.py | 1 |
| how are Python files found while skipping venv? | repomind/utils.py | repomind/utils.py,repomind/utils.py,repomind/cli.py | 1 |
| which CLI commands exist for index and search? | repomind/cli.py | tests/test_cli.py,tests/test_cli.py,repomind/cli.py | 3 |
| how are citations formatted with file and lines? | repomind/rag.py | repomind/parser.py,repomind/chunking.py,repomind/database.py | - |
| how does chunk overlap handle long functions? | repomind/chunking.py | repomind/chunking.py,repomind/chunking.py,repomind/chunking.py | 1 |
| how are external vs internal imports distinguished? | repomind/graph_builder.py | repomind/parser.py,tests/test_graph_builder.py,repomind/database.py | - |