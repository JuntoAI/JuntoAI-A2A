locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
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

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "google" {
  project = "${local.env_vars.locals.gcp_project_id}"
  region  = "${local.env_vars.locals.gcp_region}"
}

provider "google-beta" {
  project = "${local.env_vars.locals.gcp_project_id}"
  region  = "${local.env_vars.locals.gcp_region}"
}
EOF
}

inputs = {
  gcp_project_id = local.env_vars.locals.gcp_project_id
  gcp_region     = local.env_vars.locals.gcp_region
}
