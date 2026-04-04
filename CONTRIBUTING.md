# Contributing to JuntoAI A2A

Welcome, and thanks for your interest in contributing to JuntoAI A2A! Whether you're fixing a bug, proposing a feature, adding a new negotiation scenario, or improving docs - we're glad you're here.

All contributors are expected to follow our [Code of Conduct](./CODE_OF_CONDUCT.md). Please read it before participating.

## Getting Started - Fork & PR Workflow

We use a standard fork-and-PR workflow:

1. **Fork** this repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/a2a.git
   cd a2a
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/JuntoAI/a2a.git
   ```
4. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name main
   ```
5. **Make your changes**, commit with clear messages.
6. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request** from your fork's branch to `upstream/main`.

## Local Development Setup

### Prerequisites

| Tool              | Version       |
| ----------------- | ------------- |
| Docker            | Latest stable |
| Docker Compose    | v2.24+        |
| Python            | 3.11          |
| Node.js           | 20            |

### Running the Full Stack

Start all services with Docker Compose:

```bash
docker compose up
```

This spins up the backend, frontend, and any supporting services. See the project README for environment variable configuration.

### Running Tests Independently

Backend and frontend test suites can be run independently outside of Docker.

## Running Tests

All pull requests must pass the GitHub Actions CI pipeline before merge. The pipeline enforces a minimum 70% code coverage threshold on both backend and frontend.

### Backend Tests

```bash
cd backend && pytest --cov=app --cov-fail-under=70
```

This runs the full pytest suite with coverage reporting. The `--cov-fail-under=70` flag ensures the build fails if coverage drops below 70%.

### Frontend Tests

```bash
cd frontend && npx vitest run --coverage
```

This runs the Vitest suite with coverage. The 70% coverage threshold is enforced in the CI pipeline.

> **Note:** Make sure both test suites pass locally before opening a PR. The CI pipeline runs these exact commands and will block merge on failure.

## Types of Contributions

We welcome several types of contributions:

- **Scenario Configs** - JSON-only negotiation scenarios (no code changes required)
- **Bug Fixes** - Fixing issues in the backend, frontend, or infrastructure
- **Feature Proposals** - New capabilities or improvements (open an issue first to discuss)
- **Documentation** - README updates, guide improvements, inline code docs
- **Agent Strategies** - New agent behaviors and negotiation tactics

## Scenario Contributions

Adding a new negotiation scenario is the easiest way to contribute - no code changes needed.

1. Create a new JSON file following the existing scenario format in `backend/app/scenarios/data/`.
2. Drop your file into `backend/app/scenarios/data/`.
3. The scenario engine picks it up automatically at runtime.

That's it. Look at the existing `.scenario.json` files in that directory for the expected structure.

## Pull Request Process

1. Ensure your branch is up to date with `main`.
2. Run both test suites locally and confirm they pass (see [Running Tests](#running-tests)).
3. Open a PR targeting `upstream/main`.
4. The GitHub Actions CI pipeline runs automatically on every PR. Both backend and frontend test jobs must pass.
5. A minimum **70% code coverage** threshold is enforced by the CI pipeline. PRs that drop coverage below this threshold will not be merged.
6. A maintainer will review your PR once CI passes.

## Branch Protection

The `main` branch is protected:

- All changes must go through a pull request - **no direct pushes to `main`**.
- The GitHub Actions CI pipeline must pass before a PR can be merged.
- Keep your feature branches short-lived and focused.

## Labels

We use GitHub labels to organize issues and help contributors find work:

| Label | Description |
| ----- | ----------- |
| `good first issue` | Curated for new contributors - clear scope, minimal context required. |
| `scenario-contribution` | Adding a new negotiation scenario JSON config to `backend/app/scenarios/data/`. |
| `help wanted` | Maintainers are actively seeking community contributions on these issues. |

If you're new here, filter issues by [`good first issue`](../../issues?q=label%3A%22good+first+issue%22) to get started.

## Community

- **Chat**: Join our [WhatsApp community](https://chat.whatsapp.com/CZblOXj7aV3LMSKCwSUxWR) to ask questions, share ideas, and coordinate with other contributors. 
- **Code of Conduct**: All participants must follow our [Code of Conduct](./CODE_OF_CONDUCT.md). Be respectful, be constructive, be kind.
