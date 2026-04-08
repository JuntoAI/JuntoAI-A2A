"""Verify alerting/ Terraform module — structure, variables, outputs, terragrunt."""

import os
import pytest


class TestAlertingModuleStructure:
    """Module directory exists with required files."""

    def test_main_tf_exists(self, alerting_dir):
        assert os.path.isfile(os.path.join(alerting_dir, "main.tf"))

    def test_variables_tf_exists(self, alerting_dir):
        assert os.path.isfile(os.path.join(alerting_dir, "variables.tf"))

    def test_outputs_tf_exists(self, alerting_dir):
        assert os.path.isfile(os.path.join(alerting_dir, "outputs.tf"))

    def test_backend_tf_exists(self, alerting_dir):
        assert os.path.isfile(os.path.join(alerting_dir, "backend.tf"))

    def test_terragrunt_hcl_exists(self, alerting_dir):
        assert os.path.isfile(os.path.join(alerting_dir, "terragrunt.hcl"))


class TestAlertingVariables:
    """Variables with correct types and defaults."""

    @pytest.fixture(autouse=True)
    def _load(self, alerting_dir, hcl_parser):
        self.vars = hcl_parser(os.path.join(alerting_dir, "variables.tf"))

    def _find_var(self, name):
        for v in self.vars["variable"]:
            if name in v:
                return v[name]
        return None

    # --- Required variables (no default) ---

    def test_gcp_project_id_exists(self):
        var = self._find_var("gcp_project_id")
        assert var is not None, "gcp_project_id variable must exist"
        assert var["type"] == "string"

    def test_gcp_project_id_no_default(self):
        var = self._find_var("gcp_project_id")
        assert "default" not in var, "gcp_project_id must not have a default"

    def test_gcp_project_number_exists(self):
        var = self._find_var("gcp_project_number")
        assert var is not None, "gcp_project_number variable must exist"
        assert var["type"] == "string"

    def test_gcp_project_number_no_default(self):
        var = self._find_var("gcp_project_number")
        assert "default" not in var, "gcp_project_number must not have a default"

    def test_gcp_region_exists(self):
        var = self._find_var("gcp_region")
        assert var is not None, "gcp_region variable must exist"
        assert var["type"] == "string"

    def test_gcp_region_no_default(self):
        var = self._find_var("gcp_region")
        assert "default" not in var, "gcp_region must not have a default"

    def test_backend_service_name_exists(self):
        var = self._find_var("backend_service_name")
        assert var is not None, "backend_service_name variable must exist"
        assert var["type"] == "string"

    def test_backend_service_name_no_default(self):
        var = self._find_var("backend_service_name")
        assert "default" not in var, "backend_service_name must not have a default"

    def test_frontend_service_name_exists(self):
        var = self._find_var("frontend_service_name")
        assert var is not None, "frontend_service_name variable must exist"
        assert var["type"] == "string"

    def test_frontend_service_name_no_default(self):
        var = self._find_var("frontend_service_name")
        assert "default" not in var, "frontend_service_name must not have a default"

    # --- Threshold variables (with defaults) ---

    def test_backend_error_threshold(self):
        var = self._find_var("backend_error_threshold")
        assert var is not None, "backend_error_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 5

    def test_backend_fatal_threshold(self):
        var = self._find_var("backend_fatal_threshold")
        assert var is not None, "backend_fatal_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 0

    def test_frontend_error_threshold(self):
        var = self._find_var("frontend_error_threshold")
        assert var is not None, "frontend_error_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 5

    def test_backend_cpu_threshold(self):
        var = self._find_var("backend_cpu_threshold")
        assert var is not None, "backend_cpu_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 0.8

    def test_backend_memory_threshold(self):
        var = self._find_var("backend_memory_threshold")
        assert var is not None, "backend_memory_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 0.85

    def test_backend_5xx_threshold(self):
        var = self._find_var("backend_5xx_threshold")
        assert var is not None, "backend_5xx_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 10

    def test_frontend_5xx_threshold(self):
        var = self._find_var("frontend_5xx_threshold")
        assert var is not None, "frontend_5xx_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 10

    def test_backend_instance_threshold(self):
        var = self._find_var("backend_instance_threshold")
        assert var is not None, "backend_instance_threshold variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 10

    def test_notification_rate_limit_seconds(self):
        var = self._find_var("notification_rate_limit_seconds")
        assert var is not None, "notification_rate_limit_seconds variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 300

    def test_auto_close_seconds(self):
        var = self._find_var("auto_close_seconds")
        assert var is not None, "auto_close_seconds variable must exist"
        assert var["type"] == "number"
        assert var["default"] == 1800


class TestAlertingOutputs:
    """Required outputs for the alerting module."""

    @pytest.fixture(autouse=True)
    def _load(self, alerting_dir, hcl_parser):
        self.outputs = hcl_parser(os.path.join(alerting_dir, "outputs.tf"))

    def _output_names(self):
        return [list(o.keys())[0] for o in self.outputs["output"]]

    def test_pubsub_topic_name_output(self):
        assert "pubsub_topic_name" in self._output_names()

    def test_notifier_function_url_output(self):
        assert "notifier_function_url" in self._output_names()

    def test_alerting_sa_email_output(self):
        assert "alerting_sa_email" in self._output_names()


class TestAlertingTerragrunt:
    """Terragrunt config with root include and dependencies."""

    def test_includes_root(self, alerting_dir):
        path = os.path.join(alerting_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert 'find_in_parent_folders("root.hcl")' in content
        assert 'include "root"' in content

    def test_depends_on_iam(self, alerting_dir):
        path = os.path.join(alerting_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "../iam" in content

    def test_depends_on_cloud_run(self, alerting_dir):
        path = os.path.join(alerting_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "../cloud-run" in content

    def test_has_dependencies_block(self, alerting_dir, hcl_parser):
        tg = hcl_parser(os.path.join(alerting_dir, "terragrunt.hcl"))
        assert "dependencies" in tg, "terragrunt.hcl must have a dependencies block"

    def test_has_dependency_iam(self, alerting_dir, hcl_parser):
        tg = hcl_parser(os.path.join(alerting_dir, "terragrunt.hcl"))
        assert "dependency" in tg, "terragrunt.hcl must have dependency blocks"
        dep_names = [list(d.keys())[0] for d in tg["dependency"]]
        assert "iam" in dep_names, "dependency 'iam' must be declared"

    def test_has_dependency_cloud_run(self, alerting_dir, hcl_parser):
        tg = hcl_parser(os.path.join(alerting_dir, "terragrunt.hcl"))
        dep_names = [list(d.keys())[0] for d in tg["dependency"]]
        assert "cloud_run" in dep_names, "dependency 'cloud_run' must be declared"
