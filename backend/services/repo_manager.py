"""Repository manager handling discovery, selection, and indexing."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from backend.config import settings
from backend.security import validate_git_url
from repomind.database import RepoDatabase
from repomind.parser import extract_file, hash_bytes
from repomind.utils import find_python_files

logger = logging.getLogger("repomind.repo_manager")


class IndexingInProgressError(RuntimeError):
    """This repo is already being indexed by another request."""


class CloneFailedError(ValueError):
    """git couldn't clone the URL (typo, private or missing repo): nothing was downloaded."""


@dataclass
class ManagedRepo:
    id: str
    name: str
    root_path: Path
    db_path: Path
    chroma_dir: Path  # where RepoRAG keeps the vectors: always next to db_path
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
        self._index_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Register the built-in sample repo and RepoMind itself."""
        # 1. Bundled E-Commerce Sample Microservice
        sample_root = settings.samples_dir / "ecommerce_service"
        sample_db_dir = settings.data_dir / "samples" / "ecommerce"
        sample_db_dir.mkdir(parents=True, exist_ok=True)
        sample_db = sample_db_dir / "ecommerce.db"
        sample_chroma = sample_db_dir / ".repomind_chroma"

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

    def add_github_repo(self, url: str) -> tuple[ManagedRepo, bool]:
        """Shallow-clone a public Git repository and register it.

        Returns ``(repo, created)``. If the same URL was added before, the
        existing repo is re-selected and ``created`` is False.
        """
        clean_url = validate_git_url(url)
        repo_path = urllib.parse.urlparse(clean_url).path.strip("/")
        repo_path = re.sub(r"\.git$", "", repo_path)
        owner, name = repo_path.split("/", 1)

        normalized = f"{urllib.parse.urlparse(clean_url).hostname}/{repo_path}".lower()
        url_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        clean_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{owner}_{name}".lower())[:30].strip("_") or "repo"
        repo_id = f"gh_{clean_slug}_{url_hash}"

        if repo_id in self._registry:
            self._active_repo_id = repo_id
            return self._registry[repo_id], False

        clone_dir = settings.data_dir / "clones" / repo_id
        if clone_dir.exists():
            _remove_tree(clone_dir)
        clone_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._git_clone(f"https://{normalized}.git", clone_dir)
            py_count = len(find_python_files(clone_dir))
            if py_count == 0:
                raise ValueError(
                    f"'{owner}/{name}' has no Python files. RepoMind currently understands Python code only."
                )
            if py_count > settings.max_repo_files:
                raise ValueError(
                    f"'{owner}/{name}' has {py_count} Python files; the limit is {settings.max_repo_files}."
                )
        except Exception:
            _remove_tree(clone_dir)
            raise

        repo_data_dir = settings.data_dir / "repos" / repo_id
        repo_data_dir.mkdir(parents=True, exist_ok=True)
        repo = ManagedRepo(
            id=repo_id,
            name=f"{owner}/{name}",
            root_path=clone_dir,
            db_path=repo_data_dir / "repomind.db",
            chroma_dir=repo_data_dir / ".repomind_chroma",
            is_sample=False,
        )
        self._registry[repo_id] = repo
        self._active_repo_id = repo_id
        self._save_custom_repos()
        logger.info("Cloned and registered '%s' (ID: %s)", repo.name, repo_id)
        return repo, True

    def _git_clone(self, url: str, dest: Path) -> None:
        """Run a shallow, non-interactive ``git clone`` with a timeout."""
        if shutil.which("git") is None:
            raise RuntimeError("git is not installed on the server.")
        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",  # never hang waiting for a username/password
            "GIT_LFS_SKIP_SMUDGE": "1",  # don't download large LFS files
        }
        cmd = [
            "git", "-c", "core.symlinks=false",  # symlinks become plain files, so they can't point outside the clone
            "clone", "--depth", "1", "--single-branch", "--no-tags", "--", url, str(dest),
        ]
        try:
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True,
                timeout=settings.git_clone_timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(
                f"Cloning took longer than {settings.git_clone_timeout_seconds}s. Try a smaller repository."
            ) from e
        if result.returncode != 0:
            logger.warning("git clone failed for %s: %s", url, result.stderr.strip())
            raise CloneFailedError("Could not clone the repository. Check the link is correct and the repo is public.")

    @property
    def active_repo_id(self) -> str:
        return self._active_repo_id

    def set_active_repo(self, repo_id: str) -> ManagedRepo:
        if repo_id not in self._registry:
            raise ValueError(f"Unknown repository ID: '{repo_id}'")
        self._active_repo_id = repo_id
        return self._registry[repo_id]

    def has_repo(self, repo_id: str) -> bool:
        return repo_id in self._registry

    def get_repo(self, repo_id: str | None = None) -> ManagedRepo:
        target_id = repo_id or self._active_repo_id
        if target_id not in self._registry:
            # Fall back to default
            target_id = settings.default_repo_id
        return self._registry[target_id]

    def list_repos(self) -> list[ManagedRepo]:
        return list(self._registry.values())

    def index_repo(self, repo_id: str | None = None) -> dict:
        """Run complete AST parsing and database indexing for a repository.

        One index run per repo at a time: two at once would wipe each other's
        vector collection halfway through. A second request gets
        IndexingInProgressError instead of waiting.
        """
        repo = self.get_repo(repo_id)
        with self._locks_guard:
            lock = self._index_locks.setdefault(repo.id, threading.Lock())
        if not lock.acquire(blocking=False):
            raise IndexingInProgressError(f"'{repo.name}' is already being indexed. Try again in a moment.")
        try:
            return self._index(repo)
        finally:
            lock.release()

    def _index(self, repo: ManagedRepo) -> dict:
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

                if py_file.stat().st_size > settings.max_file_size_bytes:
                    continue

                current_paths.add(rel_path)
                raw = py_file.read_bytes()
                content_hash = hash_bytes(raw)
                text = raw.decode("utf-8-sig", errors="replace")  # -sig drops a BOM, which ast rejects
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
                except SyntaxError as exc:
                    logger.warning("Skipped symbols in %s: not valid Python (%s)", rel_path, exc)
                    continue

            db.commit()
            stats = db.get_stats()

        # Build the vector index too, so Q&A and semantic search work right away.
        # A failure here (e.g. the embedding model can't load) leaves keyword search working.
        chunks_embedded = 0
        if settings.embed_on_index:
            try:
                from repomind.rag import RepoRAG

                chunks_embedded = RepoRAG(repo.db_path).build_index(full_rebuild=True).get("total", 0)
            except Exception as exc:
                logger.warning("Embedding step failed for %s: %s", repo.id, exc)

        duration = round(time.time() - start_time, 3)
        return {
            "status": "success",
            "repo_id": repo.id,
            "files_indexed": stats.get("files", 0),
            "functions_indexed": stats.get("functions", 0),
            "classes_indexed": stats.get("classes", 0),
            "imports_indexed": stats.get("imports", 0),
            "chunks_embedded": chunks_embedded,
            "duration_seconds": duration,
        }


def _remove_tree(path: Path) -> None:
    """Delete a directory, including read-only files git leaves on Windows."""
    if not path.exists():
        return

    def _make_writable_and_retry(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=_make_writable_and_retry)


repo_manager = RepoManager()
