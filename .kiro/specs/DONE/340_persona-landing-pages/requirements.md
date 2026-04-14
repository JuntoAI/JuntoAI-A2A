# Requirements Document

## Introduction

Persona-based landing pages and scenario filtering for JuntoAI. This feature introduces a persona concept (Sales, Founder) that flows from dedicated landing pages through the session context into the Arena scenario selector and AI Builder. Each persona gets a tailored landing page, filtered scenario list, and pre-filled builder templates. The system also requires new founder-focused scenarios to fill the content gap (currently only 1 dedicated founder scenario exists vs. 6+ sales scenarios).

## Glossary

- **Persona**: A user archetype that determines landing page content, scenario ordering, and builder templates. Current values: `sales`, `founder`. Stored in the session context and persisted across navigation.
- **Landing_Page**: A public (unauthenticated) marketing page tailored to a specific Persona. Examples: `/` for sales, `/founders` for founders.
- **Arena**: The authenticated scenario selection and simulation control panel at `/arena`.
- **Scenario_Selector**: The dropdown component in the Arena that lists available scenarios grouped by category.
- **Builder**: The AI-guided scenario creation tool at `/arena/builder`.
- **Builder_Template**: A pre-filled starter message injected into the Builder chat based on the active Persona.
- **Session_Context**: The React context (`SessionProvider`) that stores authenticated user state including email, token balance, tier, and now persona.
- **Scenario_Category**: The `category` field on `ArenaScenario` used for grouping in the Scenario_Selector. Current values: "Corporate", "Sales", "General", "Community".
- **Scenario_Tag**: A new optional metadata field on scenarios that enables persona-based filtering without changing the existing category system. A scenario can have multiple tags (e.g., `["founder", "sales"]`).

## Requirements

### Requirement 1: Persona Storage in Session Context

**User Story:** As a user arriving from a persona-specific landing page, I want my persona preference to persist across navigation, so that the Arena and Builder are tailored to my role without re-selecting it.

#### Acceptance Criteria

1. WHEN a user navigates to the `/founders` Landing_Page, THE Session_Context SHALL store `"founder"` as the active Persona before the user authenticates.
2. WHEN a user navigates to the `/` Landing_Page, THE Session_Context SHALL store `"sales"` as the active Persona.
3. WHEN a user authenticates via the waitlist form on any Landing_Page, THE Session_Context SHALL preserve the Persona value that was set before authentication.
4. WHEN a user has no Persona set and navigates directly to the Arena, THE Session_Context SHALL default the Persona to `"sales"`.
5. THE Session_Context SHALL expose the active Persona value to all child components via the existing `useSession` hook.
6. WHEN the user logs out, THE Session_Context SHALL clear the stored Persona value.

### Requirement 2: Founders Landing Page

**User Story:** As a founder or investor, I want a dedicated landing page that speaks to my use case (pitch rehearsal, term sheet negotiation), so that I immediately understand JuntoAI's value for fundraising scenarios.

#### Acceptance Criteria

1. THE Founders Landing_Page SHALL be accessible at the `/founders` URL path.
2. THE Founders Landing_Page SHALL display a hero section with a headline and subheadline focused on pitch rehearsal and term sheet negotiation.
3. THE Founders Landing_Page SHALL display value proposition cards relevant to founders: pitch simulation, term sheet negotiation practice, and investor objection handling.
4. THE Founders Landing_Page SHALL display scenario showcase cards for founder-relevant scenarios only (startup pitch, co-founder equity split, term sheet negotiation, M&A buyout).
5. THE Founders Landing_Page SHALL include a waitlist email capture form identical in functionality to the existing WaitlistForm component.
6. THE Founders Landing_Page SHALL include a call-to-action linking to the Arena.
7. THE Founders Landing_Page SHALL follow the same responsive layout patterns as the existing `/` and `/open-source` Landing_Pages.
8. THE Founders Landing_Page SHALL include appropriate SEO metadata (title, description, Open Graph tags, canonical URL).
9. WHILE the application is running in local mode, THE Founders Landing_Page SHALL redirect to `/arena` with the Persona set to `"founder"`.

### Requirement 3: Persona-Based Scenario Filtering in Arena

**User Story:** As a sales professional, I want to see sales scenarios prominently and not be overwhelmed by founder scenarios, so that I can quickly find relevant simulations. As a founder, I want to see only founder-relevant scenarios and the self-build option, so that I am not distracted by sales-specific content.

#### Acceptance Criteria

1. WHEN the active Persona is `"sales"`, THE Scenario_Selector SHALL display sales-tagged scenarios first, followed by general/fun scenarios, and SHALL exclude founder-only scenarios.
2. WHEN the active Persona is `"founder"`, THE Scenario_Selector SHALL display founder-tagged scenarios first, followed by the "Build Your Own Scenario" option, and SHALL exclude sales-only scenarios.
3. WHEN the active Persona is `"sales"`, THE Scenario_Selector SHALL include the "Build Your Own Scenario" option.
4. THE Scenario_Selector SHALL continue to group displayed scenarios by Scenario_Category within each persona-filtered view.
5. WHEN a scenario has tags matching multiple personas (e.g., `["founder", "sales"]`), THE Scenario_Selector SHALL include that scenario for both persona views.
6. IF a scenario has no Scenario_Tags, THEN THE Scenario_Selector SHALL treat the scenario as visible to all personas.

### Requirement 4: Scenario Tagging System

**User Story:** As a developer, I want to tag scenarios with persona metadata, so that the frontend can filter scenarios by persona without changing the existing category-based grouping.

#### Acceptance Criteria

1. THE ArenaScenario model SHALL support an optional `tags` field containing a list of string values.
2. WHEN a scenario JSON file omits the `tags` field, THE ScenarioRegistry SHALL treat the scenario as having no persona restrictions (visible to all personas).
3. THE ScenarioRegistry `list_scenarios` endpoint SHALL accept an optional `persona` query parameter.
4. WHEN the `persona` parameter is provided, THE ScenarioRegistry SHALL return scenarios that either have a matching tag or have no tags defined.
5. WHEN the `persona` parameter is not provided, THE ScenarioRegistry SHALL return all scenarios (backward-compatible behavior).
6. THE ScenarioRegistry SHALL preserve the existing sort order (category alphabetical with "General" last, then difficulty, then name) within the filtered results.

### Requirement 5: Persona-Specific Builder Templates

**User Story:** As a founder entering the AI Builder, I want a pre-filled template that matches my use case (pitch simulation with LinkedIn profiles and pitch deck links), so that I can quickly create a relevant scenario without starting from scratch.

#### Acceptance Criteria

1. WHEN the active Persona is `"founder"` and the user opens the Builder, THE Builder SHALL display a pre-filled starter message template for founder scenarios.
2. THE founder Builder_Template SHALL include placeholders for: the user's name, LinkedIn URL, pitch deck link, target investor name, investor LinkedIn URL, VC firm name, VC firm link, and a confidence level target.
3. WHEN the active Persona is `"sales"` and the user opens the Builder, THE Builder SHALL display a pre-filled starter message template for sales scenarios.
4. THE sales Builder_Template SHALL include placeholders for: the user's role, company name, product/service description, target buyer role, deal size, and key objections to practice.
5. WHEN the active Persona is not set, THE Builder SHALL display the existing empty chat interface with no pre-filled template.
6. THE Builder_Template SHALL be editable by the user before sending — the template is a suggestion, not a constraint.
7. THE Builder_Template SHALL be rendered as a pre-filled message in the chat input area, not as an automatically sent message.

### Requirement 6: New Founder Scenarios

**User Story:** As a founder, I want multiple relevant scenarios to practice with (beyond just startup-pitch), so that I can rehearse different fundraising and negotiation situations.

#### Acceptance Criteria

1. THE system SHALL include a "Term Sheet Negotiation" scenario where a founder negotiates specific term sheet clauses (liquidation preferences, anti-dilution, pro-rata rights) with a lead investor and a legal advisor regulator.
2. THE system SHALL include a "VC Due Diligence Defense" scenario where a founder defends their startup's metrics, market size, and competitive positioning against a skeptical VC partner conducting due diligence, with a financial analyst regulator verifying claims.
3. EACH new founder scenario SHALL follow the existing ArenaScenario JSON schema with minimum 2 agents and at least 1 negotiator.
4. EACH new founder scenario SHALL include at least 2 toggles with hidden context payloads that meaningfully alter negotiation dynamics.
5. THE new founder scenarios SHALL be tagged with `"founder"` in the Scenario_Tag field.
6. THE existing `startup_pitch` scenario SHALL be updated to include `"founder"` in its Scenario_Tag field.
7. THE existing `startup_equity_split` scenario SHALL be updated to include `"founder"` in its Scenario_Tag field.

### Requirement 7: Existing Scenario Tagging

**User Story:** As a developer, I want all existing scenarios tagged with appropriate persona metadata, so that persona filtering works correctly from day one.

#### Acceptance Criteria

1. THE scenarios `b2b_sales`, `saas_negotiation`, `renewal_churn_save`, `discovery_qualification`, and `enterprise_multi_stakeholder` SHALL be tagged with `"sales"`.
2. THE scenarios `startup_pitch`, `startup_equity_split`, and `ma_buyout` SHALL be tagged with `"founder"`.
3. THE scenarios `talent_war` and `freelance_gig` SHALL be tagged with both `"sales"` and `"founder"` since they are relevant to both personas.
4. THE scenarios `family_curfew`, `easter_bunny_debate`, `landlord_lease_renewal`, and `urban_development` SHALL have no tags (visible to all personas as general/fun scenarios).
5. THE scenario `plg_vs_slg` SHALL retain its existing `allowed_email_domains` restriction and SHALL have no persona tags.

### Requirement 8: Persona Switcher in Arena

**User Story:** As a user who arrived via one landing page but wants to explore scenarios for a different persona, I want to switch my active persona from within the Arena, so that I do not have to navigate back to a different landing page.

#### Acceptance Criteria

1. THE Arena page SHALL display a persona toggle or selector near the Scenario_Selector allowing the user to switch between `"sales"` and `"founder"` personas.
2. WHEN the user switches Persona in the Arena, THE Session_Context SHALL update the stored Persona value immediately.
3. WHEN the user switches Persona in the Arena, THE Scenario_Selector SHALL re-filter the displayed scenarios based on the new Persona.
4. WHEN the user switches Persona, THE Arena SHALL clear any currently selected scenario to prevent stale state.
