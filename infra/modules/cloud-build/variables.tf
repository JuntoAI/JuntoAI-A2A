variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for Cloud Run and Artifact Registry"
  type        = string
}

variable "repository_id" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "juntoai-docker"
}

variable "backend_service_name" {
  description = "Cloud Run backend service name"
  type        = string
  default     = "juntoai-backend"
}

variable "frontend_service_name" {
  description = "Cloud Run frontend service name"
  type        = string
  default     = "juntoai-frontend"
}

variable "backend_sa_email" {
  description = "Backend service account email (from iam/ module output)"
  type        = string
}

variable "frontend_sa_email" {
  description = "Frontend service account email (from iam/ module output)"
  type        = string
}

variable "backend_trigger_enabled" {
  description = "Whether the backend Cloud Build trigger is active."
  type        = bool
  default     = true
}

variable "frontend_trigger_enabled" {
  description = "Whether the frontend Cloud Build trigger is active."
  type        = bool
  default     = true
}

variable "fullstack_trigger_enabled" {
  description = "Whether the fullstack Cloud Build trigger is active. Disable when using individual triggers."
  type        = bool
  default     = false
}

variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "firebase_api_key" {
  description = "Firebase web app API key for frontend build"
  type        = string
}

variable "firebase_app_id" {
  description = "Firebase web app ID for frontend build"
  type        = string
}

variable "allowed_roles" {
  description = "Allowlist of IAM roles permitted for the Cloud Build service account"
  type        = list(string)
  default = [
    "roles/artifactregistry.writer",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/logging.logWriter",
  ]

  validation {
    condition = alltrue([
      for role in var.allowed_roles :
      contains(["roles/artifactregistry.writer", "roles/run.admin", "roles/iam.serviceAccountUser", "roles/logging.logWriter"], role)
    ])
    error_message = "Only approved roles are permitted: roles/artifactregistry.writer, roles/run.admin, roles/iam.serviceAccountUser, roles/logging.logWriter."
  }
}
