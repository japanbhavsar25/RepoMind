"""RepoMind CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from repomind import __version__
from repomind.database import RepoDatabase
from repomind.git_analyzer import GitAnalyzer
from repomind.graph_builder import GraphBuilder
from repomind.llm import OllamaError
from repomind.parser import extract_file, hash_bytes
from repomind.rag import RepoRAG
from repomind.report import ReportGenerator
from repomind.utils import find_python_files

app = typer.Typer(
    name="repomind",
    help="Ask your Python codebase questions. Get answers.",
    add_completion=False,
)
console = Console()


def _show_version(value: bool) -> None:
    if value:
        console.print(f"RepoMind {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_show_version,
        is_eager=True,
        help="Show the RepoMind version and exit.",
    ),
) -> None:
    """Ask your Python codebase questions. Get answers."""


@app.command()
def index(
    path: Path = typer.Argument(Path("."), help="Path to Python project to index"),
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
) -> None:
    """Index a Python project into the database.

    Unchanged files (same content hash) are skipped, so re-indexing an
    already-indexed project is fast.
    """
    if not path.exists():
        console.print(f"[red]Path not found:[/red] {path}")
        raise typer.Exit(1)

    console.print(Panel.fit(f"Indexing [cyan]{path.resolve()}[/cyan]", title="RepoMind"))

    py_files = find_python_files(path)
    current_paths: set[str] = set()
    skipped = 0
    syntax_errors = 0

    if not py_files:
        # Project emptied since the last index: drop stale entries too
        with RepoDatabase(db) as db_conn:
            removed = db_conn.prune_paths(set())
            db_conn.commit()
        console.print("[yellow]No Python files found.[/yellow]")
        if removed:
            console.print(f"  [dim]{removed} deleted file(s) removed from index[/dim]")
        raise typer.Exit(0)

    with RepoDatabase(db) as db_conn:
        existing = db_conn.get_file_hashes()  # path -> (file_id, content_hash)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Processing {len(py_files)} files...", total=len(py_files))

            for py_file in py_files:
                rel_path = py_file.relative_to(path).as_posix()
                current_paths.add(rel_path)

                raw = py_file.read_bytes()
                content_hash = hash_bytes(raw)

                if rel_path in existing and existing[rel_path][1] == content_hash:
                    skipped += 1
                    progress.advance(task)
                    continue

                text = raw.decode("utf-8", errors="replace")
                line_count = len(text.splitlines())
                last_modified = py_file.stat().st_mtime

                # Re-parsing a changed file: drop its old symbols first
                if rel_path in existing:
                    db_conn.delete_symbols(existing[rel_path][0])

                file_id = db_conn.insert_file(rel_path, content_hash, line_count, last_modified)

                try:
                    functions, classes, imports, symbol_calls = extract_file(
                        py_file, file_id, rel_path=rel_path, source=text
                    )
                    if functions:
                        db_conn.insert_functions(functions)
                    if classes:
                        db_conn.insert_classes(classes)
                    if imports:
                        db_conn.insert_imports(imports)
                    if symbol_calls:
                        db_conn.insert_symbol_calls(symbol_calls)
                except SyntaxError as e:
                    syntax_errors += 1
                    console.print(f"[yellow]Syntax error in {rel_path}: {e}[/yellow]")

                # Commit once per file so partial work is never lost
                db_conn.commit()
                progress.advance(task)

        # Remove index entries for files that no longer exist on disk
        removed = db_conn.prune_paths(current_paths)
        db_conn.commit()

        stats = db_conn.get_stats()

    console.print("\n[green]Indexing complete![/green]")
    if skipped:
        console.print(f"  [dim]{skipped} unchanged file(s) skipped[/dim]")
    if removed:
        console.print(f"  [dim]{removed} deleted file(s) removed from index[/dim]")

    table = Table(title="Repository Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_row("Files", str(stats["files"]))
    table.add_row("Functions", str(stats["functions"]))
    table.add_row("Classes", str(stats["classes"]))
    table.add_row("Imports", str(stats["imports"]))
    console.print(table)


@app.command()
def embed(
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
    full_rebuild: bool = typer.Option(False, "--full-rebuild", help="Wipe Chroma and re-embed all"),
) -> None:
    """Build vector embeddings from indexed code for semantic search.

    Incremental by default (skips unchanged chunks). Uses the built-in
    all-MiniLM-L6-v2 sentence transformer; the Ollama
    model is only used later by the 'ask' command.
    """
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' first.[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit("Building embeddings...", title="RepoMind"))

    rag = RepoRAG(db)
    stats = rag.build_index(full_rebuild=full_rebuild)

    count = rag.collection.count()
    console.print(
        f"[green]Embeddings built![/green] {count} code chunks in ChromaDB "
        f"({stats.get('added_or_updated',0)} added/updated, "
        f"{stats.get('skipped',0)} skipped, {stats.get('deleted',0)} deleted)."
    )


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question about your codebase"),
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
    model: str = typer.Option("phi3", "--model", help="Ollama model name"),
    top_k: int = typer.Option(5, "--top-k", min=1, help="Number of code chunks to retrieve"),
    hybrid: bool = typer.Option(False, "--hybrid", help="Use BM25+vector hybrid retrieval"),
    rerank: bool = typer.Option(False, "--rerank", help="Cross-encoder rerank top candidates"),
    stream: bool = typer.Option(False, "--stream", help="Stream tokens as they arrive"),
) -> None:
    """Ask a natural-language question about your indexed codebase."""
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' first.[/red]")
        raise typer.Exit(1)

    rag = RepoRAG(db, model=model)

    if rag.collection.count() == 0:
        console.print("[yellow]No embeddings found. Run 'repomind embed' first.[/yellow]")
        raise typer.Exit(1)

    if stream:
        from rich.live import Live
        from rich.markdown import Markdown

        try:
            docs, metas, _ = rag.retrieve(question, top_k=top_k, hybrid=hybrid, rerank=rerank)
            prompt, system = rag.build_prompt(question, docs, metas)
            full = ""
            with Live(Markdown("Thinking..."), console=console, transient=True) as live:
                for tok in rag.llm.generate_stream(prompt, system=system, temperature=0.2):
                    full += tok
                    live.update(Markdown(full + "▌"))
            console.print(Panel(Markdown(full or "_Empty response_"), title=f"Q: {question}", border_style="green"))
        except OllamaError as e:
            console.print(Panel(str(e), title=f"Q: {question}", border_style="red"))
            raise typer.Exit(1) from e
        return

    with console.status("[cyan]Thinking...[/cyan]", spinner="dots"):
        try:
            answer = rag.ask(question, top_k=top_k, hybrid=hybrid, rerank=rerank)
        except OllamaError as e:
            console.print(Panel(str(e), title=f"Q: {question}", border_style="red"))
            raise typer.Exit(1) from e

    console.print(Panel(answer, title=f"Q: {question}", border_style="green"))

    if rag.last_verification:
        v = rag.last_verification
        lvl = v["level"]
        colors = {"HIGH": "bold green", "MEDIUM": "bold yellow", "LOW": "bold red"}
        color = colors.get(lvl, "white")
        if v["total_citations"] > 0:
            badge = f"[{color}]* Citation Confidence & Groundedness: {lvl} ({v['confidence_pct']}%) - {v['grounded_count']}/{v['total_citations']} citations grounded[/{color}]"
        else:
            badge = f"[dim]* Citation Confidence: {lvl} (No inline citations detected)[/dim]"
        console.print(badge)


@app.command()
def graph(
    path: Path = typer.Argument(Path("."), help="Path to Python project"),
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
    output: Path = typer.Option(Path(".repomind_output"), "--output", "-o", help="Output directory"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open graph in browser"),
    max_commits: int = typer.Option(500, "--max-commits", min=1, help="Git commits to mine"),
) -> None:
    """Generate an interactive dependency graph of your codebase."""
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' first.[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit("Building dependency graph...", title="RepoMind"))

    # Build graph from imports
    builder = GraphBuilder(db, path)
    builder.build()
    analysis = builder.analyze()

    # Git analysis for coloring
    git = GitAnalyzer(path)
    git_stats = git.analyze(max_commits=max_commits) if git.is_valid() else {}

    # Generate PyVis HTML
    net = builder.to_pyvis(git_stats=git_stats)
    reporter = ReportGenerator(output)
    graph_path = reporter.save_graph(net)

    console.print(f"[green]Graph saved:[/green] {graph_path.resolve()}")
    console.print(f"  Nodes: {analysis['node_count']} | Edges: {analysis['edge_count']}")
    console.print(f"  Orphans: {len(analysis['orphans'])}")

    if builder.warnings:
        for w in builder.warnings[:5]:
            console.print(f"  [yellow]Warn:[/yellow] {w}")

    if analysis["cycles"]:
        console.print(f"  [yellow]Cycles detected:[/yellow] {len(analysis['cycles'])}")

    if open_browser:
        typer.launch(str(graph_path.resolve()))


@app.command()
def report(
    path: Path = typer.Argument(Path("."), help="Path to Python project"),
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
    output: Path = typer.Option(Path(".repomind_output"), "--output", "-o", help="Output directory"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open report in browser"),
    max_commits: int = typer.Option(500, "--max-commits", min=1, help="Git commits to mine"),
) -> None:
    """Generate a full HTML analysis report."""
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' first.[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit("Generating analysis report...", title="RepoMind"))

    # Stats from DB
    with RepoDatabase(db) as db_conn:
        stats = db_conn.get_stats()

    # Graph analysis
    builder = GraphBuilder(db, path)
    builder.build()
    graph_analysis = builder.analyze()

    # Git analysis
    git = GitAnalyzer(path)
    git_stats = git.analyze(max_commits=max_commits) if git.is_valid() else {}
    ghost_files = git.get_ghost_files(git_stats, days=180) if git.is_valid() else []

    # Generate report
    reporter = ReportGenerator(output)
    report_path = reporter.generate(stats, graph_analysis, git_stats, ghost_files, db_path=db)
    net = builder.to_pyvis(git_stats=git_stats)
    graph_path = reporter.save_graph(net)

    console.print(f"[green]Report saved:[/green]  {report_path.resolve()}")
    console.print(f"[green]Graph saved:[/green]   {graph_path.resolve()}")

    if open_browser:
        typer.launch(str(report_path.resolve()))


@app.command()
def stats(
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
) -> None:
    """Show indexed repository statistics."""
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' first.[/red]")
        raise typer.Exit(1)

    with RepoDatabase(db) as db_conn:
        data = db_conn.get_stats()
        table = Table(title="RepoMind Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="magenta")
        table.add_row("Files", str(data["files"]))
        table.add_row("Functions", str(data["functions"]))
        table.add_row("Classes", str(data["classes"]))
        table.add_row("Imports", str(data["imports"]))
        console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search term for function/class names"),
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
) -> None:
    """Search indexed functions and classes by name."""
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' first.[/red]")
        raise typer.Exit(1)

    with RepoDatabase(db) as db_conn:
        rows = db_conn.search(query)

    if not rows:
        console.print(f"[yellow]No results for '{query}'[/yellow]")
        return

    table = Table(title=f"Search Results: '{query}'")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Location", style="yellow")
    for row in rows:
        type_, name, qname, start, end, file_path = row
        table.add_row(type_, qname or name, f"{file_path}:{start}-{end}")
    console.print(table)


@app.command()
def impact(
    target: str = typer.Argument(..., help="File path or symbol name to analyze blast radius for"),
    path: Path = typer.Option(Path("."), "--path", "-p", help="Path to Python project"),
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON analysis"),
) -> None:
    """Analyze the downstream blast radius, cyclomatic complexity, and callers for a file or symbol."""
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' first.[/red]")
        raise typer.Exit(1)

    builder = GraphBuilder(db, path)
    builder.build()
    result = builder.compute_blast_radius(target)

    if json_output:
        import json

        console.print_json(json.dumps(result, indent=2))
        return

    # Print Rich formatted analysis
    risk = result["risk_level"]
    risk_colors = {"CRITICAL": "bold red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
    risk_badge = f"[{risk_colors.get(risk, 'white')}]{risk}[/{risk_colors.get(risk, 'white')}]"

    title = f"Blast-Radius & Impact Analysis: {target}"
    console.print(
        Panel.fit(
            f"Target: [cyan]{result['file']}[/cyan] ({result['target_type']}) | Risk Level: {risk_badge}",
            title=title,
        )
    )

    # Metrics table
    metrics_table = Table(title="Criticality & Complexity Metrics")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="magenta")
    metrics_table.add_row("PageRank Criticality", f"{result['pagerank']:.4f}")
    metrics_table.add_row("Direct Importers", str(len(result["direct_importers"])))
    metrics_table.add_row("Transitive Blast Radius", f"{result['blast_radius_count']} file(s)")
    metrics_table.add_row("Max Cyclomatic Complexity", str(result["complexity"]["max"]))
    metrics_table.add_row("Avg Cyclomatic Complexity", f"{result['complexity']['average']:.1f}")
    metrics_table.add_row("Total Complexity Points", str(result["complexity"]["total"]))
    console.print(metrics_table)

    if result["direct_importers"]:
        console.print("\n[bold]Direct Importers:[/bold]")
        for imp in result["direct_importers"]:
            console.print(f"  * [green]{imp}[/green]")

    if result["transitive_dependents"]:
        console.print(
            f"\n[bold]Transitive Downstream Dependents ({len(result['transitive_dependents'])}):[/bold]"
        )
        for dep in result["transitive_dependents"][:15]:
            console.print(f"  -> [yellow]{dep}[/yellow]")
        if len(result["transitive_dependents"]) > 15:
            console.print(f"  [dim]... and {len(result['transitive_dependents']) - 15} more[/dim]")

    if result["callers"]:
        console.print(f"\n[bold]Direct Symbol Callers ({len(result['callers'])}):[/bold]")
        for c in result["callers"][:10]:
            console.print(
                f"  * [cyan]{c['caller_symbol']}[/cyan] ({c['caller_file']}:{c['line_number']}) -> [green]{c['callee']}[/green]"
            )


@app.command()
def evaluate(
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
    gold: Path = typer.Option(Path("eval/gold.json"), "--gold", help="Path to gold benchmark queries"),
    samples: int = typer.Option(20, "--samples", "-n", min=1, help="Max number of benchmark queries"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON results"),
) -> None:
    """Run quantitative retrieval evaluation comparing Dense-Only, Sparse-Only, and Hybrid RRF."""
    if not db.exists():
        console.print("[red]No database found. Run 'repomind index' and 'repomind embed' first.[/red]")
        raise typer.Exit(1)

    from repomind.evaluator import RetrievalEvaluator

    evaluator = RetrievalEvaluator(db)
    if evaluator.rag.collection.count() == 0:
        console.print("[yellow]ChromaDB is empty. Run 'repomind embed' first.[/yellow]")
        raise typer.Exit(1)

    with console.status(
        "[cyan]Evaluating retrieval strategies across benchmark queries...[/cyan]", spinner="dots"
    ):
        gold_path = gold if gold.exists() else None
        results = evaluator.run_full_evaluation(gold_path=gold_path, max_samples=samples)

    if json_output:
        import json

        console.print_json(json.dumps(results, indent=2))
        return

    table = evaluator.build_summary_table(results)
    console.print(table)


@app.command()
def mcp(
    db: Path = typer.Option(Path(".repomind.db"), "--db", help="Database file path"),
    path: Path = typer.Option(Path("."), "--path", "-p", help="Path to Python project"),
) -> None:
    """Start local Model Context Protocol (MCP) server over stdio for AI IDEs."""
    from repomind.mcp_server import RepoMindMCPServer

    server = RepoMindMCPServer(db_path=db, repo_path=path)
    server.run_stdio()


if __name__ == "__main__":
    app()
