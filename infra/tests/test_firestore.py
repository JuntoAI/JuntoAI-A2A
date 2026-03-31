"""Verify Firestore module (Req 5.1–5.3, 8.3)."""

import os
import pytest


class TestFirestoreMain:
    """Req 5.1–5.3: Native mode, API enablement, configurable location."""

    @pytest.fixture(autouse=True)
    def _load(self, firestore_dir, hcl_parser):
        self.main = hcl_parser(os.path.join(firestore_dir, "main.tf"))

    def test_firestore_native_mode(self):
        db = self.main["resource"][1]["google_firestore_database"]["database"]
        assert db["type"] == "FIRESTORE_NATIVE"

    def test_firestore_api_enabled(self):
        svc = self.main["resource"][0]["google_project_service"]["firestore"]
        assert svc["service"] == "firestore.googleapis.com"

    def test_disable_on_destroy_false(self):
        svc = self.main["resource"][0]["google_project_service"]["firestore"]
        assert svc["disable_on_destroy"] is False

    def test_location_from_variable(self):
        db = self.main["resource"][1]["google_firestore_database"]["database"]
        assert db["location_id"] == "${var.gcp_region}"


class TestFirestoreVariables:
    @pytest.fixture(autouse=True)
    def _load(self, firestore_dir, hcl_parser):
        self.vars = hcl_parser(os.path.join(firestore_dir, "variables.tf"))

    def test_gcp_project_id_variable(self):
        var_names = [list(v.keys())[0] for v in self.vars["variable"]]
        assert "gcp_project_id" in var_names

    def test_gcp_region_variable(self):
        var_names = [list(v.keys())[0] for v in self.vars["variable"]]
        assert "gcp_region" in var_names


class TestFirestoreOutputs:
    """Req 8.3: Output database_name declared."""

    @pytest.fixture(autouse=True)
    def _load(self, firestore_dir, hcl_parser):
        self.outputs = hcl_parser(os.path.join(firestore_dir, "outputs.tf"))

    def test_database_name_output(self):
        output_names = [list(o.keys())[0] for o in self.outputs["output"]]
        assert "database_name" in output_names


class TestFirestoreTerragrunt:
    def test_includes_root(self, firestore_dir):
        path = os.path.join(firestore_dir, "terragrunt.hcl")
        with open(path) as f:
            content = f.read()
        assert "find_in_parent_folders()" in content
        assert 'include "root"' in content
