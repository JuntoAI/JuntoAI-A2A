# Tasks

## Task 1: Terraform Module Scaffold
Create the alerting module directory structure and base files.

- [x] 1.1 Create `infra/modules/alerting/` directory with `main.tf`, `variables.tf`, `outputs.tf`, `backend.tf`
- [x] 1.2 Define all input variables in `variables.tf`: `gcp_project_id`, `gcp_region`, `backend_service_name`, `frontend_service_name`, and all threshold variables with defaults
- [x] 1.3 Add `backend.tf` with `terraform { backend "gcs" {} }`
- [x] 1.4 Add GCP API enablement resources in `main.tf`: `monitoring.googleapis.com`, `cloudfunctions.googleapis.com`, `pubsub.googleapis.com`, `cloudbuild.googleapis.com` with `disable_on_destroy = false`

## Task 2: Pub/Sub Topic and Notification Channel
Create the central notification infrastructure.

- [x] 2.1 Create `google_pubsub_topic.alerting` named `juntoai-alerting-notifications`
- [x] 2.2 Create `google_monitoring_notification_channel` of type `pubsub` referencing the topic
- [x] 2.3 Grant `roles/pubsub.publisher` to the GCP monitoring service account (`service-{project_number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com`) on the topic
- [x] 2.4 Create Pub/Sub subscription that triggers the Cloud Function

## Task 3: Service Account and IAM
Create the dedicated Cloud Function service account with least-privilege permissions.

- [x] 3.1 Create `google_service_account.alerting` with `account_id = "alerting-notifier-sa"`
- [x] 3.2 Grant `roles/pubsub.subscriber` to the service account
- [x] 3.3 Grant `roles/cloudfunctions.invoker` to the service account
- [x] 3.4 Grant `roles/secretmanager.secretAccessor` scoped to the two Telegram secrets (task 5)

## Task 4: Secrets Management
Create Secret Manager secrets for Telegram credentials.

- [x] 4.1 Create `google_secret_manager_secret` for `telegram-bot-token` with auto replication
- [x] 4.2 Create `google_secret_manager_secret` for `telegram-chat-id` with auto replication
- [x] 4.3 Add IAM bindings granting the alerting SA `roles/secretmanager.secretAccessor` on both secrets

## Task 5: Log-Based Metrics
Create Cloud Logging metrics for backend and frontend error detection.

- [x] 5.1 Create `google_logging_metric` for `backend/error-log-count` with filter `resource.type="cloud_run_revision" AND resource.labels.service_name="${var.backend_service_name}" AND severity >= ERROR`
- [x] 5.2 Create `google_logging_metric` for `backend/fatal-log-count` with filter `resource.type="cloud_run_revision" AND resource.labels.service_name="${var.backend_service_name}" AND severity = CRITICAL`
- [x] 5.3 Create `google_logging_metric` for `frontend/error-log-count` with filter `resource.type="cloud_run_revision" AND resource.labels.service_name="${var.frontend_service_name}" AND severity >= ERROR`

## Task 6: Alerting Policies — Log-Based
Create alerting policies for log-based error detection.

- [x] 6.1 Create alerting policy `Backend Error Log Rate`: threshold > `var.backend_error_threshold` (default 5), 5-min alignment, severity label `medium`, notification rate limit 300s, auto_close 1800s
- [x] 6.2 Create alerting policy `Backend Fatal Log`: threshold > `var.backend_fatal_threshold` (default 0), 1-min alignment, severity label `critical`
- [x] 6.3 Create alerting policy `Frontend Error Log Rate`: threshold > `var.frontend_error_threshold` (default 5), 5-min alignment, severity label `medium`
- [x] 6.4 Configure all log-based policies to treat absent data as not firing and send notifications on both open and close

## Task 7: Alerting Policies — Cloud Run Metrics
Create alerting policies for Cloud Run application metrics.

- [x] 7.1 Create alerting policy `Backend High CPU`: `run.googleapis.com/container/cpu/utilizations` > `var.backend_cpu_threshold` (default 0.8), two consecutive 5-min periods, severity `high`
- [x] 7.2 Create alerting policy `Backend High Memory`: `run.googleapis.com/container/memory/utilizations` > `var.backend_memory_threshold` (default 0.85), two consecutive 5-min periods, severity `high`
- [x] 7.3 Create alerting policy `Backend High Error Rate`: `run.googleapis.com/request_count` filtered by `response_code_class="5xx"` > `var.backend_5xx_threshold` (default 10), 5-min alignment, severity `high`
- [x] 7.4 Create alerting policy `Frontend High Error Rate`: same metric for frontend > `var.frontend_5xx_threshold` (default 10), severity `high`
- [x] 7.5 Create alerting policy `Backend Instance Count Spike`: `run.googleapis.com/container/instance_count` > `var.backend_instance_threshold` (default 10), 5-min alignment, severity `high`
- [x] 7.6 Configure all Cloud Run policies with auto_close 1800s, notification rate limit 300s, notifications on both open and close

## Task 8: Cloud Function Source Code
Implement the Telegram notifier Cloud Function in Python.

- [x] 8.1 Create `infra/modules/alerting/function/` directory with `main.py` and `requirements.txt`
- [x] 8.2 Implement `_get_secrets()` — fetch and cache `telegram-bot-token` and `telegram-chat-id` from Secret Manager
- [x] 8.3 Implement `detect_message_type(payload)` — returns `"alerting_policy"`, `"cloud_build"`, or `"unknown"`
- [x] 8.4 Implement `parse_alerting_incident(payload)` — extracts fields into `AlertIncident` dataclass
- [x] 8.5 Implement `parse_cloud_build_event(payload)` — extracts fields into `CloudBuildEvent` dataclass
- [x] 8.6 Implement `format_alerting_message(incident)` — HTML formatted with 🚨/✅ prefix
- [x] 8.7 Implement `format_cloud_build_message(build)` — HTML formatted with 🔴 prefix
- [x] 8.8 Implement `send_telegram_message(text)` — POST to Telegram Bot API, raise on non-2xx
- [x] 8.9 Implement `handle_pubsub(cloud_event)` — entry point that orchestrates detect → parse → format → send, discards SUCCESS builds and unknown schemas

## Task 9: Cloud Function Terraform Deployment
Deploy the Cloud Function via Terraform.

- [x] 9.1 Create `google_storage_bucket` and `google_storage_bucket_object` for function source (zip archive)
- [x] 9.2 Create `google_cloudfunctions2_function` with Python 3.11+ runtime, 256MB memory, 60s timeout, Pub/Sub event trigger on `juntoai-alerting-notifications` topic
- [x] 9.3 Create second Pub/Sub event trigger (or subscription) for the `cloud-builds` topic
- [x] 9.4 Configure the function to use the alerting service account

## Task 10: Terragrunt Configuration
Create the Terragrunt wrapper for the alerting module.

- [x] 10.1 Create `infra/modules/alerting/terragrunt.hcl` with `include "root"` and dependencies on `iam` and `cloud-run` modules
- [x] 10.2 Define `inputs` block mapping dependency outputs to module variables

## Task 11: Terraform Outputs
Define module outputs.

- [x] 11.1 Add `pubsub_topic_name`, `notifier_function_url`, and `alerting_sa_email` outputs in `outputs.tf`

## Task 12: Unit Tests — Terraform Module Structure
Write structural tests for the Terraform module.

- [x] 12.1 Create `infra/tests/test_alerting.py` with tests for module directory structure (main.tf, variables.tf, outputs.tf, backend.tf, terragrunt.hcl)
- [x] 12.2 Add tests verifying `variables.tf` contains all required variables with correct types and defaults
- [x] 12.3 Add tests verifying `outputs.tf` contains all required outputs
- [x] 12.4 Add tests verifying `terragrunt.hcl` includes root and declares dependencies

## Task 13: Unit Tests — Cloud Function
Write unit tests for the Cloud Function logic.

- [x] 13.1 Create `infra/tests/test_alerting_function.py` with tests for `detect_message_type()` (alerting, cloud_build, unknown)
- [x] 13.2 Add tests for `parse_alerting_incident()` with sample GCP Monitoring notification payload
- [x] 13.3 Add tests for `parse_cloud_build_event()` with sample Cloud Build event payload
- [x] 13.4 Add tests for `format_alerting_message()` — correct emoji prefix for open/closed, all fields present
- [x] 13.5 Add tests for `format_cloud_build_message()` — 🔴 prefix, all fields present
- [x] 13.6 Add tests for `send_telegram_message()` with mocked HTTP — verify URL, parse_mode, error handling on non-2xx
- [x] 13.7 Add tests for SUCCESS event discarding and unknown schema discarding

## Task 14: Property-Based Tests — Cloud Function
Write Hypothesis property-based tests for the Cloud Function logic.

- [x] 14.1 Create `infra/tests/test_alerting_function_properties.py` with Hypothesis strategies for random AlertIncident and CloudBuildEvent generation
- [x] 14.2 [PBT] Property 1: Message type detection correctness — for any valid payload, detect_message_type returns the correct type
- [x] 14.3 [PBT] Property 2: SUCCESS events are discarded — for any Cloud Build SUCCESS event, no message is produced
- [x] 14.4 [PBT] Property 3: Alerting policy parse round-trip — serialize → parse produces equivalent AlertIncident
- [x] 14.5 [PBT] Property 4: Cloud Build parse round-trip — serialize → parse produces equivalent CloudBuildEvent
- [x] 14.6 [PBT] Property 5: Alerting policy format completeness — formatted output contains correct emoji, all fields, HTML tags
- [x] 14.7 [PBT] Property 6: Cloud Build format completeness — formatted output contains 🔴, all fields, HTML tags
