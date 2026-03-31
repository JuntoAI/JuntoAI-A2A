# Requirements Document

## Introduction

This specification defines the Continuous Integration and Continuous Deployment (CI/CD) pipeline for the JuntoAI A2A MVP. The pipeline automates the build, push, and deploy workflow so that merging code into the main branch automatically builds Docker images for the FastAPI backend and Next.js frontend, pushes them to GCP Artifact Registry, and deploys updated services to Cloud Run. The pipeline is implemented using Google Cloud Build with a `cloudbuild.yaml` configuration file at the repository root.

## Glossary

- **Pipeline**: The Google Cloud Build CI/CD pipeline defined in `cloudbuild.yaml` that orchestrates build, push, and deploy steps.
- **Backend_Image**: The Docker image built from the `/backend` directory containing the FastAPI application.
- **Frontend_Image**: The Docker image built from the `/frontend` directory containing the Next.js application.
- **Artifact_Registry**: The GCP Docker repository (e.g., `REGION-docker.pkg.dev/PROJECT/REPO`) where built images are stored.
- **Cloud_Run_Backend**: The Cloud Run service hosting the FastAPI backend.
- **Cloud_Run_Frontend**: The Cloud Run service hosting the Next.js frontend.
- **Build_Trigger**: A Google Cloud Build trigger that starts the Pipeline when code is pushed to the main branch.
- **Substitution_Variable**: A Cloud Build variable (e.g., `_REGION`, `_PROJECT_ID`, `_REPO_NAME`) that parameterizes the pipeline for different environments.
- **Short_SHA**: The abbreviated Git commit hash used to tag Docker images for traceability.
- **Cloud_Build_SA**: The IAM Service Account used by Cloud Build to execute pipeline steps.

## Requirements

### Requirement 1: Cloud Build Configuration File

**User Story:** As a DevOps engineer, I want a `cloudbuild.yaml` file at the repository root, so that Google Cloud Build can execute the CI/CD pipeline.

#### Acceptance Criteria

1. THE Pipeline SHALL be defined in a `cloudbuild.yaml` file located at the root of the Monorepo.
2. THE Pipeline SHALL use Substitution_Variables for GCP project ID, region, Artifact Registry repository name, and Cloud Run service names.
3. THE Pipeline SHALL tag all built images with the Short_SHA of the triggering commit for traceability.
4. THE Pipeline SHALL tag all built images with the `latest` tag for convenience.

### Requirement 2: Backend Docker Image Build

**User Story:** As a DevOps engineer, I want the pipeline to build a Docker image for the FastAPI backend, so that the backend can be deployed as a container.

#### Acceptance Criteria

1. THE Pipeline SHALL build the Backend_Image from a `Dockerfile` located in the `/backend` directory.
2. THE Pipeline SHALL tag the Backend_Image with the Artifact_Registry path, service name, and Short_SHA (e.g., `REGION-docker.pkg.dev/PROJECT/REPO/backend:SHORT_SHA`).
3. THE Pipeline SHALL tag the Backend_Image with the Artifact_Registry path, service name, and `latest` tag.

### Requirement 3: Frontend Docker Image Build

**User Story:** As a DevOps engineer, I want the pipeline to build a Docker image for the Next.js frontend, so that the frontend can be deployed as a container.

#### Acceptance Criteria

1. THE Pipeline SHALL build the Frontend_Image from a `Dockerfile` located in the `/frontend` directory.
2. THE Pipeline SHALL tag the Frontend_Image with the Artifact_Registry path, service name, and Short_SHA (e.g., `REGION-docker.pkg.dev/PROJECT/REPO/frontend:SHORT_SHA`).
3. THE Pipeline SHALL tag the Frontend_Image with the Artifact_Registry path, service name, and `latest` tag.

### Requirement 4: Image Push to Artifact Registry

**User Story:** As a DevOps engineer, I want built Docker images pushed to Artifact Registry automatically, so that Cloud Run can pull and deploy them.

#### Acceptance Criteria

1. THE Pipeline SHALL push the Backend_Image (both Short_SHA and `latest` tags) to the Artifact_Registry.
2. THE Pipeline SHALL push the Frontend_Image (both Short_SHA and `latest` tags) to the Artifact_Registry.
3. THE Pipeline SHALL use the Cloud Build `images` field to declare all images for automatic push.

### Requirement 5: Backend Deployment to Cloud Run

**User Story:** As a DevOps engineer, I want the pipeline to deploy the newly built backend image to Cloud Run, so that the live investor demo is updated automatically.

#### Acceptance Criteria

1. WHEN the Backend_Image is pushed to Artifact_Registry, THE Pipeline SHALL deploy the Backend_Image (tagged with Short_SHA) to Cloud_Run_Backend.
2. THE Pipeline SHALL set the Cloud_Run_Backend region using the Substitution_Variable for region.
3. THE Pipeline SHALL configure Cloud_Run_Backend to use the Backend_SA service account identity via the `--service-account` flag.

### Requirement 6: Frontend Deployment to Cloud Run

**User Story:** As a DevOps engineer, I want the pipeline to deploy the newly built frontend image to Cloud Run, so that the live investor demo frontend is updated automatically.

#### Acceptance Criteria

1. WHEN the Frontend_Image is pushed to Artifact_Registry, THE Pipeline SHALL deploy the Frontend_Image (tagged with Short_SHA) to Cloud_Run_Frontend.
2. THE Pipeline SHALL set the Cloud_Run_Frontend region using the Substitution_Variable for region.
3. THE Pipeline SHALL configure Cloud_Run_Frontend to use the Frontend_SA service account identity via the `--service-account` flag.

### Requirement 7: Cloud Build Trigger Configuration

**User Story:** As a DevOps engineer, I want a Cloud Build trigger that fires on pushes to the main branch, so that deployments are fully automated.

#### Acceptance Criteria

1. THE Build_Trigger SHALL execute the Pipeline when code is pushed to the `main` branch of the repository.
2. THE Build_Trigger SHALL reference the `cloudbuild.yaml` file at the repository root.
3. THE Build_Trigger SHALL pass all required Substitution_Variables (project ID, region, repository name, service names, service account emails) to the Pipeline.

### Requirement 8: Cloud Build Service Account Permissions

**User Story:** As a security engineer, I want the Cloud Build service account to have only the permissions needed to build, push, and deploy, so that the CI/CD pipeline follows least-privilege principles.

#### Acceptance Criteria

1. THE Cloud_Build_SA SHALL have the `roles/artifactregistry.writer` role to push images to Artifact_Registry.
2. THE Cloud_Build_SA SHALL have the `roles/run.admin` role to deploy new revisions to Cloud Run.
3. THE Cloud_Build_SA SHALL have the `roles/iam.serviceAccountUser` role to act as the Backend_SA and Frontend_SA when deploying Cloud Run services.
4. IF the Cloud_Build_SA is granted a role not listed in the approved set (artifactregistry.writer, run.admin, iam.serviceAccountUser, logging.logWriter, storage.objectViewer), THEN THE Pipeline configuration SHALL be rejected during review.

### Requirement 9: Pipeline Execution Order and Dependencies

**User Story:** As a DevOps engineer, I want the pipeline steps to execute in the correct order, so that images are built before they are pushed and deployed.

#### Acceptance Criteria

1. THE Pipeline SHALL execute the Backend_Image build step and Frontend_Image build step before any deploy steps.
2. THE Pipeline SHALL execute the Cloud_Run_Backend deploy step only after the Backend_Image build step completes.
3. THE Pipeline SHALL execute the Cloud_Run_Frontend deploy step only after the Frontend_Image build step completes.
4. THE Pipeline SHALL allow the Backend_Image build and Frontend_Image build steps to execute in parallel using Cloud Build `waitFor` directives.

### Requirement 10: Terragrunt Module for Cloud Build Trigger

**User Story:** As a DevOps engineer, I want the Cloud Build trigger provisioned via Terragrunt, so that the CI/CD infrastructure is managed as code alongside other GCP resources.

#### Acceptance Criteria

1. THE Terragrunt Child_Module for Cloud Build SHALL provision a `google_cloudbuild_trigger` resource.
2. THE Terragrunt Child_Module SHALL configure the trigger to watch the `main` branch.
3. THE Terragrunt Child_Module SHALL set the trigger's `filename` to `cloudbuild.yaml`.
4. THE Terragrunt Child_Module SHALL pass all Substitution_Variables as trigger substitutions.
5. THE Terragrunt Child_Module SHALL output the trigger ID and name for reference by other modules or documentation.
