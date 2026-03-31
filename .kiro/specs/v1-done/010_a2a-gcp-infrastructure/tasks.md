# Tasks: GCP Infrastructure Provisioning

## Task 1: Monorepo Directory Structure & Root Terragrunt Configuration

- [x] 1.1 Create top-level directories: `/infra`, `/backend`, `/frontend`, `/docs` with placeholder `.gitkeep` files
- [x] 1.2 Create `/infra/env.hcl` with `locals` block containing `gcp_project_id`, `gcp_region` (default `europe-west1`), and `terraform_state_bucket`
- [x] 1.3 Create `/infra/terragrunt.hcl` (Root HCL) with:
  - `read_terragrunt_config()` loading `env.hcl`
  - `remote_state` block using `gcs` backend with bucket from variable, prefix using `path_relative_to_include()`, project and location from variables
  - `generate "provider"` block configuring `hashicorp/google` and `hashicorp/google-beta` providers with project and region from variables
  - `inputs` block passing `gcp_project_id` and `gcp_region` to child modules
- [x] 1.4 Create `/infra/modules/` directory structure with subdirectories: `artifact-registry/`, `firestore/`, `vertex-ai/`, `iam/`, `cloud-run/`

## Task 2: Artifact Registry Module

- [x] 2.1 Create `/infra/modules/artifact-registry/variables.tf` with variables: `gcp_project_id` (string), `gcp_region` (string), `repository_id` (string, default `juntoai-docker`)
- [x] 2.2 Create `/infra/modules/artifact-registry/main.tf` with `google_artifact_registry_repository` resource (format = `DOCKER`, location from variable, repository_id from variable)
- [x] 2.3 Create `/infra/modules/artifact-registry/outputs.tf` outputting `repository_path` in format `REGION-docker.pkg.dev/PROJECT/REPO`
- [x] 2.4 Create `/infra/modules/artifact-registry/terragrunt.hcl` child config that includes the root HCL

## Task 3: Firestore Module

- [x] 3.1 Create `/infra/modules/firestore/variables.tf` with variables: `gcp_project_id` (string), `gcp_region` (string)
- [x] 3.2 Create `/infra/modules/firestore/main.tf` with:
  - `google_project_service` enabling `firestore.googleapis.com` (with `disable_on_destroy = false`)
  - `google_firestore_database` resource in `FIRESTORE_NATIVE` mode with location from variable
- [x] 3.3 Create `/infra/modules/firestore/outputs.tf` outputting `database_name`
- [x] 3.4 Create `/infra/modules/firestore/terragrunt.hcl` child config that includes the root HCL

## Task 4: Vertex AI Module

- [x] 4.1 Create `/infra/modules/vertex-ai/variables.tf` with variable: `gcp_project_id` (string)
- [x] 4.2 Create `/infra/modules/vertex-ai/main.tf` with `google_project_service` enabling `aiplatform.googleapis.com` (with `disable_on_destroy = false`)
- [x] 4.3 Create `/infra/modules/vertex-ai/terragrunt.hcl` child config that includes the root HCL

## Task 5: IAM Module

- [x] 5.1 Create `/infra/modules/iam/variables.tf` with variables: `gcp_project_id` (string), `enable_run_invoker` (bool, default `false`), role validation using `validation` block against allowlist (`roles/datastore.user`, `roles/aiplatform.user`, `roles/run.invoker`)
- [x] 5.2 Create `/infra/modules/iam/main.tf` with:
  - `google_service_account` for `backend-sa`
  - `google_service_account` for `frontend-sa`
  - `google_project_iam_member` granting Backend_SA `roles/datastore.user`
  - `google_project_iam_member` granting Backend_SA `roles/aiplatform.user`
  - Conditional `google_project_iam_member` granting Backend_SA `roles/run.invoker` (only when `enable_run_invoker = true`)
  - No Firestore/Vertex AI role bindings for Frontend_SA
- [x] 5.3 Create `/infra/modules/iam/outputs.tf` outputting `backend_sa_email` and `frontend_sa_email`
- [x] 5.4 Create `/infra/modules/iam/terragrunt.hcl` child config that includes the root HCL

## Task 6: Cloud Run Module

- [x] 6.1 Create `/infra/modules/cloud-run/variables.tf` with variables: `gcp_project_id` (string), `gcp_region` (string), `backend_sa_email` (string), `frontend_sa_email` (string), `backend_image` (string), `frontend_image` (string), `backend_service_name` (string, default `juntoai-backend`), `frontend_service_name` (string, default `juntoai-frontend`)
- [x] 6.2 Create `/infra/modules/cloud-run/main.tf` with:
  - `google_cloud_run_v2_service` for backend: name from variable, location from `gcp_region`, image from `backend_image`, service_account from `backend_sa_email`
  - `google_cloud_run_v2_service` for frontend: name from variable, location from `gcp_region`, image from `frontend_image`, service_account from `frontend_sa_email`
- [x] 6.3 Create `/infra/modules/cloud-run/outputs.tf` outputting `backend_service_url` and `frontend_service_url`
- [x] 6.4 Create `/infra/modules/cloud-run/terragrunt.hcl` child config that includes the root HCL and declares `dependency` blocks on `iam` and `artifact-registry` modules, plus `dependencies` blocks on `firestore` and `vertex-ai`

## Task 7: Unit Tests (Example-Based)

- [x] 7.1 Create `infra/tests/conftest.py` with shared fixtures (paths to module directories, HCL parser helper)
- [x] 7.2 Create `infra/tests/test_directory_structure.py` verifying all required directories and files exist (Req 1.1–1.6)
- [x] 7.3 Create `infra/tests/test_root_hcl.py` verifying Root HCL content: GCS backend, `path_relative_to_include()`, variable references for bucket/project/region, both providers configured, `env.hcl` loaded (Req 2.1–2.7)
- [x] 7.4 Create `infra/tests/test_artifact_registry.py` verifying Docker format, configurable region/ID, output declared (Req 4.1–4.3, 8.2)
- [x] 7.5 Create `infra/tests/test_firestore.py` verifying Native mode, API enablement, configurable location, output declared (Req 5.1–5.3, 8.3)
- [x] 7.6 Create `infra/tests/test_vertex_ai.py` verifying `aiplatform.googleapis.com` API enablement (Req 6.1)
- [x] 7.7 Create `infra/tests/test_iam.py` verifying SA creation, role bindings for Backend_SA, no privileged roles for Frontend_SA, outputs declared (Req 7.1–7.4, 8.4)
- [x] 7.8 Create `infra/tests/test_cloud_run.py` verifying both services declared, outputs for service URLs (Req 3.1–3.2, 8.1)

## Task 8: Property-Based Tests

- [x] 8.1 Create `infra/tests/test_properties.py` with `hypothesis` property tests:
  - Property 1: Cloud Run service configuration invariant — generate random valid configs, assert image URI, SA email, and region invariants hold (Req 3.3, 3.4, 3.5)
  - Property 2: Conditional run.invoker role grant — generate random booleans, assert binding exists iff flag is true (Req 7.5)
  - Property 3: Frontend_SA least-privilege enforcement — generate random IAM binding sets, assert no privileged roles on Frontend_SA (Req 7.6)
  - Property 4: IAM role allowlist validation — generate random role strings, assert only approved roles pass validation (Req 7.7)
