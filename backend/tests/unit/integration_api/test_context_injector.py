"""Unit tests for the CRM Context Injector.

Tests cover:
- List fields joined with commas
- Boolean fields rendered as "Yes"/"No"
- deal_value formatted as currency string
- Empty/missing context produces no preamble
- Custom fields included in preamble

Requirements: 7.1, 7.2, 7.3, 7.4
"""

from __future__ import annotations

import pytest

from app.models.integrations import CRMContext
from app.services.integration_service import IntegrationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service():
    """Create an IntegrationService instance for context injection tests."""
    return IntegrationService()


# ---------------------------------------------------------------------------
# Test: List fields joined with commas (Requirement 7.3)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListFieldsJoinedWithCommas:
    """List fields (pain_points, competing_vendors) are comma-separated."""

    def test_pain_points_joined(self, service):
        context = CRMContext(pain_points=["slow onboarding", "high churn", "no analytics"])
        preamble = service.build_context_preamble(context)

        assert "Pain Points: slow onboarding, high churn, no analytics" in preamble

    def test_competing_vendors_joined(self, service):
        context = CRMContext(competing_vendors=["Salesforce", "HubSpot"])
        preamble = service.build_context_preamble(context)

        assert "Competing Vendors: Salesforce, HubSpot" in preamble

    def test_single_item_list_no_trailing_comma(self, service):
        context = CRMContext(pain_points=["budget constraints"])
        preamble = service.build_context_preamble(context)

        assert "Pain Points: budget constraints" in preamble
        # No trailing comma
        assert "budget constraints," not in preamble

    def test_empty_list_excluded_from_preamble(self, service):
        context = CRMContext(pain_points=[], contact_name="Alice")
        preamble = service.build_context_preamble(context)

        assert "Pain Points" not in preamble
        assert "Contact Name: Alice" in preamble


# ---------------------------------------------------------------------------
# Test: Boolean fields rendered as "Yes"/"No" (Requirement 7.3)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBooleanFieldsRendered:
    """Boolean fields (budget_approved) render as 'Yes' or 'No'."""

    def test_budget_approved_true_renders_yes(self, service):
        context = CRMContext(budget_approved=True)
        preamble = service.build_context_preamble(context)

        assert "Budget Approved: Yes" in preamble

    def test_budget_approved_false_renders_no(self, service):
        context = CRMContext(budget_approved=False)
        preamble = service.build_context_preamble(context)

        assert "Budget Approved: No" in preamble

    def test_budget_approved_none_excluded(self, service):
        context = CRMContext(budget_approved=None, contact_name="Bob")
        preamble = service.build_context_preamble(context)

        assert "Budget Approved" not in preamble


# ---------------------------------------------------------------------------
# Test: deal_value formatted as currency string (Requirement 7.3)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDealValueCurrencyFormat:
    """deal_value is formatted as a currency string (e.g., '$150,000.00')."""

    def test_deal_value_formatted_with_dollar_sign(self, service):
        context = CRMContext(deal_value=150000.0)
        preamble = service.build_context_preamble(context)

        assert "Deal Value: $150,000.00" in preamble

    def test_deal_value_zero(self, service):
        context = CRMContext(deal_value=0.0)
        preamble = service.build_context_preamble(context)

        assert "Deal Value: $0.00" in preamble

    def test_deal_value_with_cents(self, service):
        context = CRMContext(deal_value=99999.99)
        preamble = service.build_context_preamble(context)

        assert "Deal Value: $99,999.99" in preamble

    def test_deal_value_large_number(self, service):
        context = CRMContext(deal_value=1250000.50)
        preamble = service.build_context_preamble(context)

        assert "Deal Value: $1,250,000.50" in preamble


# ---------------------------------------------------------------------------
# Test: Empty/missing context produces no preamble (Requirement 7.4)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmptyContextNoPreamble:
    """Empty or missing context produces an empty string (no preamble)."""

    def test_none_context_returns_empty(self, service):
        preamble = service.build_context_preamble(None)
        assert preamble == ""

    def test_empty_dict_returns_empty(self, service):
        preamble = service.build_context_preamble({})
        assert preamble == ""

    def test_all_none_fields_returns_empty(self, service):
        context = CRMContext()
        preamble = service.build_context_preamble(context)
        assert preamble == ""

    def test_context_with_only_none_values_dict(self, service):
        preamble = service.build_context_preamble({"contact_name": None, "company": None})
        assert preamble == ""

    def test_non_empty_context_has_markers(self, service):
        context = CRMContext(contact_name="Alice")
        preamble = service.build_context_preamble(context)

        assert preamble.startswith("--- CRM Context ---")
        assert preamble.endswith("--- End CRM Context ---")


# ---------------------------------------------------------------------------
# Test: Custom fields included in preamble (Requirement 7.1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCustomFieldsInPreamble:
    """custom_fields dict entries appear in the preamble with proper prefix."""

    def test_custom_field_string_value(self, service):
        context = CRMContext(custom_fields={"crm_id": "SF-12345"})
        preamble = service.build_context_preamble(context)

        assert "Custom Field (crm_id): SF-12345" in preamble

    def test_custom_field_boolean_value(self, service):
        context = CRMContext(custom_fields={"is_enterprise": True})
        preamble = service.build_context_preamble(context)

        assert "Custom Field (is_enterprise): Yes" in preamble

    def test_custom_field_list_value(self, service):
        context = CRMContext(custom_fields={"tags": ["vip", "renewal"]})
        preamble = service.build_context_preamble(context)

        assert "Custom Field (tags): vip, renewal" in preamble

    def test_custom_field_none_value_excluded(self, service):
        context = CRMContext(
            contact_name="Alice",
            custom_fields={"empty_field": None, "real_field": "value"},
        )
        preamble = service.build_context_preamble(context)

        assert "empty_field" not in preamble
        assert "Custom Field (real_field): value" in preamble

    def test_multiple_custom_fields(self, service):
        context = CRMContext(
            custom_fields={
                "priority": "high",
                "region": "EMEA",
            }
        )
        preamble = service.build_context_preamble(context)

        assert "Custom Field (priority): high" in preamble
        assert "Custom Field (region): EMEA" in preamble
