"""Validation and structural tests for the 4 Sales scenario JSON files.

Ensures each scenario file loads successfully, conforms to ArenaScenario schema,
contains the expected agent roles/types/budgets, defines correct toggles, and
validates category grouping behavior.

Requirements: 1.1–1.10, 2.1–2.8, 3.1–3.9, 4.1–4.8, 6.1–6.5
"""

import json
from pathlib import Path

import pytest

from app.scenarios.loader import load_scenario_from_file
from app.scenarios.models import ArenaScenario
from app.scenarios.registry import ScenarioRegistry

# Resolve the data directory relative to this test file's location.
DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "scenarios"
    / "data"
)

SALES_SCENARIO_FILES = [
    "saas-negotiation.scenario.json",
    "renewal-churn-save.scenario.json",
    "enterprise-multi-stakeholder.scenario.json",
    "discovery-qualification.scenario.json",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_agent(scenario: ArenaScenario, role: str):
    """Return the agent with the given role, or fail."""
    for agent in scenario.agents:
        if agent.role == role:
            return agent
    pytest.fail(f"Agent with role '{role}' not found in scenario '{scenario.id}'")


def _get_toggle(scenario: ArenaScenario, toggle_id: str):
    """Return the toggle with the given id, or fail."""
    for toggle in scenario.toggles:
        if toggle.id == toggle_id:
            return toggle
    pytest.fail(f"Toggle '{toggle_id}' not found in scenario '{scenario.id}'")


# ---------------------------------------------------------------------------
# 9.1 — Parametrized validation test across all 4 sales scenarios
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSalesScenariosValidation:
    """Parametrized validation: each sales scenario must pass schema validation
    and meet baseline structural requirements."""

    @pytest.mark.parametrize("filename", SALES_SCENARIO_FILES)
    def test_sales_scenario_validates(self, filename: str):
        path = DATA_DIR / filename
        assert path.exists(), f"Scenario file not found: {path}"
        scenario = ArenaScenario.model_validate_json(path.read_text())
        assert isinstance(scenario, ArenaScenario)

    @pytest.mark.parametrize("filename", SALES_SCENARIO_FILES)
    def test_has_at_least_two_agents(self, filename: str):
        scenario = ArenaScenario.model_validate_json((DATA_DIR / filename).read_text())
        assert len(scenario.agents) >= 2

    @pytest.mark.parametrize("filename", SALES_SCENARIO_FILES)
    def test_has_at_least_two_toggles(self, filename: str):
        scenario = ArenaScenario.model_validate_json((DATA_DIR / filename).read_text())
        assert len(scenario.toggles) >= 2

    @pytest.mark.parametrize("filename", SALES_SCENARIO_FILES)
    def test_category_is_sales(self, filename: str):
        scenario = ArenaScenario.model_validate_json((DATA_DIR / filename).read_text())
        assert scenario.category == "Sales"

    @pytest.mark.parametrize("filename", SALES_SCENARIO_FILES)
    def test_has_at_least_one_negotiator(self, filename: str):
        scenario = ArenaScenario.model_validate_json((DATA_DIR / filename).read_text())
        assert any(a.type == "negotiator" for a in scenario.agents)

    @pytest.mark.parametrize("filename", SALES_SCENARIO_FILES)
    def test_has_at_least_one_regulator(self, filename: str):
        scenario = ArenaScenario.model_validate_json((DATA_DIR / filename).read_text())
        assert any(a.type == "regulator" for a in scenario.agents)


# ---------------------------------------------------------------------------
# 9.2 — Structural assertions per scenario
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSaaSNegotiationScenario:
    @pytest.fixture(scope="class")
    def scenario(self) -> ArenaScenario:
        return load_scenario_from_file(DATA_DIR / "saas-negotiation.scenario.json")

    def test_loads_successfully(self, scenario: ArenaScenario):
        assert isinstance(scenario, ArenaScenario)
        assert scenario.id == "saas_negotiation"

    def test_has_three_agents(self, scenario: ArenaScenario):
        assert len(scenario.agents) == 3

    def test_seller_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Seller")
        assert agent.name == "Rachel"
        assert agent.type == "negotiator"

    def test_buyer_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Buyer")
        assert agent.name == "Marcus"
        assert agent.type == "negotiator"

    def test_procurement_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Procurement")
        assert agent.name == "Diane"
        assert agent.type == "regulator"

    def test_max_turns_in_range(self, scenario: ArenaScenario):
        assert 10 <= scenario.negotiation_params.max_turns <= 14

    def test_has_at_least_two_toggles(self, scenario: ArenaScenario):
        assert len(scenario.toggles) >= 2

    def test_quota_pressure_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "end_of_quarter_quota")
        assert toggle.target_agent_role == "Seller"

    def test_competing_vendor_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "competing_vendor_signed")
        assert toggle.target_agent_role == "Buyer"


@pytest.mark.unit
class TestRenewalChurnSaveScenario:
    @pytest.fixture(scope="class")
    def scenario(self) -> ArenaScenario:
        return load_scenario_from_file(DATA_DIR / "renewal-churn-save.scenario.json")

    def test_loads_successfully(self, scenario: ArenaScenario):
        assert isinstance(scenario, ArenaScenario)
        assert scenario.id == "renewal_churn_save"

    def test_has_three_agents(self, scenario: ArenaScenario):
        assert len(scenario.agents) == 3

    def test_csm_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Customer Success Manager")
        assert agent.name == "Priya"
        assert agent.type == "negotiator"

    def test_customer_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Customer")
        assert agent.name == "Derek"
        assert agent.type == "negotiator"

    def test_finance_compliance_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Finance Compliance")
        assert agent.name == "Sanjay"
        assert agent.type == "regulator"

    def test_max_turns_in_range(self, scenario: ArenaScenario):
        assert 10 <= scenario.negotiation_params.max_turns <= 14

    def test_has_at_least_two_toggles(self, scenario: ArenaScenario):
        assert len(scenario.toggles) >= 2


@pytest.mark.unit
class TestEnterpriseMultiStakeholderScenario:
    @pytest.fixture(scope="class")
    def scenario(self) -> ArenaScenario:
        return load_scenario_from_file(
            DATA_DIR / "enterprise-multi-stakeholder.scenario.json"
        )

    def test_loads_successfully(self, scenario: ArenaScenario):
        assert isinstance(scenario, ArenaScenario)
        assert scenario.id == "enterprise_multi_stakeholder"

    def test_has_four_agents(self, scenario: ArenaScenario):
        assert len(scenario.agents) == 4

    def test_sales_director_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Sales Director")
        assert agent.name == "Victoria"
        assert agent.type == "negotiator"

    def test_cto_champion_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "CTO Champion")
        assert agent.name == "Raj"
        assert agent.type == "negotiator"

    def test_procurement_director_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Procurement Director")
        assert agent.name == "Helen"
        assert agent.type == "negotiator"

    def test_legal_compliance_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Legal Compliance")
        assert agent.name == "Tomoko"
        assert agent.type == "regulator"

    def test_max_turns_in_range(self, scenario: ArenaScenario):
        assert 12 <= scenario.negotiation_params.max_turns <= 16

    def test_turn_order_includes_all_four_agents(self, scenario: ArenaScenario):
        agent_roles = {a.role for a in scenario.agents}
        turn_order_roles = set(scenario.negotiation_params.turn_order)
        assert agent_roles == turn_order_roles


@pytest.mark.unit
class TestDiscoveryQualificationScenario:
    @pytest.fixture(scope="class")
    def scenario(self) -> ArenaScenario:
        return load_scenario_from_file(
            DATA_DIR / "discovery-qualification.scenario.json"
        )

    def test_loads_successfully(self, scenario: ArenaScenario):
        assert isinstance(scenario, ArenaScenario)
        assert scenario.id == "discovery_qualification"

    def test_has_three_agents(self, scenario: ArenaScenario):
        assert len(scenario.agents) == 3

    def test_sdr_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "SDR")
        assert agent.name == "Jordan"
        assert agent.type == "negotiator"

    def test_prospect_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Prospect")
        assert agent.name == "Avery"
        assert agent.type == "negotiator"

    def test_coach_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Coach")
        assert agent.name == "Morgan"
        assert agent.type == "regulator"

    def test_max_turns_in_range(self, scenario: ArenaScenario):
        assert 10 <= scenario.negotiation_params.max_turns <= 14

    def test_value_format_is_number(self, scenario: ArenaScenario):
        assert scenario.negotiation_params.value_format == "number"

    def test_value_label_is_qualification_score(self, scenario: ArenaScenario):
        assert scenario.negotiation_params.value_label == "Qualification Score"


# ---------------------------------------------------------------------------
# 9.3 — Category grouping tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCategoryGrouping:
    """Tests for the category field on ArenaScenario and its behavior
    in the registry."""

    def test_validates_with_category_present(self, valid_scenario_dict):
        """ArenaScenario validates when category is explicitly set."""
        data = {**valid_scenario_dict, "category": "Sales"}
        scenario = ArenaScenario.model_validate(data)
        assert scenario.category == "Sales"

    def test_validates_without_category_defaults_to_general(self, valid_scenario_dict):
        """ArenaScenario defaults category to 'General' when omitted."""
        data = {**valid_scenario_dict}
        data.pop("category", None)
        scenario = ArenaScenario.model_validate(data)
        assert scenario.category == "General"

    def test_list_scenarios_includes_category(self):
        """list_scenarios response includes category for each scenario."""
        registry = ScenarioRegistry(str(DATA_DIR))
        scenarios = registry.list_scenarios()
        assert len(scenarios) > 0
        for s in scenarios:
            assert "category" in s, f"Scenario '{s['id']}' missing 'category' field"
            assert isinstance(s["category"], str)
            assert len(s["category"]) > 0

    def test_existing_scenarios_have_correct_categories(self):
        """Existing scenarios have correct category values after migration."""
        expected = {
            "talent_war": "Corporate",
            "ma_buyout": "Corporate",
            "b2b_sales": "Corporate",
            "startup_pitch": "Corporate",
            "urban_development": "Corporate",
            "plg_vs_slg": "Corporate",
            "family_curfew": "Everyday",
            "freelance_gig": "Everyday",
            "easter_bunny_debate": "Fun",
            "saas_negotiation": "Sales",
            "renewal_churn_save": "Sales",
            "enterprise_multi_stakeholder": "Sales",
            "discovery_qualification": "Sales",
        }
        registry = ScenarioRegistry(str(DATA_DIR))
        # Use a juntoai.org email to access domain-restricted scenarios
        scenarios = registry.list_scenarios(email="test@juntoai.org")
        scenario_map = {s["id"]: s["category"] for s in scenarios}
        for scenario_id, expected_category in expected.items():
            assert scenario_id in scenario_map, (
                f"Scenario '{scenario_id}' not found in registry"
            )
            assert scenario_map[scenario_id] == expected_category, (
                f"Scenario '{scenario_id}' has category '{scenario_map[scenario_id]}', "
                f"expected '{expected_category}'"
            )
