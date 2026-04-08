include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "iam" {
  config_path = "../iam"

  mock_outputs = {
    backend_sa_email = "backend-sa@mock-project.iam.gserviceaccount.com"
  }
  mock_outputs_allowed_terraform_commands = ["plan", "validate"]
}

dependency "cloud_run" {
  config_path = "../cloud-run"

  mock_outputs = {
    backend_service_url  = "https://juntoai-backend-mock.run.app"
    frontend_service_url = "https://juntoai-frontend-mock.run.app"
  }
  mock_outputs_allowed_terraform_commands = ["plan", "validate"]
}

dependencies {
  paths = ["../iam", "../cloud-run"]
}

inputs = {
  # Service names — match the defaults in the cloud-run module.
  # These are not outputs of cloud-run; they are hardcoded here to stay in sync.
  backend_service_name  = "juntoai-backend"
  frontend_service_name = "juntoai-frontend"

  gcp_project_number = "141882351618"
}
