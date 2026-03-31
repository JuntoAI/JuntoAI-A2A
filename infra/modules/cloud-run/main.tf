# -----------------------------------------------------------------------------
# Cloud Run Services
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "backend" {
  name     = var.backend_service_name
  location = var.gcp_region

  template {
    service_account = var.backend_sa_email

    containers {
      image = var.backend_image
    }
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
}
