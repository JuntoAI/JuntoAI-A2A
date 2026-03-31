variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "enable_run_invoker" {
  description = "Whether to grant Backend_SA the roles/run.invoker role for inter-service invocation"
  type        = bool
  default     = false
}

variable "allowed_roles" {
  description = "Allowlist of IAM roles permitted for service accounts in this module"
  type        = list(string)
  default = [
    "roles/datastore.user",
    "roles/aiplatform.user",
    "roles/run.invoker",
  ]

  validation {
    condition = alltrue([
      for role in var.allowed_roles :
      contains(["roles/datastore.user", "roles/aiplatform.user", "roles/run.invoker"], role)
    ])
    error_message = "Only approved roles are permitted: roles/datastore.user, roles/aiplatform.user, roles/run.invoker."
  }
}
