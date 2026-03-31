# Implementation Plan: A2A CI/CD Pipelines

## Overview

Two-phase implementation: Phase A creates the `cloudbuild.yaml` pipeline definition and the Terragrunt `cloud-build/` module (SA + IAM + trigger). Phase B adds backend and frontend Dockerfiles and enables the trigger. Tests use pytest + python-hcl2 + hypothesis + pyyaml, following the same static-analysis pattern as spec 010.

## Tasks

- [ ] 1. Create `cloudbuild.yaml` pipeline definition at repo root (Phase A)
  - [ ] 1.1 Create `cloudbuild.yaml` with 4 build steps (build-backend, build-frontend, deploy-backend, deploy-frontend)
    - Use substitution variables (`_REGION`, `_PROJECT_ID`, `_REPO_NAME`, `_BACKEND_SERVICE`, `_FRONTEND_SERVICE`, `_BACKEND_SA_EMAIL`, `_FRONTEND_SA_EMAIL`) — no hardcoded literals
    - Build steps use `gcr.io/cloud-builders/docker`, deploy steps use `gcr.io/google.com/cloudsdktool/cloud-sdk`
    - Build steps: `waitFor: ["-"]` (parallel). Deploy steps: `waitFor: ["build-backend"]` / `waitFor: ["build-frontend"]`
    - Tag images with both `$SHORT_SHA` and `latest`
    - Deploy steps use `--image` with `$SHORT_SHA` tag (never `latest`) and `--service-account` flag
    - Declare all 4 image URIs in the `images` field for automatic push
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.3, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 9.1, 9.2, 9.3, 9.4_

- [ ] 2. Create Terragrunt `cloud-build/` module (Phase A)
  - [ ] 2.1 Create `infra/modules/cloud-build/variables.tf`
    - Define inputs: `gcp_project_id`, `gcp_region`, `repository_id` (default `"juntoai-docker"`), `backend_service_name` (default `"juntoai-backend"`), `frontend_service_name` (default `"juntoai-frontend"`), `backend_sa_email`, `frontend_sa_email`, `trigger_enabled` (default `false`), `github_owner`, `github_repo`, `allowed_roles` (default: 3 approved roles with validation block)
    - Add allowlist validation block on `allowed_roles` that rejects any role not in the approved set
    - _Requirements: 8.4, 10.6_

  - [ ] 2.2 Create `infra/modules/cloud-build/main.tf`
    - `google_service_account.cloudbuild` with `account_id = "cloudbuild-sa"`
    - 3x `google_project_iam_member` for `roles/artifactregistry.writer`, `roles/run.admin`, `roles/iam.serviceAccountUser`
    - `google_cloudbuild_trigger.main` with `name = "juntoai-cicd-main"`, `filename = "cloudbuild.yaml"`, `disabled = var.trigger_enabled ? false : true`, GitHub push config for `^main$`, substitutions map, `service_account` set to the Cloud Build SA
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 10.1, 10.2, 10.3, 10.4, 10.6_

  - [ ] 2.3 Create `infra/modules/cloud-build/outputs.tf`
    - Output `trigger_id`, `trigger_name`, `cloudbuild_sa_email`
    - _Requirements: 10.5_

  - [ ] 2.4 Create `infra/modules/cloud-build/terragrunt.hcl`
    - Include `root.hcl` via `find_in_parent_folders`
    - Declare dependencies on `../iam` and `../artifact-registry`
    - Wire `backend_sa_email` and `frontend_sa_email` from `dependency.iam.outputs`
    - _Requirements: 10.1_

- [ ] 3. Checkpoint — Phase A infrastructure review
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Write static analysis tests for `cloud-build/` module and `cloudbuild.yaml` (Phase A)
  - [ ] 4.1 Add `cloud_build_dir` fixture to `infra/tests/conftest.py`
    - Add path fixture for `cloud-build/` module, following existing pattern
    - _Requirements: 10.1_

  - [ ] 4.2 Create `infra/tests/test_cloud_build.py` — HCL unit tests for the module
    - Verify `cloud-build/` directory exists with `main.tf`, `variables.tf`, `outputs.tf`, `terragrunt.hcl`
    - Verify `google_cloudbuild_trigger` resource exists in `main.tf`
    - Verify `google_service_account` resource with `account_id = "cloudbuild-sa"`
    - Verify 3 `google_project_iam_member` resources with correct roles
    - Verify `trigger_enabled` variable defaults to `false`
    - Verify `terragrunt.hcl` includes `root.hcl` and declares dependencies on `iam/` and `artifact-registry/`
    - Verify outputs include `trigger_id`, `trigger_name`, `cloudbuild_sa_email`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ] 4.3 Create `infra/tests/test_cloudbuild_yaml.py` — YAML pipeline tests
    - Parse `cloudbuild.yaml` with `pyyaml` and verify 4 step IDs, builder images, `waitFor` directives
    - Verify substitution variables are used (no hardcoded project IDs or regions)
    - Verify `images` field contains all 4 expected image URI patterns
    - Verify deploy steps include `--service-account` flag
    - Verify deploy steps use `$SHORT_SHA` tag in `--image` argument
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.3, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 9.1, 9.2, 9.3, 9.4_

- [ ] 5. Write property-based tests (Phase A)
  - [ ]* 5.1 Write property test for dual image tagging
    - **Property 1: Dual image tagging (SHA + latest)**
    - Generate random service names and SHA strings, build image URI lists, verify both SHA and latest tags present for each service
    - **Validates: Requirements 1.3, 1.4, 2.2, 2.3, 3.2, 3.3, 4.1, 4.2**

  - [ ]* 5.2 Write property test for substitution variable parameterization
    - **Property 2: Substitution variable parameterization**
    - Generate random pipeline configs, verify no hardcoded environment values leak through
    - **Validates: Requirements 1.2, 5.2, 6.2**

  - [ ]* 5.3 Write property test for SHA deploy tag enforcement
    - **Property 3: Deploy steps use SHA tag**
    - Generate random deploy commands, verify image argument always uses SHA tag, never `latest`
    - **Validates: Requirements 5.1, 6.1**

  - [ ]* 5.4 Write property test for Cloud Build SA role allowlist
    - **Property 4: Cloud Build SA role allowlist**
    - Generate random role strings, verify validation accepts approved roles and rejects all others
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

  - [ ]* 5.5 Write property test for pipeline step dependency ordering
    - **Property 5: Pipeline step dependency ordering**
    - Generate random step graphs with waitFor directives, verify builds parallel and deploys depend on their build step
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4**

  - [ ]* 5.6 Write property test for trigger substitutions completeness
    - **Property 6: Trigger substitutions completeness**
    - Generate random sets of required variables, verify trigger substitutions map is a superset
    - **Validates: Requirements 7.3, 10.4**

  - [ ]* 5.7 Write property test for trigger disabled-by-default
    - **Property 7: Trigger disabled-by-default**
    - Generate random boolean for trigger_enabled, verify disabled field is the inverse
    - **Validates: Requirements 7.4, 10.6**

- [ ] 6. Checkpoint — Phase A complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Create Backend Dockerfile (Phase B — after spec 020)
  - [ ] 7.1 Create `backend/Dockerfile`
    - Multi-stage or single-stage build for FastAPI + uvicorn
    - Expose port 8080 (Cloud Run default)
    - Health check endpoint `GET /api/v1/health` must return HTTP 200
    - _Requirements: 2.1, 2.4_

- [ ] 8. Create Frontend Dockerfile (Phase B — after spec 050)
  - [ ] 8.1 Create `frontend/Dockerfile`
    - Multi-stage build for Next.js production
    - Serve on Cloud Run's `PORT` env var (default 3000)
    - Must serve the application and respond to health checks
    - _Requirements: 3.1, 3.4_

- [ ] 9. Enable Cloud Build trigger (Phase B)
  - [ ] 9.1 Set `trigger_enabled = true` in `infra/modules/cloud-build/terragrunt.hcl` inputs
    - Flip the trigger from disabled to enabled after Dockerfiles are validated
    - _Requirements: 7.4, 10.6_

- [ ] 10. Final checkpoint — Phase B complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Phase A tasks (1–6) can be executed immediately after spec 010
- Phase B tasks (7–10) require specs 020 and 050 to be complete first
- Property tests follow the same hypothesis pattern as `infra/tests/test_properties.py` from spec 010
- All property tests go in `infra/tests/test_cloud_build_properties.py`
- Static analysis tests parse HCL/YAML files without running `terraform plan` or `apply`
