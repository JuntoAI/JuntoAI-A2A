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

inputs = {
  backend_sa_email = dependency.iam.outputs.backend_sa_email
}
