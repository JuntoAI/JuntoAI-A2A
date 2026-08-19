# -----------------------------------------------------------------------------
# Cloud Run Services
# -----------------------------------------------------------------------------
#
# OWNERSHIP CONTRACT — read before editing `lifecycle.ignore_changes` below.
#
#   Terraform owns: scaling (min/max), CPU + memory limits, cpu_idle, timeout,
#                   session affinity, concurrency, service account, IAM, domain.
#   Cloud Build owns: container image, env vars, and the traffic block
#                     (canary tag + traffic migration).
#
# Because `traffic` is ignored here, Terraform can NOT remove a revision tag.
# Cloud Build MUST untag the canary after migrating traffic — see the
# `remove-*-canary-tag` steps in cloudbuild-backend.yaml / cloudbuild-frontend.yaml.
#
# Why it matters: a tagged revision gets its own dedicated URL, so Cloud Run
# honours that revision's min-instances indefinitely even at 0% traffic. In
# Apr-Aug 2026 an untagged-but-never-cleaned canary with min-instances=1 and
# CPU always allocated ran 24/7 and accounted for ~66% of the GCP bill while
# serving zero requests. Terraform kept resetting the *serving* revision to the
# correct config and could not touch the orphaned tagged one.
#
# Also note: `gcloud run deploy` inherits any unspecified flag from the previous
# revision. The Cloud Build deploy steps therefore pin scaling and cpu_idle
# explicitly, mirroring the defaults in variables.tf. Keep the two in sync.
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

    # Scaling: scale to zero when idle to eliminate costs
    scaling {
      min_instance_count = var.backend_min_instances
      max_instance_count = var.backend_max_instances
    }

    containers {
      image = var.backend_image

      resources {
        limits = {
          cpu    = var.backend_cpu
          memory = var.backend_memory
        }
        cpu_idle = var.backend_cpu_idle
      }
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

    # Scaling: scale to zero when idle
    scaling {
      min_instance_count = var.frontend_min_instances
      max_instance_count = var.frontend_max_instances
    }

    containers {
      image = var.frontend_image

      resources {
        limits = {
          cpu    = var.frontend_cpu
          memory = var.frontend_memory
        }
        cpu_idle = var.frontend_cpu_idle
      }
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
# Public Access — Frontend
# -----------------------------------------------------------------------------
# NOTE: allUsers binding is managed via GCP Console due to org policy
# constraint (constraints/iam.allowedPolicyMemberDomains) that blocks
# allUsers in IAM bindings via API/Terraform. Do NOT add an IAM resource
# here — it will fail on apply.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Public Access — Backend (allUsers → roles/run.invoker)
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  count    = var.enable_backend_public_access ? 1 : 0
  project  = google_cloud_run_v2_service.backend.project
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# -----------------------------------------------------------------------------
# Backend Invoker — Least-privilege access (e.g. frontend SA only)
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "backend_invoker" {
  for_each = toset(var.backend_invoker_members)
  project  = google_cloud_run_v2_service.backend.project
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = each.value
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
