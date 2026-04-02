# Implementation Plan: World-Class README & Contributor Hub

## Overview

Three deliverables: (1) a monorepo root `README.md` (~600–800 lines), (2) a GitHub CTA section in `frontend/app/page.tsx`, and (3) a GitHub icon in `frontend/components/Footer.tsx`. No new backend code, no new components, no new data models. Property tests validate README structure (Python/pytest) and frontend accessibility (Vitest/fast-check).

## Tasks

- [x] 1. Create the monorepo root README.md — top section and architecture
  - [x] 1.1 Create `README.md` at monorepo root with title, badges row (license, Python, Next.js, Docker, contributions welcome, Built with Kiro), Kiro callout block (within first 30 lines), hero description paragraph, and table of contents with anchor links
    - Kiro callout must NOT be inside a `<details>` tag, footnote, or comment — immediately visible
    - Badges via shields.io or similar inline images
    - Emoji/Unicode markers on all `##` section headings
    - _Requirements: 1.1, 1.2, 1.3, 10.2, 10.3, 11.1, 11.2, 11.3, 11.4, 11.5_
  - [x] 1.2 Add architecture overview section with a Mermaid diagram showing monorepo structure and data flow (scenario config → orchestrator → agents → SSE → Glass Box UI), plus a text fallback above the diagram
    - _Requirements: 1.4, 1.5_

- [x] 2. Create the README.md — Quick Start and Local Battle Arena sections
  - [x] 2.1 Add Quick Start section with prerequisites (Docker, Docker Compose, LLM API key), numbered step-by-step guide (clone, copy `.env.example`, set key, `docker compose up`, open localhost:3000), all commands in ` ```bash ` fenced code blocks, mention `RUN_MODE=local` default and no GCP credentials needed
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.2 Add Local Battle Arena section explaining `RUN_MODE=local` swaps (Firestore→SQLite, Vertex AI→LiteLLM, auth bypass), comparison table (cloud vs local components), docker-compose services (backend:8000, frontend:3000, SQLite volume), same scenario configs in both modes, model mapping system (`LLM_PROVIDER`, `LLM_MODEL_OVERRIDE`, `MODEL_MAP`)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Create the README.md — Environment Config, Scenario Engine, and Agent Connection Guide
  - [x] 3.1 Add Environment Configuration section with a table of all `.env.example` variables (name, required/optional, default, description), grouped by category (Run Mode, LLM Provider, Database, Frontend), provider-specific examples (OpenAI, Anthropic, Ollama), `LLM_MODEL_OVERRIDE` example. Use `<details>` for the full table
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 3.2 Add "Connect Your Own Agents" section documenting: zero-code scenario addition (drop JSON in `backend/app/scenarios/data/`), top-level Scenario_Config schema fields (`id`, `name`, `description`, `agents`, `toggles`, `negotiation_params`, `outcome_receipt`), agent object schema fields (`role`, `name`, `type`, `persona_prompt`, `goals`, `budget`, `tone`, `output_fields`, `model_id`, `fallback_model_id`), a complete copyable example scenario JSON inside a `<details>` block, model_id mapping explanation, LiteLLM provider-agnostic routing with custom API keys
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 4. Create the README.md — Leaderboard, Developing with Kiro, Contributing, License
  - [x] 4.1 Add Leaderboard section marked "Coming Soon" with evaluation dimensions (deal outcome, negotiation efficiency, humanization quality, regulator compliance), invitation to submit agent configs
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - [x] 4.2 Add "Developing with Kiro" section explaining: open monorepo in Kiro, `.kiro/` directory structure (`steering/`, `specs/`, `hooks/` with one-line descriptions), steering files list (`tech.md`, `styling.md`, `testing.md`, `deployment.md`, `product.md`) and that Kiro reads them automatically, specs workflow (numbered directories = features built via requirements-first), hooks directory (`spec-release-notes.kiro.hook`), contributor guidance (use specs for new features, steering for consistent AI, hooks for automation), Kiro recommended but not required
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_
  - [x] 4.3 Add Contributing section welcoming contributions, linking to GitHub issues, listing contribution types (scenario configs, bug reports, feature proposals, docs, agent strategies), branch strategy (fork → `feature/*` → PR to `main`), note that scenario contributions are JSON-only linking to agent connection guide. Add License section (MIT or as appropriate)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [x] 4.4 Verify README is under 800 lines total, all `##` headings have emoji markers, TOC anchor links resolve, collapsible `<details>` used for lengthy blocks, renders correctly as GitHub Markdown
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 5. Checkpoint — README complete
  - Ensure README renders correctly in VS Code Markdown preview, all sections present in correct order, line count under 800. Ask the user if questions arise.

- [x] 6. Add GitHub CTA to landing page and GitHub icon to footer
  - [x] 6.1 Modify `frontend/app/page.tsx` to add a GitHub CTA `<section>` after the WaitlistForm div with: link to `https://github.com/Juntoai`, `target="_blank"`, `rel="noopener noreferrer"`, `aria-label="Contribute to JuntoAI on GitHub"`, inline GitHub SVG icon, descriptive text, Tailwind styling with brand colors (`text-brand-charcoal`, `hover:text-brand-blue`), responsive from 320px up
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [x] 6.2 Modify `frontend/components/Footer.tsx` to add a GitHub icon `<a>` between the LinkedIn and X icon links with: `href="https://github.com/Juntoai"`, `target="_blank"`, `rel="noopener noreferrer"`, `aria-label="GitHub"`, inline SVG (`className="h-4 w-4"`, `fill="currentColor"`, `viewBox="0 0 24 24"`), `text-gray-400 hover:text-brand-charcoal transition-colors`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 7. Write README property tests (Python — pytest)
  - [x] 7.1 Write property test for README section ordering
    - **Property 1: README section ordering**
    - Parse `##` headings from `README.md`, verify required order: Quick Start < Local Battle Arena < Environment Configuration < Connect Your Own Agents < Leaderboard < Developing with Kiro < Contributing < License
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 1.1**
  - [x] 7.2 Write property test for quick start bash code blocks
    - **Property 2: Quick start code blocks use bash language identifier**
    - Extract all fenced code blocks from the Quick Start section, verify each has `bash` language identifier
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 2.3**
  - [x] 7.3 Write property test for scenario schema documentation completeness
    - **Property 3: Scenario schema documentation completeness**
    - For each required ArenaScenario field (`id`, `name`, `description`, `agents`, `toggles`, `negotiation_params`, `outcome_receipt`), verify the Connect Your Own Agents section mentions it
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 5.2**
  - [x] 7.4 Write property test for agent schema documentation completeness
    - **Property 4: Agent schema documentation completeness**
    - For each required AgentDefinition field (`role`, `name`, `type`, `persona_prompt`, `goals`, `budget`, `tone`, `output_fields`, `model_id`, `fallback_model_id`), verify the agent connection section mentions it
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 5.3**
  - [x] 7.5 Write property test for example scenario JSON validation
    - **Property 5: Example scenario JSON validates against schema**
    - Extract JSON code blocks from Connect Your Own Agents section, parse with ArenaScenario Pydantic model, assert no validation errors
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 5.4**
  - [x] 7.6 Write property test for section heading emoji markers
    - **Property 8: README section headings contain emoji markers**
    - For each `##` heading in README, verify it contains at least one emoji/Unicode symbol
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 10.2**
  - [x] 7.7 Write property test for TOC link resolution
    - **Property 9: Table of contents links resolve to actual headings**
    - For each anchor link in the TOC section, verify a corresponding heading exists whose GitHub-generated anchor matches
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 10.3**
  - [x] 7.8 Write property test for README line count
    - **Property 10: README line count under 800**
    - Count total lines in `README.md`, assert strictly less than 800
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 10.5**
  - [x] 7.9 Write property test for Kiro directory documentation completeness
    - **Property 11: Kiro directory documentation completeness**
    - For each required `.kiro/` element (`steering/`, `specs/`, `hooks/`, `tech.md`, `styling.md`, `testing.md`, `deployment.md`, `product.md`), verify the Developing with Kiro section mentions it
    - Test file: `backend/tests/unit/test_readme_properties.py`
    - **Validates: Requirements 12.2, 12.3**

- [x] 8. Write frontend property and unit tests (Vitest + fast-check)
  - [x] 8.1 Write property test for GitHub CTA link accessibility
    - **Property 6: GitHub CTA link has accessibility attributes**
    - Render the Home page component, verify the GitHub CTA link has non-empty `aria-label`, `href="https://github.com/Juntoai"`, `target="_blank"`, `rel="noopener noreferrer"`
    - Test file: `frontend/__tests__/components/GitHubCTA.test.tsx`
    - **Validates: Requirements 7.2, 7.6**
  - [x] 8.2 Write property test for Footer GitHub link attributes
    - **Property 7: Footer GitHub link has correct attributes**
    - Render Footer component, verify GitHub link has `aria-label="GitHub"`, `href="https://github.com/Juntoai"`, `target="_blank"`, `rel="noopener noreferrer"`, contains SVG with `h-4 w-4` class and `fill="currentColor"`
    - Test file: `frontend/__tests__/components/Footer.test.tsx`
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
  - [x] 8.3 Write unit tests for Footer social icon order and CTA placement
    - Verify Footer renders three social icons (LinkedIn, GitHub, X) in correct order
    - Verify GitHub CTA appears after WaitlistForm in DOM
    - Verify CTA text contains "GitHub" or "Contribute"
    - Test files: `frontend/__tests__/components/Footer.test.tsx`, `frontend/__tests__/components/GitHubCTA.test.tsx`
    - _Requirements: 7.1, 7.3, 8.1_

- [x] 9. Final checkpoint — Ensure all tests pass
  - Run `cd backend && pytest backend/tests/unit/test_readme_properties.py -v` and `cd frontend && npx vitest run __tests__/components/Footer.test.tsx __tests__/components/GitHubCTA.test.tsx`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- README property tests live in the backend test suite since they reference backend Pydantic schemas
- Frontend tests use Vitest + React Testing Library + fast-check per project conventions
- Checkpoints ensure incremental validation
