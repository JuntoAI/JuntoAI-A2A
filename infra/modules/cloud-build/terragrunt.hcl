include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "iam" {
  config_path = "../iam"
}

dependency "artifact_registry" {
  config_path = "../artifact-registry"
}

inputs = {
  backend_sa_email  = dependency.iam.outputs.backend_sa_email
  frontend_sa_email = dependency.iam.outputs.frontend_sa_email
  github_owner      = "JuntoAI"
  github_repo       = "JuntoAI-A2A"
}
