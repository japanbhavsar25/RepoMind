"""SQLite storage layer for RepoMind."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    content_hash TEXT,
    line_count INTEGER DEFAULT 0,
    last_modified REAL
);

CREATE TABLE IF NOT EXISTS functions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT,
    line_start INTEGER,
    line_end INTEGER,
    docstring TEXT,
    source_code TEXT,
    complexity INTEGER DEFAULT 1,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT,
    line_start INTEGER,
    line_end INTEGER,
    docstring TEXT,
    source_code TEXT,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    module_name TEXT,
    imported_name TEXT,
    is_from_import INTEGER DEFAULT 0,
    line_number INTEGER,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS symbol_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    caller_file TEXT,
    caller_symbol TEXT NOT NULL,
    callee_name TEXT NOT NULL,
    line_number INTEGER,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(name);
CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name);
CREATE INDEX IF NOT EXISTS idx_imports_module ON imports(module_name);
CREATE INDEX IF NOT EXISTS idx_symbol_calls_caller ON symbol_calls(caller_symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_calls_callee ON symbol_calls(callee_name);
"""


def _like_escape(text: str) -> str:
    """Make ``%`` and ``_`` match literally in a LIKE pattern (with ``ESCAPE '\\'``)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class FunctionRecord:
    file_id: int
    name: str
    qualified_name: str | None
    line_start: int
    line_end: int
    docstring: str | None
    source_code: str
    complexity: int = 1


@dataclass(frozen=True)
class ClassRecord:
    file_id: int
    name: str
    qualified_name: str | None
    line_start: int
    line_end: int
    docstring: str | None
    source_code: str


@dataclass(frozen=True)
class ImportRecord:
    file_id: int
    module_name: str | None
    imported_name: str | None
    is_from_import: bool
    line_number: int


@dataclass(frozen=True)
class CallRecord:
    file_id: int
    caller_file: str
    caller_symbol: str
    callee_name: str
    line_number: int


class RepoDatabase:
    """Thin wrapper around SQLite for RepoMind.

    Reads never need an explicit commit; writes do. Call ``commit()``
    when a unit of work is complete (the CLI commits once per file).
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> RepoDatabase:
        self._conn = sqlite3.connect(self.db_path)
        self._conn.executescript(SCHEMA)
        self._conn.execute("PRAGMA foreign_keys = ON")
        # Graceful schema migration for existing databases
        try:
            self._conn.execute("ALTER TABLE functions ADD COLUMN complexity INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        self._has_fts5 = self._init_fts5()
        return self

    def _init_fts5(self) -> bool:
        try:
            self._connection().execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
                    chunk_id UNINDEXED,
                    file_path UNINDEXED,
                    symbol_name,
                    content,
                    tokenize='unicode61'
                )
            """)
            return True
        except sqlite3.OperationalError:
            return False

    @property
    def has_fts5(self) -> bool:
        return getattr(self, "_has_fts5", False)

    def __exit__(self, *_) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("RepoDatabase must be used as a context manager")
        return self._conn

    def commit(self) -> None:
        self._connection().commit()

    def clear(self) -> None:
        """Remove every indexed row (used for a fresh index)."""
        conn = self._connection()
        if self.has_fts5:
            try:
                conn.execute("DELETE FROM fts_chunks")
            except Exception:
                pass
        conn.execute("DELETE FROM symbol_calls")
        conn.execute("DELETE FROM imports")
        conn.execute("DELETE FROM functions")
        conn.execute("DELETE FROM classes")
        conn.execute("DELETE FROM files")

    def insert_file(self, path: str, content_hash: str, line_count: int, last_modified: float) -> int:
        cursor = self._connection().execute(
            """
            INSERT INTO files (path, content_hash, line_count, last_modified)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                content_hash=excluded.content_hash,
                line_count=excluded.line_count,
                last_modified=excluded.last_modified
            RETURNING id
            """,
            (path, content_hash, line_count, last_modified),
        )
        return cursor.fetchone()[0]

    def insert_functions(self, records: Iterable[FunctionRecord]) -> None:
        data = [
            (
                r.file_id,
                r.name,
                r.qualified_name,
                r.line_start,
                r.line_end,
                r.docstring,
                r.source_code,
                getattr(r, "complexity", 1),
            )
            for r in records
        ]
        self._connection().executemany(
            """
            INSERT INTO functions
            (file_id, name, qualified_name, line_start, line_end, docstring, source_code, complexity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )

    def insert_symbol_calls(self, records: Iterable[CallRecord]) -> None:
        data = [
            (
                r.file_id,
                r.caller_file,
                r.caller_symbol,
                r.callee_name,
                r.line_number,
            )
            for r in records
        ]
        self._connection().executemany(
            """
            INSERT INTO symbol_calls
            (file_id, caller_file, caller_symbol, callee_name, line_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            data,
        )

    def insert_classes(self, records: Iterable[ClassRecord]) -> None:
        data = [
            (
                r.file_id,
                r.name,
                r.qualified_name,
                r.line_start,
                r.line_end,
                r.docstring,
                r.source_code,
            )
            for r in records
        ]
        self._connection().executemany(
            """
            INSERT INTO classes
            (file_id, name, qualified_name, line_start, line_end, docstring, source_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )

    def insert_imports(self, records: Iterable[ImportRecord]) -> None:
        data = [
            (
                r.file_id,
                r.module_name,
                r.imported_name,
                int(r.is_from_import),
                r.line_number,
            )
            for r in records
        ]
        self._connection().executemany(
            """
            INSERT INTO imports
            (file_id, module_name, imported_name, is_from_import, line_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            data,
        )

    def get_file_hashes(self) -> dict[str, tuple[int, str | None]]:
        """Map each indexed path to its (file_id, content_hash)."""
        rows = self._connection().execute("SELECT id, path, content_hash FROM files")
        return {path: (file_id, content_hash) for file_id, path, content_hash in rows}

    def delete_symbols(self, file_id: int) -> None:
        """Remove a file's functions/classes/imports/calls so it can be re-parsed."""
        conn = self._connection()
        if self.has_fts5:
            row = conn.execute("SELECT path FROM files WHERE id = ?", (file_id,)).fetchone()
            if row:
                self.delete_fts_by_file(row[0])
        for table in ("functions", "classes", "imports", "symbol_calls"):
            conn.execute(f"DELETE FROM {table} WHERE file_id = ?", (file_id,))

    def get_function_complexities(self, file_path: str | None = None) -> list[tuple[str, str, int, str]]:
        """Return (name, qualified_name, complexity, file_path) sorted by complexity DESC."""
        conn = self._connection()
        if file_path:
            return conn.execute(
                """
                SELECT f.name, f.qualified_name, f.complexity, fi.path
                FROM functions f
                JOIN files fi ON f.file_id = fi.id
                WHERE fi.path = ?
                ORDER BY f.complexity DESC
                """,
                (file_path,),
            ).fetchall()
        return conn.execute(
            """
            SELECT f.name, f.qualified_name, f.complexity, fi.path
            FROM functions f
            JOIN files fi ON f.file_id = fi.id
            ORDER BY f.complexity DESC
            """
        ).fetchall()

    def get_symbol_calls(
        self, callee_name: str | None = None, caller_symbol: str | None = None, file_path: str | None = None
    ) -> list[tuple[str, str, str, int]]:
        """Return (caller_file, caller_symbol, callee_name, line_number)."""
        conn = self._connection()
        query = "SELECT caller_file, caller_symbol, callee_name, line_number FROM symbol_calls WHERE 1=1"
        params: list = []
        if callee_name:
            query += " AND (callee_name = ? OR callee_name LIKE ? ESCAPE '\\')"
            params.extend([callee_name, f"%.{_like_escape(callee_name)}"])
        if caller_symbol:
            query += " AND (caller_symbol = ? OR caller_symbol LIKE ? ESCAPE '\\')"
            params.extend([caller_symbol, f"%.{_like_escape(caller_symbol)}"])
        if file_path:
            query += " AND caller_file = ?"
            params.append(file_path)
        return conn.execute(query, params).fetchall()

    def prune_paths(self, keep: Iterable[str]) -> int:
        """Delete file rows whose path is not in ``keep`` (cascades to symbols).

        Returns the number of files removed.
        """
        keep = set(keep)
        conn = self._connection()
        rows = conn.execute("SELECT id, path FROM files").fetchall()
        removed = 0
        for file_id, path in rows:
            if path not in keep:
                if self.has_fts5:
                    self.delete_fts_by_file(path)
                conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
                removed += 1
        return removed

    def insert_fts_chunks(self, records: Iterable[tuple[str, str, str, str]]) -> None:
        """Insert or update chunks into FTS5 index: (chunk_id, file_path, symbol_name, content)."""
        if not self.has_fts5:
            return
        records_list = list(records)
        if not records_list:
            return
        conn = self._connection()
        for cid, _, _, _ in records_list:
            conn.execute("DELETE FROM fts_chunks WHERE chunk_id = ?", (cid,))
        conn.executemany(
            "INSERT INTO fts_chunks (chunk_id, file_path, symbol_name, content) VALUES (?, ?, ?, ?)",
            records_list,
        )

    def delete_fts_chunks(self, chunk_ids: Iterable[str]) -> None:
        """Delete specific chunk IDs from FTS5 index."""
        if not self.has_fts5:
            return
        conn = self._connection()
        for cid in chunk_ids:
            conn.execute("DELETE FROM fts_chunks WHERE chunk_id = ?", (cid,))

    def delete_fts_by_file(self, file_path: str) -> None:
        """Delete all chunks belonging to a file path from FTS5 index."""
        if not self.has_fts5:
            return
        self._connection().execute("DELETE FROM fts_chunks WHERE file_path = ?", (file_path,))

    def search_fts(self, query: str, limit: int = 20) -> list[tuple[str, float]]:
        """Search FTS5 index using BM25, returning [(chunk_id, score), ...] best-first."""
        if not self.has_fts5:
            return []
        from repomind.utils import tokenize_code

        tokens = tokenize_code(query)
        if not tokens:
            return []
        safe_terms = [f'"{t.replace(chr(34), chr(34)*2)}"' for t in tokens if t]
        if not safe_terms:
            return []
        match_expr = " OR ".join(safe_terms)
        try:
            rows = self._connection().execute(
                """
                SELECT chunk_id, -bm25(fts_chunks) AS score
                FROM fts_chunks
                WHERE fts_chunks MATCH ?
                ORDER BY score DESC
                LIMIT ?
                """,
                (match_expr, limit),
            ).fetchall()
            return [(r[0], float(r[1])) for r in rows]
        except Exception:
            return []

    def get_files(self) -> list[tuple[int, str]]:
        """All indexed files as (id, path)."""
        return self._connection().execute("SELECT id, path FROM files").fetchall()

    def get_imports(self) -> list[tuple[int, str | None, str | None, bool]]:
        """All imports as (file_id, module_name, imported_name, is_from_import)."""
        return self._connection().execute(
            "SELECT file_id, module_name, imported_name, is_from_import FROM imports"
        ).fetchall()

    def get_all_symbols(self) -> list[tuple]:
        """Every function and class joined with its file path.

        Rows are ``(kind, id, name, qualified_name, docstring, source_code,
        line_start, line_end, path)`` with ``kind`` being ``"func"`` or ``"class"``.
        """
        conn = self._connection()
        functions = conn.execute(
            """
            SELECT f.id, f.name, f.qualified_name, f.docstring, f.source_code,
                   f.line_start, f.line_end, fi.path
            FROM functions f
            JOIN files fi ON f.file_id = fi.id
            """
        ).fetchall()
        classes = conn.execute(
            """
            SELECT c.id, c.name, c.qualified_name, c.docstring, c.source_code,
                   c.line_start, c.line_end, fi.path
            FROM classes c
            JOIN files fi ON c.file_id = fi.id
            """
        ).fetchall()
        return [("func", *row) for row in functions] + [
            ("class", *row) for row in classes
        ]

    def search(self, term: str, limit: int = 20) -> list[tuple]:
        """Find functions/classes whose name contains ``term``."""
        pattern = f"%{_like_escape(term)}%"
        return self._connection().execute(
            """
            SELECT 'function' as type, name, qualified_name, line_start, line_end,
                   f.path as file_path
            FROM functions
            JOIN files f ON functions.file_id = f.id
            WHERE name LIKE ? ESCAPE '\\' OR qualified_name LIKE ? ESCAPE '\\'
            UNION ALL
            SELECT 'class' as type, name, qualified_name, line_start, line_end,
                   f.path as file_path
            FROM classes
            JOIN files f ON classes.file_id = f.id
            WHERE name LIKE ? ESCAPE '\\' OR qualified_name LIKE ? ESCAPE '\\'
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        ).fetchall()

    def get_stats(self) -> dict[str, int]:
        cursor = self._connection().execute(
            """
            SELECT
                (SELECT COUNT(*) FROM files) as files,
                (SELECT COUNT(*) FROM functions) as functions,
                (SELECT COUNT(*) FROM classes) as classes,
                (SELECT COUNT(*) FROM imports) as imports
            """
        )
        row = cursor.fetchone()
        return {
            "files": row[0],
            "functions": row[1],
            "classes": row[2],
            "imports": row[3],
        }
