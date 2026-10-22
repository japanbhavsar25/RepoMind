"""Generate HTML reports from analysis."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pyvis.network import Network

from repomind.database import RepoDatabase
from repomind.git_analyzer import GitAnalyzer

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>RepoMind Architecture & Intelligence Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            margin: 0; padding: 0;
            background: #0d1117; color: #c9d1d9;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        h1 { color: #58a6ff; border-bottom: 2px solid #21262d; padding-bottom: 12px; }
        h2 { color: #79c0ff; margin-top: 48px; font-size: 22px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px; margin: 24px 0;
        }
        .stat-card {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 12px; padding: 20px; text-align: center;
            transition: transform 0.2s;
        }
        .stat-card:hover { transform: translateY(-4px); border-color: #58a6ff; }
        .stat-value { font-size: 36px; font-weight: 800; color: #58a6ff; }
        .stat-label { font-size: 13px; color: #8b949e; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }

        .health-card {
            background: linear-gradient(135deg, #161b22, #1c2128);
            border: 2px solid #30363d; border-radius: 12px;
            padding: 24px 32px; margin: 24px 0;
            display: flex; align-items: center; justify-content: space-between;
        }
        .health-score-ring {
            font-size: 48px; font-weight: 900;
        }
        .score-green { color: #3fb950; }
        .score-yellow { color: #d29922; }
        .score-red { color: #f85149; }

        .search-box {
            margin: 20px 0;
        }
        .search-input {
            width: 100%; max-width: 400px; padding: 10px 14px;
            border-radius: 8px; border: 1px solid #30363d;
            background: #161b22; color: #c9d1d9; font-size: 14px;
            outline: none;
        }
        .search-input:focus { border-color: #58a6ff; box-shadow: 0 0 6px rgba(88,166,255,0.3); }

        table {
            width: 100%; border-collapse: collapse; margin: 16px 0;
            background: #161b22; border-radius: 8px; overflow: hidden;
            border: 1px solid #30363d;
        }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #30363d; }
        th { background: #21262d; color: #58a6ff; font-weight: 700; font-size: 13px; text-transform: uppercase; }
        tr:hover { background: #1c2128; }
        tr:last-child td { border-bottom: none; }
        .badge {
            display: inline-block; padding: 3px 10px;
            border-radius: 12px; font-size: 11px; font-weight: 700;
        }
        .hot { background: #da3633; color: white; }
        .warm { background: #d29922; color: #0d1117; }
        .cool { background: #1f6feb; color: white; }
        .ghost-badge { background: #8957e5; color: white; }
        .silo-badge { background: #f85149; color: white; margin-left: 6px; }
        .section { margin-bottom: 50px; }
        .graph-link {
            display: inline-block; margin-top: 10px; padding: 12px 24px;
            background: #238636; color: white; text-decoration: none;
            border-radius: 6px; font-weight: 600;
        }
        .graph-link:hover { background: #2ea043; }
        .orphan { color: #f85149; font-weight: 700; }
        .empty-msg { color: #3fb950; font-style: italic; }
        .file-path { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 13px; }
        td.file-path { color: #c9d1d9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>RepoMind Architecture & Health Report</h1>
        <p style="color: #8b949e; font-size: 14px;">Generated on {{ generated_at }}</p>

        <!-- Architecture Health Card -->
        <div class="health-card">
            <div>
                <h3 style="margin: 0; color: #c9d1d9; font-size: 20px;">Architecture Health Score</h3>
                <p style="margin: 6px 0 0; color: #8b949e; font-size: 14px;">
                    Combines circular dependency penalty, orphan isolation, hotspot churn risk, and bus factor silos.
                </p>
                <p style="margin: 8px 0 0; font-weight: 700; color: #79c0ff;">Rating: {{ health_rating }}</p>
            </div>
            <div class="health-score-ring {{ score_color_class }}">
                {{ health_score }}<span style="font-size: 20px; font-weight: 400; color: #8b949e;">/100</span>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ stats.files }}</div>
                <div class="stat-label">Python Files</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.functions }}</div>
                <div class="stat-label">Functions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.classes }}</div>
                <div class="stat-label">Classes</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.imports }}</div>
                <div class="stat-label">Imports</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ graph.node_count }}</div>
                <div class="stat-label">Graph Nodes</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ graph.edge_count }}</div>
                <div class="stat-label">Graph Edges</div>
            </div>
        </div>

        <div class="search-box">
            <input type="text" id="filterInput" class="search-input" placeholder="Quick filter across all tables..." onkeyup="filterAllTables()">
        </div>

        <div class="section">
            <h2>Interactive Dependency Graph</h2>
            <p>Explore your codebase structure. Node size = PageRank criticality. Color = Git churn. Green edges = internal imports. Red edges = external dependencies.</p>
            <a href="repomind_graph.html" class="graph-link" target="_blank">Open Interactive Graph</a>
        </div>

        <!-- Composite Risk Hotspots Leaderboard -->
        <div class="section">
            <h2>Composite Risk Hotspot Leaderboard</h2>
            <p>Ranked by combined score: Commit Churn (45%) + Cyclomatic Complexity (35%) + PageRank Centrality (20%).</p>
            <table class="filterable-table">
                <thead>
                    <tr>
                        <th>File</th>
                        <th>Risk Score</th>
                        <th>Level</th>
                        <th>Commits</th>
                        <th>Complexity</th>
                        <th>PageRank</th>
                        <th>Bus Factor / Primary Author</th>
                    </tr>
                </thead>
                <tbody>
                    {% for h in composite_hotspots %}
                    <tr>
                        <td class="file-path">{{ h.path }}</td>
                        <td><strong>{{ h.risk_score }}</strong></td>
                        <td><span class="badge {{ h.heat }}">{{ h.risk_level }}</span></td>
                        <td>{{ h.commit_count }}</td>
                        <td>{{ h.complexity }}</td>
                        <td>{{ "%.4f"|format(h.pagerank) }}</td>
                        <td>
                            {{ h.top_author }} ({{ h.top_author_pct }}%)
                            {% if h.bus_factor_risk %}
                            <span class="badge silo-badge">Silo Risk</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Cyclomatic Complexity Breakdown -->
        <div class="section">
            <h2>Cyclomatic Complexity Breakdown (Top Decision Density)</h2>
            <p>Functions and methods with high decision counts (if, for, while, except, with, boolean operators). High complexity functions require more unit test coverage.</p>
            <table class="filterable-table">
                <thead>
                    <tr>
                        <th>Function / Method</th>
                        <th>Location</th>
                        <th>Complexity</th>
                        <th>Rating</th>
                    </tr>
                </thead>
                <tbody>
                    {% for f in top_complex_functions %}
                    <tr>
                        <td><strong>{{ f.name }}</strong></td>
                        <td class="file-path">{{ f.file_path }}</td>
                        <td>{{ f.complexity }}</td>
                        <td>
                            {% if f.complexity >= 15 %}
                            <span class="badge hot">High Complexity</span>
                            {% elif f.complexity >= 6 %}
                            <span class="badge warm">Moderate</span>
                            {% else %}
                            <span class="badge cool">Simple</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Ghost Files (Not touched in 6+ months)</h2>
            <p>Files that haven't been modified recently. Candidates for deprecation or removal.</p>
            {% if ghosts %}
            <table class="filterable-table">
                <thead>
                    <tr><th>File</th><th>Last Modified</th></tr>
                </thead>
                <tbody>
                    {% for file in ghosts %}
                    <tr>
                        <td class="file-path">{{ file.path }}</td>
                        <td>{{ file.last_modified }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p class="empty-msg">No ghost files found! Your codebase is actively maintained.</p>
            {% endif %}
        </div>

        <div class="section">
            <h2>Orphan Files (No internal dependencies)</h2>
            <p>Files that neither import nor are imported by other internal files. Consider if they're still needed.</p>
            {% if orphans %}
            <ul>
                {% for orphan in orphans %}
                <li class="orphan file-path">{{ orphan }}</li>
                {% endfor %}
            </ul>
            {% else %}
            <p class="empty-msg">No orphan files found.</p>
            {% endif %}
        </div>

        <div class="section">
            <h2>Top Important Files (PageRank)</h2>
            <p>Most central files in your dependency graph. Changes here have the widest impact.</p>
            <table class="filterable-table">
                <thead>
                    <tr><th>File</th><th>PageRank Score</th></tr>
                </thead>
                <tbody>
                    {% for file in pagerank %}
                    <tr>
                        <td class="file-path">{{ file.path }}</td>
                        <td>{{ file.score }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Circular Dependencies</h2>
            {% if cycles %}
            <p>Import cycles detected. These make refactoring difficult:</p>
            <ul>
                {% for cycle in cycles %}
                <li class="file-path">{{ " → ".join(cycle) }} → {{ cycle[0] }}</li>
                {% endfor %}
            </ul>
            {% else %}
            <p class="empty-msg">No circular dependencies found. Clean modular architecture!</p>
            {% endif %}
        </div>
    </div>

    <script>
        function filterAllTables() {
            var input = document.getElementById("filterInput");
            var filter = input.value.toLowerCase();
            var tables = document.querySelectorAll(".filterable-table");
            tables.forEach(function(table) {
                var rows = table.getElementsByTagName("tr");
                for (var i = 1; i < rows.length; i++) {
                    var text = rows[i].textContent || rows[i].innerText;
                    if (text.toLowerCase().indexOf(filter) > -1) {
                        rows[i].style.display = "";
                    } else {
                        rows[i].style.display = "none";
                    }
                }
            });
        }
    </script>
</body>
</html>
"""


class ReportGenerator:
    """Generates static HTML reports."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        stats: dict,
        graph_analysis: dict,
        git_stats: dict[str, dict],
        ghost_files: list[str],
        db_path: Path | None = None,
    ) -> Path:
        """Generate the HTML report."""
        from jinja2 import Template

        template = Template(HTML_TEMPLATE, autoescape=True)

        # Complexities from SQLite if db_path provided
        complexities_by_file: dict[str, int] = {}
        top_complex_functions: list[dict] = []
        if db_path and db_path.exists():
            try:
                with RepoDatabase(db_path) as db:
                    f_rows = db.get_function_complexities()
                    for _name, _qname, cc, fpath in f_rows:
                        complexities_by_file[fpath] = complexities_by_file.get(fpath, 0) + cc
                    for name, qname, cc, fpath in f_rows[:25]:
                        top_complex_functions.append({
                            "name": qname or name,
                            "file_path": fpath,
                            "complexity": cc,
                        })
            except Exception:
                pass

        # Composite Hotspots
        pr_data = graph_analysis.get("pagerank", {})
        composite_hotspots = GitAnalyzer.compute_composite_hotspots(
            git_stats, complexities_by_file, pr_data
        )[:25]

        # Calculate Architecture Health Score (0-100)
        health_score = 100
        cycles_count = len(graph_analysis.get("cycles", []))
        orphans_count = len(graph_analysis.get("orphans", []))
        health_score -= min(40, cycles_count * 15)
        health_score -= min(20, orphans_count * 3)
        critical_hotspots = sum(1 for h in composite_hotspots if h.get("risk_level") == "CRITICAL")
        health_score -= min(20, critical_hotspots * 5)
        silos_count = sum(1 for h in composite_hotspots if h.get("bus_factor_risk"))
        health_score -= min(15, silos_count * 3)
        ghost_count = len(ghost_files)
        health_score -= min(10, ghost_count * 1)
        health_score = max(10, min(100, health_score))

        if health_score >= 90:
            health_rating = "A (Excellent)"
            score_color_class = "score-green"
        elif health_score >= 80:
            health_rating = "B (Good)"
            score_color_class = "score-green"
        elif health_score >= 70:
            health_rating = "C (Fair)"
            score_color_class = "score-yellow"
        elif health_score >= 60:
            health_rating = "D (Needs Improvement)"
            score_color_class = "score-yellow"
        else:
            health_rating = "F (High Architectural Risk)"
            score_color_class = "score-red"

        # Ghosts
        ghosts = []
        for path in ghost_files[:50]:
            last = git_stats.get(path, {}).get("last_modified", "unknown")
            ghosts.append({"path": path, "last_modified": last})

        # PageRank top 20
        pagerank = []
        internal = sorted(
            ((p, s) for p, s in pr_data.items() if not p.startswith("ext:")),
            key=lambda x: x[1],
            reverse=True,
        )
        for path, score in internal[:20]:
            pagerank.append({"path": path, "score": f"{score:.4f}"})

        # Cycles
        cycles = list(graph_analysis.get("cycles", [])[:5])

        html = template.render(
            generated_at=datetime.now().isoformat(),
            stats=stats,
            graph=graph_analysis,
            health_score=health_score,
            health_rating=health_rating,
            score_color_class=score_color_class,
            composite_hotspots=composite_hotspots,
            top_complex_functions=top_complex_functions,
            ghosts=ghosts,
            orphans=graph_analysis.get("orphans", []),
            pagerank=pagerank,
            cycles=cycles,
        )

        report_path = self.output_dir / "repomind_report.html"
        report_path.write_text(html, encoding="utf-8")
        return report_path

    def save_graph(self, network: Network) -> Path:
        """Save the PyVis network to HTML with UTF-8 encoding."""
        path = self.output_dir / "repomind_graph.html"
        path.write_text(network.generate_html(), encoding="utf-8")
        return path
