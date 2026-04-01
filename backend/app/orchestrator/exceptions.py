"""Custom exceptions for the orchestration layer."""


class ModelNotAvailableError(Exception):
    """Raised when model_id is unrecognized or endpoint unavailable."""

    def __init__(self, model_id: str, message: str) -> None:
        self.model_id = model_id
        self.message = message
        super().__init__(f"Model {model_id}: {message}")


class ModelTimeoutError(Exception):
    """Raised when LLM request exceeds timeout and fallback fails."""

    def __init__(self, model_id: str, elapsed_seconds: float) -> None:
        self.model_id = model_id
        self.elapsed_seconds = elapsed_seconds
        super().__init__(
            f"Model {model_id} timed out after {elapsed_seconds:.1f}s"
        )


class AgentOutputParseError(Exception):
    """Raised when LLM response cannot be parsed after retry."""

    def __init__(self, agent_name: str, raw_response: str) -> None:
        self.agent_name = agent_name
        self.raw_response = raw_response
        super().__init__(
            f"Failed to parse output from agent {agent_name!r}: {raw_response[:200]}"
        )
