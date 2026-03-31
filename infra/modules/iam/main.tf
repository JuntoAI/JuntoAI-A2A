# -----------------------------------------------------------------------------
# Service Accounts
# -----------------------------------------------------------------------------

resource "google_service_account" "backend" {
  account_id   = "backend-sa"
  display_name = "Backend Cloud Run Service Account"
  project      = var.gcp_project_id
}

resource "google_service_account" "frontend" {
  account_id   = "frontend-sa"
  display_name = "Frontend Cloud Run Service Account"
  project      = var.gcp_project_id
}

# -----------------------------------------------------------------------------
# Backend_SA Role Bindings
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "backend_datastore" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_aiplatform" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend.email}"
}

resource "google_project_iam_member" "backend_run_invoker" {
  count   = var.enable_run_invoker ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.backend.email}"
}
