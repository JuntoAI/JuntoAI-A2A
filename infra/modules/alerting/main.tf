# -----------------------------------------------------------------------------
# GCP API Enablement
# -----------------------------------------------------------------------------

resource "google_project_service" "monitoring" {
  project = var.gcp_project_id
  service = "monitoring.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "cloudfunctions" {
  project = var.gcp_project_id
  service = "cloudfunctions.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "pubsub" {
  project = var.gcp_project_id
  service = "pubsub.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild" {
  project = var.gcp_project_id
  service = "cloudbuild.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "eventarc" {
  project = var.gcp_project_id
  service = "eventarc.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "run" {
  project = var.gcp_project_id
  service = "run.googleapis.com"

  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Pub/Sub Topic and Notification Channel (Task 2)
# -----------------------------------------------------------------------------

# 2.1 — Pub/Sub topic for all alert notifications
resource "google_pubsub_topic" "alerting" {
  project = var.gcp_project_id
  name    = "juntoai-alerting-notifications"

  depends_on = [google_project_service.pubsub]
}

# 2.2 — Notification channel (type: pubsub) referencing the topic
resource "google_monitoring_notification_channel" "pubsub" {
  project      = var.gcp_project_id
  display_name = "Alerting Pub/Sub Notification Channel"
  type         = "pubsub"

  labels = {
    topic = google_pubsub_topic.alerting.id
  }

  depends_on = [google_project_service.monitoring]
}

# 2.3 — Grant roles/pubsub.publisher to the GCP monitoring service account on the topic
resource "google_pubsub_topic_iam_member" "monitoring_publisher" {
  project = var.gcp_project_id
  topic   = google_pubsub_topic.alerting.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${var.gcp_project_number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
}

# 2.4 — Pub/Sub subscription for the Cloud Function
# The Pub/Sub event trigger on the Cloud Function (Task 9) automatically creates
# a subscription. No separate google_pubsub_subscription resource is needed here.

# -----------------------------------------------------------------------------
# Service Account and IAM (Task 3)
# -----------------------------------------------------------------------------

# 3.1 — Dedicated service account for the Cloud Function
resource "google_service_account" "alerting" {
  project      = var.gcp_project_id
  account_id   = "alerting-notifier-sa"
  display_name = "Alerting Notifier Cloud Function SA"
}

# 3.2 — Grant roles/pubsub.subscriber to the service account
resource "google_project_iam_member" "alerting_pubsub_subscriber" {
  project = var.gcp_project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.alerting.email}"
}

# 3.3 — Grant roles/cloudfunctions.invoker to the service account
resource "google_project_iam_member" "alerting_cloudfunctions_invoker" {
  project = var.gcp_project_id
  role    = "roles/cloudfunctions.invoker"
  member  = "serviceAccount:${google_service_account.alerting.email}"
}

# 3.4 — Secret Manager IAM bindings (roles/secretmanager.secretAccessor)
# Scoped to individual Telegram secrets — see IAM bindings in Task 4 section below.

# -----------------------------------------------------------------------------
# Secrets Management (Task 4)
# -----------------------------------------------------------------------------

# 4.1 — Secret Manager secret for the Telegram bot token
resource "google_secret_manager_secret" "telegram_bot_token" {
  project   = var.gcp_project_id
  secret_id = "telegram-bot-token"

  replication {
    auto {}
  }
}

# 4.2 — Secret Manager secret for the Telegram chat ID
resource "google_secret_manager_secret" "telegram_chat_id" {
  project   = var.gcp_project_id
  secret_id = "telegram-chat-id"

  replication {
    auto {}
  }
}

# 4.3 — Grant roles/secretmanager.secretAccessor to the alerting SA on each secret
resource "google_secret_manager_secret_iam_member" "alerting_bot_token_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.telegram_bot_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.alerting.email}"
}

resource "google_secret_manager_secret_iam_member" "alerting_chat_id_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.telegram_chat_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.alerting.email}"
}

# -----------------------------------------------------------------------------
# Log-Based Metrics (Task 5)
# -----------------------------------------------------------------------------

# 5.1 — Backend error log count (severity >= ERROR)
resource "google_logging_metric" "backend_error_log_count" {
  project = var.gcp_project_id
  name    = "backend/error-log-count"
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.backend_service_name}\" AND severity >= ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# 5.2 — Backend fatal log count (severity = CRITICAL)
resource "google_logging_metric" "backend_fatal_log_count" {
  project = var.gcp_project_id
  name    = "backend/fatal-log-count"
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.backend_service_name}\" AND severity = CRITICAL"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# 5.3 — Frontend error log count (severity >= ERROR)
resource "google_logging_metric" "frontend_error_log_count" {
  project = var.gcp_project_id
  name    = "frontend/error-log-count"
  filter  = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.frontend_service_name}\" AND severity >= ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# -----------------------------------------------------------------------------
# Alerting Policies — Log-Based (Task 6)
# -----------------------------------------------------------------------------

# 6.1 — Backend Error Log Rate (severity >= ERROR, 5-min alignment, medium)
resource "google_monitoring_alert_policy" "backend_error_log_rate" {
  project      = var.gcp_project_id
  display_name = "Backend Error Log Rate"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "medium"
  }

  conditions {
    display_name = "Backend error log count above threshold"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.backend_error_log_count.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backend_error_threshold
      duration        = "60s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }

      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# 6.2 — Backend Fatal Log (severity = CRITICAL, 1-min alignment, critical)
resource "google_monitoring_alert_policy" "backend_fatal_log" {
  project      = var.gcp_project_id
  display_name = "Backend Fatal Log"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "critical"
  }

  conditions {
    display_name = "Backend fatal log count above threshold"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.backend_fatal_log_count.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backend_fatal_threshold
      duration        = "60s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }

      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# 6.3 — Frontend Error Log Rate (severity >= ERROR, 5-min alignment, medium)
resource "google_monitoring_alert_policy" "frontend_error_log_rate" {
  project      = var.gcp_project_id
  display_name = "Frontend Error Log Rate"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "medium"
  }

  conditions {
    display_name = "Frontend error log count above threshold"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.frontend_error_log_count.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.frontend_error_threshold
      duration        = "60s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }

      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# -----------------------------------------------------------------------------
# Alerting Policies — Cloud Run Metrics (Task 7)
# -----------------------------------------------------------------------------

# 7.1 — Backend High CPU (P99 utilization > threshold, two consecutive 5-min periods, high)
resource "google_monitoring_alert_policy" "backend_high_cpu" {
  project      = var.gcp_project_id
  display_name = "Backend High CPU"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "high"
  }

  conditions {
    display_name = "Backend CPU utilization above threshold"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/container/cpu/utilizations\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.backend_service_name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backend_cpu_threshold
      duration        = "600s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
      }
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# 7.2 — Backend High Memory (P99 utilization > threshold, two consecutive 5-min periods, high)
resource "google_monitoring_alert_policy" "backend_high_memory" {
  project      = var.gcp_project_id
  display_name = "Backend High Memory"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "high"
  }

  conditions {
    display_name = "Backend memory utilization above threshold"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/container/memory/utilizations\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.backend_service_name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backend_memory_threshold
      duration        = "600s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
      }
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# 7.3 — Backend High Error Rate (5xx request count > threshold, 5-min alignment, high)
resource "google_monitoring_alert_policy" "backend_high_error_rate" {
  project      = var.gcp_project_id
  display_name = "Backend High Error Rate"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "high"
  }

  conditions {
    display_name = "Backend 5xx request count above threshold"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.backend_service_name}\" AND metric.labels.response_code_class=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backend_5xx_threshold
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# 7.4 — Frontend High Error Rate (5xx request count > threshold, 5-min alignment, high)
resource "google_monitoring_alert_policy" "frontend_high_error_rate" {
  project      = var.gcp_project_id
  display_name = "Frontend High Error Rate"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "high"
  }

  conditions {
    display_name = "Frontend 5xx request count above threshold"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.frontend_service_name}\" AND metric.labels.response_code_class=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.frontend_5xx_threshold
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# 7.5 — Backend Instance Count Spike (instance count > threshold, 5-min alignment, high)
resource "google_monitoring_alert_policy" "backend_instance_count_spike" {
  project      = var.gcp_project_id
  display_name = "Backend Instance Count Spike"
  combiner     = "OR"
  enabled      = true

  notification_channels = [google_monitoring_notification_channel.pubsub.name]

  user_labels = {
    severity = "high"
  }

  conditions {
    display_name = "Backend instance count above threshold"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/container/instance_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.backend_service_name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.backend_instance_threshold
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  alert_strategy {
    auto_close = "${var.auto_close_seconds}s"
  }

  depends_on = [google_project_service.monitoring]
}

# -----------------------------------------------------------------------------
# Cloud Function Deployment (Task 9)
# -----------------------------------------------------------------------------

# 9.1 — Archive the function source directory into a zip file
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = "${path.module}/function"
  output_path = "${path.module}/function.zip"
}

# 9.1 — GCS bucket for function source code
resource "google_storage_bucket" "function_source" {
  project                     = var.gcp_project_id
  name                        = "${var.gcp_project_id}-alerting-function-source"
  location                    = var.gcp_region
  force_destroy               = true
  uniform_bucket_level_access = true
}

# 9.1 — Upload the zipped function source to GCS
resource "google_storage_bucket_object" "function_source" {
  name   = "function-source-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.function_source.output_path
}

# 9.2 — Grant the default Compute SA permissions for Cloud Function builds
resource "google_project_iam_member" "compute_logs_writer" {
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${var.gcp_project_number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_ar_writer" {
  project = var.gcp_project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${var.gcp_project_number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_storage_viewer" {
  project = var.gcp_project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${var.gcp_project_number}-compute@developer.gserviceaccount.com"
}

# 9.2 — Cloud Function (2nd gen) for alerting notifications (Pub/Sub trigger)
resource "google_cloudfunctions2_function" "notifier" {
  project  = var.gcp_project_id
  name     = "juntoai-telegram-notifier"
  location = var.gcp_region

  build_config {
    runtime     = "python311"
    entry_point = "handle_pubsub"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.alerting.email

    environment_variables = {
      GCP_PROJECT = var.gcp_project_id
    }
  }

  event_trigger {
    trigger_region = var.gcp_region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.alerting.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.cloudbuild,
    google_project_service.eventarc,
    google_project_service.run,
  ]
}

# 9.2a — Grant the default Compute SA roles/run.invoker on the alerting
# Cloud Function service. Eventarc triggers use this SA to push Pub/Sub
# messages to the Cloud Run service backing the function.
resource "google_cloud_run_service_iam_member" "notifier_invoker" {
  project  = var.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.notifier.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.gcp_project_number}-compute@developer.gserviceaccount.com"
}

# 9.3 — Ensure the cloud-builds topic exists (GCP auto-creates it on first build,
# but we need it to exist for the event trigger)
resource "google_pubsub_topic" "cloud_builds" {
  project = var.gcp_project_id
  name    = "cloud-builds"

  depends_on = [google_project_service.pubsub]
}

# 9.3a — Grant the Cloud Build service agent roles/pubsub.publisher on the
# cloud-builds topic. When triggers use a custom service account (not the
# default Cloud Build SA), GCP does NOT auto-publish build events to the
# cloud-builds topic. This IAM binding enables the service agent to publish.
resource "google_pubsub_topic_iam_member" "cloudbuild_publisher" {
  project = var.gcp_project_id
  topic   = google_pubsub_topic.cloud_builds.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${var.gcp_project_number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}

# 9.3 — Second Cloud Function (2nd gen) for Cloud Build events
# Cloud Functions 2nd gen supports only one event trigger per function,
# so we deploy a second function with identical config but triggered by
# the cloud-builds topic.
resource "google_cloudfunctions2_function" "notifier_builds" {
  project  = var.gcp_project_id
  name     = "juntoai-telegram-notifier-builds"
  location = var.gcp_region

  build_config {
    runtime     = "python311"
    entry_point = "handle_pubsub"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.alerting.email

    environment_variables = {
      GCP_PROJECT = var.gcp_project_id
    }
  }

  event_trigger {
    trigger_region = var.gcp_region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.cloud_builds.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.cloudbuild,
    google_project_service.eventarc,
    google_project_service.run,
  ]
}

# 9.3b — Grant the default Compute SA roles/run.invoker on the builds
# Cloud Function service. Eventarc triggers use this SA to push Pub/Sub
# messages to the Cloud Run service backing the function.
resource "google_cloud_run_service_iam_member" "notifier_builds_invoker" {
  project  = var.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.notifier_builds.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.gcp_project_number}-compute@developer.gserviceaccount.com"
}
