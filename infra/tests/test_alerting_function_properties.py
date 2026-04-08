"""Property-based tests for the Telegram notifier Cloud Function logic.

Uses Hypothesis to verify universal properties across generated inputs.
Each test runs a minimum of 100 iterations per the design spec.

Framework: hypothesis + pytest
"""

import base64
import json
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Add the Cloud Function source to the path
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "modules", "alerting", "function"),
)

from main import (
    AlertIncident,
    CloudBuildEvent,
    detect_message_type,
    format_alerting_message,
    format_cloud_build_message,
    handle_pubsub,
    parse_alerting_incident,
    parse_cloud_build_event,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_safe_text = st.characters(whitelist_categories=("L", "N", "P", "Z"))
_alphanum = st.characters(whitelist_categories=("L", "N"))


@st.composite
def alert_incidents(draw):
    """Generate random AlertIncident instances."""
    return AlertIncident(
        policy_name=draw(st.text(min_size=1, max_size=100, alphabet=_safe_text)),
        state=draw(st.sampled_from(["open", "closed"])),
        condition_name=draw(st.text(min_size=1, max_size=100, alphabet=_safe_text)),
        resource_labels={
            "service_name": draw(st.text(min_size=1, max_size=50, alphabet=_alphanum))
        },
        summary=draw(st.text(min_size=1, max_size=200, alphabet=_safe_text)),
        started_at=draw(st.integers(min_value=0, max_value=2000000000)),
        ended_at=draw(
            st.one_of(st.none(), st.integers(min_value=0, max_value=2000000000))
        ),
        url=draw(
            st.text(
                min_size=1,
                max_size=200,
                alphabet=st.characters(whitelist_categories=("L", "N", "P")),
            )
        ),
    )


@st.composite
def cloud_build_events(draw):
    """Generate random CloudBuildEvent instances with consistent time fields."""
    start_dt = draw(
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    duration = draw(st.integers(min_value=1, max_value=7200))
    finish_dt = start_dt + timedelta(seconds=duration)
    return CloudBuildEvent(
        build_id=draw(st.text(min_size=1, max_size=50, alphabet=_alphanum)),
        status=draw(st.sampled_from(["FAILURE", "TIMEOUT", "INTERNAL_ERROR"])),
        trigger_name=draw(st.text(min_size=1, max_size=50, alphabet=_alphanum)),
        branch=draw(st.text(min_size=1, max_size=50, alphabet=_alphanum)),
        commit_sha=draw(st.text(min_size=7, max_size=7, alphabet=_alphanum)),
        log_url=draw(
            st.text(
                min_size=1,
                max_size=200,
                alphabet=st.characters(whitelist_categories=("L", "N", "P")),
            )
        ),
        start_time=start_dt.isoformat() + "Z",
        finish_time=finish_dt.isoformat() + "Z",
        duration_seconds=float(duration),
    )


# ---------------------------------------------------------------------------
# Serialization helpers (for round-trip tests)
# ---------------------------------------------------------------------------


def serialize_alert_incident(incident: AlertIncident) -> dict:
    """Serialize an AlertIncident to the GCP Monitoring notification JSON schema."""
    return {
        "incident": {
            "policy_name": incident.policy_name,
            "state": incident.state,
            "resource": {"labels": incident.resource_labels},
            "condition_name": incident.condition_name,
            "summary": incident.summary,
            "started_at": incident.started_at,
            "ended_at": incident.ended_at,
            "url": incident.url,
        },
        "version": "1.2",
    }


def serialize_cloud_build_event(build: CloudBuildEvent) -> dict:
    """Serialize a CloudBuildEvent to the Cloud Build event JSON schema."""
    return {
        "id": build.build_id,
        "status": build.status,
        "substitutions": {
            "TRIGGER_NAME": build.trigger_name,
            "BRANCH_NAME": build.branch,
            "SHORT_SHA": build.commit_sha,
        },
        "logUrl": build.log_url,
        "startTime": build.start_time,
        "finishTime": build.finish_time,
        "source": {
            "repoSource": {
                "branchName": build.branch,
                "commitSha": build.commit_sha,
            }
        },
    }


# ---------------------------------------------------------------------------
# Helper: build a mock CloudEvent for handle_pubsub
# ---------------------------------------------------------------------------


def _make_cloud_event(payload: dict) -> MagicMock:
    """Create a mock CloudEvent wrapping a Pub/Sub message with base64-encoded data."""
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    event = MagicMock()
    event.data = {"message": {"data": encoded}}
    return event


# ===========================================================================
# Property 1: Message type detection correctness
# Feature: gcp-telegram-alerting, Property 1: Message type detection correctness
#
# For any valid Pub/Sub payload, if the payload contains an `incident` field,
# detect_message_type SHALL return "alerting_policy"; if the payload contains
# a `status` field matching the Cloud Build schema, it SHALL return
# "cloud_build"; otherwise it SHALL return "unknown".
#
# Validates: Requirements 9.1
# ===========================================================================


class TestMessageTypeDetectionCorrectness:
    """Feature: gcp-telegram-alerting, Property 1: Message type detection correctness"""

    @pytest.mark.property
    @settings(max_examples=100)
    @given(incident=alert_incidents())
    def test_alerting_payload_detected(self, incident):
        """**Validates: Requirements 9.1**

        Any payload with an `incident` field must be detected as alerting_policy.
        """
        payload = serialize_alert_incident(incident)
        assert detect_message_type(payload) == "alerting_policy"

    @pytest.mark.property
    @settings(max_examples=100)
    @given(build=cloud_build_events())
    def test_cloud_build_payload_detected(self, build):
        """**Validates: Requirements 9.1**

        Any payload with `status` + `id`/`substitutions` must be detected as cloud_build.
        """
        payload = serialize_cloud_build_event(build)
        assert detect_message_type(payload) == "cloud_build"

    @pytest.mark.property
    @settings(max_examples=100)
    @given(
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet=_alphanum).filter(
                lambda k: k not in ("incident", "status")
            ),
            values=st.text(min_size=1, max_size=20),
            min_size=0,
            max_size=5,
        )
    )
    def test_unknown_payload_detected(self, data):
        """**Validates: Requirements 9.1**

        Any payload without `incident` or `status` must be detected as unknown.
        """
        assert detect_message_type(data) == "unknown"


# ===========================================================================
# Property 2: SUCCESS events are discarded
# Feature: gcp-telegram-alerting, Property 2: SUCCESS events are discarded
#
# For any Cloud Build event payload where status = "SUCCESS", the notifier
# function SHALL not produce a Telegram message.
#
# Validates: Requirements 5.3
# ===========================================================================


class TestSuccessEventsDiscarded:
    """Feature: gcp-telegram-alerting, Property 2: SUCCESS events are discarded"""

    @pytest.mark.property
    @settings(max_examples=100)
    @given(build=cloud_build_events())
    def test_success_build_not_sent(self, build):
        """**Validates: Requirements 5.3**

        For any Cloud Build event with SUCCESS status, no Telegram message is sent.
        """
        # Override status to SUCCESS
        payload = serialize_cloud_build_event(build)
        payload["status"] = "SUCCESS"

        event = _make_cloud_event(payload)

        with patch("main.send_telegram_message") as mock_send, \
             patch("main._get_secrets", return_value=("tok", "cid")):
            handle_pubsub(event)
            mock_send.assert_not_called()


# ===========================================================================
# Property 3: Alerting policy parse round-trip
# Feature: gcp-telegram-alerting, Property 3: Alerting policy parse round-trip
#
# For any valid AlertIncident object, serializing it to the GCP Monitoring
# notification JSON schema and then parsing it back with
# parse_alerting_incident SHALL produce an equivalent AlertIncident.
#
# Validates: Requirements 9.2, 9.6
# ===========================================================================


class TestAlertingPolicyParseRoundTrip:
    """Feature: gcp-telegram-alerting, Property 3: Alerting policy parse round-trip"""

    @pytest.mark.property
    @settings(max_examples=100)
    @given(incident=alert_incidents())
    def test_serialize_parse_roundtrip(self, incident):
        """**Validates: Requirements 9.2, 9.6**

        serialize → parse produces an equivalent AlertIncident.
        """
        payload = serialize_alert_incident(incident)
        parsed = parse_alerting_incident(payload)

        assert parsed.policy_name == incident.policy_name
        assert parsed.state == incident.state
        assert parsed.condition_name == incident.condition_name
        assert parsed.resource_labels == incident.resource_labels
        assert parsed.summary == incident.summary
        assert parsed.started_at == incident.started_at
        assert parsed.ended_at == incident.ended_at
        assert parsed.url == incident.url


# ===========================================================================
# Property 4: Cloud Build parse round-trip
# Feature: gcp-telegram-alerting, Property 4: Cloud Build parse round-trip
#
# For any valid CloudBuildEvent object, serializing it to the Cloud Build
# event JSON schema and then parsing it back with parse_cloud_build_event
# SHALL produce an equivalent CloudBuildEvent.
#
# Validates: Requirements 9.3, 9.7
# ===========================================================================


class TestCloudBuildParseRoundTrip:
    """Feature: gcp-telegram-alerting, Property 4: Cloud Build parse round-trip"""

    @pytest.mark.property
    @settings(max_examples=100)
    @given(build=cloud_build_events())
    def test_serialize_parse_roundtrip(self, build):
        """**Validates: Requirements 9.3, 9.7**

        serialize → parse produces an equivalent CloudBuildEvent.
        """
        payload = serialize_cloud_build_event(build)
        parsed = parse_cloud_build_event(payload)

        assert parsed.build_id == build.build_id
        assert parsed.status == build.status
        assert parsed.trigger_name == build.trigger_name
        assert parsed.branch == build.branch
        assert parsed.commit_sha == build.commit_sha
        assert parsed.log_url == build.log_url
        assert parsed.start_time == build.start_time
        assert parsed.finish_time == build.finish_time
        # Duration may have floating-point precision differences
        assert abs(parsed.duration_seconds - build.duration_seconds) < 1.0


# ===========================================================================
# Property 5: Alerting policy format completeness
# Feature: gcp-telegram-alerting, Property 5: Alerting policy format completeness
#
# For any valid alerting policy notification payload, the formatted Telegram
# message SHALL: (a) start with 🚨 when state is "open" or ✅ when state is
# "closed", (b) contain the policy_name, condition_name, resource service_name
# label, summary, and incident start time, and (c) contain <b> HTML tags.
#
# Validates: Requirements 6.4, 6.8, 9.4
# ===========================================================================


class TestAlertingPolicyFormatCompleteness:
    """Feature: gcp-telegram-alerting, Property 5: Alerting policy format completeness"""

    @pytest.mark.property
    @settings(max_examples=100)
    @given(incident=alert_incidents())
    def test_format_completeness(self, incident):
        """**Validates: Requirements 6.4, 6.8, 9.4**

        Formatted output contains correct emoji, all fields, and HTML tags.
        """
        msg = format_alerting_message(incident)

        # (a) Correct emoji prefix
        if incident.state == "open":
            assert msg.startswith("🚨")
        else:
            assert msg.startswith("✅")

        # (b) Contains key fields
        assert incident.policy_name in msg
        assert incident.condition_name in msg
        assert incident.resource_labels["service_name"] in msg

        # Summary only present for open incidents
        if incident.state == "open":
            assert incident.summary in msg

        # Start time formatted from timestamp
        if incident.started_at is not None and incident.state == "open":
            time_str = datetime.utcfromtimestamp(incident.started_at).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            assert time_str in msg

        # (c) HTML bold tags
        assert "<b>" in msg
        assert "</b>" in msg


# ===========================================================================
# Property 6: Cloud Build format completeness
# Feature: gcp-telegram-alerting, Property 6: Cloud Build format completeness
#
# For any valid Cloud Build event payload with a failure status, the formatted
# Telegram message SHALL: (a) start with 🔴, (b) contain the trigger name,
# build status, branch name, commit SHA, duration, and log URL, and (c)
# contain <b> HTML tags.
#
# Validates: Requirements 5.2, 5.4, 6.5, 6.9, 9.4
# ===========================================================================


class TestCloudBuildFormatCompleteness:
    """Feature: gcp-telegram-alerting, Property 6: Cloud Build format completeness"""

    @pytest.mark.property
    @settings(max_examples=100)
    @given(build=cloud_build_events())
    def test_format_completeness(self, build):
        """**Validates: Requirements 5.2, 5.4, 6.5, 6.9, 9.4**

        Formatted output contains 🔴, all fields, and HTML tags.
        """
        msg = format_cloud_build_message(build)

        # (a) Starts with 🔴
        assert msg.startswith("🔴")

        # (b) Contains all key fields
        assert build.trigger_name in msg
        assert build.status in msg
        assert build.branch in msg
        assert build.commit_sha in msg
        assert build.log_url in msg

        # Duration is formatted (e.g. "5m 12s" or "30s") — just check it's present
        # by verifying the duration label exists
        assert "Duration" in msg

        # (c) HTML bold tags
        assert "<b>" in msg
        assert "</b>" in msg
