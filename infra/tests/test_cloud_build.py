"""Verify cloud-build/ Terragrunt module (Req 7.1–7.4, 8.1–8.4, 10.1–10.6)."""

import os
import pytest


class TestCloudBuildModuleStructure:
    """Req 10.1: Module directory exists with required files."""

    def test_main_tf_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "main.tf"))

    def test_variables_tf_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "variables.tf"))

    def test_outputs_tf_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "outputs.tf"))

    def test_terragrunt_hcl_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "terragrunt.hcl"))


class TestCloudBuildServiceAccount:
    """Req 8.1–8.3: Cloud Build SA with correct roles."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_build_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(cloud_build_dir, "main.tf"))
        self.resources = self.main["resource"]

    def _find_sa(self, name):
        for r in self.resources:
            if "google_service_account" in r and name in r["google_service_account"]:
                return r["google_service_account"][name]
        return None

    def _find_iam_member(self, name):
        for r in self.resources:
            if "google_project_iam_member" in r and name in r["google_project_iam_member"]:
                return r["google_project_iam_member"][name]
        return None

    def test_cloudbuild_sa_exists(self):
        sa = self._find_sa("cloudbuild")
        assert sa is not None, "Cloud Build SA must be declared"
        assert sa["account_id"] == "cloudbuild-sa"

    def test_ar_writer_role(self):
        binding = self._find_iam_member("cloudbuild_ar_writer")
        assert binding is not None
        assert binding["role"] == "roles/artifactregistry.writer"

    def test_run_admin_role(self):
        binding = self._find_iam_member("cloudbuild_run_admin")
        assert binding is not None
        assert binding["role"] == "roles/run.admin"

    def test_sa_user_role(self):
        binding = self._find_iam_member("cloudbuild_sa_user")
        assert binding is not None
        assert binding["role"] == "roles/iam.serviceAccountUser"

    def test_exactly_four_iam_bindings(self):
        iam_count = 0
        for r in self.resources:
            if "google_project_iam_member" in r:
                iam_count += len(r["google_project_iam_member"])
        assert iam_count == 4, f"Expected exactly 4 IAM bindings, got {iam_count}"


class TestCloudBuildTrigger:
    """Req 7.1–7.4, 10.1–10.4: Trigger configuration."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_build_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(cloud_build_dir, "main.tf"))
        self.resources = self.main["resource"]

    def _find_trigger(self):
        for r in self.resources:
            if "google_cloudbuild_trigger" in r and "main" in r["google_cloudbuild_trigger"]:
                return r["google_cloudbuild_trigger"]["main"]
        return None

    def test_trigger_exists(self):
        trigger = self._find_trigger()
        assert trigger is not None, "Cloud Build trigger must be declared"

    def test_trigger_name(self):
        trigger = self._find_trigger()
        assert trigger["name"] == "juntoai-cicd-main"

    def test_trigger_filename(self):
        trigger = self._find_trigger()
        assert trigger["filename"] == "cloudbuild.yaml"

    def test_trigger_has_substitutions(self):
        trigger = self._find_trigger()
        subs = trigger["substitutions"]
        required_keys = [
            "_REGION", "_PROJECT_ID", "_REPO_NAME",
            "_BACKEND_SERVICE", "_FRONTEND_SERVICE",
            "_BACKEND_SA_EMAIL", "_FRONTEND_SA_EMAIL",
        ]
        for key in required_keys:
            assert key in subs, f"Substitution {key} missing from trigger"

    def test_trigger_has_github_config(self):
        trigger = self._find_trigger()
        assert "github" in trigger, "Trigger must have github config"


class TestCloudBuildVariables:
    """Req 8.4, 10.6: Variables with defaults and validation."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_build_dir, hcl_parser):
        self.vars = hcl_parser(os.path.join(cloud_build_dir, "variables.tf"))

    def _find_var(self, name):
        for v in self.vars["variable"]:
            if name in v:
                return v[name]
        return None

    def test_trigger_enabled_defaults_false(self):
        var = self._find_var("trigger_enabled")
        assert var is not None, "trigger_enabled variable must exist"
        assert var["default"] is False

    def test_repository_id_default(self):
        var = self._find_var("repository_id")
        assert var is not None
        assert var["default"] == "juntoai-docker"

    def test_allowed_roles_has_validation(self):
        var = self._find_var("allowed_roles")
        assert var is not None
        assert "validation" in var, "allowed_roles must have a validation block"


class TestCloudBuildOutputs:
    """Req 10.5: Required outputs."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_build_dir, hcl_parser):
        self.outputs = hcl_parser(os.path.join(cloud_build_dir, "outputs.tf"))

    def test_trigger_id_output(self):
        names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "trigger_id" in names

    def test_trigger_name_output(self):
        names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "trigger_name" in names

    def test_cloudbuild_sa_email_output(self):
        names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "cloudbuild_sa_email" in names


class TestCloudBuildTerragrunt:
    """Req 10.1: Terragrunt config with root include and dependencies."""

    def test_includes_root(self, cloud_build_dir):
        path = os.path.join(cloud_build_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert 'find_in_parent_folders("root.hcl")' in content
        assert 'include "root"' in content

    def test_depends_on_iam(self, cloud_build_dir):
        path = os.path.join(cloud_build_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "../iam" in content

    def test_depends_on_artifact_registry(self, cloud_build_dir):
        path = os.path.join(cloud_build_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "../artifact-registry" in content
