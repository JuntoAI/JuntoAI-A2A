"""Custom exception classes for the JuntoAI A2A API."""


class SessionNotFoundError(Exception):
    """Raised when a session_id does not exist in Firestore."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session {session_id} not found")


class DatabaseConnectionError(Exception):
    """Raised when the database connection fails (Firestore or SQLite)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# Backward compat alias (deprecated)
FirestoreConnectionError = DatabaseConnectionError
