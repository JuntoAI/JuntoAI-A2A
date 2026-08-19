include "root" {
  path = find_in_parent_folders("root.hcl")
}

# NOTE: this module needs `user_project_override = true` on the provider, because
# the Cloud Billing Budgets API rejects local user ADC without an attached quota
# project. That is set once in infra/root.hcl rather than here — Terragrunt
# refuses duplicate `generate` block names between parent and child.

inputs = {
  billing_account_id = "01F691-B995EA-A93C8F"

  # Set to the credit grant spread over the months it needs to cover, not to
  # current spend. A budget that tracks actual spend never warns you about
  # anything.
  budget_amount   = 100
  budget_currency = "EUR"
}
