include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "firestore" {
  config_path = "../firestore"
}
