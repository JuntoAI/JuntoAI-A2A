output "backend_sa_email" {
  description = "Email address of the Backend service account"
  value       = google_service_account.backend.email
}

output "frontend_sa_email" {
  description = "Email address of the Frontend service account"
  value       = google_service_account.frontend.email
}
