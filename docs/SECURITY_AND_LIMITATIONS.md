# RepoMind Security Model & Limitations

This document details the security posture, threat model, input sanitization controls, and architectural limitations of RepoMind v2.0.

---

## 1. Threat Model & Principles

RepoMind is designed to inspect unfamiliar and third-party codebases. As a fundamental security requirement:

> **All ingested repositories and user-supplied file paths must be treated as untrusted input.**

### 1.1 Evaluated Threat Vectors

1. **Arbitrary Code Execution (RCE):**
   - *Risk:* An analyzer executing code while inspecting it (e.g., executing `setup.py` or importing modules dynamically).
   - *Mitigation:* RepoMind uses **pure static Abstract Syntax Tree (`ast.parse`) analysis**. It never imports, executes, evaluates (`eval`/`exec`), or runs user code during indexing, symbol extraction, or graph building.

2. **Directory & Path Traversal:**
   - *Risk:* An attacker supplying relative path escapes (e.g., `../../../../etc/passwd` or `..\..\Windows\System32\drivers\etc\hosts`) to read arbitrary host files via the `/api/files/content` endpoint.
   - *Mitigation:* The `resolve_safe_path()` boundary in `backend/security.py`.

3. **Server-Side Request Forgery (SSRF):**
   - *Risk:* An attacker supplying a malicious Git URL pointing to internal private services or cloud metadata endpoints (e.g., `http://169.254.169.254/latest/meta-data/` or `http://10.0.0.1/admin`).
   - *Mitigation:* The `validate_git_url()` validator in `backend/security.py`.

4. **Resource Exhaustion / Denial of Service:**
   - *Risk:* Ingesting binary blobs, minified JavaScript, 100MB log files, or circular directory symlinks causing out-of-memory crashes.
   - *Mitigation:* Enforced file size limits (5 MB maximum per file), binary detection, and path cycle rejection.

---

## 2. Implemented Security Controls

### 2.1 Path Traversal Sanitization (`backend/security.py`)

All file and path operations in the backend service pass through `resolve_safe_path`:

```python
def resolve_safe_path(base_dir: Union[str, Path], user_path: str) -> Path:
    """Resolve and sanitize a path, guaranteeing it remains inside base_dir."""
    if "\0" in user_path:
        raise HTTPException(status_code=400, detail="Invalid path: null byte detected.")

    base_resolved = Path(base_dir).resolve()
    target = (base_resolved / user_path.lstrip("/\\")).resolve()

    # Enforce containment using os.path.commonpath
    try:
        common = os.path.commonpath([str(base_resolved).lower(), str(target).lower()])
        if common != str(base_resolved).lower():
            raise HTTPException(status_code=403, detail="Access denied: path traversal attempt detected.")
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied: path traversal across drive boundaries.")

    return target
```

**Key Invariants:**
- Null bytes (`\0`) are immediately rejected.
- Paths are canonicalized using `Path.resolve()` to expand symlinks and remove `..` segments.
- `os.path.commonpath` verifies that the target canonical path is strictly contained within the repository root directory.
- Cross-drive boundary traversal (common on Windows, e.g., `D:\RepoMind` to `C:\Windows`) throws `HTTPException(403)`.

### 2.2 Git URL & SSRF Protection (`backend/security.py`)

When importing remote Git repositories, URLs must pass `validate_git_url()`:

```python
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),    # Private RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),   # Private RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),   # Link-Local / AWS Metadata
    ipaddress.ip_network("::1/128"),          # IPv6 Loopback
]
```

**Rules Enforced:**
- Scheme must be `https://` or `git@` (SSH). Insecure `http://`, `ftp://`, or `file://` schemes are rejected.
- Resolves the hostname's DNS A/AAAA records. If the resolved IP belongs to any private or link-local range, the request is rejected with `HTTPException(400)`.
- Validates URL syntax and character set to prevent command-injection parameters during `git clone`.

---

## 3. Architectural Limitations & Boundaries

### 3.1 Static AST Analysis Limitations
- **Dynamic Invocations:** Python's standard `ast` module only inspects explicit syntax trees. Dynamic metaprogramming (`getattr(obj, func_name)()`), runtime monkeypatching, or dynamic imports (`__import__('module')`) cannot be resolved with certainty via static analysis.
- **Python Language Scope:** In RepoMind v2.0, deep AST symbol extraction, cyclomatic complexity calculations, and caller-callee graphs are implemented for Python (`.py`). Non-Python source files (Markdown, JSON, HTML, SQL) are indexed into SQLite FTS5 and ChromaDB for text and semantic retrieval, but do not generate AST symbol records.

### 3.2 Offline & Hardware Constraints
- **8 GB RAM Envelope:** To maintain reliable execution on modest developer hardware (8 GB RAM / Windows/macOS/Linux), RepoMind avoids keeping large neural models permanently resident in RAM. ChromaDB and SentenceTransformers are lazily loaded on demand.
- **Local LLM Performance:** When running local LLMs via Ollama (e.g. 7B/8B models), response quality depends on the selected model. RepoMind mitigates hallucination risks through **Deterministic Evidence Synthesis** (default mode) and regex-based **Citation Verification**, which cross-checks every cited `[file:start-end]` line range against the actual repository files.
