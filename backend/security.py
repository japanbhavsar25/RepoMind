"""Security guards, path traversal prevention, and input validation."""

import re
import urllib.parse
from pathlib import Path


class SecurityError(Exception):
    """Raised when an operation violates security constraints."""
    pass


ALLOWED_GIT_HOSTS = {
    "github.com",
    "gitlab.com",
    "bitbucket.org",
}


def resolve_safe_path(base_dir: Path, relative_path: str) -> Path:
    """Resolve a relative path against base_dir and ensure it does not escape base_dir.
    
    Prevents path traversal attacks (e.g., ../../windows/system32).
    """
    if not relative_path:
        return base_dir.resolve()

    # Reject null bytes or suspect characters
    if "\0" in relative_path:
        raise SecurityError("Null bytes in path are forbidden")

    clean_rel = relative_path.lstrip("/\\")
    resolved_base = base_dir.resolve()
    target_path = (resolved_base / clean_rel).resolve()

    try:
        # relative_to will raise ValueError if target_path is not within resolved_base
        target_path.relative_to(resolved_base)
    except ValueError:
        raise SecurityError(f"Access denied: path '{relative_path}' escapes repository boundary") from None

    return target_path


def validate_git_url(url: str) -> str:
    """Validate public Git repository URL against SSRF and command injection.
    
    Accepts only HTTPS URLs from recognized Git hosting providers.
    """
    clean_url = url.strip()
    if not clean_url:
        raise SecurityError("Repository URL cannot be empty")

    parsed = urllib.parse.urlparse(clean_url)

    if parsed.scheme.lower() != "https":
        raise SecurityError("Only HTTPS Git URLs are permitted")

    hostname = (parsed.hostname or "").lower()
    if hostname in {"localhost", "127.0.0.1", "0.0.0.0"} or hostname.startswith("192.168.") or hostname.startswith("10."):
        raise SecurityError("Local and private network URLs are prohibited")

    if hostname not in ALLOWED_GIT_HOSTS:
        raise SecurityError(f"Host '{hostname}' is not in the permitted Git hosts list ({', '.join(sorted(ALLOWED_GIT_HOSTS))})")

    # Ensure path matches a typical owner/repo pattern
    path = parsed.path.strip("/")
    if not re.match(r"^[\w\.-]+/[\w\.-]+(?:\.git)?$", path):
        raise SecurityError(f"Malformed repository path in URL: '{path}'")

    return clean_url
