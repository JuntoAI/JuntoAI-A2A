# -----------------------------------------------------------------------------
# Cloud Run Services
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "backend" {
  name     = var.backend_service_name
  location = var.gcp_region

  template {
    service_account = var.backend_sa_email

    # Allow old instances to finish in-flight SSE streams during traffic migration
    timeout                          = "${var.backend_instance_shutdown_timeout}s"
    session_affinity                 = true
    max_instance_request_concurrency = 80

    containers {
      image = var.backend_image
    }
  }

  # New revisions deploy with --no-traffic; traffic migrated separately
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      template[0].containers[0].env,
      client,
      client_version,
      traffic,
    ]
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  name     = var.frontend_service_name
  location = var.gcp_region

  template {
    service_account = var.frontend_sa_email

    containers {
      image = var.frontend_image
    }
  }

  # New revisions deploy with --no-traffic; traffic migrated separately
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      template[0].containers[0].env,
      client,
      client_version,
      traffic,
    ]
  }
}

# -----------------------------------------------------------------------------
# Public Access (allUsers → roles/run.invoker)
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  count    = var.enable_public_access ? 1 : 0
  project  = google_cloud_run_v2_service.backend.project
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  count    = var.enable_public_access ? 1 : 0
  project  = google_cloud_run_v2_service.frontend.project
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# -----------------------------------------------------------------------------
# Custom Domain Mapping
# -----------------------------------------------------------------------------

resource "google_cloud_run_domain_mapping" "frontend" {
  count    = var.custom_domain != "" ? 1 : 0
  location = var.gcp_region
  name     = var.custom_domain

  metadata {
    namespace = var.gcp_project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.frontend.name
  }
}
