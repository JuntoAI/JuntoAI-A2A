"""Verify Cloud Run module (Req 3.1–3.2, 8.1)."""

import os
import pytest


class TestCloudRunServices:
    """Req 3.1–3.2: Backend and Frontend services declared."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_run_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(cloud_run_dir, "main.tf"))
        self.resources = self.main["resource"]

    def _find_service(self, name):
        for r in self.resources:
            if "google_cloud_run_v2_service" in r and name in r["google_cloud_run_v2_service"]:
                return r["google_cloud_run_v2_service"][name]
        return None

    def test_backend_service_declared(self):
        svc = self._find_service("backend")
        assert svc is not None, "Backend Cloud Run service must be declared"

    def test_frontend_service_declared(self):
        svc = self._find_service("frontend")
        assert svc is not None, "Frontend Cloud Run service must be declared"

    def test_backend_uses_region_variable(self):
        svc = self._find_service("backend")
        assert svc["location"] == "${var.gcp_region}"

    def test_frontend_uses_region_variable(self):
        svc = self._find_service("frontend")
        assert svc["location"] == "${var.gcp_region}"

    def test_backend_uses_sa_variable(self):
        svc = self._find_service("backend")
        template = svc["template"][0]
        assert template["service_account"] == "${var.backend_sa_email}"

    def test_frontend_uses_sa_variable(self):
        svc = self._find_service("frontend")
        template = svc["template"][0]
        assert template["service_account"] == "${var.frontend_sa_email}"


class TestCloudRunOutputs:
    """Req 8.1: Service URL outputs declared."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_run_dir, hcl_parser):
        self.outputs = hcl_parser(os.path.join(cloud_run_dir, "outputs.tf"))

    def test_backend_service_url_output(self):
        output_names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "backend_service_url" in output_names

    def test_frontend_service_url_output(self):
        output_names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "frontend_service_url" in output_names


class TestCloudRunVariables:
    @pytest.fixture(autouse=True)
    def _load(self, cloud_run_dir, hcl_parser):
        self.vars = hcl_parser(os.path.join(cloud_run_dir, "variables.tf"))

    def _var_names(self):
        return [list(v.keys())[0] for v in self.vars["variable"]]

    def test_required_variables_exist(self):
        names = self._var_names()
        for expected in [
            "gcp_project_id", "gcp_region",
            "backend_sa_email", "frontend_sa_email",
            "backend_image", "frontend_image",
        ]:
            assert expected in names, f"Variable {expected} must be declared"

    def test_service_name_defaults(self):
        for v in self.vars["variable"]:
            if "backend_service_name" in v:
                assert v["backend_service_name"]["default"] == "juntoai-backend"
            if "frontend_service_name" in v:
                assert v["frontend_service_name"]["default"] == "juntoai-frontend"


class TestCloudRunTerragrunt:
    """Child terragrunt.hcl includes root and declares dependencies."""

    def test_includes_root(self, cloud_run_dir):
        path = os.path.join(cloud_run_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert 'find_in_parent_folders("root.hcl")' in content
        assert 'include "root"' in content

    def test_depends_on_iam(self, cloud_run_dir):
        path = os.path.join(cloud_run_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "../iam" in content

    def test_depends_on_artifact_registry(self, cloud_run_dir):
        path = os.path.join(cloud_run_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "../artifact-registry" in content
