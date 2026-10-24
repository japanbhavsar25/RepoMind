"""File explorer and source code viewing router."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas import FileContentResponse, FileNode, FileTreeResponse
from backend.security import SecurityError, resolve_safe_path
from backend.services.repo_manager import repo_manager
from repomind.utils import should_skip_dir

router = APIRouter(prefix="/files", tags=["Files"])


def _build_tree(root_dir: Path) -> tuple[FileNode, int]:
    """Recursively build a directory tree structure."""
    total_files = 0

    def traverse(current_path: Path) -> FileNode:
        nonlocal total_files
        try:
            rel = current_path.relative_to(root_dir).as_posix()
        except ValueError:
            rel = current_path.name

        if current_path.is_file():
            total_files += 1
            return FileNode(
                name=current_path.name,
                path=rel,
                type="file",
                size=current_path.stat().st_size,
            )

        children: list[FileNode] = []
        try:
            # Sort directories first, then files alphabetically
            entries = sorted(
                current_path.iterdir(),
                key=lambda p: (0 if p.is_dir() else 1, p.name.lower()),
            )
            for entry in entries:
                if entry.is_dir() and should_skip_dir(entry):
                    continue
                children.append(traverse(entry))
        except PermissionError:
            pass

        return FileNode(
            name=current_path.name or "root",
            path=rel,
            type="directory",
            size=0,
            children=children,
        )

    root_node = traverse(root_dir)
    return root_node, total_files


@router.get("/tree", response_model=FileTreeResponse)
def get_file_tree(repo_id: str | None = Query(None)) -> FileTreeResponse:
    """Return hierarchical file and folder structure for the repository."""
    repo = repo_manager.get_repo(repo_id)
    if not repo.root_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository path '{repo.root_path}' does not exist",
        )

    root_node, total_files = _build_tree(repo.root_path)
    return FileTreeResponse(
        repo_id=repo.id,
        root=root_node,
        total_files=total_files,
    )


@router.get("/content", response_model=FileContentResponse)
def get_file_content(path: str = Query(...), repo_id: str | None = Query(None)) -> FileContentResponse:
    """Fetch raw source content for a repository file with path traversal validation."""
    repo = repo_manager.get_repo(repo_id)

    try:
        safe_file_path = resolve_safe_path(repo.root_path, path)
    except SecurityError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err

    if not safe_file_path.exists() or not safe_file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: '{path}'",
        )

    content = safe_file_path.read_text(encoding="utf-8", errors="replace")
    stat = safe_file_path.stat()

    return FileContentResponse(
        path=path,
        content=content,
        line_count=len(content.splitlines()),
        last_modified=stat.st_mtime,
    )
