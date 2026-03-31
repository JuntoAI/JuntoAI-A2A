resource "google_project_service" "firestore" {
  project = var.gcp_project_id
  service = "firestore.googleapis.com"

  disable_on_destroy = false
}

resource "google_firestore_database" "database" {
  project     = var.gcp_project_id
  name        = "(default)"
  location_id = var.gcp_region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.firestore]
}
