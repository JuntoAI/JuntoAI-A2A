output "aws_ses_access_key_id_secret_name" {
  description = "Secret Manager resource name for AWS SES access key ID"
  value       = google_secret_manager_secret.aws_ses_access_key_id.secret_id
}

output "aws_ses_secret_access_key_secret_name" {
  description = "Secret Manager resource name for AWS SES secret access key"
  value       = google_secret_manager_secret.aws_ses_secret_access_key.secret_id
}
