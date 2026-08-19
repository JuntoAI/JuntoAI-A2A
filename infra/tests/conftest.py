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


@pytest.fixture(scope="session")
def cloud_build_dir(modules_root):
    return os.path.join(modules_root, "cloud-build")


@pytest.fixture(scope="session")
def alerting_dir(modules_root):
    return os.path.join(modules_root, "alerting")


@pytest.fixture(scope="session")
def billing_dir(modules_root):
    return os.path.join(modules_root, "billing")


@pytest.fixture(scope="session")
def repo_root(infra_root):
    """Absolute path to the repository root (parent of infra/)."""
    return os.path.abspath(os.path.join(infra_root, os.pardir))


# ---------------------------------------------------------------------------
# HCL parser helper
# ---------------------------------------------------------------------------

def _strip_one_quote_pair(value: str) -> str:
    """Remove exactly one pair of surrounding double quotes, if present.

    Deliberately not `.strip('"')`, which would eat every leading/trailing quote
    and mangle values that legitimately end in one.
    """
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _normalize(node):
    """Recursively unquote dict keys and string values from a parsed HCL tree.

    python-hcl2 8.x preserves the source quotes on block labels AND on string
    literals, so `service = "bigquery.googleapis.com"` arrives as
    '"bigquery.googleapis.com"' and a resource block is keyed
    '"google_project_service"'. Tests in this suite were written against the
    pre-8.x behaviour and index with bare names, so normalize once here rather
    than sprinkling quote handling across every assertion.

    Idempotent: already-unquoted input passes through unchanged.
    """
    if isinstance(node, dict):
        return {
            (_strip_one_quote_pair(k) if isinstance(k, str) else k): _normalize(v)
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [_normalize(item) for item in node]
    if isinstance(node, str):
        return _strip_one_quote_pair(node)
    return node


def parse_hcl_file(filepath: str) -> dict:
    """Parse a .tf or .hcl file using python-hcl2 and return the dict.

    Output is normalized by _normalize() so block labels and string values are
    unquoted regardless of the installed python-hcl2 major version.
    """
    with open(filepath, "r") as f:
        return _normalize(hcl2.load(f))


@pytest.fixture(scope="session")
def hcl_parser():
    """Expose the HCL parser helper as a fixture."""
    return parse_hcl_file


# ---------------------------------------------------------------------------
# Resource lookup helpers
# ---------------------------------------------------------------------------
#
# python-hcl2 8.x preserves the quotes around block labels, so a parsed resource
# block looks like:
#
#     {'"google_bigquery_dataset"': {'"billing_export"': {...}}}
#
# and `resource` is a LIST of single-entry dicts whose order follows the file.
#
# Tests must therefore never index positionally (`parsed["resource"][1][...]`)
# nor assume unquoted keys. Both assumptions broke when hcl2 moved to 8.x, which
# is why a large part of this suite currently fails. Use these helpers instead.
# ---------------------------------------------------------------------------

def _unquote(key: str) -> str:
    return key.strip('"')


def hcl_str(value):
    """Strip the quotes python-hcl2 8.x preserves around string literals.

    hcl2 8.x returns string values with their source quotes intact, so
    `service = "bigquery.googleapis.com"` parses to '"bigquery.googleapis.com"'.
    Compare through this helper rather than against a bare Python string.
    """
    if isinstance(value, str):
        return value.strip('"')
    return value


def iter_resources(parsed: dict):
    """Yield (resource_type, resource_name, body) for every resource block."""
    for block in parsed.get("resource", []) or []:
        for res_type, named in block.items():
            for res_name, body in named.items():
                yield _unquote(res_type), _unquote(res_name), body


def find_resource(parsed: dict, res_type: str, res_name: str) -> dict:
    """Return the body of a single resource block, or raise AssertionError."""
    for found_type, found_name, body in iter_resources(parsed):
        if found_type == res_type and found_name == res_name:
            return body
    available = [f"{t}.{n}" for t, n, _ in iter_resources(parsed)]
    raise AssertionError(
        f"resource {res_type}.{res_name} not found. Present: {available}"
    )


def resources_of_type(parsed: dict, res_type: str) -> dict:
    """Return {resource_name: body} for every resource of the given type."""
    return {
        name: body
        for found_type, name, body in iter_resources(parsed)
        if found_type == res_type
    }


def find_variable(parsed: dict, name: str) -> dict:
    """Return the body of a variable block, or raise AssertionError."""
    for block in parsed.get("variable", []) or []:
        for var_name, body in block.items():
            if _unquote(var_name) == name:
                return body
    raise AssertionError(f"variable {name!r} not declared")


@pytest.fixture(scope="session")
def hcl_helpers():
    """Expose the quote-tolerant lookup helpers to tests."""
    return {
        "iter_resources": iter_resources,
        "find_resource": find_resource,
        "resources_of_type": resources_of_type,
        "find_variable": find_variable,
        "hcl_str": hcl_str,
    }
