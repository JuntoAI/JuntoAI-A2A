# Feature: 197_token-usage-history, Property 5: Token cost formula correctness
"""Property-based tests for compute_token_cost.

**Validates: Requirements 3.1, 3.4**

For any non-negative integer total_tokens_used, verify:
- compute_token_cost(total_tokens_used) == max(1, ceil(total_tokens_used / 1000))
- result >= 1
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.utils.token_cost import compute_token_cost


@pytest.mark.property
@given(total_tokens_used=st.integers(min_value=0, max_value=10_000_000))
@settings(max_examples=200)
def test_token_cost_formula_correctness(total_tokens_used: int):
    """Property 5: Token cost formula correctness.

    **Validates: Requirements 3.1, 3.4**
    """
    result = compute_token_cost(total_tokens_used)
    expected = max(1, math.ceil(total_tokens_used / 1000))
    assert result == expected
    assert result >= 1
    assert isinstance(result, int)
