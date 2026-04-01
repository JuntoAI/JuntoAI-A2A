output "backend_trigger_id" {
  description = "Cloud Build backend trigger ID"
  value       = google_cloudbuild_trigger.backend.trigger_id
}

output "frontend_trigger_id" {
  description = "Cloud Build frontend trigger ID"
  value       = google_cloudbuild_trigger.frontend.trigger_id
}

output "fullstack_trigger_id" {
  description = "Cloud Build fullstack trigger ID"
  value       = google_cloudbuild_trigger.fullstack.trigger_id
}

output "backend_trigger_name" {
  description = "Cloud Build backend trigger name"
  value       = google_cloudbuild_trigger.backend.name
}

output "frontend_trigger_name" {
  description = "Cloud Build frontend trigger name"
  value       = google_cloudbuild_trigger.frontend.name
}

output "fullstack_trigger_name" {
  description = "Cloud Build fullstack trigger name"
  value       = google_cloudbuild_trigger.fullstack.name
}

output "cloudbuild_sa_email" {
  description = "Cloud Build service account email"
  value       = google_service_account.cloudbuild.email
}
