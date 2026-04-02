# Requirements Document — World-Class README & Contributor Hub

## Introduction

The JuntoAI A2A project needs a world-class open-source presence that converts GitHub visitors into active contributors. This spec covers four deliverables: (1) a comprehensive monorepo root `README.md` that explains the project, documents local setup via `docker compose up`, covers the Local Battle Arena feature, and showcases the scenario engine; (2) a GitHub CTA on the landing page that invites visitors to contribute; (3) a GitHub icon link in the footer; and (4) an agent connection guide that teaches developers how to plug their own AI agents into the system via scenario JSON configs, LiteLLM routing, and custom API keys.

The README is the single most important file in the repo. It must be visually compelling (badges, architecture diagram, clear sections), technically complete (setup instructions that work on first try), and community-oriented (contribution guidelines, agent leaderboard concept, link to discussions).

## Glossary

- **README**: The `README.md` file at the monorepo root that serves as the primary entry point for all GitHub visitors.
- **Landing_Page**: The Next.js page at `frontend/app/page.tsx` that renders the public-facing marketing page with headline, subheadline, waitlist form, and scenario banner.
- **Footer**: The `frontend/components/Footer.tsx` component rendered at the bottom of every page, containing copyright, legal links, and social media icons.
- **Scenario_Config**: A JSON file (e.g., `talent-war.scenario.json`) in `backend/app/scenarios/data/` that defines agents, toggles, negotiation parameters, and outcome receipt metadata.
- **Agent_Connection_Guide**: A dedicated section within the README (or linked document) that explains how developers create custom agents by authoring Scenario_Config files and configuring LLM providers.
- **Local_Battle_Arena**: The local development mode (from spec 080) where `docker compose up` launches the full stack with SQLite, LiteLLM, and auth bypass — zero GCP dependencies.
- **LiteLLM_Router**: The local-mode LLM routing layer that translates scenario `model_id` values to any provider (OpenAI, Anthropic, Ollama) via the LiteLLM library.
- **CTA**: Call-to-action — a visible UI element that directs users to perform a specific action (e.g., visit the GitHub repo).
- **GitHub_Org_URL**: `https://github.com/Juntoai` — the JuntoAI GitHub organization page.
- **Badge**: A small inline image in the README (via shields.io or similar) that displays project metadata such as license, build status, or tech stack.
- **Kiro**: The AI-powered IDE used as the primary development environment for building JuntoAI A2A, providing specs-driven workflows, steering files for project context, and automation hooks.
- **Steering_Files**: Markdown files in `.kiro/steering/` that provide Kiro with project-specific context (tech stack, styling, testing, deployment, product rules) so AI assistance is tuned to the project's conventions.
- **Specs_Directory**: The `.kiro/specs/` directory containing feature specifications that were planned and implemented through Kiro's requirements-first workflow.
- **Kiro_Hooks**: Automation files in `.kiro/hooks/` that Kiro triggers during development workflows (e.g., generating release notes when a spec is completed).

## Requirements

### Requirement 1: Monorepo Root README Structure and Content

**User Story:** As a GitHub visitor, I want a visually compelling and well-structured README at the monorepo root, so that I immediately understand what JuntoAI A2A is, why it matters, and how to get involved.

#### Acceptance Criteria

1. THE README SHALL contain the following top-level sections in order: project title with tagline, badges row, hero description, architecture overview, quick start guide, scenario engine explanation, agent connection guide, local battle arena setup, environment configuration reference, contributing guidelines, and license.
2. THE README SHALL include a badges row displaying at minimum: license type, Python version, Next.js version, Docker support indicator, and a "contributions welcome" badge.
3. THE README SHALL include a hero description paragraph that positions JuntoAI A2A as a config-driven scenario engine and universal protocol-level execution layer for professional negotiations — not a chatbot.
4. THE README SHALL include a Mermaid or ASCII architecture diagram showing the monorepo structure (backend, frontend, infra) and the data flow between components (scenario config → orchestrator → agents → SSE → Glass Box UI).
5. THE README SHALL use Markdown formatting that renders correctly on GitHub (headings, code blocks, tables, collapsible sections via `<details>` tags, and relative links to files within the repo).

### Requirement 2: Quick Start Guide in README

**User Story:** As a developer, I want a quick start section that gets me from clone to running the full stack in under 5 minutes, so that I experience the product before reading detailed docs.

#### Acceptance Criteria

1. THE README quick start section SHALL list prerequisites: Docker, Docker Compose, and at least one LLM API key (OpenAI, Anthropic, or Ollama).
2. THE README quick start section SHALL provide a numbered step-by-step guide covering: clone the repo, copy `.env.example` to `.env`, set an API key, run `docker compose up`, and open `http://localhost:3000` in a browser.
3. THE README quick start section SHALL include the exact shell commands for each step as fenced code blocks with the `bash` language identifier.
4. THE README quick start section SHALL mention that the default `RUN_MODE` is `local` and that no GCP credentials are required for local development.
5. IF a developer follows the quick start steps with a valid API key, THEN THE Local_Battle_Arena SHALL start successfully and display the Arena Selector in the browser.

### Requirement 3: Local Battle Arena Documentation in README

**User Story:** As a developer, I want the README to explain the Local Battle Arena architecture (SQLite, LiteLLM, auth bypass, RUN_MODE switching), so that I understand how local mode differs from cloud mode.

#### Acceptance Criteria

1. THE README SHALL include a dedicated "Local Battle Arena" section explaining that `RUN_MODE=local` replaces Firestore with SQLite, Vertex AI with LiteLLM, and bypasses the auth gate.
2. THE README Local Battle Arena section SHALL include a comparison table showing cloud-mode vs local-mode components (database, LLM router, auth, hosting).
3. THE README Local Battle Arena section SHALL document the `docker-compose.yml` services (backend on port 8000, frontend on port 3000) and the SQLite volume persistence.
4. THE README Local Battle Arena section SHALL explain that the same Scenario_Config JSON files work in both modes without modification.
5. THE README Local Battle Arena section SHALL document the model mapping system: how `LLM_PROVIDER`, `LLM_MODEL_OVERRIDE`, and `MODEL_MAP` environment variables control which LLM models are used locally.

### Requirement 4: Environment Configuration Reference in README

**User Story:** As a developer, I want a complete environment variable reference in the README, so that I can configure the system without reading source code.

#### Acceptance Criteria

1. THE README SHALL include an environment configuration section with a table listing every configurable variable from `.env.example`: variable name, required/optional status, default value, and description.
2. THE README environment configuration section SHALL group variables by category: Run Mode, LLM Provider, Database, and Frontend.
3. THE README environment configuration section SHALL include provider-specific examples showing how to configure OpenAI, Anthropic, and Ollama as the LLM provider.
4. THE README environment configuration section SHALL document the `LLM_MODEL_OVERRIDE` variable with an example showing how to force all agents to use a single model (e.g., `gpt-4o-mini` for cost savings during development).

### Requirement 5: Scenario Engine and Agent Connection Guide in README

**User Story:** As a developer who wants to connect my own AI agents, I want the README to explain the scenario JSON config system, so that I can create custom negotiation scenarios with my preferred LLM providers.

#### Acceptance Criteria

1. THE README SHALL include a "Connect Your Own Agents" section explaining that new scenarios are added by creating a JSON file in `backend/app/scenarios/data/` with zero code changes.
2. THE README agent connection section SHALL document the Scenario_Config JSON schema: top-level fields (`id`, `name`, `description`, `agents`, `toggles`, `negotiation_params`, `outcome_receipt`) with a description of each.
3. THE README agent connection section SHALL document the agent object schema: `role`, `name`, `type`, `persona_prompt`, `goals`, `budget`, `tone`, `output_fields`, `model_id`, and optional `fallback_model_id`.
4. THE README agent connection section SHALL include a minimal but complete example Scenario_Config JSON that a developer can copy, modify, and drop into the scenarios directory.
5. THE README agent connection section SHALL explain how `model_id` values in the scenario config are translated to local provider models via the model mapping layer, and how developers can override mappings via environment variables.
6. THE README agent connection section SHALL explain how to use LiteLLM for provider-agnostic routing, including how to bring custom API keys for any LiteLLM-supported provider.

### Requirement 6: Contributing Guidelines in README

**User Story:** As a potential contributor, I want clear contributing guidelines in the README, so that I know how to submit scenarios, report bugs, and propose features.

#### Acceptance Criteria

1. THE README SHALL include a "Contributing" section that welcomes contributions and links to the GitHub issues page.
2. THE README contributing section SHALL list the types of contributions accepted: new scenario configs, bug reports, feature proposals, documentation improvements, and agent strategy submissions.
3. THE README contributing section SHALL describe the branch strategy: fork the repo, create a `feature/*` branch, submit a pull request to `main`.
4. THE README contributing section SHALL mention that all scenario contributions are JSON-only (no code changes required) and link to the agent connection guide section.

### Requirement 7: Landing Page GitHub CTA

**User Story:** As a landing page visitor, I want a visible call-to-action inviting me to contribute on GitHub, so that I can discover the open-source project and get involved.

#### Acceptance Criteria

1. WHEN the Landing_Page renders, THE Landing_Page SHALL display a GitHub CTA section below the waitlist form.
2. THE GitHub CTA SHALL include a link to the GitHub_Org_URL (`https://github.com/Juntoai`) that opens in a new tab with `rel="noopener noreferrer"`.
3. THE GitHub CTA SHALL include a GitHub icon (from Lucide React or an inline SVG consistent with the existing icon style) alongside descriptive text inviting users to contribute.
4. THE GitHub CTA SHALL be styled using Tailwind CSS with the brand color palette, maintaining WCAG AA contrast ratios (minimum 4.5:1 for text).
5. THE GitHub CTA SHALL be responsive: readable and tappable on viewports from 320px to 1920px wide, following the mobile-first approach.
6. THE GitHub CTA link SHALL include an `aria-label` attribute describing the destination for screen reader accessibility.

### Requirement 8: Footer GitHub Icon Link

**User Story:** As a site visitor, I want a GitHub icon in the footer alongside the existing LinkedIn and X icons, so that I can quickly navigate to the JuntoAI GitHub organization from any page.

#### Acceptance Criteria

1. THE Footer SHALL include a GitHub icon link positioned in the social icons row alongside the existing LinkedIn and X (Twitter) icon links.
2. THE Footer GitHub link SHALL point to `https://github.com/Juntoai` and open in a new tab with `rel="noopener noreferrer"`.
3. THE Footer GitHub icon SHALL use an inline SVG with `className="h-4 w-4"` and `fill="currentColor"`, matching the size and rendering approach of the existing LinkedIn and X icons.
4. THE Footer GitHub link SHALL include `aria-label="GitHub"` for screen reader accessibility.
5. THE Footer GitHub link SHALL use the same hover color transition as the existing social links (`text-gray-400` default with a hover state transition).
6. WHEN the Footer renders on any page, THE GitHub icon SHALL be visible without horizontal scrolling on viewports 320px wide and above.

### Requirement 9: Agent Leaderboard Teaser in README

**User Story:** As a developer, I want the README to tease the concept of an agent leaderboard showing which AI agents run the best negotiations, so that I am motivated to submit my own agent configurations and compete.

#### Acceptance Criteria

1. THE README SHALL include a "Leaderboard" or "Best Agents" section that explains the concept: scenarios are run with different agent configurations and the results are compared on negotiation quality metrics.
2. THE README leaderboard section SHALL describe the evaluation dimensions: deal outcome (final terms vs targets), negotiation efficiency (turns to agreement), humanization quality (natural language, strategic reasoning), and regulator compliance (warnings received).
3. THE README leaderboard section SHALL clearly mark the leaderboard as a "Coming Soon" or "Roadmap" feature if it is not yet implemented, to set accurate expectations.
4. THE README leaderboard section SHALL invite developers to submit their agent configurations (scenario JSON files with custom persona prompts and model choices) for future leaderboard inclusion.

### Requirement 10: README Visual Quality and Formatting

**User Story:** As a GitHub visitor, I want the README to be visually polished and scannable, so that I can quickly find the information I need without reading the entire document.

#### Acceptance Criteria

1. THE README SHALL use collapsible `<details>` sections for lengthy content blocks (full scenario JSON examples, complete environment variable tables) to keep the main flow scannable.
2. THE README SHALL use emoji or Unicode symbols as section markers (e.g., 🚀 for Quick Start, 🏗️ for Architecture, 🤖 for Agent Connection) to improve visual scanning.
3. THE README SHALL include a table of contents at the top with anchor links to each major section.
4. THE README SHALL render correctly on GitHub's Markdown renderer, GitHub Mobile app, and in VS Code's Markdown preview without broken formatting.
5. THE README total length SHALL remain under 800 lines to avoid overwhelming readers, using collapsible sections and links to separate docs for detailed content.

### Requirement 11: Kiro Development Attribution in README

**User Story:** As a GitHub visitor, I want to see that JuntoAI A2A was built using Kiro (the AI-powered IDE), so that I understand the development tooling behind the project and can evaluate Kiro as a development environment.

#### Acceptance Criteria

1. THE README SHALL include a visible callout (badge, banner, or dedicated callout block) in the top portion of the document (above the fold, within the first 30 lines) stating that JuntoAI A2A was primarily developed using Kiro.
2. THE README Kiro callout SHALL describe Kiro as the AI-powered IDE that served as the primary development environment for building the project.
3. THE README Kiro callout SHALL NOT be hidden inside a collapsible `<details>` section, a footnote, or a comment — the attribution SHALL be immediately visible when the README renders on GitHub.
4. THE README Kiro callout SHALL include a link to the official Kiro website or documentation so visitors can learn more about the tool.
5. THE README badges row SHALL include a "Built with Kiro" badge alongside the existing license, Python, Next.js, and Docker badges.

### Requirement 12: Developing with Kiro Section in README

**User Story:** As a developer who wants to contribute to JuntoAI A2A, I want a "Developing with Kiro" section in the README, so that I understand how to use Kiro's features (specs, steering files, hooks) to get AI-assisted development that is already tuned to the project's conventions.

#### Acceptance Criteria

1. THE README SHALL include a "Developing with Kiro" section that explains how to open the monorepo in Kiro and begin contributing with full AI context.
2. THE README Developing with Kiro section SHALL document the `.kiro/` directory structure, listing the three subdirectories (`steering/`, `specs/`, `hooks/`) with a one-line description of each subdirectory's purpose.
3. THE README Developing with Kiro section SHALL explain that the steering files in `.kiro/steering/` provide project context to Kiro covering: technology stack (`tech.md`), styling conventions (`styling.md`), testing guidelines (`testing.md`), deployment rules (`deployment.md`), and product context (`product.md`).
4. THE README Developing with Kiro section SHALL explain that Kiro reads the steering files automatically, so contributors receive AI assistance that is already tuned to the project's conventions, tech stack, and coding standards without manual configuration.
5. THE README Developing with Kiro section SHALL explain how the specs workflow in `.kiro/specs/` was used to plan and implement features, describing that each numbered directory (e.g., `080_a2a-local-battle-arena`, `130_ai-scenario-builder`) represents a feature that was designed and built through Kiro's requirements-first spec process.
6. THE README Developing with Kiro section SHALL explain that the `.kiro/hooks/` directory contains automation hooks (e.g., `spec-release-notes.kiro.hook`) that Kiro triggers during development workflows.
7. THE README Developing with Kiro section SHALL provide guidance on how contributors can leverage Kiro's features when working on the project: using specs to plan new features, relying on steering files for consistent AI suggestions, and using hooks for automated workflows.
8. THE README Developing with Kiro section SHALL clarify that Kiro is recommended but not required — contributors can use any IDE, but Kiro provides the richest AI-assisted experience for this repo due to the pre-configured context files.
