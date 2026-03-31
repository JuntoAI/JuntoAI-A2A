"""Verify IAM module (Req 7.1–7.4, 8.4)."""

import os
import pytest


class TestIamServiceAccounts:
    """Req 7.1–7.2: Backend_SA and Frontend_SA created."""

    @pytest.fixture(autouse=True)
    def _load(self, iam_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(iam_dir, "main.tf"))
        self.resources = self.main["resource"]

    def _find_sa(self, name):
        for r in self.resources:
            if "google_service_account" in r and name in r["google_service_account"]:
                return r["google_service_account"][name]
        return None

    def test_backend_sa_exists(self):
        sa = self._find_sa("backend")
        assert sa is not None, "Backend service account must be declared"
        assert sa["account_id"] == "backend-sa"

    def test_frontend_sa_exists(self):
        sa = self._find_sa("frontend")
        assert sa is not None, "Frontend service account must be declared"
        assert sa["account_id"] == "frontend-sa"


class TestIamRoleBindings:
    """Req 7.3–7.4: Backend_SA role bindings."""

    @pytest.fixture(autouse=True)
    def _load(self, iam_dir, hcl_parser):
        self.content = open(os.path.join(iam_dir, "main.tf")).read()
        self.main = hcl_parser(os.path.join(iam_dir, "main.tf"))
        self.resources = self.main["resource"]

    def _find_iam_member(self, name):
        for r in self.resources:
            if "google_project_iam_member" in r and name in r["google_project_iam_member"]:
                return r["google_project_iam_member"][name]
        return None

    def test_backend_datastore_user_role(self):
        binding = self._find_iam_member("backend_datastore")
        assert binding is not None
        assert binding["role"] == "roles/datastore.user"

    def test_backend_aiplatform_user_role(self):
        binding = self._find_iam_member("backend_aiplatform")
        assert binding is not None
        assert binding["role"] == "roles/aiplatform.user"

    def test_backend_run_invoker_conditional(self):
        binding = self._find_iam_member("backend_run_invoker")
        assert binding is not None
        assert binding["role"] == "roles/run.invoker"

    def test_no_frontend_privileged_roles(self):
        """Frontend_SA must not have datastore, aiplatform, or run.invoker roles."""
        for r in self.resources:
            if "google_project_iam_member" in r:
                for name, cfg in r["google_project_iam_member"].items():
                    member = cfg.get("member", "")
                    if "frontend" in member:
                        assert cfg["role"] not in [
                            "roles/datastore.user",
                            "roles/aiplatform.user",
                            "roles/run.invoker",
                        ], f"Frontend_SA must not have {cfg['role']}"


class TestIamOutputs:
    """Req 8.4: SA email outputs declared."""

    @pytest.fixture(autouse=True)
    def _load(self, iam_dir, hcl_parser):
        self.outputs = hcl_parser(os.path.join(iam_dir, "outputs.tf"))

    def test_backend_sa_email_output(self):
        output_names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "backend_sa_email" in output_names

    def test_frontend_sa_email_output(self):
        output_names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "frontend_sa_email" in output_names


class TestIamVariables:
    @pytest.fixture(autouse=True)
    def _load(self, iam_dir, hcl_parser):
        self.vars = hcl_parser(os.path.join(iam_dir, "variables.tf"))

    def test_gcp_project_id_variable(self):
        var_names = [list(v.keys())[0] for v in self.vars["variable"]]
        assert "gcp_project_id" in var_names

    def test_enable_run_invoker_variable(self):
        for v in self.vars["variable"]:
            if "enable_run_invoker" in v:
                assert v["enable_run_invoker"]["default"] is False
                return
        pytest.fail("enable_run_invoker variable not found")


class TestIamTerragrunt:
    def test_includes_root(self, iam_dir):
        path = os.path.join(iam_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert 'find_in_parent_folders("root.hcl")' in content
        assert 'include "root"' in content
