"""Deploy RepoMind to a Hugging Face Docker Space.

Uploads the git-tracked files (so local data, secrets and build output never
leave the machine) and prepends the Space metadata header to README.md.

Usage (after `hf auth login`):
    python scripts/deploy_hf.py               # -> <your-username>/RepoMind
    python scripts/deploy_hf.py owner/Space   # custom Space id
"""

from __future__ import annotations

import shutil
import subprocess
import sys
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


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line]


def main() -> None:
    api = HfApi()
    space_id = sys.argv[1] if len(sys.argv) > 1 else f"{api.whoami()['name']}/RepoMind"

    api.create_repo(space_id, repo_type="space", space_sdk="docker", exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        for rel in tracked_files():
            src = ROOT / rel
            if src.is_file():
                dest = staging / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

        readme = staging / "README.md"
        readme.write_text(SPACE_HEADER + readme.read_text(encoding="utf-8"), encoding="utf-8")

        api.upload_folder(
            folder_path=staging,
            repo_id=space_id,
            repo_type="space",
            commit_message="Deploy RepoMind",
        )

    print(f"Deployed: https://huggingface.co/spaces/{space_id}")


if __name__ == "__main__":
    main()
