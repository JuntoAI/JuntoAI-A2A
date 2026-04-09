"""Property-based tests for exception handling.

# Feature: 080_a2a-local-battle-arena, Property 9: DatabaseConnectionError produces HTTP 503
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.exceptions import DatabaseConnectionError
from app.main import app
from app.orchestrator.availability_checker import AllowedModels


# Use a single persistent test route to avoid polluting app.routes on every call.
_TEST_PATH = "/_test_db_error_prop9"
_route_installed = False


def _ensure_test_route():
    global _route_installed
    if _route_installed:
        return
    from fastapi import APIRouter

    router = APIRouter()

    @router.get(_TEST_PATH)
    async def _raise_db_error(msg: str = "default"):
        raise DatabaseConnectionError(msg)

    app.include_router(router)
    _route_installed = True


@given(
    message=st.text(min_size=1, max_size=200),
)
@hypothesis_settings(max_examples=100)
def test_database_connection_error_returns_503(message: str):
    """**Validates: Requirements 10.5**

    For any request triggering DatabaseConnectionError, the handler returns
    HTTP 503 with {"detail": "Database unavailable"}.
    """
    _ensure_test_route()
    with patch(
        "app.main.AvailabilityChecker.probe_all",
        new_callable=AsyncMock,
        return_value=AllowedModels(
            entries=(),
            model_ids=frozenset(),
            probe_results=(),
            probed_at="2025-01-01T00:00:00+00:00",
        ),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(_TEST_PATH, params={"msg": message})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Database unavailable"}
