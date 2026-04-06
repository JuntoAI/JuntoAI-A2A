# -----------------------------------------------------------------------------
# Enable Secret Manager API
# -----------------------------------------------------------------------------

resource "google_project_service" "secretmanager" {
  project = var.gcp_project_id
  service = "secretmanager.googleapis.com"

  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Secret Manager — AWS SES credentials for email verification (cloud only)
#
# Terraform creates the secret shells + IAM bindings only.
# Secret values are set manually in GCP Console → Secret Manager.
# The lifecycle block prevents Terraform from overwriting manual values.
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret" "admin_password" {
  secret_id = "admin-password"
  project   = var.gcp_project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "aws_ses_access_key_id" {
  secret_id = "aws-ses-access-key-id"
  project   = var.gcp_project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "aws_ses_secret_access_key" {
  secret_id = "aws-ses-secret-access-key"
  project   = var.gcp_project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

# -----------------------------------------------------------------------------
# Grant backend SA access to read the secrets
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret_iam_member" "backend_admin_password" {
  secret_id = google_secret_manager_secret.admin_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.backend_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "backend_access_key" {
  secret_id = google_secret_manager_secret.aws_ses_access_key_id.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.backend_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "backend_secret_key" {
  secret_id = google_secret_manager_secret.aws_ses_secret_access_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.backend_sa_email}"
}
