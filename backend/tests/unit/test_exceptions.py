"""Tests for custom exception classes."""

from app.exceptions import FirestoreConnectionError, SessionNotFoundError


def test_session_not_found_stores_session_id():
    exc = SessionNotFoundError("abc-123")
    assert exc.session_id == "abc-123"
    assert "abc-123" in str(exc)
    assert "Session abc-123 not found" == str(exc)


def test_firestore_connection_error_stores_message():
    exc = FirestoreConnectionError("connection refused")
    assert exc.message == "connection refused"
    assert str(exc) == "connection refused"
