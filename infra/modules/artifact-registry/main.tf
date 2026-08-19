# -----------------------------------------------------------------------------
# Artifact Registry — Docker repository
# -----------------------------------------------------------------------------
#
# CLEANUP POLICY SEMANTICS — the subtlety that let 63 GiB accumulate.
#
# A KEEP policy does not delete anything. It only shields versions from DELETE
# policies. So `keep-recent-tagged` alone is inert: with no DELETE policy that
# matches TAGGED versions, every commit-SHA image ever pushed lives forever.
#
# By Aug 2026 this repo held 699 images / 65 GiB, of which 637 images / 63 GiB
# were tagged and therefore unreachable by the only DELETE policy present
# (which matched UNTAGGED only). `delete-old-tagged` below closes that gap.
#
# Second gotcha: Artifact Registry cannot delete an image that a live Cloud Run
# revision still references. Pruning revisions is a prerequisite for reclaim —
# see scripts/prune_cloud_run_revisions.py.
#
# SAFETY: cleanup_policy_dry_run defaults to true. The first apply only logs
# what would be deleted. Review those logs, then set cleanup_dry_run = false in
# terragrunt.hcl to arm it. Deletion is irreversible.
# -----------------------------------------------------------------------------

resource "google_artifact_registry_repository" "docker" {
  repository_id = var.repository_id
  location      = var.gcp_region
  format        = "DOCKER"
  project       = var.gcp_project_id

  cleanup_policy_dry_run = var.cleanup_dry_run

  # Untagged layers are build residue — safe to drop once they are older than
  # the window in which a rollback might still need them.
  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "${var.untagged_older_than_days * 24}h"
    }
  }

  # The DELETE rule that was missing. Without it, tagged images accumulate
  # without bound and `keep-recent-tagged` protects nothing.
  cleanup_policies {
    id     = "delete-old-tagged"
    action = "DELETE"
    condition {
      tag_state  = "TAGGED"
      older_than = "${var.tagged_older_than_days * 24}h"
    }
  }

  # Evaluated ahead of the DELETE rules: the newest N versions always survive,
  # however old they are. Keep this at least as large as the number of Cloud Run
  # revisions retained by scripts/prune_cloud_run_revisions.py, otherwise a
  # retained revision can lose its image.
  cleanup_policies {
    id     = "keep-recent-tagged"
    action = "KEEP"
    most_recent_versions {
      keep_count = var.keep_recent_versions
    }
  }
}
