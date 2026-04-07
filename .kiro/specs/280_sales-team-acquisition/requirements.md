# Requirements Document

## Introduction

Sales team acquisition package for the JuntoAI A2A negotiation engine. The thesis: sales calls are structured negotiations — exactly what the engine was built for. This spec covers three deliverables: (1) four polished, drop-in sales scenario JSON files targeting the highest-value B2B call types, (2) a public sales landing page at `/sales` with sales-team-specific messaging and CTAs, and (3) a detailed 60-second demo video storyline/shot list for LinkedIn distribution. No engine code changes required — scenarios use the existing `ArenaScenario` schema, and the landing page is a standalone Next.js route.

## Glossary

- **Scenario_JSON**: A `.scenario.json` file in `backend/app/scenarios/data/` conforming to the `ArenaScenario` Pydantic model, loaded at runtime by the scenario registry
- **ArenaScenario_Schema**: The Pydantic V2 model defined in `backend/app/scenarios/models.py` including `AgentDefinition`, `ToggleDefinition`, `NegotiationParams`, `OutcomeReceipt`, and `EvaluatorConfig`
- **Sales_Landing_Page**: A public (unauthenticated) Next.js page at route `/sales` targeting sales professionals
- **Glass_Box_View**: The live split-screen simulation UI showing agent inner thoughts, chat messages, and metrics dashboard
- **Toggle**: A hidden context payload injected into a specific agent at runtime, altering negotiation behavior without the other agents' knowledge
- **Demo_Storyline**: A markdown document containing a shot-by-shot script and visual direction for a 60-second video
- **CTA**: Call-to-action UI element directing users to try sales scenarios or sign up
- **BATNA**: Best Alternative To a Negotiated Agreement — a negotiation concept representing a party's fallback option
- **Scenario_Registry**: The backend module that discovers and loads `.scenario.json` files from the scenarios data directory

## Requirements

### Requirement 1: SaaS Contract Negotiation Scenario

**User Story:** As a sales professional, I want a realistic SaaS contract negotiation scenario, so that I can rehearse high-stakes pricing conversations with AI agents that behave like real enterprise buyers and procurement gatekeepers.

#### Acceptance Criteria

1. THE Scenario_JSON SHALL conform to the ArenaScenario_Schema with valid `id`, `name`, `description`, `difficulty`, `agents`, `toggles`, `negotiation_params`, and `outcome_receipt` fields
2. THE Scenario_JSON SHALL define exactly three agents: a Seller agent (type `negotiator`), a Buyer agent (type `negotiator`), and a Procurement agent (type `regulator`)
3. WHEN loaded by the Scenario_Registry, THE Scenario_JSON SHALL pass Pydantic V2 validation without errors
4. THE Seller agent SHALL have a `persona_prompt` that establishes a senior Account Executive persona with specific product knowledge, pricing authority limits, and concession strategy guidelines
5. THE Buyer agent SHALL have a `persona_prompt` that establishes a VP-level buyer persona with specific pain points, budget constraints, competing vendor context, and data-driven negotiation behavior
6. THE Procurement agent SHALL have a `persona_prompt` that establishes a compliance-focused gatekeeper with specific SLA requirements, security certification demands, and contractual standards to enforce
7. THE Scenario_JSON SHALL define at least two toggles: one injecting quota pressure into the Seller agent and one injecting a competing vendor offer into the Buyer agent
8. EACH toggle SHALL include a `hidden_context_payload` with specific behavioral instructions that do not instruct the agent to reveal the hidden information directly
9. THE `negotiation_params` SHALL specify a `turn_order` that alternates negotiators with the regulator, an `agreement_threshold` appropriate for the price range, and `max_turns` between 10 and 14
10. THE Scenario_JSON SHALL be saved as a `.scenario.json` file in `backend/app/scenarios/data/` and be discoverable by the Scenario_Registry without code changes

### Requirement 2: Renewal / Churn Save Scenario

**User Story:** As a sales professional, I want a renewal negotiation scenario where the customer is threatening to cancel, so that I can practice retention conversations and objection handling against a realistic churn risk.

#### Acceptance Criteria

1. THE Scenario_JSON SHALL conform to the ArenaScenario_Schema and pass Pydantic V2 validation without errors
2. THE Scenario_JSON SHALL define exactly three agents: a Customer Success Manager agent (type `negotiator`), a Customer agent (type `negotiator`), and a Finance Compliance agent (type `regulator`)
3. THE Customer agent SHALL have a `persona_prompt` establishing a dissatisfied customer persona with specific grievances (e.g., underused features, poor support response times, price increases) and an active competing vendor evaluation
4. THE Customer Success Manager agent SHALL have a `persona_prompt` establishing a retention specialist persona with specific discount authority, product roadmap knowledge, and escalation paths
5. THE Finance Compliance agent SHALL have a `persona_prompt` that enforces discount ceiling policies, contract modification rules, and flags revenue recognition risks from non-standard terms
6. THE Scenario_JSON SHALL define at least two toggles: one revealing that the Customer has already signed a competitor contract (strengthening the Customer BATNA), and one revealing internal churn risk data to the Customer Success Manager
7. THE `negotiation_params` SHALL specify `max_turns` between 10 and 14 and an `agreement_threshold` appropriate for the renewal price range
8. THE Scenario_JSON SHALL be saved as a `.scenario.json` file in `backend/app/scenarios/data/` and be discoverable by the Scenario_Registry without code changes

### Requirement 3: Enterprise Multi-Stakeholder Scenario

**User Story:** As a sales professional, I want a multi-stakeholder enterprise scenario where a technical champion supports the deal but procurement is blocking on price, so that I can practice navigating complex buying committees.

#### Acceptance Criteria

1. THE Scenario_JSON SHALL conform to the ArenaScenario_Schema and pass Pydantic V2 validation without errors
2. THE Scenario_JSON SHALL define at least four agents: a Sales Director agent (type `negotiator`), a CTO/Champion agent (type `negotiator`), a Procurement Director agent (type `negotiator`), and a Legal/Compliance agent (type `regulator`)
3. THE CTO/Champion agent SHALL have a `persona_prompt` establishing a technical advocate who supports the product but must justify the spend to internal stakeholders, with specific technical requirements and integration concerns
4. THE Procurement Director agent SHALL have a `persona_prompt` establishing a cost-focused blocker persona with specific budget reduction targets, preferred vendor list policies, and multi-year commitment aversion
5. THE Sales Director agent SHALL have a `persona_prompt` establishing a strategic seller who must navigate the champion-blocker dynamic, with authority to offer proof-of-concept periods, phased rollouts, and executive sponsorship
6. THE Legal/Compliance agent SHALL have a `persona_prompt` that enforces data processing agreement requirements, liability caps, IP ownership clauses, and vendor risk assessment standards
7. THE Scenario_JSON SHALL define at least two toggles: one revealing that the CTO has executive air cover (CEO pre-approved the budget), and one revealing that Procurement has a mandate to cut vendor spend by 20%
8. THE `negotiation_params` SHALL specify a `turn_order` that includes all four agents, `max_turns` between 12 and 16, and an `agreement_threshold` appropriate for the enterprise deal size
9. THE Scenario_JSON SHALL be saved as a `.scenario.json` file in `backend/app/scenarios/data/` and be discoverable by the Scenario_Registry without code changes

### Requirement 4: Discovery / Qualification Call Scenario

**User Story:** As a sales professional, I want a discovery call scenario where I'm qualifying a prospect for the first time, so that I can practice asking the right questions and identifying deal-qualifying signals.

#### Acceptance Criteria

1. THE Scenario_JSON SHALL conform to the ArenaScenario_Schema and pass Pydantic V2 validation without errors
2. THE Scenario_JSON SHALL define exactly three agents: a Sales Development Rep agent (type `negotiator`), a Prospect agent (type `negotiator`), and a Sales Manager/Coach agent (type `regulator`)
3. THE Prospect agent SHALL have a `persona_prompt` establishing a guarded executive persona who does not volunteer information freely, has a real but unstated pain point, and is evaluating multiple solutions without revealing the full picture
4. THE Sales Development Rep agent SHALL have a `persona_prompt` establishing a discovery-focused seller who must uncover budget, authority, need, and timeline (BANT) through strategic questioning rather than pitching
5. THE Sales Manager/Coach agent SHALL have a `persona_prompt` that evaluates discovery quality: flags premature pitching, rewards open-ended questions, warns when the rep talks more than 40% of the exchange, and tracks qualification criteria coverage
6. THE Scenario_JSON SHALL define at least two toggles: one revealing that the Prospect has an urgent internal deadline driving the evaluation, and one revealing that the Prospect's current vendor just raised prices 40%
7. THE `negotiation_params` SHALL specify `max_turns` between 10 and 14, and the `value_format` and `value_label` SHALL be configured appropriately for a qualification score rather than a price negotiation
8. THE Scenario_JSON SHALL be saved as a `.scenario.json` file in `backend/app/scenarios/data/` and be discoverable by the Scenario_Registry without code changes

### Requirement 5: Sales Landing Page

**User Story:** As a sales professional visiting the JuntoAI website, I want a dedicated landing page that speaks to my use case, so that I immediately understand how AI deal rehearsal helps me close more deals.

#### Acceptance Criteria

1. THE Sales_Landing_Page SHALL be accessible at the `/sales` route as a public page without authentication
2. THE Sales_Landing_Page SHALL include a hero section with a headline and subheadline using sales-specific language (e.g., "Rehearse your next deal", "AI deal rehearsal", referencing close rates and objection handling)
3. THE Sales_Landing_Page SHALL include a value proposition section with at least three cards highlighting sales-specific benefits (e.g., objection handling practice, deal rehearsal with hidden variables, multi-stakeholder navigation)
4. THE Sales_Landing_Page SHALL include a CTA section that links users to try the sales scenarios in the Arena (route: `/arena`)
5. THE Sales_Landing_Page SHALL include a section showcasing the four sales scenario types available (SaaS negotiation, renewal/churn save, enterprise multi-stakeholder, discovery call)
6. THE Sales_Landing_Page SHALL be responsive across viewport widths from 320px to 1920px
7. THE Sales_Landing_Page SHALL use the existing brand color palette (Primary Blue `#007BFF`, Secondary Green `#00E676`, Dark Charcoal `#1C1C1E`, Off-White `#FAFAFA`), Tailwind CSS utility classes, and Lucide React icons consistent with the existing landing page
8. THE Sales_Landing_Page SHALL include appropriate `<title>` and Open Graph metadata for SEO and social sharing, with sales-specific descriptions
9. WHEN a user is in local mode, THE Sales_Landing_Page SHALL still be accessible at `/sales` (no redirect behavior like the main landing page)
10. THE Sales_Landing_Page SHALL include a waitlist/signup form or link to the main waitlist for lead capture

### Requirement 6: Demo Video Storyline

**User Story:** As a marketing team member, I want a detailed 60-second demo video script with shot-by-shot direction, so that a video editor can produce a compelling LinkedIn video showing a sales simulation in the Glass Box view.

#### Acceptance Criteria

1. THE Demo_Storyline SHALL be a markdown document saved in the repository
2. THE Demo_Storyline SHALL cover exactly 60 seconds of content, with timestamps for each shot/scene
3. THE Demo_Storyline SHALL include at least five distinct shots/scenes covering: hook/opening, scenario setup, live negotiation with visible agent reasoning, toggle flip showing outcome change, and closing CTA
4. THE Demo_Storyline SHALL specify for each shot: timestamp range, visual description (what's on screen), text overlay or caption content, and any transition effects
5. THE Demo_Storyline SHALL use one of the four sales scenarios as the featured simulation, showing the Glass_Box_View with agent inner thoughts and chat messages
6. THE Demo_Storyline SHALL include a scene demonstrating a toggle activation and its visible impact on agent behavior, reinforcing the "one toggle changes everything" value proposition
7. THE Demo_Storyline SHALL end with a clear CTA directing viewers to the `/sales` landing page or the GitHub repository
8. THE Demo_Storyline SHALL be written in language that a video editor with no product knowledge can follow, with explicit visual direction rather than abstract descriptions
