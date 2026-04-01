output "backend_service_url" {
  description = "URL of the backend Cloud Run service"
  value       = google_cloud_run_v2_service.backend.uri
}

output "frontend_service_url" {
  description = "URL of the frontend Cloud Run service"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "domain_mapping_dns_records" {
  description = "DNS records to configure in Route 53 for the custom domain"
  value       = var.custom_domain != "" ? google_cloud_run_domain_mapping.frontend[0].status[0].resource_records : []
}
