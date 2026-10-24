"""Shared pytest fixtures."""

import pytest

from backend.config import settings


@pytest.fixture(scope="session", autouse=True)
def _test_settings(tmp_path_factory):
    """Session-wide test settings (session-scoped so module fixtures see them too).

    - Indexing through the API normally builds vector embeddings, which loads a
      model and is slow. Tests that need embeddings re-enable it explicitly.
    - Skip the background model warm-up on app startup.
    - Repos registered by tests go to a temp data dir, not the developer's real
      .repomind_data/custom_repos.json.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "embed_on_index", False)
        mp.setattr(settings, "warmup_models", False)
        mp.setattr(settings, "data_dir", tmp_path_factory.mktemp("repomind_data"))
        yield
