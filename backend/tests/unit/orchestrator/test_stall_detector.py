"""Unit tests for the negotiation stall detector."""

import pytest

from app.orchestrator.stall_detector import (
    StallDiagnosis,
    _check_instant_convergence,
    _check_message_repetition,
    _check_price_ping_pong,
    _check_price_stagnation,
    detect_stall,
)


def _make_state(
    turn_count=5,
    max_turns=10,
    history=None,
    agent_states=None,
    agreement_threshold=5000.0,
    current_offer=0.0,
):
    return {
        "session_id": "test",
        "turn_count": turn_count,
        "max_turns": max_turns,
        "history": history or [],
        "agent_states": agent_states or {},
        "agreement_threshold": agreement_threshold,
        "current_offer": current_offer,
    }


def _neg_entry(role, price, message="some message", turn=0):
    return {
        "role": role,
        "agent_type": "negotiator",
        "turn_number": turn,
        "content": {
            "inner_thought": "thinking",
            "public_message": message,
            "proposed_price": price,
        },
    }


class TestDetectStallEarlyExit:
    def test_returns_not_stalled_below_min_turns(self):
        state = _make_state(turn_count=1)
        result = detect_stall(state)
        assert not result.is_stalled

    def test_returns_not_stalled_at_min_turns_no_issues(self):
        state = _make_state(
            turn_count=3,
            history=[
                _neg_entry("Buyer", 50000, "I offer 50k"),
                _neg_entry("Seller", 80000, "I counter 80k"),
                _neg_entry("Buyer", 55000, "How about 55k"),
                _neg_entry("Seller", 75000, "Let me come down to 75k"),
            ],
        )
        result = detect_stall(state)
        assert not result.is_stalled


class TestPricePingPong:
    def test_detects_repeated_same_price(self):
        history = [
            _neg_entry("Buyer", 70000),
            _neg_entry("Seller", 80000),
            _neg_entry("Buyer", 70000),
            _neg_entry("Seller", 80000),
            _neg_entry("Buyer", 70000),
            _neg_entry("Seller", 80000),
        ]
        state = _make_state(history=history)
        result = _check_price_ping_pong(state)
        assert result.is_stalled
        assert result.stall_type == "price_ping_pong"
        assert result.confidence >= 0.8

    def test_no_stall_with_moving_prices(self):
        history = [
            _neg_entry("Buyer", 50000),
            _neg_entry("Seller", 90000),
            _neg_entry("Buyer", 55000),
            _neg_entry("Seller", 85000),
            _neg_entry("Buyer", 60000),
            _neg_entry("Seller", 80000),
        ]
        state = _make_state(history=history)
        result = _check_price_ping_pong(state)
        assert not result.is_stalled

    def test_not_enough_history(self):
        history = [_neg_entry("Buyer", 70000)]
        state = _make_state(history=history)
        result = _check_price_ping_pong(state)
        assert not result.is_stalled


class TestPriceStagnation:
    def test_detects_all_prices_clustered(self):
        history = [
            _neg_entry("Buyer", 70000),
            _neg_entry("Seller", 70100),
            _neg_entry("Buyer", 70050),
            _neg_entry("Seller", 70000),
            _neg_entry("Buyer", 70100),
            _neg_entry("Seller", 70050),
        ]
        state = _make_state(history=history)
        result = _check_price_stagnation(state)
        assert result.is_stalled
        assert result.stall_type == "price_stagnation"

    def test_no_stall_with_spread_prices(self):
        history = [
            _neg_entry("Buyer", 50000),
            _neg_entry("Seller", 90000),
            _neg_entry("Buyer", 60000),
            _neg_entry("Seller", 80000),
            _neg_entry("Buyer", 65000),
            _neg_entry("Seller", 75000),
        ]
        state = _make_state(history=history)
        result = _check_price_stagnation(state)
        assert not result.is_stalled


class TestMessageRepetition:
    def test_detects_repeated_messages(self):
        msg = "I believe we can find a mutually beneficial partnership at this price point"
        history = [
            _neg_entry("Buyer", 70000, msg),
            _neg_entry("Seller", 80000, "different"),
            _neg_entry("Buyer", 70000, msg),
            _neg_entry("Seller", 80000, "different"),
            _neg_entry("Buyer", 70000, msg),
        ]
        state = _make_state(history=history)
        result = _check_message_repetition(state)
        assert result.is_stalled
        assert result.stall_type == "message_repetition"

    def test_no_stall_with_varied_messages(self):
        history = [
            _neg_entry("Buyer", 70000, "Let me start with an offer of 70k"),
            _neg_entry("Seller", 80000, "I counter at 80k"),
            _neg_entry("Buyer", 72000, "Based on market data I can go to 72k"),
            _neg_entry("Seller", 78000, "Considering your points I drop to 78k"),
            _neg_entry("Buyer", 74000, "With the multi-year commitment how about 74k"),
        ]
        state = _make_state(history=history)
        result = _check_message_repetition(state)
        assert not result.is_stalled


class TestInstantConvergence:
    def test_detects_opening_prices_too_close(self):
        history = [
            _neg_entry("Buyer", 69000),
            _neg_entry("Seller", 71000),
        ]
        state = _make_state(
            turn_count=2,
            history=history,
            agreement_threshold=5000,
        )
        result = _check_instant_convergence(state)
        assert result.is_stalled
        assert result.stall_type == "instant_convergence"

    def test_no_stall_with_wide_opening_gap(self):
        history = [
            _neg_entry("Buyer", 50000),
            _neg_entry("Seller", 90000),
        ]
        state = _make_state(
            turn_count=2,
            history=history,
            agreement_threshold=5000,
        )
        result = _check_instant_convergence(state)
        assert not result.is_stalled

    def test_skipped_after_early_turns(self):
        history = [
            _neg_entry("Buyer", 69000),
            _neg_entry("Seller", 71000),
        ]
        state = _make_state(
            turn_count=5,
            history=history,
            agreement_threshold=5000,
        )
        result = _check_instant_convergence(state)
        assert not result.is_stalled


class TestDetectStallIntegration:
    def test_returns_highest_confidence_stall(self):
        """When multiple stalls detected, return highest confidence."""
        msg = "same message repeated over and over again in this negotiation"
        history = [
            _neg_entry("Buyer", 70000, msg),
            _neg_entry("Seller", 70100, "other"),
            _neg_entry("Buyer", 70000, msg),
            _neg_entry("Seller", 70050, "other"),
            _neg_entry("Buyer", 70000, msg),
            _neg_entry("Seller", 70100, "other"),
        ]
        state = _make_state(history=history)
        result = detect_stall(state)
        assert result.is_stalled
        # price_ping_pong has 0.9 confidence, should win
        assert result.confidence >= 0.8

    def test_stall_diagnosis_to_dict(self):
        d = StallDiagnosis(
            is_stalled=True,
            stall_type="test",
            confidence=0.85,
            advice=["fix it"],
            details={"key": "val"},
        )
        result = d.to_dict()
        assert result["is_stalled"] is True
        assert result["stall_type"] == "test"
        assert result["confidence"] == 0.85
        assert result["advice"] == ["fix it"]
