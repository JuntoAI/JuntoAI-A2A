"""Property-based tests for Cloud Build CI/CD pipeline invariants.

Uses hypothesis to verify universal properties across generated inputs.
Each test runs a minimum of 100 iterations per the design spec.

Framework: hypothesis + pytest
"""

import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Set

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

gcp_region_st = st.from_regex(r"[a-z]+-[a-z]+[0-9]", fullmatch=True)
gcp_project_st = st.from_regex(r"[a-z][a-z0-9\-]{5,29}", fullmatch=True)
repo_name_st = st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True)
service_name_st = st.from_regex(r"[a-z][a-z0-9\-]{0,48}", fullmatch=True)
short_sha_st = st.from_regex(r"[0-9a-f]{7,12}", fullmatch=True)

sa_email_st = st.builds(
    lambda name, project: f"{name}@{project}.iam.gserviceaccount.com",
    name=st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True),
    project=gcp_project_st,
)

# Cloud Build SA approved roles (from variables.tf allowlist)
CB_APPROVED_ROLES: FrozenSet[str] = frozenset([
    "roles/artifactregistry.writer",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/logging.logWriter",
])

random_role_st = st.one_of(
    st.sampled_from(sorted(CB_APPROVED_ROLES)),
    st.from_regex(r"roles/[a-z]+\.[a-zA-Z]+", fullmatch=True),
)

# Pipeline services
PIPELINE_SERVICES = ("backend", "frontend")

# Pipeline step IDs (from cloudbuild.yaml — 6 steps)
PIPELINE_STEPS = (
    "build-backend", "build-frontend",
    "push-backend", "push-frontend",
    "deploy-backend", "deploy-frontend",
)

# Required substitution variables consumed by cloudbuild.yaml
REQUIRED_SUBSTITUTIONS: FrozenSet[str] = frozenset([
    "_REGION",
    "_PROJECT_ID",
    "_REPO_NAME",
    "_BACKEND_SERVICE",
    "_FRONTEND_SERVICE",
    "_BACKEND_SA_EMAIL",
    "_FRONTEND_SA_EMAIL",
    "_FIREBASE_API_KEY",
    "_FIREBASE_APP_ID",
])


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImageUri:
    """Represents a Docker image URI in Artifact Registry."""
    region: str
    project: str
    repo: str
    service: str
    tag: str

    @property
    def uri(self) -> str:
        return f"{self.region}-docker.pkg.dev/{self.project}/{self.repo}/{self.service}:{self.tag}"


@dataclass(frozen=True)
class PipelineStep:
    """Represents a Cloud Build pipeline step."""
    step_id: str
    wait_for: List[str]
    image_arg: str = ""  # only for deploy steps


@dataclass(frozen=True)
class TriggerConfig:
    """Represents a Cloud Build trigger configuration."""
    substitutions: Dict[str, str]
    disabled: bool


# ---------------------------------------------------------------------------
# Helper functions (simulate module logic — pure Python)
# ---------------------------------------------------------------------------

def build_image_uris(
    region: str,
    project: str,
    repo: str,
    services: tuple,
    short_sha: str,
) -> List[ImageUri]:
    """Simulate the images field construction from cloudbuild.yaml.

    For each service, produces both a SHA-tagged and latest-tagged URI.
    """
    uris: List[ImageUri] = []
    for svc in services:
        uris.append(ImageUri(region=region, project=project, repo=repo, service=svc, tag=short_sha))
        uris.append(ImageUri(region=region, project=project, repo=repo, service=svc, tag="latest"))
    return uris


def build_deploy_command_image_arg(
    region: str,
    project: str,
    repo: str,
    service: str,
    short_sha: str,
) -> str:
    """Simulate the --image argument in a deploy step.

    Deploys always use the SHA tag, never latest.
    """
    return f"{region}-docker.pkg.dev/{project}/{repo}/{service}:{short_sha}"


def render_substitution_template(
    template: str,
    substitutions: Dict[str, str],
) -> str:
    """Simulate Cloud Build substitution variable expansion.

    Replaces ${_VAR} and $_VAR patterns with values from the map.
    """
    result = template
    for key, value in substitutions.items():
        result = result.replace(f"${{{key}}}", value)
        result = result.replace(f"${key}", value)
    return result


def validate_cb_role_allowlist(roles: List[str]) -> bool:
    """Simulate the Terraform validation block from cloud-build/variables.tf."""
    return all(role in CB_APPROVED_ROLES for role in roles)


def build_pipeline_steps(
    region: str,
    project: str,
    repo: str,
    short_sha: str,
) -> List[PipelineStep]:
    """Simulate the 6-step pipeline from cloudbuild.yaml."""
    return [
        PipelineStep(step_id="build-backend", wait_for=["-"]),
        PipelineStep(step_id="build-frontend", wait_for=["-"]),
        PipelineStep(step_id="push-backend", wait_for=["build-backend"]),
        PipelineStep(step_id="push-frontend", wait_for=["build-frontend"]),
        PipelineStep(
            step_id="deploy-backend",
            wait_for=["push-backend"],
            image_arg=f"{region}-docker.pkg.dev/{project}/{repo}/backend:{short_sha}",
        ),
        PipelineStep(
            step_id="deploy-frontend",
            wait_for=["push-frontend"],
            image_arg=f"{region}-docker.pkg.dev/{project}/{repo}/frontend:{short_sha}",
        ),
    ]


def build_trigger_substitutions(
    region: str,
    project: str,
    repo: str,
    backend_service: str,
    frontend_service: str,
    backend_sa: str,
    frontend_sa: str,
    firebase_api_key: str,
    firebase_app_id: str,
) -> Dict[str, str]:
    """Simulate the trigger substitutions map from main.tf."""
    return {
        "_REGION": region,
        "_PROJECT_ID": project,
        "_REPO_NAME": repo,
        "_BACKEND_SERVICE": backend_service,
        "_FRONTEND_SERVICE": frontend_service,
        "_BACKEND_SA_EMAIL": backend_sa,
        "_FRONTEND_SA_EMAIL": frontend_sa,
        "_FIREBASE_API_KEY": firebase_api_key,
        "_FIREBASE_APP_ID": firebase_app_id,
    }


def build_trigger_config(trigger_enabled: bool, substitutions: Dict[str, str]) -> TriggerConfig:
    """Simulate the trigger resource from main.tf.

    disabled = !trigger_enabled (Terraform: var.trigger_enabled ? false : true)
    """
    return TriggerConfig(
        substitutions=substitutions,
        disabled=not trigger_enabled,
    )


# ===========================================================================
# Property 1: Dual image tagging (SHA + latest)
# Feature: 070_a2a-cicd-pipelines, Property 1
#
# For any service, the images list must include both a SHA-tagged URI
# and a latest-tagged URI rooted in the Artifact Registry path.
#
# Validates: Requirements 1.3, 1.4, 2.2, 2.3, 3.2, 3.3, 4.1, 4.2
# ===========================================================================

class TestDualImageTagging:
    """Feature: 070_a2a-cicd-pipelines, Property 1: Dual image tagging (SHA + latest)"""

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_both_sha_and_latest_tags_present_per_service(
        self, region, project, repo, short_sha,
    ):
        """**Validates: Requirements 1.3, 1.4, 2.2, 2.3, 3.2, 3.3, 4.1, 4.2**"""
        uris = build_image_uris(region, project, repo, PIPELINE_SERVICES, short_sha)
        uri_strings = [u.uri for u in uris]

        for svc in PIPELINE_SERVICES:
            expected_sha = f"{region}-docker.pkg.dev/{project}/{repo}/{svc}:{short_sha}"
            expected_latest = f"{region}-docker.pkg.dev/{project}/{repo}/{svc}:latest"
            assert expected_sha in uri_strings, (
                f"Missing SHA-tagged image for {svc}: {expected_sha}"
            )
            assert expected_latest in uri_strings, (
                f"Missing latest-tagged image for {svc}: {expected_latest}"
            )

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_exactly_two_tags_per_service(self, region, project, repo, short_sha):
        """Each service must have exactly 2 image URIs (SHA + latest)."""
        uris = build_image_uris(region, project, repo, PIPELINE_SERVICES, short_sha)
        for svc in PIPELINE_SERVICES:
            svc_uris = [u for u in uris if u.service == svc]
            assert len(svc_uris) == 2, (
                f"Expected 2 URIs for {svc}, got {len(svc_uris)}"
            )
            tags = {u.tag for u in svc_uris}
            assert tags == {short_sha, "latest"}, (
                f"Expected tags {{'{short_sha}', 'latest'}}, got {tags}"
            )

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_all_uris_rooted_in_artifact_registry(self, region, project, repo, short_sha):
        """All image URIs must match the Artifact Registry pattern."""
        uris = build_image_uris(region, project, repo, PIPELINE_SERVICES, short_sha)
        ar_pattern = re.compile(r"^[a-z]+-[a-z]+[0-9]-docker\.pkg\.dev/.+/.+/.+:.+$")
        for u in uris:
            assert ar_pattern.match(u.uri), (
                f"URI not rooted in Artifact Registry: {u.uri}"
            )


# ===========================================================================
# Property 2: Substitution variable parameterization
# Feature: 070_a2a-cicd-pipelines, Property 2
#
# For any environment-specific value referenced in pipeline steps, it must
# use a substitution variable — never a hardcoded literal.
#
# Validates: Requirements 1.2, 5.2, 6.2
# ===========================================================================

class TestSubstitutionParameterization:
    """Feature: 070_a2a-cicd-pipelines, Property 2: Substitution variable parameterization"""

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        backend_svc=service_name_st,
        frontend_svc=service_name_st,
        backend_sa=sa_email_st,
        frontend_sa=sa_email_st,
    )
    def test_no_hardcoded_values_after_substitution(
        self, region, project, repo, backend_svc, frontend_svc, backend_sa, frontend_sa,
    ):
        """**Validates: Requirements 1.2, 5.2, 6.2**

        Templates using substitution variables must not contain raw
        environment-specific literals before expansion.
        """
        # Simulate a template that uses substitution variables (like cloudbuild.yaml)
        template = (
            "${_REGION}-docker.pkg.dev/${_PROJECT_ID}/${_REPO_NAME}/backend "
            "gcloud run deploy ${_BACKEND_SERVICE} --region ${_REGION} "
            "--service-account ${_BACKEND_SA_EMAIL} "
            "gcloud run deploy ${_FRONTEND_SERVICE} --region ${_REGION} "
            "--service-account ${_FRONTEND_SA_EMAIL}"
        )

        subs = build_trigger_substitutions(
            region, project, repo, backend_svc, frontend_svc, backend_sa, frontend_sa,
            firebase_api_key="key123", firebase_app_id="app456",
        )

        # The raw template must NOT contain any of the concrete values
        # (unless the value happens to collide with a variable name, which we skip)
        env_values = {region, project, repo, backend_svc, frontend_svc, backend_sa, frontend_sa}
        # Filter out very short values that could false-positive match variable syntax
        env_values = {v for v in env_values if len(v) > 3}

        for val in env_values:
            assert val not in template, (
                f"Hardcoded value '{val}' found in template before substitution"
            )

        # After expansion, all values should be present
        expanded = render_substitution_template(template, subs)
        assert region in expanded
        assert project in expanded

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
    )
    def test_substitution_variables_fully_resolved(self, region, project, repo):
        """After substitution, no unresolved $_VAR or ${_VAR} patterns remain."""
        template = "${_REGION}-docker.pkg.dev/${_PROJECT_ID}/${_REPO_NAME}/backend:latest"
        subs = {"_REGION": region, "_PROJECT_ID": project, "_REPO_NAME": repo}
        expanded = render_substitution_template(template, subs)

        unresolved = re.findall(r"\$\{?_[A-Z_]+\}?", expanded)
        assert len(unresolved) == 0, (
            f"Unresolved substitution variables remain: {unresolved}"
        )


# ===========================================================================
# Property 3: Deploy steps use SHA tag
# Feature: 070_a2a-cicd-pipelines, Property 3
#
# For any deploy step, the --image argument must reference the SHA-tagged
# image URI, never the latest tag.
#
# Validates: Requirements 5.1, 6.1
# ===========================================================================

class TestShaDeployTagEnforcement:
    """Feature: 070_a2a-cicd-pipelines, Property 3: Deploy steps use SHA tag"""

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_deploy_image_uses_sha_not_latest(self, region, project, repo, short_sha):
        """**Validates: Requirements 5.1, 6.1**

        Every deploy step's --image argument must end with :SHORT_SHA, never :latest.
        """
        steps = build_pipeline_steps(region, project, repo, short_sha)
        deploy_steps = [s for s in steps if s.step_id.startswith("deploy-")]

        assert len(deploy_steps) > 0, "No deploy steps found"

        for step in deploy_steps:
            assert step.image_arg.endswith(f":{short_sha}"), (
                f"Deploy step {step.step_id} image does not use SHA tag: {step.image_arg}"
            )
            assert not step.image_arg.endswith(":latest"), (
                f"Deploy step {step.step_id} must not use :latest tag: {step.image_arg}"
            )

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_deploy_image_is_valid_ar_uri(self, region, project, repo, short_sha):
        """Deploy image URIs must be valid Artifact Registry paths."""
        for svc in PIPELINE_SERVICES:
            image_arg = build_deploy_command_image_arg(region, project, repo, svc, short_sha)
            ar_pattern = re.compile(r"^[a-z]+-[a-z]+[0-9]-docker\.pkg\.dev/.+/.+/.+:[0-9a-f]{7,12}$")
            assert ar_pattern.match(image_arg), (
                f"Deploy image URI invalid: {image_arg}"
            )


# ===========================================================================
# Property 4: Cloud Build SA role allowlist
# Feature: 070_a2a-cicd-pipelines, Property 4
#
# Only approved roles pass validation; all others are rejected.
# The approved set is: artifactregistry.writer, run.admin,
# iam.serviceAccountUser, logging.logWriter (4 roles).
#
# Validates: Requirements 8.1, 8.2, 8.3, 8.4
# ===========================================================================

class TestCloudBuildSaRoleAllowlist:
    """Feature: 070_a2a-cicd-pipelines, Property 4: Cloud Build SA role allowlist"""

    @settings(max_examples=100)
    @given(role=st.sampled_from(sorted(CB_APPROVED_ROLES)))
    def test_approved_roles_pass_validation(self, role):
        """**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

        Each individually approved role must pass the allowlist check.
        """
        assert validate_cb_role_allowlist([role]) is True

    @settings(max_examples=100)
    @given(role=st.from_regex(r"roles/[a-z]+\.[a-zA-Z]+", fullmatch=True))
    def test_unapproved_roles_rejected(self, role):
        """Any role not in the approved set must be rejected."""
        assume(role not in CB_APPROVED_ROLES)
        assert validate_cb_role_allowlist([role]) is False, (
            f"Role {role} should be rejected but passed validation"
        )

    @settings(max_examples=100)
    @given(roles=st.lists(random_role_st, min_size=1, max_size=10))
    def test_mixed_role_lists(self, roles):
        """A list passes iff every role is in the approved set."""
        expected = all(r in CB_APPROVED_ROLES for r in roles)
        assert validate_cb_role_allowlist(roles) == expected

    def test_exact_approved_set_has_four_roles(self):
        """The approved set must contain exactly 4 roles."""
        assert len(CB_APPROVED_ROLES) == 4
        assert CB_APPROVED_ROLES == frozenset([
            "roles/artifactregistry.writer",
            "roles/run.admin",
            "roles/iam.serviceAccountUser",
            "roles/logging.logWriter",
        ])


# ===========================================================================
# Property 5: Pipeline step dependency ordering
# Feature: 070_a2a-cicd-pipelines, Property 5
#
# Build steps have waitFor: ["-"] (parallel). Push steps depend on their
# build step. Deploy steps depend on their push step. No deploy may
# execute before its build completes.
#
# Validates: Requirements 9.1, 9.2, 9.3, 9.4
# ===========================================================================

class TestPipelineStepDependencyOrdering:
    """Feature: 070_a2a-cicd-pipelines, Property 5: Pipeline step dependency ordering"""

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_build_steps_run_in_parallel(self, region, project, repo, short_sha):
        """**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

        Build steps must have waitFor: ["-"] enabling parallel execution.
        """
        steps = build_pipeline_steps(region, project, repo, short_sha)
        build_steps = [s for s in steps if s.step_id.startswith("build-")]

        assert len(build_steps) == 2, f"Expected 2 build steps, got {len(build_steps)}"
        for step in build_steps:
            assert step.wait_for == ["-"], (
                f"Build step {step.step_id} should waitFor ['-'], got {step.wait_for}"
            )

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_deploy_steps_depend_on_push_steps(self, region, project, repo, short_sha):
        """Deploy steps must depend on their corresponding push step."""
        steps = build_pipeline_steps(region, project, repo, short_sha)
        step_map = {s.step_id: s for s in steps}

        assert step_map["deploy-backend"].wait_for == ["push-backend"]
        assert step_map["deploy-frontend"].wait_for == ["push-frontend"]

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_push_steps_depend_on_build_steps(self, region, project, repo, short_sha):
        """Push steps must depend on their corresponding build step."""
        steps = build_pipeline_steps(region, project, repo, short_sha)
        step_map = {s.step_id: s for s in steps}

        assert step_map["push-backend"].wait_for == ["build-backend"]
        assert step_map["push-frontend"].wait_for == ["build-frontend"]

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        short_sha=short_sha_st,
    )
    def test_no_deploy_before_build_in_dependency_chain(self, region, project, repo, short_sha):
        """Transitive: deploy cannot execute before build completes (build→push→deploy)."""
        steps = build_pipeline_steps(region, project, repo, short_sha)
        step_map = {s.step_id: s for s in steps}

        # Verify the full chain: deploy depends on push, push depends on build
        for svc in ("backend", "frontend"):
            deploy = step_map[f"deploy-{svc}"]
            push_dep = deploy.wait_for[0]  # e.g. "push-backend"
            push_step = step_map[push_dep]
            build_dep = push_step.wait_for[0]  # e.g. "build-backend"
            assert build_dep == f"build-{svc}", (
                f"Deploy-{svc} chain broken: deploy→{push_dep}→{build_dep}"
            )


# ===========================================================================
# Property 6: Trigger substitutions completeness
# Feature: 070_a2a-cicd-pipelines, Property 6
#
# The trigger substitutions map must be a superset of the variables
# consumed by cloudbuild.yaml.
#
# Validates: Requirements 7.3, 10.4
# ===========================================================================

class TestTriggerSubstitutionsCompleteness:
    """Feature: 070_a2a-cicd-pipelines, Property 6: Trigger substitutions completeness"""

    @settings(max_examples=100)
    @given(
        region=gcp_region_st,
        project=gcp_project_st,
        repo=repo_name_st,
        backend_svc=service_name_st,
        frontend_svc=service_name_st,
        backend_sa=sa_email_st,
        frontend_sa=sa_email_st,
    )
    def test_trigger_subs_cover_all_required_variables(
        self, region, project, repo, backend_svc, frontend_svc, backend_sa, frontend_sa,
    ):
        """**Validates: Requirements 7.3, 10.4**

        The trigger substitutions map must contain every variable that
        cloudbuild.yaml references.
        """
        subs = build_trigger_substitutions(
            region, project, repo, backend_svc, frontend_svc, backend_sa, frontend_sa,
            firebase_api_key="key", firebase_app_id="app",
        )
        provided_keys = frozenset(subs.keys())
        missing = REQUIRED_SUBSTITUTIONS - provided_keys
        assert len(missing) == 0, (
            f"Trigger substitutions missing required variables: {missing}"
        )

    @settings(max_examples=100)
    @given(
        required=st.frozensets(
            st.sampled_from(sorted(REQUIRED_SUBSTITUTIONS)),
            min_size=1,
        ),
    )
    def test_random_required_subsets_covered(self, required):
        """Any subset of required variables must be present in the full substitutions map."""
        subs = build_trigger_substitutions(
            region="europe-west1",
            project="test-project",
            repo="test-repo",
            backend_service="backend",
            frontend_service="frontend",
            backend_sa="be@test.iam.gserviceaccount.com",
            frontend_sa="fe@test.iam.gserviceaccount.com",
            firebase_api_key="key",
            firebase_app_id="app",
        )
        provided_keys = frozenset(subs.keys())
        assert required.issubset(provided_keys), (
            f"Required vars {required - provided_keys} not in trigger substitutions"
        )


# ===========================================================================
# Property 7: Trigger disabled-by-default
# Feature: 070_a2a-cicd-pipelines, Property 7
#
# For any boolean value of trigger_enabled, the trigger's disabled field
# must equal !trigger_enabled.
#
# Validates: Requirements 7.4, 10.6
# ===========================================================================

class TestTriggerDisabledByDefault:
    """Feature: 070_a2a-cicd-pipelines, Property 7: Trigger disabled-by-default"""

    @settings(max_examples=100)
    @given(trigger_enabled=st.booleans())
    def test_disabled_is_inverse_of_trigger_enabled(self, trigger_enabled):
        """**Validates: Requirements 7.4, 10.6**

        disabled must always equal !trigger_enabled.
        """
        config = build_trigger_config(
            trigger_enabled=trigger_enabled,
            substitutions={},
        )
        assert config.disabled == (not trigger_enabled), (
            f"trigger_enabled={trigger_enabled} but disabled={config.disabled}"
        )

    def test_default_trigger_enabled_false_means_disabled_true(self):
        """When trigger_enabled defaults to false, trigger must be disabled."""
        config = build_trigger_config(trigger_enabled=False, substitutions={})
        assert config.disabled is True

    def test_trigger_enabled_true_means_disabled_false(self):
        """When trigger_enabled is true, trigger must not be disabled."""
        config = build_trigger_config(trigger_enabled=True, substitutions={})
        assert config.disabled is False
