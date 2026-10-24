"""Deploy RepoMind to a Hugging Face Docker Space.

Uploads the committed HEAD tree (so local data, secrets, uncommitted edits and
Windows CRLF line endings never reach the Space) and prepends the Space
metadata header to README.md.

Usage (after `hf auth login`):
    python scripts/deploy_hf.py               # -> <your-username>/RepoMind
    python scripts/deploy_hf.py owner/Space   # custom Space id
"""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent

SPACE_HEADER = """---
title: RepoMind
emoji: 🧠
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Ask any Python GitHub repo questions, with line citations
---

"""


def export_head(dest: Path) -> None:
    """Extract the committed HEAD tree into dest, exactly as stored in git."""
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")


def main() -> None:
    api = HfApi()
    space_id = sys.argv[1] if len(sys.argv) > 1 else f"{api.whoami()['name']}/RepoMind"

    api.create_repo(space_id, repo_type="space", space_sdk="docker", exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        export_head(staging)

        readme = staging / "README.md"
        readme.write_bytes(SPACE_HEADER.encode("utf-8") + readme.read_bytes())

        api.upload_folder(
            folder_path=staging,
            repo_id=space_id,
            repo_type="space",
            commit_message="Deploy RepoMind",
        )

    print(f"Deployed: https://huggingface.co/spaces/{space_id}")


if __name__ == "__main__":
    main()
