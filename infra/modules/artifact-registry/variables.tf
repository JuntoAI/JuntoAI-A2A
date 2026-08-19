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

# -----------------------------------------------------------------------------
# Cleanup policy tuning
# -----------------------------------------------------------------------------

variable "cleanup_dry_run" {
  description = "When true, cleanup policies only log what they would delete. Keep true until the delete list has been reviewed; image deletion is irreversible."
  type        = bool
  default     = true
}

variable "untagged_older_than_days" {
  description = "Delete UNTAGGED versions older than this many days."
  type        = number
  default     = 7
}

variable "tagged_older_than_days" {
  description = "Delete TAGGED versions older than this many days. Anything within keep_recent_versions survives regardless."
  type        = number
  default     = 90
}

variable "keep_recent_versions" {
  description = "Number of most recent versions always retained. Must be >= the Cloud Run revision retention used by scripts/prune_cloud_run_revisions.py, or a retained revision can lose its image."
  type        = number
  default     = 10
}
