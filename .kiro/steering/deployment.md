# JuntoAI A2A MVP — Deployment Guide

## Infrastructure: Terragrunt Only
- **Never** create or modify GCP resources manually via Console or CLI
- **Always** run `terragrunt plan` before `terragrunt apply`
- All infrastructure defined in `/infra/modules/` as Terraform files

```bash
cd infra
terragrunt plan    # Review changes
terragrunt apply   # Deploy infrastructure
```

## Application: CI/CD Pipeline Only
- **Never** manually push Docker images or deploy Cloud Run services
- Pushing to `main` triggers Google Cloud Build automatically
- Cloud Build builds Docker images, pushes to Artifact Registry, deploys to Cloud Run

```bash
git push origin main   # Triggers full build + deploy
```

## Pipeline Flow
1. Push to `main` → Cloud Build trigger fires
2. Build backend Docker image from `/backend/Dockerfile`
3. Build frontend Docker image from `/frontend/Dockerfile`
4. Push both images to Artifact Registry (tagged with commit SHA + `latest`)
5. Deploy backend image to Cloud Run (Backend service)
6. Deploy frontend image to Cloud Run (Frontend service)

## Remote State
- **Backend**: GCS bucket `juntoai-terraform-state-prod`
- **Locking**: GCS native locking (no separate lock table needed)
- **Region**: EU

## Branch Strategy
- `main` — production deployments (auto-deploy via Cloud Build)
- `feature/*` — feature branches, create PR to merge into `main`
- Never commit directly to `main`

## Cloud Build Service Account
Requires these roles (least-privilege):
- `roles/artifactregistry.writer` — push images
- `roles/run.admin` — deploy to Cloud Run
- `roles/iam.serviceAccountUser` — act as Backend_SA / Frontend_SA
