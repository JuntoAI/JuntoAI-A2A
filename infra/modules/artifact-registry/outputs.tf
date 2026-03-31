output "repository_path" {
  description = "Full Artifact Registry repository path for Docker images"
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${var.repository_id}"
}
