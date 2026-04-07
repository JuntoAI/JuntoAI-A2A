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

# Composite index for negotiation history query:
# WHERE owner_email == X AND created_at >= Y ORDER BY created_at DESC
resource "google_firestore_index" "negotiation_sessions_owner_created" {
  project    = var.gcp_project_id
  database   = google_firestore_database.database.name
  collection = "negotiation_sessions"

  fields {
    field_path = "owner_email"
    order      = "ASCENDING"
  }

  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
}
