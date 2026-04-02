"""Tests for custom exception classes."""

from app.exceptions import DatabaseConnectionError, FirestoreConnectionError, SessionNotFoundError


def test_session_not_found_stores_session_id():
    exc = SessionNotFoundError("abc-123")
    assert exc.session_id == "abc-123"
    assert "abc-123" in str(exc)
    assert "Session abc-123 not found" == str(exc)


def test_database_connection_error_stores_message():
    exc = DatabaseConnectionError("connection refused")
    assert exc.message == "connection refused"
    assert str(exc) == "connection refused"


def test_firestore_connection_error_alias():
    """FirestoreConnectionError is a backward-compat alias for DatabaseConnectionError."""
    assert FirestoreConnectionError is DatabaseConnectionError
    exc = FirestoreConnectionError("legacy call")
    assert isinstance(exc, DatabaseConnectionError)
