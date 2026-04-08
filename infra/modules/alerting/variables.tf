# -----------------------------------------------------------------------------
# Required Variables
# -----------------------------------------------------------------------------

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_project_number" {
  description = "GCP project number (used for monitoring service account IAM binding)"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for alerting resources"
  type        = string
}

variable "backend_service_name" {
  description = "Name of the backend Cloud Run service"
  type        = string
}

variable "frontend_service_name" {
  description = "Name of the frontend Cloud Run service"
  type        = string
}

# -----------------------------------------------------------------------------
# Alerting Thresholds — tunable without modifying module source
# -----------------------------------------------------------------------------

variable "backend_error_threshold" {
  description = "Error log count threshold for backend alerting policy (5-min window)"
  type        = number
  default     = 5
}

variable "backend_fatal_threshold" {
  description = "Fatal log count threshold for backend alerting policy (1-min window)"
  type        = number
  default     = 0
}

variable "frontend_error_threshold" {
  description = "Error log count threshold for frontend alerting policy (5-min window)"
  type        = number
  default     = 5
}

variable "backend_cpu_threshold" {
  description = "CPU utilization threshold for backend alerting policy (0.0–1.0)"
  type        = number
  default     = 0.8
}

variable "backend_memory_threshold" {
  description = "Memory utilization threshold for backend alerting policy (0.0–1.0)"
  type        = number
  default     = 0.85
}

variable "backend_5xx_threshold" {
  description = "5xx response count threshold for backend alerting policy (5-min window)"
  type        = number
  default     = 10
}

variable "frontend_5xx_threshold" {
  description = "5xx response count threshold for frontend alerting policy (5-min window)"
  type        = number
  default     = 10
}

variable "backend_instance_threshold" {
  description = "Active instance count threshold for backend instance spike alerting policy"
  type        = number
  default     = 10
}

# -----------------------------------------------------------------------------
# Alerting Policy Configuration
# -----------------------------------------------------------------------------

variable "notification_rate_limit_seconds" {
  description = "Minimum seconds between notifications for each alerting policy"
  type        = number
  default     = 300
}

variable "auto_close_seconds" {
  description = "Seconds after which stale incidents are automatically closed"
  type        = number
  default     = 1800
}
