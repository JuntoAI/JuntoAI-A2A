resource "google_artifact_registry_repository" "docker" {
  repository_id = var.repository_id
  location      = var.gcp_region
  format        = "DOCKER"
  project       = var.gcp_project_id

  # Auto-delete untagged images and keep only the 5 most recent tagged versions
  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state = "UNTAGGED"
    }
  }

  cleanup_policies {
    id     = "keep-recent-tagged"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }
}
