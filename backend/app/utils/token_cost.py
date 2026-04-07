"""Shared token cost calculation utility.

Used by both the negotiation history endpoint and the stream_negotiation
deduction logic to ensure a single source of truth for the formula.
"""

import math


def compute_token_cost(total_tokens_used: int) -> int:
    """1 user token per 1,000 AI tokens, rounded up, minimum 1."""
    return max(1, math.ceil(total_tokens_used / 1000))
