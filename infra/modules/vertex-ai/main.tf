resource "google_project_service" "vertex_ai" {
  project = var.gcp_project_id
  service = "aiplatform.googleapis.com"

  disable_on_destroy = false
}
