# Requirements Document

## Introduction

JuntoAI A2A is an open-source agent-to-agent negotiation engine. The codebase is public on GitHub, the README invites contributions, and the Local Battle Arena lets developers clone and run the full stack. But the project currently lacks the infrastructure that turns a public repo into an actual developer community: no contribution guide, no code of conduct, no issue/PR templates, no automated PR test pipeline, and no community channel. This spec defines the files, workflows, and processes needed to make JuntoAI A2A a contributor-ready open-source project where developers can fork, build, test, and submit PRs with confidence — and where maintainers can review those PRs efficiently.

The PR CI pipeline uses GitHub Actions (not Cloud Build). Cloud Build remains the production deployment pipeline triggered on push to `main`. GitHub Actions runs on pull requests only, executing backend and frontend tests to gate merges. These are two separate pipelines with distinct responsibilities.

## Glossary

- **PR_CI_Pipeline**: A GitHub Actions workflow that runs automatically on pull requests targeting `main`. Executes backend pytest and frontend Vitest test suites with coverage enforcement. This is separate from the Cloud Build production pipeline.
- **Contribution_Guide**: The `CONTRIBUTING.md` file at the monorepo root that documents the fork-and-PR workflow, local development setup, commit conventions, and PR expectations for external contributors.
- **Code_of_Conduct**: The `CODE_OF_CONDUCT.md` file at the monorepo root that establishes behavioral expectations for all community participants, based on the Contributor Covenant.
- **Issue_Template**: YAML-based GitHub issue form templates in `.github/ISSUE_TEMPLATE/` that provide structured forms for bug reports and feature requests.
- **PR_Template**: A markdown template at `.github/PULL_REQUEST_TEMPLATE.md` that provides a checklist and structure for pull request descriptions.
- **Community_Channel**: The WhatsApp group linked in the README and CONTRIBUTING.md where contributors can ask questions and coordinate.
- **Good_First_Issue**: A GitHub label applied to issues that are suitable for new contributors, with clear scope and minimal context required.
- **README_Community_Section**: The existing "Contributing" section in `README.md`, updated to reference the Contribution_Guide, Code_of_Conduct, Community_Channel, and PR_CI_Pipeline.
- **Coverage_Threshold**: The minimum 70% code coverage required for both backend (pytest-cov) and frontend (vitest coverage-v8) test suites, enforced by the PR_CI_Pipeline.
- **Monorepo**: The repository structure with three top-level directories: `/backend` (Python/FastAPI), `/frontend` (Next.js), `/infra` (Terraform).

## Requirements

### Requirement 1: GitHub Actions PR CI Pipeline

**User Story:** As a contributor, I want my pull request to be automatically tested against the backend and frontend test suites, so that I know my changes do not break existing functionality before a maintainer reviews.

#### Acceptance Criteria

1. WHEN a pull request is opened or updated targeting the `main` branch, THE PR_CI_Pipeline SHALL trigger automatically via GitHub Actions.
2. WHEN a pull request is synchronized (new commits pushed), THE PR_CI_Pipeline SHALL re-run all test jobs.
3. THE PR_CI_Pipeline SHALL execute backend tests using `pytest --cov=app --cov-fail-under=70` in the `/backend` directory using Python 3.11.
4. THE PR_CI_Pipeline SHALL execute frontend tests using `npx vitest run --coverage` in the `/frontend` directory using Node.js 20.
5. THE PR_CI_Pipeline SHALL run the backend and frontend test jobs in parallel to minimize total pipeline duration.
6. THE PR_CI_Pipeline SHALL report a failing status check on the pull request if any test job fails or coverage drops below the Coverage_Threshold of 70%.
7. THE PR_CI_Pipeline SHALL report a passing status check on the pull request only when all test jobs pass and coverage meets or exceeds the Coverage_Threshold.
8. THE PR_CI_Pipeline SHALL install backend dependencies from `backend/requirements.txt` and frontend dependencies using `npm ci` in the `/frontend` directory.
9. THE PR_CI_Pipeline SHALL define the workflow file at `.github/workflows/pr-tests.yml`.
10. IF a pull request modifies only files in the `/infra` directory, THEN THE PR_CI_Pipeline SHALL still run all test jobs to prevent configuration drift from breaking application code.

### Requirement 2: Contribution Guide

**User Story:** As a new contributor, I want a clear guide explaining how to fork the repo, set up my local environment, run tests, and submit a pull request, so that I can contribute without guessing the workflow.

#### Acceptance Criteria

1. THE Contribution_Guide SHALL be located at `CONTRIBUTING.md` in the monorepo root.
2. THE Contribution_Guide SHALL document the fork-and-PR workflow: fork the repo, clone the fork, create a `feature/*` branch from `main`, make changes, push to the fork, open a PR to `upstream/main`.
3. THE Contribution_Guide SHALL document local development setup: prerequisites (Docker, Docker Compose v2.24+, Python 3.11, Node.js 20), running `docker compose up` for the full stack, and running tests independently for backend and frontend.
4. THE Contribution_Guide SHALL document the exact commands to run backend tests (`cd backend && pytest --cov=app --cov-fail-under=70`) and frontend tests (`cd frontend && npx vitest run --coverage`).
5. THE Contribution_Guide SHALL document that all PRs must pass the PR_CI_Pipeline (GitHub Actions) before merge, and that the Coverage_Threshold of 70% is enforced.
6. THE Contribution_Guide SHALL document the types of contributions accepted: scenario configs (JSON-only, no code changes), bug fixes, feature proposals, documentation improvements, and agent strategies.
7. THE Contribution_Guide SHALL document that scenario contributions require only dropping a JSON file in `backend/app/scenarios/data/` — no code changes needed.
8. THE Contribution_Guide SHALL link to the Community_Channel (WhatsApp group) for questions and coordination.
9. THE Contribution_Guide SHALL link to the Code_of_Conduct and state that all contributors must adhere to the Code_of_Conduct.

### Requirement 3: Code of Conduct

**User Story:** As a community member, I want a published code of conduct, so that I know the behavioral expectations and feel safe participating.

#### Acceptance Criteria

1. THE Code_of_Conduct SHALL be located at `CODE_OF_CONDUCT.md` in the monorepo root.
2. THE Code_of_Conduct SHALL be based on the Contributor Covenant v2.1.
3. THE Code_of_Conduct SHALL specify the enforcement contact email for reporting violations.
4. THE Code_of_Conduct SHALL define the scope as all community spaces: GitHub issues, pull requests, discussions, and the Community_Channel.

### Requirement 4: GitHub Issue Templates

**User Story:** As a contributor, I want structured issue templates for bug reports and feature requests, so that I can provide the right information upfront and maintainers can triage efficiently.

#### Acceptance Criteria

1. THE Issue_Template for bug reports SHALL be located at `.github/ISSUE_TEMPLATE/bug-report.yml` and use the GitHub issue forms YAML format.
2. THE Issue_Template for bug reports SHALL require fields for: description of the bug, steps to reproduce, expected behavior, actual behavior, and environment (OS, Docker version, LLM provider).
3. THE Issue_Template for feature requests SHALL be located at `.github/ISSUE_TEMPLATE/feature-request.yml` and use the GitHub issue forms YAML format.
4. THE Issue_Template for feature requests SHALL require fields for: description of the feature, the problem it solves, and proposed solution.
5. THE Issue_Template directory SHALL include a `config.yml` file that links to the Community_Channel as an alternative contact option and disables blank issues.

### Requirement 5: Pull Request Template

**User Story:** As a contributor, I want a PR template with a checklist, so that I remember to run tests, describe my changes, and link related issues before requesting review.

#### Acceptance Criteria

1. THE PR_Template SHALL be located at `.github/PULL_REQUEST_TEMPLATE.md`.
2. THE PR_Template SHALL include a section for describing the changes made.
3. THE PR_Template SHALL include a section for linking related issues.
4. THE PR_Template SHALL include a checklist with items for: tests pass locally, coverage meets 70% threshold, code follows existing patterns, and the contributor has read the Contribution_Guide.
5. THE PR_Template SHALL include a section for indicating the type of change: bug fix, feature, scenario config, documentation, or other.

### Requirement 6: GitHub Labels for Contributor Onboarding

**User Story:** As a new contributor, I want to find issues labeled "good first issue" so that I can start with tasks that have clear scope and minimal context requirements.

#### Acceptance Criteria

1. THE Contribution_Guide SHALL document the `good first issue` label and explain that these issues are curated for new contributors.
2. THE Contribution_Guide SHALL document the `scenario-contribution` label for issues related to adding new negotiation scenario JSON configs.
3. THE Contribution_Guide SHALL document the `help wanted` label for issues where maintainers are actively seeking community contributions.
4. THE README_Community_Section SHALL link to the filtered GitHub issues view for `good first issue` labeled issues.

### Requirement 7: README Community Section Update

**User Story:** As a visitor to the repository, I want the README to clearly point me to the contribution guide, community channel, and getting-started resources, so that I can quickly find how to participate.

#### Acceptance Criteria

1. THE README_Community_Section SHALL link to the Contribution_Guide (`CONTRIBUTING.md`).
2. THE README_Community_Section SHALL link to the Code_of_Conduct (`CODE_OF_CONDUCT.md`).
3. THE README_Community_Section SHALL link to the Community_Channel (WhatsApp group) with a brief description of its purpose.
4. THE README_Community_Section SHALL link to the filtered GitHub issues view for `good first issue` labeled issues.
5. THE README_Community_Section SHALL mention that all PRs are automatically tested by the PR_CI_Pipeline via GitHub Actions.
6. THE README_Community_Section SHALL retain the existing contribution types (scenario configs, bug reports, feature proposals, documentation, agent strategies) from the current README.

### Requirement 8: Community Channel Integration

**User Story:** As a developer interested in contributing, I want a direct link to a community chat channel, so that I can ask questions, get help, and coordinate with other contributors.

#### Acceptance Criteria

1. THE Community_Channel link SHALL be included in the README_Community_Section.
2. THE Community_Channel link SHALL be included in the Contribution_Guide.
3. THE Community_Channel link SHALL be included in the Issue_Template `config.yml` as an alternative contact option.
4. WHEN a contributor opens the Community_Channel link, THE link SHALL direct to the WhatsApp group invite URL.

### Requirement 9: Branch Protection Guidance

**User Story:** As a maintainer, I want documentation on recommended branch protection rules, so that I can configure GitHub to require passing CI checks before merging PRs.

#### Acceptance Criteria

1. THE Contribution_Guide SHALL document that the `main` branch should have branch protection rules enabled.
2. THE Contribution_Guide SHALL document that the recommended branch protection configuration requires the PR_CI_Pipeline status checks to pass before merging.
3. THE Contribution_Guide SHALL document that direct pushes to `main` are prohibited — all changes go through pull requests.
