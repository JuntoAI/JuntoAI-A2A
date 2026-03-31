variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for the Artifact Registry repository"
  type        = string
}

variable "repository_id" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "juntoai-docker"
}
