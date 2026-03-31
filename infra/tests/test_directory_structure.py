"""Verify monorepo directory structure (Req 1.1–1.6)."""

import os
import pytest


class TestTopLevelDirectories:
    """Req 1.1–1.4: Top-level directories exist."""

    @pytest.mark.parametrize("dirname", ["infra", "backend", "frontend", "docs"])
    def test_top_level_dir_exists(self, infra_root, dirname):
        repo_root = os.path.dirname(infra_root)
        assert os.path.isdir(os.path.join(repo_root, dirname)), (
            f"Top-level /{dirname} directory must exist"
        )


class TestInfraRootFiles:
    """Req 1.5: Root terragrunt.hcl exists."""

    def test_root_terragrunt_hcl_exists(self, infra_root):
        assert os.path.isfile(os.path.join(infra_root, "root.hcl"))

    def test_env_hcl_exists(self, infra_root):
        assert os.path.isfile(os.path.join(infra_root, "env.hcl"))


class TestModuleDirectories:
    """Req 1.6: /modules subdirectory with one dir per GCP resource."""

    EXPECTED_MODULES = [
        "artifact-registry",
        "firestore",
        "vertex-ai",
        "iam",
        "cloud-run",
    ]

    def test_modules_dir_exists(self, modules_root):
        assert os.path.isdir(modules_root)

    @pytest.mark.parametrize("module", EXPECTED_MODULES)
    def test_module_dir_exists(self, modules_root, module):
        assert os.path.isdir(os.path.join(modules_root, module)), (
            f"Module directory /modules/{module} must exist"
        )
