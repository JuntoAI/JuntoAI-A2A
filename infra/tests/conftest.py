"""Shared fixtures for infrastructure static-analysis tests."""

import os
import json
import pytest
import hcl2


# ---------------------------------------------------------------------------
# Path fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def infra_root():
    """Absolute path to the infra/ directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


@pytest.fixture(scope="session")
def modules_root(infra_root):
    """Absolute path to infra/modules/."""
    return os.path.join(infra_root, "modules")


@pytest.fixture(scope="session")
def artifact_registry_dir(modules_root):
    return os.path.join(modules_root, "artifact-registry")


@pytest.fixture(scope="session")
def firestore_dir(modules_root):
    return os.path.join(modules_root, "firestore")


@pytest.fixture(scope="session")
def vertex_ai_dir(modules_root):
    return os.path.join(modules_root, "vertex-ai")


@pytest.fixture(scope="session")
def iam_dir(modules_root):
    return os.path.join(modules_root, "iam")


@pytest.fixture(scope="session")
def cloud_run_dir(modules_root):
    return os.path.join(modules_root, "cloud-run")


# ---------------------------------------------------------------------------
# HCL parser helper
# ---------------------------------------------------------------------------

def parse_hcl_file(filepath: str) -> dict:
    """Parse a .tf or .hcl file using python-hcl2 and return the dict."""
    with open(filepath, "r") as f:
        return hcl2.load(f)


@pytest.fixture(scope="session")
def hcl_parser():
    """Expose the HCL parser helper as a fixture."""
    return parse_hcl_file
