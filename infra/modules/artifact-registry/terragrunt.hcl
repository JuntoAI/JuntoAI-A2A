include "root" {
  path = find_in_parent_folders("root.hcl")
}

inputs = {
  # Armed: cleanup policies now DELETE rather than only log.
  # Verified 2026-08-19: zero delete-eligible images are referenced by a
  # live Cloud Run revision. 643 images / 54.79 GiB eligible for deletion
  # (TAGGED older than 90d outside keep-10 window).
  cleanup_dry_run = false
}
