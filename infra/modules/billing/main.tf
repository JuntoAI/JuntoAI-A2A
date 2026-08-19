# -----------------------------------------------------------------------------
# Billing visibility and guardrails
# -----------------------------------------------------------------------------
#
# WHY THIS MODULE EXISTS
#
# Cloud Billing exposes accounts, project links and SKU price lists through its
# API, but NOT actual consumption. The only two sources of real spend data are
# the Console billing reports and a BigQuery billing export. With neither in
# place, spend is unobservable from code.
#
# That gap cost real money: an abandoned canary Cloud Run revision with
# min-instances=1 ran 24/7 at 0% traffic from April to August 2026 and grew to
# ~66% of the monthly bill before anyone noticed. There was no export to query
# and no budget to trip. See infra/modules/cloud-run/main.tf for that story.
#
# -----------------------------------------------------------------------------
# MANUAL STEP REQUIRED — TERRAFORM CANNOT FINISH THIS
# -----------------------------------------------------------------------------
#
# Enabling the billing -> BigQuery export link is Console-only. There is no
# gcloud command, no stable REST endpoint and no Terraform resource for it. This
# module creates the destination dataset and the budget; a human must flip the
# export switch once:
#
#   Console -> Billing -> <account> -> Billing export -> BigQuery export
#     -> Edit settings
#     -> Standard usage cost   : project juntoai-a2a-mvp, dataset billing_export
#     -> Detailed usage cost   : same dataset (optional, adds SKU-level detail)
#     -> Pricing               : same dataset (optional)
#
# Data starts flowing within ~24h and is NOT backfilled, so the sooner this is
# switched on the sooner history begins. Verify with:
#
#   bq ls --project_id=juntoai-a2a-mvp billing_export
#
# -----------------------------------------------------------------------------

resource "google_project_service" "billingbudgets" {
  project = var.gcp_project_id
  service = "billingbudgets.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "bigquery" {
  project = var.gcp_project_id
  service = "bigquery.googleapis.com"

  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# BigQuery dataset — destination for the Cloud Billing export
# -----------------------------------------------------------------------------
#
# No table schema is declared here on purpose: Cloud Billing creates and manages
# its own tables (gcp_billing_export_v1_*, gcp_billing_export_resource_v1_*)
# inside this dataset once the export is switched on.
#
# delete_contents_on_destroy stays false. Billing history is not reproducible —
# if the export is ever turned off the data is gone for good.
# -----------------------------------------------------------------------------

resource "google_bigquery_dataset" "billing_export" {
  project    = var.gcp_project_id
  dataset_id = var.billing_export_dataset_id
  location   = var.billing_export_location

  friendly_name = "Cloud Billing export"
  description   = "Destination for Cloud Billing BigQuery export. Tables are created and managed by Cloud Billing, not Terraform. The export link itself must be enabled in the Console."

  delete_contents_on_destroy = false

  depends_on = [google_project_service.bigquery]
}

# -----------------------------------------------------------------------------
# Budget — alerts on actual AND forecasted spend
# -----------------------------------------------------------------------------
#
# Scoped to the whole billing account rather than a single project, because the
# leak that motivated this module spanned projects and a project-scoped budget
# would have missed spend in juntoai-espocrm and intense-base-456414-u5.
#
# Forecast thresholds matter more than actual ones: a 100% actual alert tells you
# the money is already gone, while a 100% forecast alert arrives with time to act.
#
# NOTE: applying this requires billing-account-level permission
# (roles/billing.admin or roles/billing.costsManager) on the account, not just
# project-level rights. A plan will surface a 403 if that is missing.
# -----------------------------------------------------------------------------

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "JuntoAI monthly budget (${var.budget_amount} ${var.budget_currency})"

  budget_filter {
    calendar_period = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = var.budget_thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  dynamic "threshold_rules" {
    for_each = var.budget_forecast_thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "FORECASTED_SPEND"
    }
  }

  # all_updates_rule is only emitted when an extra delivery channel is supplied.
  #
  # The provider rejects the block unless it carries `pubsub_topic` or
  # `monitoring_notification_channels`, so an "email the billing admins only"
  # budget must omit it entirely. That is the default: Cloud Billing already
  # emails budget alerts to billing account admins and users, and
  # disable_default_iam_recipients exists only inside this block, so leaving the
  # block out keeps those emails on.
  #
  # Supply budget_pubsub_topic or budget_monitoring_notification_channels to add
  # programmatic delivery. Note that budget messages use their own payload
  # schema, so the consumer must handle it explicitly — pointing this at the
  # existing juntoai-alerting-notifications topic will NOT produce sensible
  # Telegram messages until the notifier learns that schema.
  dynamic "all_updates_rule" {
    for_each = (
      var.budget_pubsub_topic != "" ||
      length(var.budget_monitoring_notification_channels) > 0
    ) ? [1] : []

    content {
      disable_default_iam_recipients = var.budget_disable_default_iam_recipients
      pubsub_topic                   = var.budget_pubsub_topic != "" ? var.budget_pubsub_topic : null
      schema_version                 = var.budget_pubsub_topic != "" ? "1.0" : null
      monitoring_notification_channels = (
        length(var.budget_monitoring_notification_channels) > 0
        ? var.budget_monitoring_notification_channels
        : null
      )
    }
  }

  depends_on = [google_project_service.billingbudgets]
}
