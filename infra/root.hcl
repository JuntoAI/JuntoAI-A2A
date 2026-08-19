locals {
  env_vars = read_terragrunt_config("${get_repo_root()}/infra/env.hcl")
}

remote_state {
  backend = "gcs"
  config = {
    bucket   = local.env_vars.locals.terraform_state_bucket
    prefix   = "${path_relative_to_include()}/terraform.tfstate"
    project  = local.env_vars.locals.gcp_project_id
    location = local.env_vars.locals.gcp_region
  }
}

# user_project_override / billing_project are required by APIs that refuse
# requests made with local user Application Default Credentials unless a quota
# project is attached — Cloud Billing Budgets is one. The Google provider does
# not forward the ADC quota project on its own, so
# `gcloud auth application-default set-quota-project` alone still yields a 403.
#
# Setting it here keeps every module applying the same way instead of depending
# on USER_PROJECT_OVERRIDE / GOOGLE_BILLING_PROJECT being exported by hand.
# Service-account credentials in CI are unaffected.
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "google" {
  project               = "${local.env_vars.locals.gcp_project_id}"
  region                = "${local.env_vars.locals.gcp_region}"
  user_project_override = true
  billing_project       = "${local.env_vars.locals.gcp_project_id}"
}

provider "google-beta" {
  project               = "${local.env_vars.locals.gcp_project_id}"
  region                = "${local.env_vars.locals.gcp_region}"
  user_project_override = true
  billing_project       = "${local.env_vars.locals.gcp_project_id}"
}
EOF
}

inputs = {
  gcp_project_id = local.env_vars.locals.gcp_project_id
  gcp_region     = local.env_vars.locals.gcp_region
}
