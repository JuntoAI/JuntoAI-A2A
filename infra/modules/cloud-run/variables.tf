variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for Cloud Run services"
  type        = string
}

variable "backend_sa_email" {
  description = "Email address of the Backend service account"
  type        = string
}

variable "frontend_sa_email" {
  description = "Email address of the Frontend service account"
  type        = string
}

variable "backend_image" {
  description = "Full Docker image URI for the backend service"
  type        = string
  default     = "gcr.io/cloudrun/placeholder"
}

variable "frontend_image" {
  description = "Full Docker image URI for the frontend service"
  type        = string
  default     = "gcr.io/cloudrun/placeholder"
}

variable "backend_service_name" {
  description = "Name of the backend Cloud Run service"
  type        = string
  default     = "juntoai-backend"
}

variable "frontend_service_name" {
  description = "Name of the frontend Cloud Run service"
  type        = string
  default     = "juntoai-frontend"
}

variable "enable_backend_public_access" {
  description = "Whether to allow unauthenticated (public) access to the backend service. Prefer false and use backend_invoker_members for least-privilege."
  type        = bool
  default     = false
}

variable "backend_invoker_members" {
  description = "IAM members granted roles/run.invoker on the backend (e.g. frontend SA). Use instead of public access."
  type        = list(string)
  default     = []
}

variable "custom_domain" {
  description = "Custom domain to map to the frontend service (e.g. a2a.juntoai.org). Empty string disables."
  type        = string
  default     = ""
}

variable "backend_instance_shutdown_timeout" {
  description = "Seconds Cloud Run waits for in-flight requests (SSE streams) to finish before killing the old revision during traffic migration. Max 3600."
  type        = number
  default     = 1200
}
