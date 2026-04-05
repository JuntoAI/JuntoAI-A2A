variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "backend_sa_email" {
  description = "Backend service account email — granted secretAccessor on SES secrets"
  type        = string
}
