include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "iam" {
  config_path = "../iam"
}

dependency "artifact_registry" {
  config_path = "../artifact-registry"
}

dependency "firebase" {
  config_path = "../firebase"
}

inputs = {
  backend_sa_email       = dependency.iam.outputs.backend_sa_email
  frontend_sa_email      = dependency.iam.outputs.frontend_sa_email
  firebase_api_key       = dependency.firebase.outputs.api_key
  firebase_app_id        = dependency.firebase.outputs.app_id
  google_oauth_client_id = "141882351618-g2p9n0felvpc7lp573gu4ufkcsghlddd.apps.googleusercontent.com"
  github_owner           = "JuntoAI"
  github_repo            = "JuntoAI-A2A"
  trigger_enabled        = true
}
