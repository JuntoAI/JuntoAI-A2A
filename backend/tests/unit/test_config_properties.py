"""Property-based tests for application configuration.

# Feature: 080_a2a-local-battle-arena, Property 7: RUN_MODE validation rejects invalid values
"""

import pytest
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.config import Settings


@given(
    run_mode=st.text().filter(lambda s: s not in ("cloud", "local")),
)
@hypothesis_settings(max_examples=100)
def test_run_mode_rejects_invalid_values(run_mode: str):
    """**Validates: Requirements 6.5**

    For any string not in {"cloud", "local"}, constructing Settings with that
    RUN_MODE raises ValidationError.
    """
    with pytest.raises(ValidationError):
        Settings(RUN_MODE=run_mode)
