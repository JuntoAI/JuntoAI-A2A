"""Unit tests for the Telegram notifier Cloud Function logic.

Covers: detect_message_type, parse_alerting_incident, parse_cloud_build_event,
format_alerting_message, format_cloud_build_message, send_telegram_message,
and handle_pubsub integration (SUCCESS discard, unknown schema discard).
"""

import base64
import json
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

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
    send_telegram_message,
)


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

ALERTING_PAYLOAD = {
    "incident": {
        "policy_name": "Backend Error Log Rate",
        "state": "open",
        "resource": {
            "labels": {
                "service_name": "juntoai-backend",
                "project_id": "juntoai-a2a-mvp",
            }
        },
        "condition_name": "backend/error-log-count above 5",
        "summary": "Error log count exceeded threshold",
        "started_at": 1704067200,
        "ended_at": None,
        "url": "https://console.cloud.google.com/monitoring/alerting/incidents/123",
    },
    "version": "1.2",
}

ALERTING_CLOSED_PAYLOAD = {
    "incident": {
        "policy_name": "Backend Error Log Rate",
        "state": "closed",
        "resource": {
            "labels": {
                "service_name": "juntoai-backend",
                "project_id": "juntoai-a2a-mvp",
            }
        },
        "condition_name": "backend/error-log-count above 5",
        "summary": "Error log count exceeded threshold",
        "started_at": 1704067200,
        "ended_at": 1704067500,
        "url": "https://console.cloud.google.com/monitoring/alerting/incidents/123",
    },
    "version": "1.2",
}

CLOUD_BUILD_FAILURE_PAYLOAD = {
    "id": "build-id-123",
    "status": "FAILURE",
    "substitutions": {
        "_REGION": "europe-west1",
        "TRIGGER_NAME": "juntoai-cicd-backend",
        "SHORT_SHA": "abc1234",
        "BRANCH_NAME": "main",
    },
    "logUrl": "https://console.cloud.google.com/cloud-build/builds/123",
    "startTime": "2025-01-01T00:00:00Z",
    "finishTime": "2025-01-01T00:05:12Z",
    "source": {
        "repoSource": {
            "branchName": "main",
            "commitSha": "abc1234567890",
        }
    },
}

CLOUD_BUILD_SUCCESS_PAYLOAD = {
    "id": "build-id-456",
    "status": "SUCCESS",
    "substitutions": {
        "TRIGGER_NAME": "juntoai-cicd-backend",
        "SHORT_SHA": "def5678",
        "BRANCH_NAME": "main",
    },
    "logUrl": "https://console.cloud.google.com/cloud-build/builds/456",
    "startTime": "2025-01-01T00:00:00Z",
    "finishTime": "2025-01-01T00:03:00Z",
    "source": {"repoSource": {"branchName": "main", "commitSha": "def5678901234"}},
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
# 13.1 — detect_message_type()
# ===========================================================================


class TestDetectMessageType:
    """Tests for detect_message_type() — alerting, cloud_build, unknown."""

    def test_alerting_policy_payload(self):
        assert detect_message_type(ALERTING_PAYLOAD) == "alerting_policy"

    def test_alerting_closed_payload(self):
        assert detect_message_type(ALERTING_CLOSED_PAYLOAD) == "alerting_policy"

    def test_cloud_build_failure_payload(self):
        assert detect_message_type(CLOUD_BUILD_FAILURE_PAYLOAD) == "cloud_build"

    def test_cloud_build_success_payload(self):
        assert detect_message_type(CLOUD_BUILD_SUCCESS_PAYLOAD) == "cloud_build"

    def test_unknown_empty_payload(self):
        assert detect_message_type({}) == "unknown"

    def test_unknown_random_payload(self):
        assert detect_message_type({"foo": "bar", "baz": 42}) == "unknown"

    def test_payload_with_status_only_no_id(self):
        """status alone without id or substitutions → unknown."""
        assert detect_message_type({"status": "FAILURE"}) == "unknown"

    def test_payload_with_status_and_id(self):
        """status + id → cloud_build."""
        assert detect_message_type({"status": "FAILURE", "id": "x"}) == "cloud_build"

    def test_payload_with_status_and_substitutions(self):
        """status + substitutions → cloud_build."""
        assert detect_message_type({"status": "SUCCESS", "substitutions": {}}) == "cloud_build"


# ===========================================================================
# 13.2 — parse_alerting_incident()
# ===========================================================================


class TestParseAlertingIncident:
    """Tests for parse_alerting_incident() with sample GCP Monitoring payload."""

    def test_extracts_policy_name(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert result.policy_name == "Backend Error Log Rate"

    def test_extracts_state(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert result.state == "open"

    def test_extracts_condition_name(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert result.condition_name == "backend/error-log-count above 5"

    def test_extracts_resource_labels(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert result.resource_labels == {
            "service_name": "juntoai-backend",
            "project_id": "juntoai-a2a-mvp",
        }

    def test_extracts_summary(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert result.summary == "Error log count exceeded threshold"

    def test_extracts_started_at(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert result.started_at == 1704067200

    def test_ended_at_none_for_open(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert result.ended_at is None

    def test_ended_at_present_for_closed(self):
        result = parse_alerting_incident(ALERTING_CLOSED_PAYLOAD)
        assert result.ended_at == 1704067500

    def test_extracts_url(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert "monitoring/alerting/incidents/123" in result.url

    def test_returns_alert_incident_dataclass(self):
        result = parse_alerting_incident(ALERTING_PAYLOAD)
        assert isinstance(result, AlertIncident)

    def test_missing_fields_use_defaults(self):
        """Payload with empty incident → safe defaults."""
        result = parse_alerting_incident({"incident": {}})
        assert result.policy_name == "Unknown Policy"
        assert result.state == "unknown"
        assert result.condition_name == ""
        assert result.resource_labels == {}
        assert result.summary == ""
        assert result.started_at is None
        assert result.ended_at is None
        assert result.url == ""


# ===========================================================================
# 13.3 — parse_cloud_build_event()
# ===========================================================================


class TestParseCloudBuildEvent:
    """Tests for parse_cloud_build_event() with sample Cloud Build payload."""

    def test_extracts_build_id(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.build_id == "build-id-123"

    def test_extracts_status(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.status == "FAILURE"

    def test_extracts_trigger_name(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.trigger_name == "juntoai-cicd-backend"

    def test_extracts_branch(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.branch == "main"

    def test_extracts_commit_sha(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.commit_sha == "abc1234"

    def test_extracts_log_url(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert "cloud-build/builds/123" in result.log_url

    def test_extracts_start_time(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.start_time == "2025-01-01T00:00:00Z"

    def test_extracts_finish_time(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.finish_time == "2025-01-01T00:05:12Z"

    def test_calculates_duration(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert result.duration_seconds == 312.0  # 5m 12s

    def test_returns_cloud_build_event_dataclass(self):
        result = parse_cloud_build_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        assert isinstance(result, CloudBuildEvent)

    def test_missing_substitutions_use_defaults(self):
        """Payload without substitutions → falls back to repoSource or 'unknown'."""
        payload = {
            "id": "x",
            "status": "FAILURE",
            "logUrl": "",
            "startTime": "",
            "finishTime": "",
            "source": {"repoSource": {"branchName": "dev", "commitSha": "1234567890"}},
        }
        result = parse_cloud_build_event(payload)
        assert result.trigger_name == "unknown"
        assert result.branch == "dev"
        assert result.commit_sha == "1234567"  # first 7 chars of commitSha

    def test_completely_empty_payload_defaults(self):
        result = parse_cloud_build_event({})
        assert result.build_id == "unknown"
        assert result.status == "UNKNOWN"
        assert result.trigger_name == "unknown"
        assert result.branch == "unknown"
        assert result.duration_seconds == 0.0


# ===========================================================================
# 13.4 — format_alerting_message()
# ===========================================================================


class TestFormatAlertingMessage:
    """Tests for format_alerting_message() — emoji prefix, all fields present."""

    def _make_incident(self, state="open", **overrides):
        defaults = dict(
            policy_name="Backend Error Log Rate",
            state=state,
            condition_name="backend/error-log-count above 5",
            resource_labels={"service_name": "juntoai-backend"},
            summary="Error log count exceeded threshold",
            started_at=1704067200,
            ended_at=1704067500 if state == "closed" else None,
            url="https://console.cloud.google.com/monitoring/alerting/incidents/123",
        )
        defaults.update(overrides)
        return AlertIncident(**defaults)

    def test_open_incident_starts_with_alarm_emoji(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert msg.startswith("🚨")

    def test_closed_incident_starts_with_resolved_emoji(self):
        msg = format_alerting_message(self._make_incident("closed"))
        assert msg.startswith("✅")

    def test_open_incident_title_contains_alarm(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "ALARM:" in msg

    def test_closed_incident_title_contains_resolved(self):
        msg = format_alerting_message(self._make_incident("closed"))
        assert "RESOLVED:" in msg

    def test_open_state_label_is_firing(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "FIRING" in msg

    def test_closed_state_label_is_resolved(self):
        msg = format_alerting_message(self._make_incident("closed"))
        assert "RESOLVED" in msg

    def test_contains_policy_name(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "Backend Error Log Rate" in msg

    def test_contains_resource_service_name(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "juntoai-backend" in msg

    def test_contains_condition_name(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "backend/error-log-count above 5" in msg

    def test_open_contains_summary(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "Error log count exceeded threshold" in msg

    def test_open_contains_link(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "View Incident" in msg
        assert "incidents/123" in msg

    def test_closed_does_not_contain_summary(self):
        msg = format_alerting_message(self._make_incident("closed"))
        assert "Summary" not in msg

    def test_contains_html_bold_tags(self):
        msg = format_alerting_message(self._make_incident("open"))
        assert "<b>" in msg and "</b>" in msg

    def test_contains_timestamp(self):
        msg = format_alerting_message(self._make_incident("open"))
        # 1704067200 = 2024-01-01 00:00:00 UTC
        assert "2024-01-01" in msg


# ===========================================================================
# 13.5 — format_cloud_build_message()
# ===========================================================================


class TestFormatCloudBuildMessage:
    """Tests for format_cloud_build_message() — 🔴 prefix, all fields present."""

    def _make_build(self, **overrides):
        defaults = dict(
            build_id="build-id-123",
            status="FAILURE",
            trigger_name="juntoai-cicd-backend",
            branch="main",
            commit_sha="abc1234",
            log_url="https://console.cloud.google.com/cloud-build/builds/123",
            start_time="2025-01-01T00:00:00Z",
            finish_time="2025-01-01T00:05:12Z",
            duration_seconds=312.0,
        )
        defaults.update(overrides)
        return CloudBuildEvent(**defaults)

    def test_starts_with_red_circle_emoji(self):
        msg = format_cloud_build_message(self._make_build())
        assert msg.startswith("🔴")

    def test_contains_build_failed_title(self):
        msg = format_cloud_build_message(self._make_build())
        assert "Build FAILED:" in msg

    def test_contains_trigger_name(self):
        msg = format_cloud_build_message(self._make_build())
        assert "juntoai-cicd-backend" in msg

    def test_contains_status(self):
        msg = format_cloud_build_message(self._make_build())
        assert "FAILURE" in msg

    def test_contains_branch(self):
        msg = format_cloud_build_message(self._make_build())
        assert "main" in msg

    def test_contains_commit_sha(self):
        msg = format_cloud_build_message(self._make_build())
        assert "abc1234" in msg

    def test_contains_duration(self):
        msg = format_cloud_build_message(self._make_build())
        assert "5m 12s" in msg

    def test_contains_log_url(self):
        msg = format_cloud_build_message(self._make_build())
        assert "View Build Logs" in msg
        assert "cloud-build/builds/123" in msg

    def test_contains_html_bold_tags(self):
        msg = format_cloud_build_message(self._make_build())
        assert "<b>" in msg and "</b>" in msg

    def test_timeout_status(self):
        msg = format_cloud_build_message(self._make_build(status="TIMEOUT"))
        assert "TIMEOUT" in msg


# ===========================================================================
# 13.6 — send_telegram_message()
# ===========================================================================


class TestSendTelegramMessage:
    """Tests for send_telegram_message() with mocked HTTP — URL, parse_mode, error handling."""

    @patch("main.requests.post")
    @patch("main._get_secrets", return_value=("fake-bot-token", "fake-chat-id"))
    def test_posts_to_correct_url(self, mock_secrets, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200)
        send_telegram_message("hello")
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert url == "https://api.telegram.org/botfake-bot-token/sendMessage"

    @patch("main.requests.post")
    @patch("main._get_secrets", return_value=("fake-bot-token", "fake-chat-id"))
    def test_sends_html_parse_mode(self, mock_secrets, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200)
        send_telegram_message("hello")
        payload = mock_post.call_args[1]["json"]
        assert payload["parse_mode"] == "HTML"

    @patch("main.requests.post")
    @patch("main._get_secrets", return_value=("fake-bot-token", "fake-chat-id"))
    def test_sends_correct_chat_id(self, mock_secrets, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200)
        send_telegram_message("hello")
        payload = mock_post.call_args[1]["json"]
        assert payload["chat_id"] == "fake-chat-id"

    @patch("main.requests.post")
    @patch("main._get_secrets", return_value=("fake-bot-token", "fake-chat-id"))
    def test_sends_message_text(self, mock_secrets, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200)
        send_telegram_message("test message")
        payload = mock_post.call_args[1]["json"]
        assert payload["text"] == "test message"

    @patch("main.requests.post")
    @patch("main._get_secrets", return_value=("fake-bot-token", "fake-chat-id"))
    def test_raises_on_non_2xx(self, mock_secrets, mock_post):
        mock_response = MagicMock(ok=False, status_code=403, text="Forbidden")
        mock_response.raise_for_status.side_effect = Exception("403 Forbidden")
        mock_post.return_value = mock_response
        with pytest.raises(Exception, match="403"):
            send_telegram_message("hello")

    @patch("main.requests.post")
    @patch("main._get_secrets", return_value=("fake-bot-token", "fake-chat-id"))
    def test_sets_timeout(self, mock_secrets, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200)
        send_telegram_message("hello")
        assert mock_post.call_args[1]["timeout"] == 10


# ===========================================================================
# 13.7 — SUCCESS event discarding and unknown schema discarding
# ===========================================================================


class TestHandlePubsubIntegration:
    """Integration tests for handle_pubsub: SUCCESS discard, unknown discard."""

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_success_build_event_is_discarded(self, mock_secrets, mock_send):
        """Cloud Build SUCCESS events should NOT trigger a Telegram message."""
        event = _make_cloud_event(CLOUD_BUILD_SUCCESS_PAYLOAD)
        handle_pubsub(event)
        mock_send.assert_not_called()

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_non_failure_build_statuses_are_discarded(self, mock_secrets, mock_send):
        """QUEUED, WORKING, CANCELLED build events should NOT trigger a Telegram message."""
        for status in ("QUEUED", "WORKING", "CANCELLED"):
            mock_send.reset_mock()
            payload = {**CLOUD_BUILD_SUCCESS_PAYLOAD, "status": status}
            event = _make_cloud_event(payload)
            handle_pubsub(event)
            mock_send.assert_not_called(), f"Expected no message for status={status}"

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_unknown_schema_is_discarded(self, mock_secrets, mock_send):
        """Payloads matching no known schema should NOT trigger a Telegram message."""
        event = _make_cloud_event({"random": "data", "nothing": "useful"})
        handle_pubsub(event)
        mock_send.assert_not_called()

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_failure_build_event_sends_message(self, mock_secrets, mock_send):
        """Cloud Build FAILURE events SHOULD trigger a Telegram message."""
        event = _make_cloud_event(CLOUD_BUILD_FAILURE_PAYLOAD)
        handle_pubsub(event)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "🔴" in msg
        assert "juntoai-cicd-backend" in msg

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_alerting_open_event_sends_message(self, mock_secrets, mock_send):
        """Alerting policy open incidents SHOULD trigger a Telegram message."""
        event = _make_cloud_event(ALERTING_PAYLOAD)
        handle_pubsub(event)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "🚨" in msg
        assert "Backend Error Log Rate" in msg

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_alerting_closed_event_sends_message(self, mock_secrets, mock_send):
        """Alerting policy closed incidents SHOULD trigger a Telegram message."""
        event = _make_cloud_event(ALERTING_CLOSED_PAYLOAD)
        handle_pubsub(event)
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "✅" in msg

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_empty_payload_is_discarded(self, mock_secrets, mock_send):
        """Empty JSON payload should be discarded."""
        event = _make_cloud_event({})
        handle_pubsub(event)
        mock_send.assert_not_called()

    @patch("main.send_telegram_message")
    @patch("main._get_secrets", return_value=("tok", "cid"))
    def test_invalid_json_is_discarded(self, mock_secrets, mock_send):
        """Non-JSON Pub/Sub data should be discarded without crashing."""
        encoded = base64.b64encode(b"not valid json").decode()
        event = MagicMock()
        event.data = {"message": {"data": encoded}}
        handle_pubsub(event)
        mock_send.assert_not_called()
