# Requirements Document

## Introduction

GCP Telegram Alerting Pipeline — a centralized monitoring and notification system for the JuntoAI A2A MVP production environment on Google Cloud Platform. The pipeline detects errors from Cloud Run structured logs, monitors application-level metrics (CPU, memory, request errors), catches Cloud Build CI/CD failures, and delivers formatted notifications to a Telegram group chat via Pub/Sub → Cloud Function → Telegram Bot API. All infrastructure is defined as a Terraform module at `infra/modules/alerting/` and deployed exclusively via Terragrunt.

This is the GCP equivalent of the existing AWS alerting pipeline documented in `docs/alerting-telegram-pipeline.md`, adapted to GCP-native services: Cloud Logging log-based metrics replace CloudWatch metric filters, GCP Alerting Policies replace CloudWatch Alarms, Pub/Sub replaces SNS, and a Cloud Function (Python 3.11+) replaces the Lambda notifier.

## Glossary

- **Alerting_Module**: The Terraform module at `infra/modules/alerting/` that defines all alerting infrastructure resources
- **Log_Based_Metric**: A GCP Cloud Logging metric that counts log entries matching a filter expression (e.g., `severity >= ERROR`)
- **Alerting_Policy**: A GCP Cloud Monitoring alerting policy that evaluates a metric condition and fires when a threshold is breached
- **Notification_Channel**: A GCP Cloud Monitoring notification channel of type `pubsub` that publishes alert incidents to a Pub/Sub topic
- **Pub_Sub_Topic**: A Google Cloud Pub/Sub topic that receives alert notifications and Cloud Build event messages
- **Notifier_Function**: A Cloud Function (2nd gen, Python 3.11+) that subscribes to the Pub_Sub_Topic, parses incoming messages, formats them, and sends them to the Telegram Bot API
- **Telegram_Bot_API**: The HTTPS endpoint (`https://api.telegram.org/bot<token>/sendMessage`) used to deliver formatted alert messages to a Telegram group chat
- **Secret_Manager**: GCP Secret Manager, used to store and retrieve the Telegram bot token and chat ID
- **Cloud_Build_Notification**: A Cloud Build Pub/Sub integration that publishes build status events (including failures) to a Pub/Sub topic
- **Backend_Service**: The FastAPI Python Cloud Run service (`juntoai-backend`) that emits structured JSON logs
- **Frontend_Service**: The Next.js Cloud Run service (`juntoai-frontend`) that emits structured JSON logs
- **Recovery_Notification**: A notification sent when an alerting policy transitions from firing (incident open) to resolved (incident closed), indicating the issue has been resolved

## Requirements

### Requirement 1: Pub/Sub Notification Topic

**User Story:** As a platform engineer, I want a single Pub/Sub topic that aggregates all alert notifications, so that a single Cloud Function can process all alert types through one subscription.

#### Acceptance Criteria

1. THE Alerting_Module SHALL create a Pub_Sub_Topic named `juntoai-alerting-notifications` in the configured GCP project and region
2. THE Alerting_Module SHALL create a Notification_Channel of type `pubsub` that references the Pub_Sub_Topic
3. THE Alerting_Module SHALL grant the `roles/pubsub.publisher` role to the GCP monitoring service account (`service-{project_number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com`) on the Pub_Sub_Topic
4. THE Alerting_Module SHALL create a Pub/Sub subscription on the Pub_Sub_Topic that triggers the Notifier_Function

### Requirement 2: Log-Based Error Detection for Backend Service

**User Story:** As a platform engineer, I want to detect error and fatal log entries from the backend FastAPI service, so that the team is alerted when the backend encounters errors in production.

#### Acceptance Criteria

1. THE Alerting_Module SHALL create a Log_Based_Metric named `backend/error-log-count` that counts log entries from the Backend_Service where `severity >= ERROR`
2. THE Alerting_Module SHALL create a Log_Based_Metric named `backend/fatal-log-count` that counts log entries from the Backend_Service where `severity = CRITICAL` (Python logging CRITICAL maps to fatal-level events)
3. THE Alerting_Module SHALL create an Alerting_Policy named `Backend Error Log Rate` that fires WHEN the `backend/error-log-count` metric exceeds 5 within a 5-minute alignment period
4. THE Alerting_Module SHALL create an Alerting_Policy named `Backend Fatal Log` that fires WHEN the `backend/fatal-log-count` metric exceeds 0 within a 1-minute alignment period
5. WHEN an Alerting_Policy for the Backend_Service fires, THE Alerting_Module SHALL route the incident notification to the Notification_Channel
6. WHEN an Alerting_Policy for the Backend_Service resolves, THE Alerting_Module SHALL route the Recovery_Notification to the Notification_Channel

### Requirement 3: Log-Based Error Detection for Frontend Service

**User Story:** As a platform engineer, I want to detect error log entries from the frontend Next.js service, so that the team is alerted when the frontend encounters errors in production.

#### Acceptance Criteria

1. THE Alerting_Module SHALL create a Log_Based_Metric named `frontend/error-log-count` that counts log entries from the Frontend_Service where `severity >= ERROR`
2. THE Alerting_Module SHALL create an Alerting_Policy named `Frontend Error Log Rate` that fires WHEN the `frontend/error-log-count` metric exceeds 5 within a 5-minute alignment period
3. WHEN an Alerting_Policy for the Frontend_Service fires, THE Alerting_Module SHALL route the incident notification to the Notification_Channel
4. WHEN an Alerting_Policy for the Frontend_Service resolves, THE Alerting_Module SHALL route the Recovery_Notification to the Notification_Channel

### Requirement 4: Cloud Run Application Metric Alerting

**User Story:** As a platform engineer, I want to monitor Cloud Run resource utilization and request error rates, so that the team is alerted when services are under stress or returning errors.

#### Acceptance Criteria

1. THE Alerting_Module SHALL create an Alerting_Policy named `Backend High CPU` that fires WHEN the Backend_Service CPU utilization metric (`run.googleapis.com/container/cpu/utilizations`) exceeds 80% averaged over two consecutive 5-minute alignment periods
2. THE Alerting_Module SHALL create an Alerting_Policy named `Backend High Memory` that fires WHEN the Backend_Service memory utilization metric (`run.googleapis.com/container/memory/utilizations`) exceeds 85% averaged over two consecutive 5-minute alignment periods
3. THE Alerting_Module SHALL create an Alerting_Policy named `Backend High Error Rate` that fires WHEN the Backend_Service 5xx response count metric (`run.googleapis.com/request_count` filtered by `response_code_class = "5xx"`) exceeds 10 within a 5-minute alignment period
4. THE Alerting_Module SHALL create an Alerting_Policy named `Frontend High Error Rate` that fires WHEN the Frontend_Service 5xx response count metric exceeds 10 within a 5-minute alignment period
5. THE Alerting_Module SHALL create an Alerting_Policy named `Backend Instance Count Spike` that fires WHEN the Backend_Service active instance count metric (`run.googleapis.com/container/instance_count`) exceeds a configurable threshold (default: 10) over a 5-minute alignment period
6. WHEN any Cloud Run Alerting_Policy fires or resolves, THE Alerting_Module SHALL route the notification to the Notification_Channel
7. THE Alerting_Module SHALL configure all Cloud Run Alerting_Policies with `auto_close` set to 1800 seconds (30 minutes) to automatically resolve stale incidents

### Requirement 5: Cloud Build Failure Notifications

**User Story:** As a platform engineer, I want to receive Telegram notifications when Cloud Build pipelines fail, so that the team can respond to CI/CD failures immediately.

#### Acceptance Criteria

1. THE Alerting_Module SHALL subscribe the Notifier_Function to the Cloud Build Pub/Sub topic (`cloud-builds`) that GCP automatically publishes build status events to
2. WHEN the Notifier_Function receives a Cloud Build event with `status = "FAILURE"` or `status = "TIMEOUT"` or `status = "INTERNAL_ERROR"`, THE Notifier_Function SHALL send a formatted failure notification to the Telegram group chat
3. WHEN the Notifier_Function receives a Cloud Build event with `status = "SUCCESS"`, THE Notifier_Function SHALL discard the message without sending a Telegram notification
4. THE Notifier_Function SHALL extract the trigger name, branch, commit SHA, build duration, and log URL from the Cloud Build event payload and include them in the failure notification

### Requirement 6: Telegram Notifier Cloud Function

**User Story:** As a platform engineer, I want a Cloud Function that formats and sends alert messages to Telegram, so that the team receives readable, actionable notifications in a single chat.

#### Acceptance Criteria

1. THE Alerting_Module SHALL deploy the Notifier_Function as a Cloud Function (2nd gen) using Python 3.11+ runtime with 256MB memory and 60-second timeout
2. THE Notifier_Function SHALL read the Telegram bot token from Secret_Manager secret `telegram-bot-token`
3. THE Notifier_Function SHALL read the Telegram chat ID from Secret_Manager secret `telegram-chat-id`
4. WHEN the Notifier_Function receives a Pub/Sub message from a GCP Alerting_Policy incident, THE Notifier_Function SHALL format the message with the emoji prefix `🚨 ALARM:` for firing incidents and `✅ RESOLVED:` for resolved incidents
5. WHEN the Notifier_Function receives a Pub/Sub message from a Cloud Build failure event, THE Notifier_Function SHALL format the message with the emoji prefix `🔴 Build FAILED:`
6. THE Notifier_Function SHALL send messages to the Telegram_Bot_API using the `sendMessage` endpoint with `parse_mode = "HTML"` for rich formatting
7. IF the Telegram_Bot_API returns a non-2xx HTTP status, THEN THE Notifier_Function SHALL log the error with the response body and raise an exception to trigger Pub/Sub retry
8. THE Notifier_Function SHALL include the alert policy name, condition display name, resource labels, incident start time, and summary in Alerting_Policy notifications
9. THE Notifier_Function SHALL include the trigger name, build status, branch, commit SHA, duration, and Cloud Build log URL in Cloud Build failure notifications

### Requirement 7: Secrets Management for Telegram Credentials

**User Story:** As a platform engineer, I want Telegram credentials stored securely in GCP Secret Manager, so that the bot token and chat ID are never exposed in code or Terraform state.

#### Acceptance Criteria

1. THE Alerting_Module SHALL create a Secret_Manager secret named `telegram-bot-token` for storing the Telegram Bot API token
2. THE Alerting_Module SHALL create a Secret_Manager secret named `telegram-chat-id` for storing the target Telegram group chat ID
3. THE Alerting_Module SHALL grant the `roles/secretmanager.secretAccessor` role to the Notifier_Function service account on both Telegram secrets
4. THE Alerting_Module SHALL configure the Notifier_Function to access secrets at runtime via the Secret Manager API (not mounted as environment variables in Terraform state)

### Requirement 8: Terraform Module Structure and IAM

**User Story:** As a platform engineer, I want the alerting infrastructure defined as a self-contained Terraform module with least-privilege IAM, so that it follows existing project conventions and can be deployed via Terragrunt.

#### Acceptance Criteria

1. THE Alerting_Module SHALL be located at `infra/modules/alerting/` and follow the existing module structure: `main.tf`, `variables.tf`, `outputs.tf`, `terragrunt.hcl`, `backend.tf`
2. THE Alerting_Module SHALL accept `gcp_project_id` and `gcp_region` as required input variables (consistent with existing modules)
3. THE Alerting_Module SHALL accept `backend_service_name` and `frontend_service_name` as input variables to reference the Cloud Run services
4. THE Alerting_Module SHALL create a dedicated service account for the Notifier_Function with only the permissions required: `roles/pubsub.subscriber`, `roles/secretmanager.secretAccessor` (scoped to Telegram secrets), and `roles/cloudfunctions.invoker`
5. THE Alerting_Module SHALL enable the required GCP APIs (`monitoring.googleapis.com`, `cloudfunctions.googleapis.com`, `pubsub.googleapis.com`, `cloudbuild.googleapis.com`) with `disable_on_destroy = false`
6. THE Alerting_Module SHALL output the Pub_Sub_Topic name, Notifier_Function URL, and the alerting service account email

### Requirement 9: Notifier Function Message Parsing and Formatting

**User Story:** As a platform engineer, I want the notifier function to correctly parse different Pub/Sub message formats and produce well-formatted Telegram messages, so that alerts are immediately actionable.

#### Acceptance Criteria

1. WHEN the Notifier_Function receives a Pub/Sub message, THE Notifier_Function SHALL detect the message type by checking for the presence of `incident` field (Alerting_Policy notification) or `status` field with Cloud Build schema (Cloud_Build_Notification)
2. THE Notifier_Function SHALL parse Alerting_Policy notification JSON payloads conforming to the GCP Monitoring notification schema (containing `incident.policy_name`, `incident.state`, `incident.resource.labels`, `incident.summary`)
3. THE Notifier_Function SHALL parse Cloud Build notification JSON payloads conforming to the Cloud Build event schema (containing `status`, `substitutions`, `logUrl`, `startTime`, `finishTime`, `source.repoSource`)
4. THE Notifier_Function SHALL produce Telegram messages using HTML formatting with `<b>` for field labels and newlines for readability
5. IF the Notifier_Function receives a Pub/Sub message that does not match any known schema, THEN THE Notifier_Function SHALL log a warning with the raw message payload and discard the message without sending a Telegram notification
6. FOR ALL valid Alerting_Policy notification JSON payloads, parsing then formatting then extracting fields SHALL produce output containing the original policy name and incident state (round-trip property)
7. FOR ALL valid Cloud Build event JSON payloads with failure status, parsing then formatting then extracting fields SHALL produce output containing the original trigger name and build status (round-trip property)

### Requirement 10: Alerting Policy Configuration Standards

**User Story:** As a platform engineer, I want all alerting policies to follow consistent configuration standards, so that alerts are reliable and do not produce false positives during low-traffic periods.

#### Acceptance Criteria

1. THE Alerting_Module SHALL configure all Alerting_Policies with `notification_rate_limit` of 300 seconds (5 minutes) to prevent notification storms
2. THE Alerting_Module SHALL configure all log-based Alerting_Policies to treat absent data as not firing (equivalent to `treat_missing_data = "notBreaching"` in the AWS pipeline)
3. THE Alerting_Module SHALL configure all Alerting_Policies to send notifications on both incident open (firing) and incident close (resolved) states
4. THE Alerting_Module SHALL define all alerting thresholds as Terraform variables with sensible defaults, allowing operators to tune thresholds without modifying module source code
5. THE Alerting_Module SHALL add a `severity` label to each Alerting_Policy: `critical` for fatal-level log alerts, `high` for error-rate and resource-utilization alerts, `medium` for log-error-count alerts
