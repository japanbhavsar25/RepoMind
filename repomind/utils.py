"""Utility helpers for RepoMind."""

from __future__ import annotations

import re
from pathlib import Path

# Python keywords and common programming stopwords to filter
PYTHON_STOPWORDS = {
    "def", "class", "return", "import", "from", "self", "cls",
    "none", "true", "false", "if", "else", "elif", "for", "while",
    "try", "except", "finally", "with", "as", "in", "is", "and",
    "or", "not", "pass", "break", "continue", "raise", "yield",
    "async", "await", "lambda", "global", "nonlocal", "assert", "del",
}


def split_identifier(name: str) -> list[str]:
    """Split camelCase, PascalCase, snake_case and dot-paths into constituent sub-tokens."""
    parts = re.split(r"[_]+", name)
    subtokens: list[str] = []
    for part in parts:
        if not part:
            continue
        # Split CamelCase / PascalCase / Acronym sequences (e.g. parseASTNode -> parse, AST, Node)
        matches = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", part)
        if matches:
            subtokens.extend([m.lower() for m in matches if m])
        else:
            subtokens.append(part.lower())
    return subtokens


def tokenize_code(text: str, strip_stopwords: bool = True) -> list[str]:
    """Deterministic code tokenizer that splits camelCase, PascalCase, snake_case,
    and dot-paths into both original identifiers and sub-tokens.
    """
    raw_tokens = re.findall(r"[a-zA-Z0-9_\.]+", text)
    tokens: list[str] = []
    seen: set[str] = set()

    for raw in raw_tokens:
        clean = raw.strip(".")
        if not clean:
            continue
        lowered = clean.lower()
        subtokens: list[str] = []

        if "." in clean:
            subtokens.append(lowered)
            dot_parts = clean.split(".")
            for dp in dot_parts:
                dp_low = dp.lower()
                if dp_low:
                    subtokens.append(dp_low)
                    subtokens.extend(split_identifier(dp))
        else:
            subtokens.append(lowered)
            subtokens.extend(split_identifier(clean))

        for t in subtokens:
            if not t:
                continue
            if strip_stopwords and t in PYTHON_STOPWORDS:
                continue
            if t not in seen:
                seen.add(t)
                tokens.append(t)
    return tokens


# Directories to always skip
SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".hypothesis",
    "node_modules",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "site-packages",
    ".repomind_output",
    ".repomind_chroma",
}


def should_skip_dir(path: Path) -> bool:
    """Check if a directory should be skipped."""
    return path.name in SKIP_DIRS or path.name.endswith(".egg-info")


def find_python_files(root: Path) -> list[Path]:
    """Recursively find all .py files under root, respecting skips."""
    files: list[Path] = []

    for path in root.rglob("*.py"):
        # Check if any parent directory should be skipped
        if any(should_skip_dir(p) for p in path.parents):
            continue
        files.append(path)

    return sorted(files)