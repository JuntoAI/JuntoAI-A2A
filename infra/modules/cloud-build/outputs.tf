output "trigger_id" {
  description = "Cloud Build trigger ID"
  value       = google_cloudbuild_trigger.main.trigger_id
}

output "trigger_name" {
  description = "Cloud Build trigger name"
  value       = google_cloudbuild_trigger.main.name
}

output "cloudbuild_sa_email" {
  description = "Cloud Build service account email"
  value       = google_service_account.cloudbuild.email
}
