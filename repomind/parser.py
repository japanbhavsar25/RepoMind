"""AST-based Python code extractor."""

from __future__ import annotations

import ast
import dis
import hashlib
import inspect
from pathlib import Path, PurePosixPath

from repomind.database import CallRecord, ClassRecord, FunctionRecord, ImportRecord

_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _compute_complexity(func_node: ast.AST) -> int:
    """Compute Cyclomatic Complexity for a function or method.

    Counts decision points: If, IfExp, For, AsyncFor, While, ExceptHandler,
    With, AsyncWith, Assert, BoolOp (operands - 1), comprehension.
    Skips nested functions and classes so they don't double count.
    """
    cc = 1
    stack = list(ast.iter_child_nodes(func_node))
    while stack:
        curr = stack.pop()
        if isinstance(curr, (*_FUNCTION_NODES, ast.ClassDef)):
            continue
        if isinstance(
            curr,
            (
                ast.If,
                ast.IfExp,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.ExceptHandler,
                ast.With,
                ast.AsyncWith,
                ast.Assert,
            ),
        ):
            cc += 1
        elif isinstance(curr, ast.BoolOp):
            cc += max(0, len(curr.values) - 1)
        elif isinstance(curr, ast.comprehension):
            cc += 1 + len(curr.ifs)
        stack.extend(ast.iter_child_nodes(curr))
    return cc


def _callee_name(node: ast.AST) -> str:
    """Extract callee identifier from a Call node's func."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        val = _callee_name(node.value)
        return f"{val}.{node.attr}" if val else node.attr
    elif isinstance(node, ast.Call):
        return _callee_name(node.func)
    return ""


def _get_docstring(node: ast.AST) -> str | None:
    """Safely extract docstring from a node."""
    try:
        return ast.get_docstring(node)
    except Exception:
        return None


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Map every node to its immediate parent so we can walk ancestry."""
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _qualified_name(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    """Build 'Outer.Inner.method' style names from the ancestor chain."""
    parts = [node.name]  # type: ignore[attr-defined]
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (*_FUNCTION_NODES, ast.ClassDef)):
            parts.append(current.name)
            current = parents.get(current)
        else:
            break
    return ".".join(reversed(parts))


def _get_source_lines(source: str, node: ast.AST) -> tuple[int, int]:
    """Get 1-based start and end line numbers."""
    return node.lineno, getattr(node, "end_lineno", node.lineno)


def _package_of(rel_path: str) -> str:
    """Dotted package path that a file belongs to ('pkg/sub/mod.py' -> 'pkg.sub').

    An ``__init__.py`` belongs to the package it defines, not to a module
    named ``__init__``. Top-level files get an empty package string.
    """
    parts = PurePosixPath(rel_path).parts
    return ".".join(parts[:-1])


class PythonExtractor:
    """Extracts symbols from a single Python file.

    Uses a parent map so functions and classes are found at *any* nesting
    depth (methods, nested functions, classes inside ``if`` blocks, ...).
    """

    def __init__(self, source: str) -> None:
        source = source.removeprefix("\ufeff")  # a BOM (Windows editors) is a SyntaxError for ast
        self.source = source
        self.lines = source.splitlines()
        self.tree = ast.parse(source)
        self._parents = _build_parent_map(self.tree)

    def extract_functions(self, file_id: int) -> list[FunctionRecord]:
        """Extract every function and method, at any nesting depth."""
        records: list[FunctionRecord] = []
        for node in ast.walk(self.tree):
            if isinstance(node, _FUNCTION_NODES):
                start, end = _get_source_lines(self.source, node)
                records.append(
                    FunctionRecord(
                        file_id=file_id,
                        name=node.name,
                        qualified_name=_qualified_name(node, self._parents),
                        line_start=start,
                        line_end=end,
                        docstring=_get_docstring(node),
                        source_code="\n".join(self.lines[start - 1 : end]),
                        complexity=_compute_complexity(node),
                    )
                )
        return records

    def extract_calls(self, file_id: int, caller_file: str = "") -> list[CallRecord]:
        """Extract caller-to-callee relationships from ast.Call nodes."""
        records: list[CallRecord] = []
        for parent_func in ast.walk(self.tree):
            if isinstance(parent_func, _FUNCTION_NODES):
                caller_sym = _qualified_name(parent_func, self._parents)
                stack = list(ast.iter_child_nodes(parent_func))
                while stack:
                    curr = stack.pop()
                    if isinstance(curr, (*_FUNCTION_NODES, ast.ClassDef)):
                        continue
                    if isinstance(curr, ast.Call):
                        cname = _callee_name(curr.func)
                        if cname:
                            records.append(
                                CallRecord(
                                    file_id=file_id,
                                    caller_file=caller_file,
                                    caller_symbol=caller_sym,
                                    callee_name=cname,
                                    line_number=curr.lineno,
                                )
                            )
                    stack.extend(ast.iter_child_nodes(curr))
        return records

    def extract_classes(self, file_id: int) -> list[ClassRecord]:
        """Extract every class, at any nesting depth."""
        records: list[ClassRecord] = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                start, end = _get_source_lines(self.source, node)
                records.append(
                    ClassRecord(
                        file_id=file_id,
                        name=node.name,
                        qualified_name=_qualified_name(node, self._parents),
                        line_start=start,
                        line_end=end,
                        docstring=_get_docstring(node),
                        source_code="\n".join(self.lines[start - 1 : end]),
                    )
                )
        return records

    def extract_imports(
        self, file_id: int, package: str | None = None
    ) -> list[ImportRecord]:
        """Extract import statements, resolving relative imports when possible.

        ``package`` is the dotted package of the containing file (see
        ``_package_of``). With it, ``from . import x`` in ``pkg/cli.py``
        resolves to the absolute module ``pkg.x``; without it, relative
        imports are recorded with their leading dots.
        """
        records: list[ImportRecord] = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    records.append(
                        ImportRecord(
                            file_id=file_id,
                            module_name=alias.name,
                            imported_name=alias.asname or alias.name,
                            is_from_import=False,
                            line_number=node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                module = _resolve_from_module(node.module, node.level, package)
                for alias in node.names:
                    records.append(
                        ImportRecord(
                            file_id=file_id,
                            module_name=module,
                            imported_name=alias.asname or alias.name,
                            is_from_import=True,
                            line_number=node.lineno,
                        )
                    )
        return records


def _resolve_from_module(
    module: str | None, level: int, package: str | None
) -> str | None:
    """Turn a relative ``from`` import into an absolute module name.

    Returns ``None`` when the import cannot be resolved within the known
    package tree (top-level modules, or going above the top-level package).
    """
    if not level:
        return module
    base = package.split(".") if package else []
    if not base:
        return None
    up = level - 1  # level=1 means the current package, level=2 its parent, ...
    if up >= len(base):
        return None
    parts = base[: len(base) - up]
    if module:
        parts = [*parts, module]
    return ".".join(parts)


class ParseResult(tuple):
    """Backwards-compatible tuple for (functions, classes, imports, symbol_calls).
    Supports unpacking 3 items (funcs, classes, imports) or 4 items (funcs, classes, imports, calls).
    """

    def __new__(cls, functions, classes, imports, calls):
        return super().__new__(cls, (functions, classes, imports, calls))

    def __init__(self, functions, classes, imports, calls):
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.calls = calls

    def __iter__(self):
        try:
            frame = inspect.currentframe().f_back
            if frame:
                code = frame.f_code
                lasti = frame.f_lasti
                if 0 <= lasti < len(code.co_code):
                    opcode = code.co_code[lasti]
                    if dis.opname[opcode] == "UNPACK_SEQUENCE":
                        count = code.co_code[lasti + 1]
                        if count == 3:
                            return iter((self.functions, self.classes, self.imports))
        except Exception:
            pass
        return super().__iter__()


def extract_file(
    file_path: Path,
    file_id: int,
    rel_path: str | None = None,
    source: str | None = None,
) -> ParseResult:
    """Parse a single file and return all extracted records.

    ``rel_path`` (posix-style, relative to the project root) enables
    relative-import resolution; ``source`` lets callers reuse text they
    have already read instead of re-reading the file.
    """
    if source is None:
        source = file_path.read_text(encoding="utf-8-sig", errors="replace")  # -sig drops a BOM
    extractor = PythonExtractor(source)
    package = _package_of(rel_path) if rel_path else None
    posix_path = rel_path or file_path.as_posix()
    return ParseResult(
        extractor.extract_functions(file_id),
        extractor.extract_classes(file_id),
        extractor.extract_imports(file_id, package=package),
        extractor.extract_calls(file_id, caller_file=posix_path),
    )


def hash_bytes(data: bytes) -> str:
    """SHA-256 of raw bytes, truncated to 16 hex chars for change detection."""
    return hashlib.sha256(data).hexdigest()[:16]


def file_hash(path: Path) -> str:
    """SHA-256 hash of a file's contents for change detection."""
    return hash_bytes(path.read_bytes())
