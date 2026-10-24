"""Shared pytest fixtures."""

import pytest

from backend.config import settings


@pytest.fixture(scope="session", autouse=True)
def _skip_embedding_on_index():
    """Indexing through the API normally builds vector embeddings, which loads a
    model and is slow. Tests that need embeddings re-enable it explicitly.
    Session-scoped so it also covers module-scoped fixtures that index repos."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "embed_on_index", False)
        yield
