output "api_key" {
  description = "Firebase web app API key (NEXT_PUBLIC_FIREBASE_API_KEY)"
  value       = data.google_firebase_web_app_config.frontend.api_key
}

output "project_id" {
  description = "Firebase project ID (NEXT_PUBLIC_FIREBASE_PROJECT_ID)"
  value       = var.gcp_project_id
}

output "app_id" {
  description = "Firebase web app ID (NEXT_PUBLIC_FIREBASE_APP_ID)"
  value       = google_firebase_web_app.frontend.app_id
}
