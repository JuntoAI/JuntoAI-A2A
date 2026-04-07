# Implementation Plan: Sales Team Acquisition Package

## Overview

Content-heavy delivery: 4 scenario JSON files, 1 Next.js landing page, 1 demo storyline markdown, plus backend and frontend tests. No engine code changes. Each scenario is a standalone task for independent execution.

## Tasks

- [ ] 1. Create SaaS Contract Negotiation scenario
  - Create `backend/app/scenarios/data/saas-negotiation.scenario.json`
  - 3 agents: Seller (negotiator), Buyer (negotiator), Procurement (regulator)
  - Seller persona: senior AE with SaaS pricing authority, seat-based pricing, implementation fees
  - Buyer persona: VP-level with budget constraints, competing vendor context, SLA demands
  - Procurement persona: compliance gatekeeper with SLA requirements, security certs, contractual standards
  - 2+ toggles: quota pressure (Seller), competing vendor offer (Buyer)
  - `negotiation_params`: `max_turns` 10–14, `agreement_threshold` appropriate for SaaS ACV, turn_order alternating negotiators with regulator
  - Use `gemini-2.5-pro` / `gemini-3-flash-preview` per existing model assignment pattern
  - Must pass `ArenaScenario.model_validate()` — validate by running `cd backend && python -c "from app.scenarios.models import ArenaScenario; import json; ArenaScenario.model_validate(json.loads(open('app/scenarios/data/saas-negotiation.scenario.json').read()))"`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

- [ ] 2. Create Renewal / Churn Save scenario
  - Create `backend/app/scenarios/data/renewal-churn-save.scenario.json`
  - 3 agents: Customer Success Manager (negotiator), Customer (negotiator), Finance Compliance (regulator)
  - Customer persona: dissatisfied, underused features, poor support, active competitor eval
  - CSM persona: retention specialist with discount authority, product roadmap knowledge, escalation paths
  - Finance Compliance persona: enforces discount ceilings, contract modification rules, revenue recognition risks
  - 2+ toggles: customer already signed competitor contract (Customer), internal churn risk data (CSM)
  - `negotiation_params`: `max_turns` 10–14, `agreement_threshold` appropriate for renewal price range
  - Must pass `ArenaScenario.model_validate()`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [ ] 3. Create Enterprise Multi-Stakeholder scenario
  - Create `backend/app/scenarios/data/enterprise-multi-stakeholder.scenario.json`
  - 4 agents: Sales Director (negotiator), CTO/Champion (negotiator), Procurement Director (negotiator), Legal/Compliance (regulator)
  - CTO/Champion persona: technical advocate who must justify spend, integration concerns
  - Procurement Director persona: cost-focused blocker, budget reduction targets, multi-year aversion
  - Sales Director persona: strategic seller navigating champion-blocker dynamic, can offer POC/phased rollout
  - Legal/Compliance persona: DPA requirements, liability caps, IP ownership, vendor risk assessment
  - 2+ toggles: CEO pre-approved budget (CTO), 20% vendor spend cut mandate (Procurement)
  - `negotiation_params`: `max_turns` 12–16, turn_order includes all 4 agents, `agreement_threshold` for enterprise deal size
  - Must pass `ArenaScenario.model_validate()`
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [ ] 4. Create Discovery / Qualification Call scenario
  - Create `backend/app/scenarios/data/discovery-qualification.scenario.json`
  - 3 agents: Sales Development Rep (negotiator), Prospect (negotiator), Sales Manager/Coach (regulator)
  - Prospect persona: guarded executive, real but unstated pain point, evaluating multiple solutions
  - SDR persona: discovery-focused, must uncover BANT through strategic questioning
  - Sales Manager/Coach persona: evaluates discovery quality, flags premature pitching, tracks qualification criteria
  - 2+ toggles: urgent internal deadline (Prospect), current vendor raised prices 40% (Prospect)
  - `negotiation_params`: `max_turns` 10–14, `value_format: "number"`, `value_label: "Qualification Score"`
  - `difficulty: "beginner"`
  - Must pass `ArenaScenario.model_validate()`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

- [ ] 5. Checkpoint — Validate all 4 scenarios
  - Ensure all 4 scenario JSON files pass Pydantic validation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Backend tests for sales scenarios
  - [ ] 6.1 Create parametrized validation test
    - Create `backend/tests/unit/test_sales_scenario_files.py`
    - Parametrized pytest over all 4 filenames: `saas-negotiation.scenario.json`, `renewal-churn-save.scenario.json`, `enterprise-multi-stakeholder.scenario.json`, `discovery-qualification.scenario.json`
    - Each must pass `ArenaScenario.model_validate_json()`, assert `len(agents) >= 2`, `len(toggles) >= 2`, at least one negotiator, at least one regulator
    - _Requirements: 1.1, 1.3, 2.1, 3.1, 4.1_
  - [ ] 6.2 Add structural assertions per scenario
    - In the same test file, add test classes per scenario (following `test_scenario_files.py` pattern)
    - SaaS: assert 3 agents, correct roles/types, max_turns 10–14, 2+ toggles with correct targets
    - Renewal: assert 3 agents, correct roles/types, max_turns 10–14, 2+ toggles
    - Enterprise: assert 4 agents, correct roles/types, max_turns 12–16, 4-agent turn_order
    - Discovery: assert 3 agents, correct roles/types, max_turns 10–14, `value_format == "number"`, `value_label == "Qualification Score"`
    - _Requirements: 1.2, 1.7, 1.9, 2.2, 2.6, 2.7, 3.2, 3.7, 3.8, 4.2, 4.6, 4.7_

- [ ] 7. Create `/sales` landing page
  - Create `frontend/app/sales/page.tsx` as a server component (no `"use client"`)
  - Export `metadata` with sales-specific `title`, `description`, and `openGraph` fields
  - Hero section: headline ("Rehearse Your Next Deal" or similar), subheadline, `WaitlistForm` component
  - Value props section: 3 cards (objection handling, hidden variables, multi-stakeholder navigation) with Lucide icons
  - Scenario showcase section: 4 cards for SaaS, Renewal, Enterprise, Discovery scenarios
  - CTA section: link to `/arena`, link to GitHub repo
  - Use brand palette (`brand-blue`, `brand-green`, `brand-charcoal`, `brand-offwhite`, `brand-gray`), Tailwind utilities, Lucide React icons
  - Responsive from 320px to 1920px
  - No `isLocalMode` redirect — page renders in both modes
  - Import `WaitlistForm` from `@/components/WaitlistForm`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_

- [ ] 8. Frontend tests for `/sales` page
  - [ ] 8.1 Create sales page render tests
    - Create `frontend/__tests__/pages/sales.test.tsx`
    - Mock `WaitlistForm` (same pattern as `page.test.tsx`)
    - Assert: hero heading rendered, WaitlistForm rendered, 3+ value prop cards, 4 scenario showcase cards, CTA link with `href="/arena"`, no redirect behavior
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.9, 5.10_
  - [ ] 8.2 Test metadata export
    - Import `metadata` from `@/app/sales/page`, assert `title` contains sales-specific text, `openGraph.title` and `openGraph.description` are present and sales-specific
    - _Requirements: 5.8_

- [ ] 9. Checkpoint — Ensure all tests pass
  - Run `cd backend && pytest tests/unit/test_sales_scenario_files.py -v`
  - Run `cd frontend && npx vitest run __tests__/pages/sales.test.tsx`
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Create demo video storyline
  - Create `docs/sales-demo-storyline.md`
  - 60-second script with timestamps for each shot/scene
  - 5+ distinct shots: hook/opening, scenario setup, live negotiation with visible agent reasoning in Glass Box view, toggle flip showing outcome change, closing CTA
  - Each shot specifies: timestamp range, visual description, text overlay/caption, transition effects
  - Feature the SaaS Negotiation scenario (most universally relatable)
  - Include toggle activation scene ("one toggle changes everything")
  - End with CTA to `/sales` landing page and GitHub repo
  - Written for a video editor with no product knowledge — explicit visual direction
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [ ] 11. Final checkpoint — Ensure all tests pass
  - Run full backend test suite: `cd backend && pytest tests/unit/test_sales_scenario_files.py -v`
  - Run full frontend test suite: `cd frontend && npx vitest run __tests__/pages/sales.test.tsx`
  - Verify `docs/sales-demo-storyline.md` exists and has correct structure
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- No property-based testing — all deliverables are fixed content validated by example-based tests
- Each scenario JSON is a standalone task for independent, parallel execution
- No new backend code — just JSON files dropped into the existing data directory
- The `/sales` page is a single server component reusing `WaitlistForm` — no new components needed
