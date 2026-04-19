"""Unit tests for Integration API Pydantic models.

Tests cover:
- SimulateRequest validator: scenario_builder required when _dynamic, forbidden otherwise
- callback_url HTTPS validation
- CreateKeyRequest field constraints

Requirements: 14.1, 14.2
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.models.integrations import (
    CreateKeyRequest,
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


# ---------------------------------------------------------------------------
# Test: CreateKeyRequest field constraints (Requirement 14.1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateKeyRequestConstraints:
    """CreateKeyRequest validates org_name, rate_limit_daily, rate_limit_per_minute."""

    def test_valid_request(self):
        """A fully valid CreateKeyRequest passes validation."""
        req = CreateKeyRequest(
            org_name="Acme Corp",
            scopes=["simulate", "read_sessions"],
            rate_limit_daily=500,
            rate_limit_per_minute=20,
        )
        assert req.org_name == "Acme Corp"
        assert req.rate_limit_daily == 500
        assert req.rate_limit_per_minute == 20

    def test_org_name_empty_raises(self):
        """Empty org_name raises ValidationError (min_length=1)."""
        with pytest.raises(ValidationError):
            CreateKeyRequest(org_name="")

    def test_org_name_too_long_raises(self):
        """org_name exceeding 200 chars raises ValidationError."""
        with pytest.raises(ValidationError):
            CreateKeyRequest(org_name="x" * 201)

    def test_org_name_max_length_valid(self):
        """org_name at exactly 200 chars is valid."""
        req = CreateKeyRequest(org_name="x" * 200)
        assert len(req.org_name) == 200

    def test_rate_limit_daily_zero_raises(self):
        """rate_limit_daily=0 raises ValidationError (gt=0)."""
        with pytest.raises(ValidationError):
            CreateKeyRequest(org_name="Test", rate_limit_daily=0)

    def test_rate_limit_daily_negative_raises(self):
        """Negative rate_limit_daily raises ValidationError."""
        with pytest.raises(ValidationError):
            CreateKeyRequest(org_name="Test", rate_limit_daily=-1)

    def test_rate_limit_daily_exceeds_max_raises(self):
        """rate_limit_daily > 10000 raises ValidationError (le=10000)."""
        with pytest.raises(ValidationError):
            CreateKeyRequest(org_name="Test", rate_limit_daily=10001)

    def test_rate_limit_daily_at_max_valid(self):
        """rate_limit_daily=10000 is valid."""
        req = CreateKeyRequest(org_name="Test", rate_limit_daily=10000)
        assert req.rate_limit_daily == 10000

    def test_rate_limit_per_minute_zero_raises(self):
        """rate_limit_per_minute=0 raises ValidationError (gt=0)."""
        with pytest.raises(ValidationError):
            CreateKeyRequest(org_name="Test", rate_limit_per_minute=0)

    def test_rate_limit_per_minute_exceeds_max_raises(self):
        """rate_limit_per_minute > 100 raises ValidationError (le=100)."""
        with pytest.raises(ValidationError):
            CreateKeyRequest(org_name="Test", rate_limit_per_minute=101)

    def test_rate_limit_per_minute_at_max_valid(self):
        """rate_limit_per_minute=100 is valid."""
        req = CreateKeyRequest(org_name="Test", rate_limit_per_minute=100)
        assert req.rate_limit_per_minute == 100

    def test_optional_fields_default_to_none(self):
        """scopes, rate_limit_daily, rate_limit_per_minute default to None."""
        req = CreateKeyRequest(org_name="MinimalOrg")
        assert req.scopes is None
        assert req.rate_limit_daily is None
        assert req.rate_limit_per_minute is None
