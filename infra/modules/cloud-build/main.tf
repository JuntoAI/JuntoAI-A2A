# -----------------------------------------------------------------------------
# Cloud Build Service Account
# -----------------------------------------------------------------------------

resource "google_service_account" "cloudbuild" {
  account_id   = "cloudbuild-sa"
  display_name = "Cloud Build CI/CD Service Account"
  project      = var.gcp_project_id
}

# -----------------------------------------------------------------------------
# Cloud Build SA IAM Role Bindings
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "cloudbuild_ar_writer" {
  project = var.gcp_project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

resource "google_project_iam_member" "cloudbuild_run_admin" {
  project = var.gcp_project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

resource "google_project_iam_member" "cloudbuild_sa_user" {
  project = var.gcp_project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

resource "google_project_iam_member" "cloudbuild_log_writer" {
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

# -----------------------------------------------------------------------------
# Cloud Build Trigger
# -----------------------------------------------------------------------------

resource "google_cloudbuild_trigger" "main" {
  name     = "juntoai-cicd-main"
  project  = var.gcp_project_id
  disabled = var.trigger_enabled ? false : true

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"

  substitutions = {
    _REGION            = var.gcp_region
    _PROJECT_ID        = var.gcp_project_id
    _REPO_NAME         = var.repository_id
    _BACKEND_SERVICE   = var.backend_service_name
    _FRONTEND_SERVICE  = var.frontend_service_name
    _BACKEND_SA_EMAIL  = var.backend_sa_email
    _FRONTEND_SA_EMAIL = var.frontend_sa_email
    _FIREBASE_API_KEY  = var.firebase_api_key
    _FIREBASE_APP_ID   = var.firebase_app_id
  }

  service_account = google_service_account.cloudbuild.id
}
