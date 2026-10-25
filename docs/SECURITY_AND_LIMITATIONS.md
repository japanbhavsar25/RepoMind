# RepoMind Security Model & Limitations

How RepoMind handles untrusted repositories and user input, what is actually enforced in code, and where its limits are.

> **Principle:** every ingested repository, file path and URL is untrusted input.

---

## 1. Threats and mitigations

| Threat | Mitigation | Where |
|---|---|---|
| **Running hostile code** while analyzing it (e.g. `setup.py`, import side effects) | Pure static analysis with `ast.parse`. Repository code is never imported, executed, `eval`'d or `exec`'d. | `repomind/parser.py` |
| **Path traversal** (`../../etc/passwd`) through the file viewer | `resolve_safe_path()` resolves the path and requires it to stay inside the repo root | `backend/security.py`, used by `backend/routers/files.py` |
| **SSRF / cloning arbitrary hosts** | `validate_git_url()`: HTTPS only, **host allow-list** (github.com, gitlab.com, bitbucket.org), strict `owner/repo` path pattern | `backend/security.py` |
| **Argument injection into `git`** | URL validated first; `git` invoked as an argument list (no shell) with `--` before the URL | `backend/services/repo_manager.py` |
| **Clone hanging or prompting for credentials** | `GIT_TERMINAL_PROMPT=0`, timeout (`GIT_CLONE_TIMEOUT_SECONDS`, default 60 s), shallow `--depth 1` | `repo_manager._git_clone` |
| **Symlinks pointing outside the clone** | Clone with `core.symlinks=false`, so symlinks become plain files | `repo_manager._git_clone` |
| **Oversized repos / files** | Reject repos with more than `MAX_REPO_FILES` (2000) Python files; skip files over `MAX_FILE_SIZE_BYTES` (2 MB) when indexing | `repo_manager` |
| **Reading the host's own folders** on a public server | `PUBLIC_MODE=true` disables `POST /api/repos/local` and the folder picker (403) | `backend/routers/repos.py` |
| **Clone flooding** on a public server | `PUBLIC_MODE` rate limit: `GITHUB_ADDS_PER_HOUR` (default 5) per client IP | `backend/routers/repos.py` |
| **Prompt injection** inside repository code | Code is fenced as context; system and user prompts say never to follow instructions inside it. Citations are verified afterwards. | `repomind/rag.py` |
| **Leaking secrets** | API keys come only from environment variables or `.env` (git-ignored). The deploy script uploads only the committed tree. | `backend/config.py`, `.gitignore` |

---

## 2. Implementation notes

### 2.1 Path containment (`resolve_safe_path`)
```python
clean_rel = relative_path.lstrip("/\\")
target_path = (base_dir.resolve() / clean_rel).resolve()
target_path.relative_to(base_dir.resolve())  # raises -> SecurityError if outside
```
- Null bytes are rejected.
- `Path.resolve()` collapses `..` and follows symlinks before the containment check.

### 2.2 Git URL validation (`validate_git_url`)
- Scheme must be `https`.
- Host must be in the allow-list. **This is the real SSRF control:** internal hosts and cloud metadata IPs can't be reached because only three public hosts are accepted at all.
- A cheap literal check also rejects `localhost`, `127.0.0.1`, `0.0.0.0`, `10.*` and `192.168.*` with a clearer error. It does **not** do DNS resolution; the allow-list makes that unnecessary.
- The path must match `owner/repo(.git)`, which rejects extra segments, spaces and shell metacharacters.

---

## 3. Known limitations

### 3.1 Analysis
- **Python only.** Only `.py` files are parsed and indexed; other files are ignored.
- **Static analysis only.** Dynamic dispatch (`getattr(obj, name)()`), monkeypatching and runtime imports aren't resolved.
- Hidden folders (`.something/`) and common build/virtualenv folders inside a repo are skipped.

### 3.2 Public deployment
- The rate limit is per IP and kept in memory, so it resets on restart and is best-effort behind proxies (`X-Forwarded-For` is trusted).
- There's one shared "active repo" for all visitors, and repos added by visitors live on ephemeral disk (lost when the free instance restarts).
- Snippets of the analyzed code are sent to the configured LLM (Groq in the hosted demo). For fully local use, run with Ollama and no `GROQ_API_KEY`.

### 3.3 Answer quality
- The citation verifier proves a cited range **exists and was retrieved**, not that the sentence citing it is correct.
- Citations the verifier can't match (e.g. a bare `[24-45]`) lower the "% verified" score rather than being silently accepted.
