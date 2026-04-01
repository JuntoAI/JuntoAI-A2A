"""Validation tests for the 3 MVP scenario JSON files.

Ensures each scenario file loads successfully, contains the expected agent
roles/names/budgets, and defines the expected toggles with correct targets.

Requirements: 6.1–6.6, 7.1–7.6, 8.1–8.6
"""

from pathlib import Path

import pytest

from app.scenarios.loader import load_scenario_from_file
from app.scenarios.models import ArenaScenario

# Resolve the data directory relative to this test file's location.
DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "scenarios"
    / "data"
)


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
# Talent War
# ---------------------------------------------------------------------------

class TestTalentWarScenario:
    @pytest.fixture(scope="class")
    def scenario(self) -> ArenaScenario:
        return load_scenario_from_file(DATA_DIR / "talent-war.scenario.json")

    def test_loads_successfully(self, scenario: ArenaScenario):
        assert isinstance(scenario, ArenaScenario)
        assert scenario.id == "talent_war"

    def test_recruiter_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Recruiter")
        assert agent.name == "Sarah"
        assert agent.type == "negotiator"
        assert agent.budget.max == 130000

    def test_candidate_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Candidate")
        assert agent.name == "Alex"
        assert agent.type == "negotiator"
        assert agent.budget.min == 120000

    def test_regulator_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Regulator")
        assert agent.name == "HR Compliance Bot"
        assert agent.type == "regulator"

    def test_competing_offer_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "competing_offer")
        assert toggle.target_agent_role == "Candidate"

    def test_deadline_pressure_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "deadline_pressure")
        assert toggle.target_agent_role == "Recruiter"


# ---------------------------------------------------------------------------
# M&A Buyout
# ---------------------------------------------------------------------------

class TestMABuyoutScenario:
    @pytest.fixture(scope="class")
    def scenario(self) -> ArenaScenario:
        return load_scenario_from_file(DATA_DIR / "ma-buyout.scenario.json")

    def test_loads_successfully(self, scenario: ArenaScenario):
        assert isinstance(scenario, ArenaScenario)
        assert scenario.id == "ma_buyout"

    def test_buyer_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Buyer")
        assert agent.name == "Titan Corp CEO"
        assert agent.type == "negotiator"
        assert agent.budget.max == 50_000_000

    def test_seller_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Seller")
        assert agent.name == "Innovate Tech Founder"
        assert agent.type == "negotiator"
        assert agent.budget.min == 40_000_000

    def test_regulator_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Regulator")
        assert agent.name == "EU Regulator Bot"
        assert agent.type == "regulator"

    def test_hidden_debt_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "hidden_debt")
        assert toggle.target_agent_role == "Buyer"

    def test_max_strictness_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "max_strictness")
        assert toggle.target_agent_role == "Regulator"


# ---------------------------------------------------------------------------
# B2B Sales
# ---------------------------------------------------------------------------

class TestB2BSalesScenario:
    @pytest.fixture(scope="class")
    def scenario(self) -> ArenaScenario:
        return load_scenario_from_file(DATA_DIR / "b2b-sales.scenario.json")

    def test_loads_successfully(self, scenario: ArenaScenario):
        assert isinstance(scenario, ArenaScenario)
        assert scenario.id == "b2b_sales"

    def test_seller_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Seller")
        assert agent.name == "SaaS Account Executive"
        assert agent.type == "negotiator"
        assert agent.budget.max == 100_000

    def test_buyer_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Buyer")
        assert agent.name == "Target CTO"
        assert agent.type == "negotiator"
        assert agent.budget.max == 70_000

    def test_regulator_agent(self, scenario: ArenaScenario):
        agent = _get_agent(scenario, "Regulator")
        assert agent.name == "Procurement Bot"
        assert agent.type == "regulator"

    def test_q4_pressure_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "q4_pressure")
        assert toggle.target_agent_role == "Seller"

    def test_budget_freeze_toggle(self, scenario: ArenaScenario):
        toggle = _get_toggle(scenario, "budget_freeze")
        assert toggle.target_agent_role == "Buyer"
