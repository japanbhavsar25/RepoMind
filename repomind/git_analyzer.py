"""Analyze git history for code hotspots and ghost files."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from git import Repo


class GitAnalyzer:
    """Mines git history for insights."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path
        try:
            self.repo = Repo(repo_path)
        except Exception:
            self.repo = None

    def is_valid(self) -> bool:
        return self.repo is not None and not self.repo.bare

    def analyze(self, max_commits: int = 500) -> dict[str, dict]:
        """Return per-file git statistics."""
        if not self.is_valid():
            return {}

        file_stats: dict[str, dict] = defaultdict(
            lambda: {
                "commit_count": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "authors": defaultdict(int),
                "last_modified": None,
            }
        )

        commits = list(self.repo.iter_commits("HEAD", max_count=max_commits))
        
        for commit in commits:
            commit_date = datetime.fromtimestamp(commit.committed_date, tz=UTC)

            try:
                for file_path, stat in commit.stats.files.items():
                    if not file_path.endswith(".py"):
                        continue

                    # Normalize to forward slashes for consistency
                    normalized = file_path.replace("\\", "/")

                    file_stats[normalized]["commit_count"] += 1
                    file_stats[normalized]["lines_added"] += stat["insertions"]
                    file_stats[normalized]["lines_deleted"] += stat["deletions"]
                    file_stats[normalized]["authors"][commit.author.name] += 1

                    if (
                        file_stats[normalized]["last_modified"] is None
                        or commit_date > file_stats[normalized]["last_modified"]
                    ):
                        file_stats[normalized]["last_modified"] = commit_date
            except Exception:
                continue

        # Convert sets/dicts to counts and compute Bus Factor for serialization
        result = {}
        for path, data in file_stats.items():
            author_dict = data["authors"]
            total_c = data["commit_count"]
            top_author = max(author_dict.keys(), key=lambda a: author_dict[a]) if author_dict else "unknown"
            top_count = author_dict.get(top_author, 0)
            top_pct = round((top_count / total_c) * 100) if total_c else 0
            # Bus Factor risk: >=85% commits by single author with at least 3 commits
            bus_risk = total_c >= 3 and top_pct >= 85

            result[path] = {
                "commit_count": total_c,
                "lines_added": data["lines_added"],
                "lines_deleted": data["lines_deleted"],
                "author_count": len(author_dict),
                "top_author": top_author,
                "top_author_pct": top_pct,
                "bus_factor_risk": bus_risk,
                "last_modified": (
                    data["last_modified"].isoformat() if data["last_modified"] else None
                ),
            }

        return result

    @staticmethod
    def compute_composite_hotspots(
        git_stats: dict[str, dict],
        complexities: dict[str, int],
        pagerank: dict[str, float],
    ) -> list[dict]:
        """Compute composite risk scores (0-100) combining churn, complexity, and PageRank."""
        all_files = set(git_stats.keys()) | set(complexities.keys()) | {
            p for p in pagerank if not p.startswith("ext:")
        }
        if not all_files:
            return []

        max_churn = max((git_stats.get(f, {}).get("commit_count", 0) for f in all_files), default=1) or 1
        max_cc = max((complexities.get(f, 0) for f in all_files), default=1) or 1
        max_pr = max((pagerank.get(f, 0.0) for f in all_files), default=0.001) or 0.001

        results = []
        for f in all_files:
            g = git_stats.get(f, {})
            churn = g.get("commit_count", 0)
            cc = complexities.get(f, 0)
            pr = pagerank.get(f, 0.0)

            norm_churn = min(1.0, churn / max_churn)
            norm_cc = min(1.0, cc / max_cc)
            norm_pr = min(1.0, pr / max_pr)

            raw_score = (0.45 * norm_churn + 0.35 * norm_cc + 0.20 * norm_pr) * 100
            score = round(raw_score)

            if score >= 65:
                risk_level = "CRITICAL"
                heat = "hot"
            elif score >= 40:
                risk_level = "HIGH"
                heat = "hot"
            elif score >= 20:
                risk_level = "MEDIUM"
                heat = "warm"
            else:
                risk_level = "LOW"
                heat = "cool"

            results.append({
                "path": f,
                "risk_score": score,
                "risk_level": risk_level,
                "heat": heat,
                "commit_count": churn,
                "author_count": g.get("author_count", 0),
                "lines_added": g.get("lines_added", 0),
                "lines_deleted": g.get("lines_deleted", 0),
                "complexity": cc,
                "pagerank": pr,
                "bus_factor_risk": g.get("bus_factor_risk", False),
                "top_author": g.get("top_author", "N/A"),
                "top_author_pct": g.get("top_author_pct", 0),
            })

        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def get_ghost_files(self, stats: dict[str, dict], days: int = 180) -> list[str]:
        """Find files not modified in the last N days."""
        if not stats:
            return []

        now = datetime.now(UTC)
        ghosts = []
        for path, data in stats.items():
            last = data.get("last_modified")
            if not last:
                continue
            last_dt = datetime.fromisoformat(last)
            if (now - last_dt).days > days:
                ghosts.append(path)

        return sorted(ghosts)