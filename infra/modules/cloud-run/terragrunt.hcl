include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "iam" {
  config_path = "../iam"

  mock_outputs = {
    backend_sa_email  = "backend-sa@mock-project.iam.gserviceaccount.com"
    frontend_sa_email = "frontend-sa@mock-project.iam.gserviceaccount.com"
  }
  mock_outputs_allowed_terraform_commands = ["plan", "validate"]
}

dependency "artifact_registry" {
  config_path = "../artifact-registry"

  mock_outputs = {
    repository_path = "europe-west1-docker.pkg.dev/mock-project/juntoai-docker"
  }
  mock_outputs_allowed_terraform_commands = ["plan", "validate"]
}

dependencies {
  paths = ["../firestore", "../vertex-ai"]
}

inputs = {
  backend_sa_email     = dependency.iam.outputs.backend_sa_email
  frontend_sa_email    = dependency.iam.outputs.frontend_sa_email
  enable_public_access = false
  custom_domain        = "a2a.juntoai.org"
}
