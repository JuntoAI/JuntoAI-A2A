"""Verify Vertex AI module (Req 6.1)."""

import os
import pytest


class TestVertexAiMain:
    """Req 6.1: aiplatform.googleapis.com API enablement."""

    @pytest.fixture(autouse=True)
    def _load(self, vertex_ai_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(vertex_ai_dir, "main.tf"))

    def test_aiplatform_api_enabled(self):
        svc = self.main["resource"][0]["google_project_service"]["vertex_ai"]
        assert svc["service"] == "aiplatform.googleapis.com"

    def test_disable_on_destroy_false(self):
        svc = self.main["resource"][0]["google_project_service"]["vertex_ai"]
        assert svc["disable_on_destroy"] is False

    def test_project_from_variable(self):
        svc = self.main["resource"][0]["google_project_service"]["vertex_ai"]
        assert svc["project"] == "${var.gcp_project_id}"


class TestVertexAiVariables:
    @pytest.fixture(autouse=True)
    def _load(self, vertex_ai_dir, hcl_parser):
        self.vars = hcl_parser(os.path.join(vertex_ai_dir, "variables.tf"))

    def test_gcp_project_id_variable(self):
        var_names = [list(v.keys())[0] for v in self.vars["variable"]]
        assert "gcp_project_id" in var_names


class TestVertexAiTerragrunt:
    def test_includes_root(self, vertex_ai_dir):
        path = os.path.join(vertex_ai_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "find_in_parent_folders()" in content
        assert 'include "root"' in content
