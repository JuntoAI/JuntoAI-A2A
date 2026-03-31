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
