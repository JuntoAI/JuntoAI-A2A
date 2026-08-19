variable "gcp_project_id" {
  description = "GCP project ID that hosts the billing export dataset"
  type        = string
}

variable "gcp_region" {
  description = "GCP region (passed by root.hcl; the dataset uses billing_export_location)"
  type        = string
}

variable "billing_account_id" {
  description = "Cloud Billing account ID that funds this project, without the 'billingAccounts/' prefix (e.g. 01F691-B995EA-A93C8F)."
  type        = string

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "billing_account_id must look like 01F691-B995EA-A93C8F."
  }
}

# -----------------------------------------------------------------------------
# BigQuery billing export
# -----------------------------------------------------------------------------

variable "billing_export_dataset_id" {
  description = "BigQuery dataset that receives Cloud Billing export tables."
  type        = string
  default     = "billing_export"
}

variable "billing_export_location" {
  description = "BigQuery dataset location. Must be a multi-region or region; EU keeps billing data in Europe."
  type        = string
  default     = "EU"
}

# -----------------------------------------------------------------------------
# Budget
# -----------------------------------------------------------------------------

variable "budget_amount" {
  description = "Monthly budget in budget_currency. Set this to the credit grant divided across the months you expect it to last, NOT to your current spend."
  type        = number
  default     = 100
}

variable "budget_currency" {
  description = "Currency for the budget amount. Must match the billing account currency."
  type        = string
  default     = "EUR"
}

variable "budget_thresholds" {
  description = "Fractions of budget_amount at which to alert on ACTUAL spend."
  type        = list(number)
  default     = [0.5, 0.75, 0.9, 1.0]
}

variable "budget_forecast_thresholds" {
  description = "Fractions of budget_amount at which to alert on FORECASTED spend. Forecast alerts are the ones that give you time to react."
  type        = list(number)
  default     = [1.0]
}

variable "budget_pubsub_topic" {
  description = "Optional Pub/Sub topic ID (projects/<p>/topics/<t>) for programmatic budget notifications. Budget messages use their own schema, so the consumer must handle it explicitly. Empty string disables."
  type        = string
  default     = ""
}

variable "budget_monitoring_notification_channels" {
  description = "Optional Cloud Monitoring notification channel IDs for budget alerts. Cloud Billing only accepts EMAIL-type channels here, so the pubsub-type channel created by the alerting module will not work. Empty list disables."
  type        = list(string)
  default     = []
}

variable "budget_disable_default_iam_recipients" {
  description = "Only takes effect when budget_pubsub_topic or budget_monitoring_notification_channels is set, because it lives inside all_updates_rule. When false, Cloud Billing emails budget alerts to billing account admins and users."
  type        = bool
  default     = false
}
