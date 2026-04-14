# Implementation Plan: Persona Landing Pages

## Overview

Implement a persona system (`sales` | `founder`) that flows from dedicated landing pages through the session context into the Arena scenario selector and AI Builder. The implementation proceeds bottom-up: backend model + filtering first, then session context, then landing pages and Arena UI, then Builder templates, and finally new scenario content.

## Tasks

- [x] 1. Add `tags` field to ArenaScenario model and update ScenarioRegistry filtering
  - [x] 1.1 Add optional `tags` field to `ArenaScenario` in `backend/app/scenarios/models.py`
    - Add `tags: list[str] | None = Field(default=None, ...)` to the `ArenaScenario` class
    - No validation constraints on tag values — free-form strings
    - _Requirements: 4.1, 4.2_

  - [x] 1.2 Update `ScenarioRegistry.list_scenarios` to accept optional `persona` parameter and filter scenarios
    - Add `persona: str | None = None` parameter to `list_scenarios`
    - Filter logic: include scenario if `scenario.tags is None` OR `persona in scenario.tags`
    - Exclude scenario if `scenario.tags is not None` AND `persona not in scenario.tags`
    - When `persona` is `None`, return all scenarios (backward-compatible)
    - Add `tags` to the returned dict for each scenario
    - _Requirements: 4.3, 4.4, 4.5, 4.6_

  - [x] 1.3 Update scenarios router to accept `persona` query parameter
    - Add `persona: str | None = Query(default=None)` to `list_scenarios` endpoint in `backend/app/scenarios/router.py`
    - Pass `persona` through to `registry.list_scenarios`
    - _Requirements: 4.3_

  - [x] 1.4 Write property test for persona filtering correctness
    - **Property 1: Persona filtering correctness**
    - Use Hypothesis to generate arbitrary scenario lists with random tag combinations and persona values
    - Assert: every returned scenario has `tags is None` or `persona in tags`; no excluded scenario should have matching tags
    - Test file: `backend/tests/property/test_persona_filtering.py`
    - **Validates: Requirements 3.1, 3.2, 3.5, 3.6, 4.4**

  - [x] 1.5 Write property test for category sort order preserved after filtering
    - **Property 2: Category sort order preserved after persona filtering**
    - Use Hypothesis to generate arbitrary scenario lists, apply persona filter, assert sort order: categories alphabetical with "General" last, then difficulty, then name
    - Test file: `backend/tests/property/test_persona_filtering.py`
    - **Validates: Requirements 3.4, 4.6**

  - [x] 1.6 Write property test for ArenaScenario tags round-trip
    - **Property 3: ArenaScenario tags round-trip**
    - Use Hypothesis to generate valid ArenaScenario instances with arbitrary tags (None, empty, populated)
    - Assert: `model_validate(model_dump())` produces equivalent tags
    - Test file: `backend/tests/property/test_scenario_tags_roundtrip.py`
    - **Validates: Requirements 4.1, 4.2**

  - [x] 1.7 Write unit tests for ScenarioRegistry filtering and router endpoint
    - Test `list_scenarios` with persona=`"sales"`, `"founder"`, `None` — verify correct filtering
    - Test backward compatibility: no persona param returns all scenarios
    - Test `ArenaScenario` model validation with tags field: None, empty, populated
    - Test router endpoint with persona query param
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 2. Checkpoint — Backend model and filtering
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Tag all existing scenario JSON files per Requirement 7
  - [x] 3.1 Add `"tags": ["sales"]` to `b2b_sales`, `saas_negotiation`, `renewal_churn_save`, `discovery_qualification`, `enterprise_multi_stakeholder` scenario JSON files
    - Add `"tags"` field after `"category"` in each file
    - _Requirements: 7.1_

  - [x] 3.2 Add `"tags": ["founder"]` to `startup_pitch`, `startup_equity_split`, `ma_buyout` scenario JSON files
    - _Requirements: 7.2_

  - [x] 3.3 Add `"tags": ["sales", "founder"]` to `talent_war` and `freelance_gig` scenario JSON files
    - _Requirements: 7.3_

  - [x] 3.4 Verify `family_curfew`, `easter_bunny_debate`, `landlord_lease_renewal`, `urban_development` have no tags (leave unchanged)
    - Verify `plg_vs_slg` retains `allowed_email_domains` and has no persona tags
    - _Requirements: 7.4, 7.5_

- [x] 4. Create new founder scenario JSON files
  - [x] 4.1 Create `backend/app/scenarios/data/term-sheet-negotiation.scenario.json`
    - ID: `term_sheet_negotiation`, Category: "Corporate", Tags: `["founder"]`
    - Agents: Founder (negotiator), Lead Investor (negotiator), Legal Advisor (regulator) — minimum 2 agents, at least 1 negotiator
    - At least 2 toggles with hidden context payloads (e.g., competing term sheet, fund timeline pressure)
    - Focus: liquidation preferences, anti-dilution, pro-rata rights, board composition
    - Follow existing ArenaScenario JSON schema
    - _Requirements: 6.1, 6.3, 6.4, 6.5_

  - [x] 4.2 Create `backend/app/scenarios/data/vc-due-diligence.scenario.json`
    - ID: `vc_due_diligence`, Category: "Corporate", Tags: `["founder"]`
    - Agents: Founder (negotiator), VC Partner (negotiator), Financial Analyst (regulator)
    - At least 2 toggles with hidden context payloads (e.g., inflated metrics, competitor pivot knowledge)
    - Focus: metrics defense, market sizing, competitive positioning, unit economics
    - _Requirements: 6.2, 6.3, 6.4, 6.5_

  - [x] 4.3 Update `startup_pitch` scenario to include `"founder"` tag (if not already done in 3.2)
    - _Requirements: 6.6_

  - [x] 4.4 Update `startup_equity_split` scenario to include `"founder"` tag (if not already done in 3.2)
    - _Requirements: 6.7_

- [x] 5. Checkpoint — Scenario data complete
  - Ensure all scenario JSON files load and validate against ArenaScenario schema, ask the user if questions arise.

- [x] 6. Add persona to SessionContext and update frontend API client
  - [x] 6.1 Add `persona` field to `SessionState` and `setPersona` to `SessionContextValue` in `frontend/context/SessionContext.tsx`
    - Add `Persona` type: `"sales" | "founder" | null`
    - Add `persona: Persona` to `SessionState` (default `null`)
    - Add `setPersona` callback that updates state and `sessionStorage`
    - Add `STORAGE_KEY_PERSONA = "junto_persona"` constant
    - Restore persona from `sessionStorage` on mount
    - Clear persona on `logout`
    - Local mode: persona defaults to `"sales"` unless overridden
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 6.2 Update `fetchScenarios` in `frontend/lib/api.ts` to accept optional `persona` parameter
    - Add `persona?: string` parameter
    - Pass as `persona` query param to backend
    - Add optional `tags?: string[] | null` to `ScenarioSummary` interface
    - _Requirements: 3.1, 3.2_

  - [x] 6.3 Write unit tests for SessionContext persona behavior
    - Test: persona storage, setPersona, logout clears persona, default behavior, sessionStorage persistence
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 7. Create Founders Landing Page
  - [x] 7.1 Create `frontend/app/founders/page.tsx` as a server component
    - Export `metadata` with founder-focused SEO (title, description, Open Graph tags, canonical URL `/founders`)
    - `isLocalMode` check → redirect to `/arena`
    - Hero section with headline/subheadline focused on pitch rehearsal and term sheet negotiation
    - Value proposition cards: pitch simulation, term sheet negotiation practice, investor objection handling
    - Scenario showcase cards: startup pitch, co-founder equity split, term sheet negotiation, M&A buyout
    - Reuse `WaitlistForm` component
    - CTA linking to Arena
    - Follow same responsive layout patterns as `/` and `/open-source` pages
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [x] 7.2 Create `FoundersPersonaSetter` client component wrapper to set `persona="founder"` in SessionContext on mount
    - Wrap the founders page content or render as a child component
    - _Requirements: 1.1_

  - [x] 7.3 Add `SalesPersonaSetter` client component to the existing `/` page (`frontend/app/page.tsx`) to set `persona="sales"` on mount
    - Minimal change — add a client component wrapper that calls `setPersona("sales")`
    - _Requirements: 1.2_

  - [x] 7.4 Write unit tests for Founders Landing Page
    - Test: renders hero, value props, scenario cards, WaitlistForm, CTA, SEO metadata
    - Test: SalesPersonaSetter sets persona on mount
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 8. Implement PersonaToggle and update Arena page
  - [x] 8.1 Create `PersonaToggle` component at `frontend/components/arena/PersonaToggle.tsx`
    - Two-option segmented control: "Sales" | "Founders"
    - Props: `persona`, `onPersonaChange`
    - Styled to match Arena UI (gray-900 background, brand-blue active state)
    - _Requirements: 8.1_

  - [x] 8.2 Update Arena page (`frontend/app/(protected)/arena/page.tsx`) to integrate persona
    - Import and render `PersonaToggle` above `ScenarioSelector`
    - Read `persona` from `useSession()`, default to `"sales"` if null
    - Pass `persona` to `fetchScenarios` call
    - On persona change: update session context via `setPersona`, clear selected scenario and scenario detail, re-fetch scenarios
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 8.3 Write unit tests for PersonaToggle and Arena persona integration
    - Test: PersonaToggle renders both options, fires onPersonaChange
    - Test: Arena page shows persona toggle, switching clears selected scenario
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 9. Implement Builder template system
  - [x] 9.1 Add persona-specific builder templates to the Builder page (`frontend/app/(protected)/arena/builder/page.tsx`)
    - Define `BUILDER_TEMPLATES` constant with `founder` and `sales` template strings per design
    - Read `persona` from `useSession()`
    - Pre-fill the `BuilderChat` input with the appropriate template based on persona
    - Pass initial template as a prop or set initial input state in `BuilderChat`
    - No template when persona is `null`
    - Template is editable — just the initial value of the textarea, not auto-sent
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 9.2 Write unit tests for Builder template pre-fill
    - Test: correct template per persona, no template when null, template is editable
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [x] 10. Final checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend uses Python (pytest + Hypothesis), frontend uses TypeScript (Vitest + RTL)
