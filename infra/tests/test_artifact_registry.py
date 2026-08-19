"""Verify Artifact Registry module (Req 4.1–4.3, 8.2)."""

import os
import pytest


class TestArtifactRegistryMain:
    """Req 4.1–4.3: Docker format, configurable region/ID."""

    @pytest.fixture(autouse=True)
    def _load(self, artifact_registry_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(artifact_registry_dir, "main.tf"))

    def test_docker_format(self):
        repo = self.main["resource"][0]["google_artifact_registry_repository"]["docker"]
        assert repo["format"] == "DOCKER"

    def test_location_from_variable(self):
        repo = self.main["resource"][0]["google_artifact_registry_repository"]["docker"]
        assert repo["location"] == "${var.gcp_region}"

    def test_repository_id_from_variable(self):
        repo = self.main["resource"][0]["google_artifact_registry_repository"]["docker"]
        assert repo["repository_id"] == "${var.repository_id}"


class TestArtifactRegistryVariables:
    @pytest.fixture(autouse=True)
    def _load(self, artifact_registry_dir, hcl_parser):
        self.vars = hcl_parser(os.path.join(artifact_registry_dir, "variables.tf"))

    def test_gcp_project_id_variable(self):
        var_names = [list(v.keys())[0] for v in self.vars["variable"]]
        assert "gcp_project_id" in var_names

    def test_gcp_region_variable(self):
        var_names = [list(v.keys())[0] for v in self.vars["variable"]]
        assert "gcp_region" in var_names

    def test_repository_id_variable_with_default(self):
        for v in self.vars["variable"]:
            if "repository_id" in v:
                assert v["repository_id"]["default"] == "juntoai-docker"
                return
        pytest.fail("repository_id variable not found")


class TestArtifactRegistryOutputs:
    """Req 8.2: Output repository_path declared."""

    @pytest.fixture(autouse=True)
    def _load(self, artifact_registry_dir, hcl_parser):
        self.outputs = hcl_parser(os.path.join(artifact_registry_dir, "outputs.tf"))

    def test_repository_path_output(self):
        output_names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "repository_path" in output_names


class TestArtifactRegistryTerragrunt:
    """Child terragrunt.hcl includes root."""

    def test_includes_root(self, artifact_registry_dir):
        path = os.path.join(artifact_registry_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert 'find_in_parent_folders("root.hcl")' in content
        assert 'include "root"' in content


# ---------------------------------------------------------------------------
# Cleanup policy guards
# ---------------------------------------------------------------------------
#
# A KEEP policy deletes nothing; it only shields versions from DELETE policies.
# For a long time this repo had `keep-recent-tagged` but no DELETE policy that
# matched TAGGED versions, so every commit-SHA image was retained forever and
# the repo grew to 699 images / 65 GiB (637 images / 63 GiB of them tagged).
#
# Uses the quote-tolerant helpers from conftest.
# ---------------------------------------------------------------------------

import os as _os

import pytest as _pytest

from conftest import find_resource as _find_resource
from conftest import find_variable as _find_variable
from conftest import hcl_str as _hcl_str
from conftest import parse_hcl_file as _parse_hcl_file


@_pytest.fixture(scope="module")
def ar_main(artifact_registry_dir):
    return _parse_hcl_file(_os.path.join(artifact_registry_dir, "main.tf"))


@_pytest.fixture(scope="module")
def ar_variables(artifact_registry_dir):
    return _parse_hcl_file(_os.path.join(artifact_registry_dir, "variables.tf"))


def _cleanup_policies(repo_body):
    policies = repo_body.get("cleanup_policies", [])
    if isinstance(policies, dict):
        policies = [policies]
    return {_hcl_str(p["id"]): p for p in policies}


class TestCleanupPolicies:
    def test_untagged_delete_policy_exists(self, ar_main):
        repo = _find_resource(ar_main, "google_artifact_registry_repository", "docker")
        policies = _cleanup_policies(repo)
        untagged = [
            p for p in policies.values()
            if _hcl_str(p.get("action")) == "DELETE" and "UNTAGGED" in str(p.get("condition"))
        ]
        assert untagged, "need a DELETE policy matching UNTAGGED versions"

    def test_tagged_delete_policy_exists(self, ar_main):
        """The rule whose absence let 63 GiB of tagged images accumulate."""
        repo = _find_resource(ar_main, "google_artifact_registry_repository", "docker")
        policies = _cleanup_policies(repo)
        tagged = [
            p for p in policies.values()
            if _hcl_str(p.get("action")) == "DELETE"
            and "TAGGED" in str(p.get("condition"))
            and "UNTAGGED" not in str(p.get("condition"))
        ]
        assert tagged, (
            "need a DELETE policy matching TAGGED versions; a KEEP policy alone "
            "never reclaims anything"
        )

    def test_keep_policy_exists(self, ar_main):
        repo = _find_resource(ar_main, "google_artifact_registry_repository", "docker")
        policies = _cleanup_policies(repo)
        keeps = [p for p in policies.values() if _hcl_str(p.get("action")) == "KEEP"]
        assert keeps, "a KEEP policy must protect the most recent versions"

    def test_dry_run_defaults_to_true(self, ar_variables):
        """Image deletion is irreversible; the first apply must only report."""
        var = _find_variable(ar_variables, "cleanup_dry_run")
        assert var["default"] is True

    def test_keep_count_covers_revision_retention(self, ar_variables):
        """Artifact Registry must retain at least as many versions as
        scripts/prune_cloud_run_revisions.py keeps revisions (default 10),
        otherwise a retained revision can lose its image."""
        var = _find_variable(ar_variables, "keep_recent_versions")
        assert int(var["default"]) >= 10
