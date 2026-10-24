"""Repository manager handling discovery, selection, and indexing."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from backend.config import settings
from repomind.database import RepoDatabase
from repomind.parser import extract_file, hash_bytes
from repomind.utils import find_python_files

logger = logging.getLogger("repomind.repo_manager")


@dataclass
class ManagedRepo:
    id: str
    name: str
    root_path: Path
    db_path: Path
    chroma_dir: Path
    is_sample: bool = False

    def is_indexed(self) -> bool:
        """Check if SQLite database exists and has at least one file."""
        if not self.db_path.exists():
            return False
        try:
            with RepoDatabase(self.db_path) as db:
                stats = db.get_stats()
                return stats.get("files", 0) > 0
        except Exception:
            return False

    def get_stats(self) -> dict:
        """Fetch current counts from database."""
        if not self.db_path.exists():
            return {"files": 0, "functions": 0, "classes": 0, "imports": 0}
        try:
            with RepoDatabase(self.db_path) as db:
                return db.get_stats()
        except Exception:
            return {"files": 0, "functions": 0, "classes": 0, "imports": 0}


class RepoManager:
    """Manages active repositories and indexing pipelines."""

    def __init__(self):
        self._active_repo_id = settings.default_repo_id
        self._registry: dict[str, ManagedRepo] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Register the built-in sample repo and RepoMind itself."""
        # 1. Bundled E-Commerce Sample Microservice
        sample_root = settings.samples_dir / "ecommerce_service"
        sample_db_dir = settings.data_dir / "samples" / "ecommerce"
        sample_db_dir.mkdir(parents=True, exist_ok=True)
        sample_db = sample_db_dir / "ecommerce.db"
        sample_chroma = sample_db_dir / "chroma"

        self._registry["ecommerce_sample"] = ManagedRepo(
            id="ecommerce_sample",
            name="E-Commerce Microservice (Sample)",
            root_path=sample_root,
            db_path=sample_db,
            chroma_dir=sample_chroma,
            is_sample=True,
        )

        # 2. RepoMind Core Codebase itself
        core_root = settings.base_dir
        core_db = settings.base_dir / ".repomind.db"
        core_chroma = settings.base_dir / ".repomind_chroma"

        self._registry["repomind_core"] = ManagedRepo(
            id="repomind_core",
            name="RepoMind v2.0 (Self)",
            root_path=core_root,
            db_path=core_db,
            chroma_dir=core_chroma,
            is_sample=False,
        )

        # 3. Restore persisted custom local repositories
        self._load_custom_repos()

    @property
    def custom_repos_file(self) -> Path:
        return settings.data_dir / "custom_repos.json"

    def _load_custom_repos(self) -> None:
        """Load persisted custom repositories from disk."""
        if not self.custom_repos_file.exists():
            return
        try:
            with open(self.custom_repos_file, encoding="utf-8") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                return
            for entry in entries:
                repo_id = entry.get("id")
                name = entry.get("name")
                root_path_str = entry.get("root_path")
                db_path_str = entry.get("db_path")
                chroma_dir_str = entry.get("chroma_dir")
                if not repo_id or not root_path_str or not name:
                    continue
                root_path = Path(root_path_str)
                db_path = Path(db_path_str) if db_path_str else (settings.data_dir / "repos" / repo_id / "repomind.db")
                chroma_dir = Path(chroma_dir_str) if chroma_dir_str else (settings.data_dir / "repos" / repo_id / ".repomind_chroma")
                self._registry[repo_id] = ManagedRepo(
                    id=repo_id,
                    name=name,
                    root_path=root_path,
                    db_path=db_path,
                    chroma_dir=chroma_dir,
                    is_sample=False,
                )
        except Exception as exc:
            logger.warning("Failed to load custom repositories from %s: %s", self.custom_repos_file, exc)

    def _save_custom_repos(self) -> None:
        """Persist registered custom repositories to disk."""
        custom_repos = []
        for r in self._registry.values():
            if r.is_sample or r.id == "repomind_core":
                continue
            custom_repos.append({
                "id": r.id,
                "name": r.name,
                "root_path": str(r.root_path),
                "db_path": str(r.db_path),
                "chroma_dir": str(r.chroma_dir),
            })
        try:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.custom_repos_file, "w", encoding="utf-8") as f:
                json.dump(custom_repos, f, indent=2)
        except Exception as exc:
            logger.error("Failed to save custom repositories to %s: %s", self.custom_repos_file, exc)

    def add_local_repo(self, name: str, folder_path: str | Path) -> ManagedRepo:
        """Register a new local repository from a directory path."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Repository name cannot be empty.")

        raw_path = str(folder_path).strip()
        if not raw_path:
            raise ValueError("Folder path cannot be empty.")
        if "\0" in raw_path:
            raise ValueError("Folder path contains invalid null bytes.")

        resolved = Path(raw_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Folder path does not exist: '{resolved}'")
        if not resolved.is_dir():
            raise ValueError(f"Path is a file, not a directory: '{resolved}'")

        # Test readability
        try:
            next(resolved.iterdir(), None)
        except PermissionError:
            raise PermissionError(f"Permission denied: unable to access '{resolved}'") from None

        # Duplicate check against existing registered paths
        for existing in self._registry.values():
            try:
                existing_resolved = existing.root_path.resolve()
            except OSError:
                continue
            if str(existing_resolved).lower() == str(resolved).lower():
                raise ValueError(f"Repository already registered: '{existing.name}' (ID: {existing.id})")

        # Generate unique and safe slug
        clean_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", clean_name.lower())[:30].strip("_") or "repo"
        path_hash = hashlib.sha256(str(resolved).lower().encode("utf-8")).hexdigest()[:8]
        repo_id = f"{clean_slug}_{path_hash}"

        # Isolated directory for database and vector index
        repo_data_dir = settings.data_dir / "repos" / repo_id
        repo_data_dir.mkdir(parents=True, exist_ok=True)
        db_path = repo_data_dir / "repomind.db"
        chroma_dir = repo_data_dir / ".repomind_chroma"

        repo = ManagedRepo(
            id=repo_id,
            name=clean_name,
            root_path=resolved,
            db_path=db_path,
            chroma_dir=chroma_dir,
            is_sample=False,
        )

        self._registry[repo_id] = repo
        self._active_repo_id = repo_id
        self._save_custom_repos()
        logger.info("Successfully registered local repository '%s' (ID: %s) at %s", clean_name, repo_id, resolved)
        return repo

    @property
    def active_repo_id(self) -> str:
        return self._active_repo_id

    def set_active_repo(self, repo_id: str) -> ManagedRepo:
        if repo_id not in self._registry:
            raise ValueError(f"Unknown repository ID: '{repo_id}'")
        self._active_repo_id = repo_id
        return self._registry[repo_id]

    def get_repo(self, repo_id: str | None = None) -> ManagedRepo:
        target_id = repo_id or self._active_repo_id
        if target_id not in self._registry:
            # Fall back to default
            target_id = settings.default_repo_id
        return self._registry[target_id]

    def list_repos(self) -> list[ManagedRepo]:
        return list(self._registry.values())

    def index_repo(self, repo_id: str | None = None) -> dict:
        """Run complete AST parsing and database indexing for a repository."""
        repo = self.get_repo(repo_id)
        start_time = time.time()

        if not repo.root_path.exists():
            raise FileNotFoundError(f"Repository root directory does not exist: {repo.root_path}")

        py_files = find_python_files(repo.root_path)
        if not py_files:
            # Check direct glob if no subdirectories
            py_files = sorted(repo.root_path.glob("*.py"))

        repo.db_path.parent.mkdir(parents=True, exist_ok=True)

        with RepoDatabase(repo.db_path) as db:
            db.clear()
            current_paths = set()

            for py_file in py_files:
                try:
                    rel_path = py_file.relative_to(repo.root_path).as_posix()
                except ValueError:
                    rel_path = py_file.name

                current_paths.add(rel_path)
                raw = py_file.read_bytes()
                content_hash = hash_bytes(raw)
                text = raw.decode("utf-8", errors="replace")
                line_count = len(text.splitlines())
                last_mod = py_file.stat().st_mtime

                file_id = db.insert_file(rel_path, content_hash, line_count, last_mod)
                try:
                    res = extract_file(py_file, file_id, rel_path=rel_path, source=text)
                    if res.functions:
                        db.insert_functions(res.functions)
                    if res.classes:
                        db.insert_classes(res.classes)
                    if res.imports:
                        db.insert_imports(res.imports)
                    if res.calls:
                        db.insert_symbol_calls(res.calls)
                except SyntaxError:
                    continue

            db.commit()
            stats = db.get_stats()

        duration = round(time.time() - start_time, 3)
        return {
            "status": "success",
            "repo_id": repo.id,
            "files_indexed": stats.get("files", 0),
            "functions_indexed": stats.get("functions", 0),
            "classes_indexed": stats.get("classes", 0),
            "imports_indexed": stats.get("imports", 0),
            "duration_seconds": duration,
        }


repo_manager = RepoManager()
