"""Verify Root HCL content via raw string matching (Req 2.1–2.7).

python-hcl2 cannot parse Terragrunt-specific functions like
read_terragrunt_config(), find_in_parent_folders(), path_relative_to_include(),
so we use regex / substring checks on the raw file content.
"""

import os
import re
import pytest


@pytest.fixture(scope="module")
def root_hcl_content(infra_root):
    path = os.path.join(infra_root, "root.hcl")
    with open(path) as f:
        return f.read()


@pytest.fixture(scope="module")
def env_hcl_content(infra_root):
    path = os.path.join(infra_root, "env.hcl")
    with open(path) as f:
        return f.read()


# --- Req 2.7: env.hcl loaded ---
class TestEnvHclLoaded:
    def test_reads_env_hcl(self, root_hcl_content):
        assert "read_terragrunt_config" in root_hcl_content
        assert "env.hcl" in root_hcl_content


# --- Req 2.1: GCS backend ---
class TestGcsBackend:
    def test_remote_state_gcs(self, root_hcl_content):
        assert 'backend = "gcs"' in root_hcl_content

    def test_remote_state_block(self, root_hcl_content):
        assert "remote_state" in root_hcl_content


# --- Req 2.2: Bucket from variable ---
class TestBucketVariable:
    def test_bucket_from_variable(self, root_hcl_content):
        assert "local.env_vars.locals.terraform_state_bucket" in root_hcl_content


# --- Req 2.3: path_relative_to_include ---
class TestStatePrefix:
    def test_path_relative_to_include(self, root_hcl_content):
        assert "path_relative_to_include()" in root_hcl_content


# --- Req 2.4: Project from variable ---
class TestProjectVariable:
    def test_project_from_variable(self, root_hcl_content):
        assert "local.env_vars.locals.gcp_project_id" in root_hcl_content


# --- Req 2.5: Region from variable ---
class TestRegionVariable:
    def test_location_from_variable(self, root_hcl_content):
        assert "local.env_vars.locals.gcp_region" in root_hcl_content


# --- Req 2.6: Both providers configured ---
class TestProviders:
    def test_google_provider(self, root_hcl_content):
        assert 'provider "google"' in root_hcl_content

    def test_google_beta_provider(self, root_hcl_content):
        assert 'provider "google-beta"' in root_hcl_content

    def test_generate_provider_block(self, root_hcl_content):
        assert 'generate "provider"' in root_hcl_content


# --- env.hcl content ---
class TestEnvHclContent:
    def test_has_gcp_project_id(self, env_hcl_content):
        assert "gcp_project_id" in env_hcl_content

    def test_has_gcp_region(self, env_hcl_content):
        assert "gcp_region" in env_hcl_content

    def test_has_terraform_state_bucket(self, env_hcl_content):
        assert "terraform_state_bucket" in env_hcl_content

    def test_has_locals_block(self, env_hcl_content):
        assert "locals" in env_hcl_content


# --- Inputs block ---
class TestInputsBlock:
    def test_inputs_gcp_project_id(self, root_hcl_content):
        assert re.search(r"inputs\s*=\s*\{", root_hcl_content)
        assert "gcp_project_id" in root_hcl_content

    def test_inputs_gcp_region(self, root_hcl_content):
        assert "gcp_region" in root_hcl_content
