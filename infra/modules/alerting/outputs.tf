output "pubsub_topic_name" {
  description = "Name of the alerting Pub/Sub topic"
  value       = google_pubsub_topic.alerting.name
}

output "notifier_function_url" {
  description = "URL of the Telegram notifier Cloud Function"
  value       = google_cloudfunctions2_function.notifier.url
}

output "alerting_sa_email" {
  description = "Email of the alerting service account"
  value       = google_service_account.alerting.email
}
