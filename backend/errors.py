"""Turning unexpected failures into 500 responses without leaking server internals."""

import logging

from fastapi import HTTPException, status

logger = logging.getLogger("repomind.errors")


def internal_error(action: str, exc: Exception) -> HTTPException:
    """Log the full error for whoever runs the server; tell the client only what failed.

    Raw exception text can contain file paths, SQL or library internals, so it
    goes to the log, not into the response.
    """
    logger.error("%s failed: %s", action, exc, exc_info=exc)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{action} failed on the server. Please try again; the server log has the details.",
    )
