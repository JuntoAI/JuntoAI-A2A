"""Property-based tests for GCP infrastructure invariants.

Uses hypothesis to verify universal properties across generated inputs.
Each test runs a minimum of 100 iterations per the design spec.

Framework: hypothesis + pytest
"""

import re
from dataclasses import dataclass
from typing import List, Optional

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Valid GCP region pattern (e.g., europe-west1, us-central1, asia-east2)
gcp_region_st = st.from_regex(r"[a-z]+-[a-z]+[0-9]", fullmatch=True)

# Valid GCP project ID pattern (6-30 chars, lowercase + digits + hyphens)
gcp_project_st = st.from_regex(r"[a-z][a-z0-9\-]{5,29}", fullmatch=True)

# Valid SA email pattern
sa_email_st = st.builds(
    lambda name, project: f"{name}@{project}.iam.gserviceaccount.com",
    name=st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True),
    project=gcp_project_st,
)

# Valid Docker image URI rooted in Artifact Registry
ar_image_st = st.builds(
    lambda region, project, repo, tag: (
        f"{region}-docker.pkg.dev/{project}/{repo}/app:{tag}"
    ),
    region=gcp_region_st,
    project=gcp_project_st,
    repo=st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True),
    tag=st.from_regex(r"[a-z0-9]{6,12}", fullmatch=True),
)

# Valid Cloud Run service name (1-49 chars, lowercase + digits + hyphens)
service_name_st = st.from_regex(r"[a-z][a-z0-9\-]{0,48}", fullmatch=True)

# IAM approved roles
APPROVED_ROLES = frozenset([
    "roles/datastore.user",
    "roles/aiplatform.user",
    "roles/run.invoker",
])

# Privileged roles that Frontend_SA must never have
PRIVILEGED_ROLES = frozenset([
    "roles/datastore.user",
    "roles/aiplatform.user",
    "roles/run.invoker",
])

# Random IAM role strings (mix of valid and invalid)
random_role_st = st.one_of(
    st.sampled_from(sorted(APPROVED_ROLES)),
    st.from_regex(r"roles/[a-z]+\.[a-z]+", fullmatch=True),
)


# ---------------------------------------------------------------------------
# Domain models (simulate what Terraform would produce)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CloudRunServiceConfig:
    name: str
    location: str
    image: str
    service_account: str


@dataclass(frozen=True)
class IamBinding:
    member: str
    role: str


# ---------------------------------------------------------------------------
# Helper functions (simulate module logic)
# ---------------------------------------------------------------------------

def build_cloud_run_config(
    service_name: str,
    region: str,
    image: str,
    sa_email: str,
) -> CloudRunServiceConfig:
    """Simulate Cloud Run module resource construction."""
    return CloudRunServiceConfig(
        name=service_name,
        location=region,
        image=image,
        service_account=sa_email,
    )


def build_iam_bindings(
    backend_sa_email: str,
    frontend_sa_email: str,
    enable_run_invoker: bool,
) -> List[IamBinding]:
    """Simulate IAM module binding construction (mirrors main.tf logic)."""
    bindings = [
        IamBinding(member=f"serviceAccount:{backend_sa_email}", role="roles/datastore.user"),
        IamBinding(member=f"serviceAccount:{backend_sa_email}", role="roles/aiplatform.user"),
    ]
    if enable_run_invoker:
        bindings.append(
            IamBinding(member=f"serviceAccount:{backend_sa_email}", role="roles/run.invoker")
        )
    # Frontend_SA gets no bindings — this is the design invariant
    return bindings


def validate_role_allowlist(roles: List[str]) -> bool:
    """Simulate the Terraform validation block from iam/variables.tf."""
    return all(role in APPROVED_ROLES for role in roles)


# ===========================================================================
# Property 1: Cloud Run service configuration invariant
# Feature: 010_a2a-gcp-infrastructure, Property 1
#
# For any Cloud Run service, the service must:
# (a) reference a container image URI rooted in Artifact Registry
# (b) have service_account set to a dedicated SA email
# (c) derive location from the configurable gcp_region variable
# ===========================================================================

class TestCloudRunConfigInvariant:
    """Feature: 010_a2a-gcp-infrastructure, Property 1: Cloud Run service configuration invariant"""

    @settings(max_examples=100)
    @given(
        service_name=service_name_st,
        region=gcp_region_st,
        image=ar_image_st,
        sa_email=sa_email_st,
    )
    def test_image_uri_rooted_in_artifact_registry(self, service_name, region, image, sa_email):
        """(a) Image URI must match Artifact Registry pattern."""
        config = build_cloud_run_config(service_name, region, image, sa_email)
        assert re.match(
            r"^[a-z]+-[a-z]+[0-9]-docker\.pkg\.dev/.+/.+/.+:.+$",
            config.image,
        ), f"Image URI not rooted in Artifact Registry: {config.image}"

    @settings(max_examples=100)
    @given(
        service_name=service_name_st,
        region=gcp_region_st,
        image=ar_image_st,
        sa_email=sa_email_st,
    )
    def test_service_account_is_dedicated_sa(self, service_name, region, image, sa_email):
        """(b) Service account must be a valid GCP SA email."""
        config = build_cloud_run_config(service_name, region, image, sa_email)
        assert config.service_account.endswith(
            ".iam.gserviceaccount.com"
        ), f"SA email invalid: {config.service_account}"

    @settings(max_examples=100)
    @given(
        service_name=service_name_st,
        region=gcp_region_st,
        image=ar_image_st,
        sa_email=sa_email_st,
    )
    def test_location_matches_input_region(self, service_name, region, image, sa_email):
        """(c) Location must equal the input region, not a hardcoded string."""
        config = build_cloud_run_config(service_name, region, image, sa_email)
        assert config.location == region


# ===========================================================================
# Property 2: Conditional run.invoker role grant
# Feature: 010_a2a-gcp-infrastructure, Property 2
#
# roles/run.invoker binding exists iff enable_run_invoker is True.
# ===========================================================================

class TestConditionalRunInvoker:
    """Feature: 010_a2a-gcp-infrastructure, Property 2: Conditional run.invoker role grant"""

    @settings(max_examples=100)
    @given(
        enable_run_invoker=st.booleans(),
        backend_sa=sa_email_st,
        frontend_sa=sa_email_st,
    )
    def test_run_invoker_iff_flag_true(self, enable_run_invoker, backend_sa, frontend_sa):
        bindings = build_iam_bindings(backend_sa, frontend_sa, enable_run_invoker)
        has_run_invoker = any(b.role == "roles/run.invoker" for b in bindings)
        assert has_run_invoker == enable_run_invoker, (
            f"enable_run_invoker={enable_run_invoker} but "
            f"run.invoker binding present={has_run_invoker}"
        )


# ===========================================================================
# Property 3: Frontend_SA least-privilege enforcement
# Feature: 010_a2a-gcp-infrastructure, Property 3
#
# No IAM binding shall assign privileged roles to Frontend_SA.
# ===========================================================================

class TestFrontendLeastPrivilege:
    """Feature: 010_a2a-gcp-infrastructure, Property 3: Frontend_SA least-privilege enforcement"""

    @settings(max_examples=100)
    @given(
        enable_run_invoker=st.booleans(),
        backend_sa=sa_email_st,
        frontend_sa=sa_email_st,
    )
    def test_no_privileged_roles_on_frontend_sa(
        self, enable_run_invoker, backend_sa, frontend_sa
    ):
        assume(backend_sa != frontend_sa)
        bindings = build_iam_bindings(backend_sa, frontend_sa, enable_run_invoker)
        frontend_bindings = [
            b for b in bindings if frontend_sa in b.member
        ]
        for binding in frontend_bindings:
            assert binding.role not in PRIVILEGED_ROLES, (
                f"Frontend_SA must not have {binding.role}"
            )

    @settings(max_examples=100)
    @given(
        enable_run_invoker=st.booleans(),
        backend_sa=sa_email_st,
        frontend_sa=sa_email_st,
    )
    def test_frontend_sa_has_zero_bindings(
        self, enable_run_invoker, backend_sa, frontend_sa
    ):
        """Frontend_SA must have zero project-level role bindings."""
        assume(backend_sa != frontend_sa)
        bindings = build_iam_bindings(backend_sa, frontend_sa, enable_run_invoker)
        frontend_bindings = [
            b for b in bindings if frontend_sa in b.member
        ]
        assert len(frontend_bindings) == 0, (
            f"Frontend_SA should have 0 bindings, got {len(frontend_bindings)}"
        )


# ===========================================================================
# Property 4: IAM role allowlist validation
# Feature: 010_a2a-gcp-infrastructure, Property 4
#
# Only approved roles pass validation; all others are rejected.
# ===========================================================================

class TestIamRoleAllowlist:
    """Feature: 010_a2a-gcp-infrastructure, Property 4: IAM role allowlist validation"""

    @settings(max_examples=100)
    @given(role=st.sampled_from(sorted(APPROVED_ROLES)))
    def test_approved_roles_pass_validation(self, role):
        assert validate_role_allowlist([role]) is True

    @settings(max_examples=100)
    @given(role=st.from_regex(r"roles/[a-z]+\.[a-z]+", fullmatch=True))
    def test_unapproved_roles_rejected(self, role):
        assume(role not in APPROVED_ROLES)
        assert validate_role_allowlist([role]) is False, (
            f"Role {role} should be rejected but passed validation"
        )

    @settings(max_examples=100)
    @given(
        roles=st.lists(random_role_st, min_size=1, max_size=10),
    )
    def test_mixed_role_lists(self, roles):
        """A list passes iff every role is in the approved set."""
        expected = all(r in APPROVED_ROLES for r in roles)
        assert validate_role_allowlist(roles) == expected
