# Implementation Plan: Developer Community Infrastructure

## Overview

Create the static files (markdown, YAML) that transform the JuntoAI A2A repo into a contributor-ready open-source project. Files are created in dependency order per the design: Code of Conduct first (referenced by everything), then CONTRIBUTING.md, CI pipeline, issue templates, PR template, and finally the README community section update. No runtime code changes — all artifacts are documentation and GitHub configuration.

## Tasks

- [x] 1. Create CODE_OF_CONDUCT.md
  - Create `CODE_OF_CONDUCT.md` at the monorepo root based on Contributor Covenant v2.1
  - Include the full standard text: Pledge, Standards, Responsibilities, Scope, Enforcement, Attribution
  - Set enforcement contact to placeholder `conduct@juntoai.org` with a TODO comment to replace
  - Define scope as all community spaces: GitHub issues, PRs, discussions, and WhatsApp community channel
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 2. Create CONTRIBUTING.md
  - [x] 2.1 Create CONTRIBUTING.md with welcome, workflow, and setup sections
    - Create `CONTRIBUTING.md` at the monorepo root
    - Welcome section linking to Code of Conduct
    - Fork-and-PR workflow: fork, clone, create `feature/*` branch from `main`, push to fork, open PR to `upstream/main`
    - Local development setup: prerequisites (Docker, Docker Compose v2.24+, Python 3.11, Node.js 20), `docker compose up`, independent test commands
    - Exact test commands: `cd backend && pytest --cov=app --cov-fail-under=70` and `cd frontend && npx vitest run --coverage`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.9_

  - [x] 2.2 Add contribution types, labels, branch protection, and community sections
    - Types of contributions: scenario configs (JSON-only), bug fixes, feature proposals, documentation, agent strategies
    - Scenario contribution workflow: drop JSON in `backend/app/scenarios/data/`, no code changes
    - PR process: CI pipeline must pass, 70% coverage enforced
    - Branch protection guidance: `main` is protected, all changes via PR, CI must pass before merge, no direct pushes
    - Labels section: `good first issue`, `scenario-contribution`, `help wanted` with descriptions
    - Community section: WhatsApp link (placeholder URL), Code of Conduct link
    - _Requirements: 2.5, 2.6, 2.7, 2.8, 2.9, 6.1, 6.2, 6.3, 8.2, 9.1, 9.2, 9.3_

- [x] 3. Create GitHub Actions PR CI pipeline
  - Create `.github/workflows/pr-tests.yml`
  - Trigger on `pull_request` events (opened, synchronize, reopened) targeting `main`
  - Define two parallel jobs (no `needs` dependency): `backend-tests` and `frontend-tests`
  - Backend job: `ubuntu-latest`, `actions/checkout@v4`, `actions/setup-python@v5` with Python 3.11, `pip install -r backend/requirements.txt`, run `pytest --cov=app --cov-fail-under=70` in `backend/` directory
  - Frontend job: `ubuntu-latest`, `actions/checkout@v4`, `actions/setup-node@v4` with Node.js 20, `npm ci` in `frontend/`, run `npx vitest run --coverage` in `frontend/` directory
  - No path filtering — all PRs trigger all jobs (Requirement 1.10)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

- [x] 4. Checkpoint — Verify CI pipeline and docs
  - Ensure all files created so far are valid YAML/markdown
  - Verify cross-references: CONTRIBUTING.md links to CODE_OF_CONDUCT.md, CONTRIBUTING.md links to WhatsApp placeholder
  - Ask the user if questions arise

- [x] 5. Create GitHub issue templates
  - [x] 5.1 Create bug report issue template
    - Create `.github/ISSUE_TEMPLATE/bug-report.yml` using GitHub issue forms YAML format
    - Required fields: description (textarea), steps to reproduce (textarea), expected behavior (textarea), actual behavior (textarea), environment info (OS dropdown + Docker version + LLM provider as textarea)
    - _Requirements: 4.1, 4.2_

  - [x] 5.2 Create feature request issue template
    - Create `.github/ISSUE_TEMPLATE/feature-request.yml` using GitHub issue forms YAML format
    - Required fields: description (textarea), problem it solves (textarea), proposed solution (textarea)
    - _Requirements: 4.3, 4.4_

  - [x] 5.3 Create issue template config
    - Create `.github/ISSUE_TEMPLATE/config.yml`
    - Set `blank_issues_enabled: false`
    - Add contact link to WhatsApp community channel (placeholder URL) as alternative contact option
    - _Requirements: 4.5, 8.3_

- [x] 6. Create pull request template
  - Create `.github/PULL_REQUEST_TEMPLATE.md`
  - Description section for changes made
  - Related issues section (Closes #XX / Relates to #XX)
  - Type of change section with checkboxes: bug fix, feature, scenario config, documentation, other
  - Checklist: tests pass locally, coverage meets 70%, code follows existing patterns, contributor has read CONTRIBUTING.md
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 7. Update README.md community section
  - Replace the existing `## 🤝 Contributing` section in `README.md`
  - Link to `CONTRIBUTING.md` as primary call to action
  - Link to `CODE_OF_CONDUCT.md`
  - Link to WhatsApp community channel (placeholder URL)
  - Link to filtered GitHub issues view for `good first issue` label
  - Mention that all PRs are automatically tested by GitHub Actions CI
  - Retain existing contribution types: scenario configs, bug reports, feature proposals, documentation, agent strategies
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 6.4, 8.1, 8.4_

- [x] 8. Final checkpoint — Cross-reference validation
  - Verify all cross-references between documents are correct and use relative links
  - Verify WhatsApp placeholder URL appears in: README.md, CONTRIBUTING.md, `.github/ISSUE_TEMPLATE/config.yml`
  - Ensure all files created so far are valid
  - Ensure all tests pass, ask the user if questions arise

## Notes

- All deliverables are static files (markdown, YAML) — no runtime code changes
- Property-based tests are not applicable (no functions or data transformations to test)
- WhatsApp community link uses a placeholder URL with TODO comments — replace before shipping
- Enforcement contact email is a placeholder — replace before shipping
- Files follow the dependency order from the design: CODE_OF_CONDUCT → CONTRIBUTING → CI → templates → README
