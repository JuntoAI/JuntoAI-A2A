"""Unit tests for Integration API Pydantic models.

Tests cover:
- SimulateRequest validator: scenario_builder required when _dynamic, forbidden otherwise
- callback_url HTTPS validation

Requirements: 14.2
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.models.integrations import (
    SimulateRequest,
    ScenarioBuilderInput,
    MyProfileInput,
    TheirProfileInput,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scenario_builder() -> dict:
    """Create a minimal valid scenario_builder dict."""
    return {
        "simulation_type": "sales_call",
        "my_profile": {
            "name": "Alice",
            "role": "Account Exec",
            "company": "Acme Corp",
            "goals": ["Close deal at $100k"],
        },
        "their_profile": {
            "name": "Bob",
            "role": "CTO",
            "company": "TechCo",
            "goals": ["Get best price"],
        },
    }


# ---------------------------------------------------------------------------
# Test: SimulateRequest validator — scenario_builder mutual exclusion (Req 14.2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSimulateRequestDynamicValidator:
    """scenario_builder is required when _dynamic, forbidden otherwise."""

    def test_dynamic_without_builder_raises(self):
        """scenario_id='_dynamic' without scenario_builder raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SimulateRequest(scenario_id="_dynamic", scenario_builder=None)

        errors = exc_info.value.errors()
        assert any(
            "scenario_builder is required" in str(e.get("msg", "")).lower()
            for e in errors
        )

    def test_dynamic_with_builder_valid(self):
        """scenario_id='_dynamic' with scenario_builder is valid."""
        req = SimulateRequest(
            scenario_id="_dynamic",
            scenario_builder=ScenarioBuilderInput(**_make_scenario_builder()),
        )
        assert req.scenario_id == "_dynamic"
        assert req.scenario_builder is not None

    def test_non_dynamic_with_builder_raises(self):
        """Non-_dynamic scenario_id with scenario_builder raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SimulateRequest(
                scenario_id="talent_war",
                scenario_builder=ScenarioBuilderInput(**_make_scenario_builder()),
            )

        errors = exc_info.value.errors()
        assert any(
            "scenario_builder is forbidden" in str(e.get("msg", "")).lower()
            for e in errors
        )

    def test_non_dynamic_without_builder_valid(self):
        """Non-_dynamic scenario_id without scenario_builder is valid."""
        req = SimulateRequest(scenario_id="talent_war")
        assert req.scenario_id == "talent_war"
        assert req.scenario_builder is None

    def test_empty_scenario_id_raises(self):
        """Empty scenario_id raises ValidationError (min_length=1)."""
        with pytest.raises(ValidationError):
            SimulateRequest(scenario_id="")


# ---------------------------------------------------------------------------
# Test: callback_url HTTPS validation (Requirement 14.2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCallbackUrlValidation:
    """callback_url must be HTTPS in cloud mode, HTTP allowed in local mode."""

    def test_https_url_valid_in_cloud_mode(self):
        """HTTPS callback_url is accepted in cloud mode."""
        with patch("app.models.integrations.settings") as mock_settings:
            mock_settings.RUN_MODE = "cloud"
            req = SimulateRequest(
                scenario_id="talent_war",
                callback_url="https://example.com/webhook",
            )
        assert req.callback_url == "https://example.com/webhook"

    def test_http_url_rejected_in_cloud_mode(self):
        """HTTP callback_url is rejected in cloud mode."""
        with patch("app.models.integrations.settings") as mock_settings:
            mock_settings.RUN_MODE = "cloud"
            with pytest.raises(ValidationError) as exc_info:
                SimulateRequest(
                    scenario_id="talent_war",
                    callback_url="http://example.com/webhook",
                )

        errors = exc_info.value.errors()
        assert any("https://" in str(e.get("msg", "")).lower() for e in errors)

    def test_http_url_valid_in_local_mode(self):
        """HTTP callback_url is accepted in local mode."""
        with patch("app.models.integrations.settings") as mock_settings:
            mock_settings.RUN_MODE = "local"
            req = SimulateRequest(
                scenario_id="talent_war",
                callback_url="http://localhost:8080/webhook",
            )
        assert req.callback_url == "http://localhost:8080/webhook"

    def test_https_url_valid_in_local_mode(self):
        """HTTPS callback_url is also accepted in local mode."""
        with patch("app.models.integrations.settings") as mock_settings:
            mock_settings.RUN_MODE = "local"
            req = SimulateRequest(
                scenario_id="talent_war",
                callback_url="https://example.com/webhook",
            )
        assert req.callback_url == "https://example.com/webhook"

    def test_invalid_scheme_rejected(self):
        """Non-HTTP(S) schemes are rejected in any mode."""
        with patch("app.models.integrations.settings") as mock_settings:
            mock_settings.RUN_MODE = "local"
            with pytest.raises(ValidationError):
                SimulateRequest(
                    scenario_id="talent_war",
                    callback_url="ftp://example.com/webhook",
                )

    def test_none_callback_url_valid(self):
        """None callback_url is valid (field is optional)."""
        req = SimulateRequest(scenario_id="talent_war", callback_url=None)
        assert req.callback_url is None
