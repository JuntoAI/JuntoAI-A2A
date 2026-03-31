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
