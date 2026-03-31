# Requirements Document

## Introduction

This specification covers the greenfield monorepo scaffolding and Google Cloud Platform infrastructure provisioning for the JuntoAI A2A MVP. The infrastructure is managed via Terragrunt (wrapping Terraform) and provisions the core GCP resources needed to host the backend (FastAPI on Cloud Run), frontend (Next.js on Cloud Run), Docker image storage (Artifact Registry), state management (Firestore Native mode), and AI access (Vertex AI). IAM Service Accounts follow least-privilege principles.

## Glossary

- **Monorepo**: A single Git repository containing the `/infra`, `/backend`, and `/frontend` project directories.
- **Terragrunt**: A thin wrapper for Terraform that keeps IaC configurations DRY and manages remote state.
- **Root_HCL**: The top-level `terragrunt.hcl` file in `/infra` that defines shared provider configuration, remote state, and common inputs inherited by all child modules.
- **Child_Module**: A Terragrunt directory under `/infra/modules/` representing a single GCP resource (e.g., Cloud Run, Artifact Registry).
- **Cloud_Run**: A GCP serverless container platform used to host the Backend and Frontend services.
- **Artifact_Registry**: A GCP service for storing and managing Docker container images.
- **Firestore**: A GCP NoSQL document database, configured in Native mode, used for state and waitlist management.
- **Vertex_AI**: A GCP managed ML platform providing access to foundation models (Gemini, Claude) via Model Garden.
- **IAM_Service_Account**: A GCP identity resource representing a non-human principal, assigned specific IAM roles for least-privilege access.
- **GCS_Remote_State**: A Google Cloud Storage bucket used to store Terraform state files with native state locking.
- **Backend_SA**: The IAM Service Account assigned to the Backend Cloud Run service.
- **Frontend_SA**: The IAM Service Account assigned to the Frontend Cloud Run service.

## Requirements

### Requirement 1: Monorepo Directory Structure

**User Story:** As a developer, I want a well-organized monorepo structure, so that infrastructure, backend, and frontend code are cleanly separated from the start.

#### Acceptance Criteria

1. THE Monorepo SHALL contain a top-level `/infra` directory for all Terragrunt and Terraform configurations.
2. THE Monorepo SHALL contain a top-level `/backend` directory for the Python FastAPI application code.
3. THE Monorepo SHALL contain a top-level `/frontend` directory for the Next.js application code.
4. THE Monorepo SHALL contain a top-level `/docs` directory for project documentation.
5. THE `/infra` directory SHALL contain a root `terragrunt.hcl` file (Root_HCL) that child modules inherit from.
6. THE `/infra` directory SHALL contain a `/modules` subdirectory with one directory per GCP resource module.

### Requirement 2: Terragrunt Remote State Configuration

**User Story:** As a DevOps engineer, I want Terraform state stored remotely in GCS with locking, so that team members can collaborate safely on infrastructure changes.

#### Acceptance Criteria

1. THE Root_HCL SHALL configure remote state using the `gcs` backend.
2. THE Root_HCL SHALL set the GCS bucket name to `juntoai-terraform-state-prod`.
3. THE Root_HCL SHALL set the state file prefix using `path_relative_to_include()` to ensure unique state paths per module.
4. THE Root_HCL SHALL set the GCP project to `juntoai-project-id`.
5. THE Root_HCL SHALL set the GCS bucket location to `eu` for EU compliance.
6. THE Root_HCL SHALL configure the `hashicorp/google` and `hashicorp/google-beta` providers.

### Requirement 3: Cloud Run Service Provisioning

**User Story:** As a DevOps engineer, I want Cloud Run services provisioned for both the backend and frontend, so that containerized applications can be deployed in a serverless manner.

#### Acceptance Criteria

1. THE Cloud_Run Child_Module SHALL provision a Cloud Run service named for the Backend (FastAPI).
2. THE Cloud_Run Child_Module SHALL provision a Cloud Run service named for the Frontend (Next.js).
3. WHEN a Cloud Run service is provisioned, THE Child_Module SHALL configure the service to pull its container image from the Artifact_Registry.
4. WHEN a Cloud Run service is provisioned, THE Child_Module SHALL assign the corresponding IAM_Service_Account (Backend_SA or Frontend_SA) as the service identity.
5. THE Cloud_Run Child_Module SHALL set the Cloud Run service region to a configurable GCP region variable.

### Requirement 4: Artifact Registry Provisioning

**User Story:** As a DevOps engineer, I want an Artifact Registry repository for Docker images, so that CI/CD pipelines can push and Cloud Run can pull container images.

#### Acceptance Criteria

1. THE Artifact_Registry Child_Module SHALL provision a Docker-format repository in Artifact Registry.
2. THE Artifact_Registry Child_Module SHALL set the repository region to a configurable GCP region variable.
3. THE Artifact_Registry Child_Module SHALL set the repository ID to a configurable name (e.g., `juntoai-docker`).

### Requirement 5: Firestore Provisioning

**User Story:** As a DevOps engineer, I want a Firestore database in Native mode, so that the backend can persist negotiation state and waitlist data.

#### Acceptance Criteria

1. THE Firestore Child_Module SHALL provision a Firestore database in Native mode.
2. THE Firestore Child_Module SHALL set the Firestore location to a configurable GCP region variable.
3. THE Firestore Child_Module SHALL enable the Firestore API (`firestore.googleapis.com`) for the GCP project.

### Requirement 6: Vertex AI API Enablement

**User Story:** As a DevOps engineer, I want the Vertex AI API enabled on the GCP project, so that the backend can call foundation models via the Vertex AI SDK.

#### Acceptance Criteria

1. THE Vertex_AI Child_Module SHALL enable the `aiplatform.googleapis.com` API for the GCP project.

### Requirement 7: IAM Service Accounts with Least-Privilege Access

**User Story:** As a security engineer, I want dedicated IAM Service Accounts for each Cloud Run service with only the permissions they need, so that the blast radius of a compromised service is minimized.

#### Acceptance Criteria

1. THE IAM Child_Module SHALL create a Backend_SA IAM_Service_Account for the Backend Cloud Run service.
2. THE IAM Child_Module SHALL create a Frontend_SA IAM_Service_Account for the Frontend Cloud Run service.
3. THE IAM Child_Module SHALL grant Backend_SA the `roles/datastore.user` role for Firestore access.
4. THE IAM Child_Module SHALL grant Backend_SA the `roles/aiplatform.user` role for Vertex AI access.
5. THE IAM Child_Module SHALL grant Backend_SA the `roles/run.invoker` role only if inter-service invocation is required.
6. THE Frontend_SA SHALL receive no Firestore or Vertex AI roles, limiting the Frontend to serving static content and calling the Backend API.
7. IF a service account is granted a role not listed in the approved set (datastore.user, aiplatform.user, run.invoker), THEN THE IAM Child_Module SHALL reject the configuration with a validation error.

### Requirement 8: Terragrunt Module Outputs

**User Story:** As a DevOps engineer, I want each Terragrunt module to export key resource identifiers, so that downstream modules and CI/CD pipelines can reference them.

#### Acceptance Criteria

1. THE Cloud_Run Child_Module SHALL output the Cloud Run service URLs for both Backend and Frontend.
2. THE Artifact_Registry Child_Module SHALL output the full repository path (e.g., `REGION-docker.pkg.dev/PROJECT/REPO`).
3. THE Firestore Child_Module SHALL output the Firestore database name.
4. THE IAM Child_Module SHALL output the email addresses of Backend_SA and Frontend_SA.
