"""Chunking for RepoMind: split long symbols into overlapping retrievable pieces."""

from __future__ import annotations


def chunk_source(
    source: str,
    base_start_line: int,
    max_chars: int = 3000,
    overlap_chars: int = 300,
) -> list[tuple[str, int, int]]:
    """Split source into overlapping chunks with line numbers.

    Returns list of (chunk_text, chunk_start_line, chunk_end_line).
    Single short source returns one chunk unchanged.
    """
    if not source:
        return [("", base_start_line, base_start_line)]
    if len(source) <= max_chars:
        end_line = base_start_line + source.count("\n")
        return [(source, base_start_line, end_line)]

    # Precompute line-start offsets for mapping char -> line
    line_offsets = [0]
    for i, ch in enumerate(source):
        if ch == "\n":
            line_offsets.append(i + 1)

    def line_for_offset(off: int) -> int:
        # binary search would be overkill; linear via bisect
        import bisect

        idx = bisect.bisect_right(line_offsets, off) - 1
        return base_start_line + max(0, idx)

    chunks: list[tuple[str, int, int]] = []
    step = max_chars - overlap_chars
    if step <= 0:
        step = max_chars
    for start in range(0, len(source), step):
        end = min(start + max_chars, len(source))
        text = source[start:end]
        cs = line_for_offset(start)
        # end offset is exclusive; use end-1 for line calc
        ce = line_for_offset(max(start, end - 1))
        chunks.append((text, cs, ce))
        if end >= len(source):
            break
    return chunks


def build_symbol_chunks(
    kind: str,
    row_id: int,
    name: str,
    qname: str | None,
    docstring: str | None,
    source: str,
    file_path: str,
    line_start: int,
    line_end: int,
    max_chars: int = 3000,
    overlap_chars: int = 300,
) -> list[dict]:
    """Build one or more retrievable chunks for a single function/class.

    Returns list of dicts with keys: id, document, metadata.
    """
    display = qname or name
    pieces = chunk_source(source, line_start, max_chars, overlap_chars)
    total = len(pieces)
    out: list[dict] = []
    for i, (text, cs, ce) in enumerate(pieces):
        parts = [f"Name: {display}"]
        # Docstring only on first chunk to save tokens, note continuation after
        if i == 0 and docstring:
            parts.append(f"Docstring: {docstring}")
        if total > 1:
            parts.append(f"File: {file_path} [{cs}-{ce}] Chunk {i + 1}/{total}")
        else:
            parts.append(f"File: {file_path} [{cs}-{ce}]")
        parts.append(f"Source:\n```python\n{text}\n```")
        doc = "\n\n".join(parts)
        chunk_id = f"{kind}_{row_id}#{i}" if total > 1 else f"{kind}_{row_id}"
        out.append(
            {
                "id": chunk_id,
                "document": doc,
                "metadata": {
                    "name": display,
                    "file": file_path,
                    "kind": kind,
                    "start": cs,
                    "end": ce,
                    "chunk": i,
                    "total": total,
                    "symbol_id": f"{kind}_{row_id}",
                },
            }
        )
    return out
