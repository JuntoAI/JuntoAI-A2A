"""Unit tests for compute_token_cost utility.

Requirements: 3.1, 3.2, 3.4
"""

import pytest

from app.utils.token_cost import compute_token_cost


class TestComputeTokenCost:
    """Boundary-value and edge-case tests for the token cost formula."""

    def test_zero_tokens_returns_minimum(self):
        """Requirement 3.2: zero tokens → minimum cost of 1."""
        assert compute_token_cost(0) == 1

    def test_one_token_returns_minimum(self):
        """1 AI token rounds up to 1 user token."""
        assert compute_token_cost(1) == 1

    def test_999_tokens_returns_one(self):
        """999 AI tokens → ceil(999/1000) = 1."""
        assert compute_token_cost(999) == 1

    def test_1000_tokens_returns_one(self):
        """Exact boundary: 1000 AI tokens → 1 user token."""
        assert compute_token_cost(1000) == 1

    def test_1001_tokens_returns_two(self):
        """Just over boundary: 1001 AI tokens → 2 user tokens."""
        assert compute_token_cost(1001) == 2

    def test_large_value(self):
        """Large token count: 5_500_000 → 5500 user tokens."""
        assert compute_token_cost(5_500_000) == 5500

    def test_exact_multiple(self):
        """Exact multiple: 3000 → 3."""
        assert compute_token_cost(3000) == 3

    def test_result_always_at_least_one(self):
        """Requirement 3.4: result is always >= 1 for any non-negative input."""
        for val in [0, 1, 500, 999, 1000, 1001, 10_000_000]:
            assert compute_token_cost(val) >= 1
