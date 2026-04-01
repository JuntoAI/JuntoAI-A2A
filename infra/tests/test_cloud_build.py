"""Verify cloud-build/ Terragrunt module — path-filtered triggers."""

import os
import pytest


class TestCloudBuildModuleStructure:
    """Module directory exists with required files."""

    def test_main_tf_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "main.tf"))

    def test_variables_tf_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "variables.tf"))

    def test_outputs_tf_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "outputs.tf"))

    def test_terragrunt_hcl_exists(self, cloud_build_dir):
        assert os.path.isfile(os.path.join(cloud_build_dir, "terragrunt.hcl"))


class TestCloudBuildServiceAccount:
    """Cloud Build SA with correct roles."""

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


class TestCloudBuildTriggers:
    """Three path-filtered triggers: backend, frontend, fullstack."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_build_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(cloud_build_dir, "main.tf"))
        self.resources = self.main["resource"]

    def _find_trigger(self, name):
        for r in self.resources:
            if "google_cloudbuild_trigger" in r and name in r["google_cloudbuild_trigger"]:
                return r["google_cloudbuild_trigger"][name]
        return None

    # --- Backend trigger ---
    def test_backend_trigger_exists(self):
        assert self._find_trigger("backend") is not None

    def test_backend_trigger_name(self):
        trigger = self._find_trigger("backend")
        assert trigger["name"] == "juntoai-cicd-backend"

    def test_backend_trigger_filename(self):
        trigger = self._find_trigger("backend")
        assert trigger["filename"] == "cloudbuild-backend.yaml"

    def test_backend_trigger_included_files(self):
        trigger = self._find_trigger("backend")
        assert trigger["included_files"] == ["backend/**"]

    def test_backend_trigger_has_github_config(self):
        trigger = self._find_trigger("backend")
        assert "github" in trigger

    # --- Frontend trigger ---
    def test_frontend_trigger_exists(self):
        assert self._find_trigger("frontend") is not None

    def test_frontend_trigger_name(self):
        trigger = self._find_trigger("frontend")
        assert trigger["name"] == "juntoai-cicd-frontend"

    def test_frontend_trigger_filename(self):
        trigger = self._find_trigger("frontend")
        assert trigger["filename"] == "cloudbuild-frontend.yaml"

    def test_frontend_trigger_included_files(self):
        trigger = self._find_trigger("frontend")
        assert trigger["included_files"] == ["frontend/**"]

    def test_frontend_trigger_has_github_config(self):
        trigger = self._find_trigger("frontend")
        assert "github" in trigger

    # --- Fullstack trigger ---
    def test_fullstack_trigger_exists(self):
        assert self._find_trigger("fullstack") is not None

    def test_fullstack_trigger_name(self):
        trigger = self._find_trigger("fullstack")
        assert trigger["name"] == "juntoai-cicd-fullstack"

    def test_fullstack_trigger_filename(self):
        trigger = self._find_trigger("fullstack")
        assert trigger["filename"] == "cloudbuild.yaml"

    def test_fullstack_trigger_included_files(self):
        trigger = self._find_trigger("fullstack")
        included = trigger["included_files"]
        assert "cloudbuild.yaml" in included
        assert "infra/**" in included

    def test_fullstack_trigger_has_github_config(self):
        trigger = self._find_trigger("fullstack")
        assert "github" in trigger

    # --- Substitutions ---
    def test_backend_trigger_substitutions(self):
        trigger = self._find_trigger("backend")
        subs = trigger["substitutions"]
        for key in ["_REGION", "_PROJECT_ID", "_REPO_NAME", "_BACKEND_SERVICE",
                     "_FRONTEND_SERVICE", "_BACKEND_SA_EMAIL"]:
            assert key in subs, f"Substitution {key} missing from backend trigger"

    def test_frontend_trigger_substitutions(self):
        trigger = self._find_trigger("frontend")
        subs = trigger["substitutions"]
        for key in ["_REGION", "_PROJECT_ID", "_REPO_NAME", "_FRONTEND_SERVICE", "_FRONTEND_SA_EMAIL"]:
            assert key in subs, f"Substitution {key} missing from frontend trigger"

    def test_fullstack_trigger_substitutions(self):
        trigger = self._find_trigger("fullstack")
        subs = trigger["substitutions"]
        for key in ["_REGION", "_PROJECT_ID", "_REPO_NAME", "_BACKEND_SERVICE",
                     "_FRONTEND_SERVICE", "_BACKEND_SA_EMAIL", "_FRONTEND_SA_EMAIL"]:
            assert key in subs, f"Substitution {key} missing from fullstack trigger"

    # --- Exactly 3 triggers ---
    def test_exactly_three_triggers(self):
        count = 0
        for r in self.resources:
            if "google_cloudbuild_trigger" in r:
                count += len(r["google_cloudbuild_trigger"])
        assert count == 3, f"Expected 3 triggers, got {count}"


class TestCloudBuildVariables:
    """Variables with defaults and validation."""

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
    """Required outputs for all three triggers."""

    @pytest.fixture(autouse=True)
    def _load(self, cloud_build_dir, hcl_parser):
        self.outputs = hcl_parser(os.path.join(cloud_build_dir, "outputs.tf"))

    def _output_names(self):
        return [list(o.keys())[0] for o in self.outputs["output"]]

    def test_backend_trigger_id_output(self):
        assert "backend_trigger_id" in self._output_names()

    def test_frontend_trigger_id_output(self):
        assert "frontend_trigger_id" in self._output_names()

    def test_fullstack_trigger_id_output(self):
        assert "fullstack_trigger_id" in self._output_names()

    def test_backend_trigger_name_output(self):
        assert "backend_trigger_name" in self._output_names()

    def test_frontend_trigger_name_output(self):
        assert "frontend_trigger_name" in self._output_names()

    def test_fullstack_trigger_name_output(self):
        assert "fullstack_trigger_name" in self._output_names()

    def test_cloudbuild_sa_email_output(self):
        assert "cloudbuild_sa_email" in self._output_names()


class TestCloudBuildTerragrunt:
    """Terragrunt config with root include and dependencies."""

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
