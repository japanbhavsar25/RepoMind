"""Symbol discovery and code structure exploration router."""


from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas import SymbolInfo, SymbolListResponse
from backend.services.repo_manager import repo_manager
from repomind.database import RepoDatabase

router = APIRouter(prefix="/symbols", tags=["Symbols"])


@router.get("", response_model=SymbolListResponse)
def list_symbols(
    repo_id: str | None = Query(None),
    kind: str | None = Query(None, description="Filter by 'function' or 'class'"),
) -> SymbolListResponse:
    """List all extracted AST symbols in the repository."""
    repo = repo_manager.get_repo(repo_id)
    if not repo.db_path.exists():
        return SymbolListResponse(symbols=[], total_count=0)

    symbols: list[SymbolInfo] = []
    with RepoDatabase(repo.db_path) as db:
        complexities = {row[0]: row[2] for row in db.get_function_complexities()}
        all_syms = db.get_all_symbols()

        for kind_val, _id, name, qname, doc, _src, lstart, lend, fpath in all_syms:
            sym_kind = "function" if kind_val == "func" else "class"
            if kind and sym_kind.lower() != kind.lower():
                continue

            complexity = complexities.get(name, 1) if sym_kind == "function" else 1

            symbols.append(
                SymbolInfo(
                    name=name,
                    kind=sym_kind,
                    qualified_name=qname,
                    file_path=fpath,
                    line_start=lstart or 1,
                    line_end=lend or (lstart or 1),
                    complexity=complexity,
                    docstring=doc,
                )
            )

    symbols.sort(key=lambda s: (s.file_path, s.line_start))
    return SymbolListResponse(symbols=symbols, total_count=len(symbols))


@router.get("/{symbol_name}")
def get_symbol_detail(symbol_name: str, repo_id: str | None = Query(None)):
    """Fetch detailed metadata, code, complexity, and callers for a specific symbol."""
    repo = repo_manager.get_repo(repo_id)
    if not repo.db_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository database has not been indexed yet",
        )

    with RepoDatabase(repo.db_path) as db:
        all_syms = db.get_all_symbols()
        # Find exact match
        matches = [s for s in all_syms if s[2] == symbol_name or s[3] == symbol_name]
        if not matches:
            # Try fuzzy search
            hits = db.search(symbol_name)
            if hits:
                hit_name = hits[0][1]
                matches = [s for s in all_syms if s[2] == hit_name]

        if not matches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Symbol '{symbol_name}' not found",
            )

        match = matches[0]
        # match is (kind, id, name, qualified_name, docstring, source_code, line_start, line_end, path)
        kind_val, row_id, name, qname, doc, src, lstart, lend, fpath = match
        sym_kind = "function" if kind_val == "func" else "class"

        # Look up complexity
        comp_rows = db.get_function_complexities(file_path=fpath)
        comp_map = {r[0]: r[2] for r in comp_rows}
        complexity = comp_map.get(name, 1)

        # Look up callers
        calls = db.get_symbol_calls(callee_name=name)
        callers = [
            {"caller_file": c[0], "caller_symbol": c[1], "line_number": c[3]}
            for c in calls
        ]

        return {
            "name": name,
            "type": sym_kind,
            "qualified_name": qname,
            "file_path": fpath,
            "line_start": lstart or 1,
            "line_end": lend or (lstart or 1),
            "complexity": complexity,
            "docstring": doc,
            "source_code": src or "",
            "callers": callers,
        }
