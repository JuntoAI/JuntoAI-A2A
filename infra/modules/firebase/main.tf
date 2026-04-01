resource "google_project_service" "firebase" {
  project = var.gcp_project_id
  service = "firebase.googleapis.com"

  disable_on_destroy = false
}

resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.gcp_project_id

  depends_on = [google_project_service.firebase]
}

resource "google_firebase_web_app" "frontend" {
  provider     = google-beta
  project      = var.gcp_project_id
  display_name = var.display_name

  depends_on = [google_firebase_project.default]
}

data "google_firebase_web_app_config" "frontend" {
  provider   = google-beta
  project    = var.gcp_project_id
  web_app_id = google_firebase_web_app.frontend.app_id
}
