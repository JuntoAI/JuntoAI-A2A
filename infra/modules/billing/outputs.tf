output "billing_export_dataset_id" {
  description = "BigQuery dataset ID that receives the Cloud Billing export"
  value       = google_bigquery_dataset.billing_export.dataset_id
}

output "billing_export_dataset_ref" {
  description = "Fully qualified dataset reference, for use in the Console export settings"
  value       = "${google_bigquery_dataset.billing_export.project}:${google_bigquery_dataset.billing_export.dataset_id}"
}

output "budget_name" {
  description = "Resource name of the monthly budget"
  value       = google_billing_budget.monthly.name
}
