resource "google_artifact_registry_repository" "docker" {
  repository_id = var.repository_id
  location      = var.gcp_region
  format        = "DOCKER"
  project       = var.gcp_project_id
}
