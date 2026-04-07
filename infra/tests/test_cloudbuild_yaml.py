"""Verify cloudbuild YAML pipeline definitions — kaniko-cached per-service pipelines.

All pipelines use a two-phase deploy strategy:
  1. Deploy new revision with --no-traffic (old instances keep serving)
  2. Migrate traffic to latest (Cloud Run drains old instances gracefully)
"""

import os
import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fullstack_pipeline(repo_root):
    path = os.path.join(repo_root, "cloudbuild.yaml")
    assert os.path.isfile(path), "cloudbuild.yaml must exist at repo root"
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def backend_pipeline(repo_root):
    path = os.path.join(repo_root, "cloudbuild-backend.yaml")
    assert os.path.isfile(path), "cloudbuild-backend.yaml must exist at repo root"
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def frontend_pipeline(repo_root):
    path = os.path.join(repo_root, "cloudbuild-frontend.yaml")
    assert os.path.isfile(path), "cloudbuild-frontend.yaml must exist at repo root"
    with open(path) as f:
        return yaml.safe_load(f)


def _steps_by_id(pipeline):
    return {s["id"]: s for s in pipeline["steps"]}


def _kaniko_args_dict(args):
    """Parse kaniko --key=value args into a dict."""
    result = {}
    for arg in args:
        if "=" in arg:
            key, val = arg.split("=", 1)
            result.setdefault(key, []).append(val)
        else:
            result[arg] = True
    return result


# ---------------------------------------------------------------------------
# Fullstack pipeline (cloudbuild.yaml)
# ---------------------------------------------------------------------------

class TestFullstackPipeline:
    """cloudbuild.yaml — builds and deploys both services with no-traffic + migrate."""

    def test_step_count(self, fullstack_pipeline):
        # test-backend, test-frontend,
        # build-backend, build-frontend, write-backend-env, write-frontend-env,
        # deploy-backend-no-traffic, deploy-frontend-no-traffic,
        # migrate-backend-traffic, migrate-frontend-traffic
        assert len(fullstack_pipeline["steps"]) == 10

    def test_step_ids(self, fullstack_pipeline):
        ids = {s["id"] for s in fullstack_pipeline["steps"]}
        expected = {
            "test-backend", "test-frontend",
            "build-backend", "build-frontend",
            "write-backend-env", "write-frontend-env",
            "deploy-backend-no-traffic", "deploy-frontend-no-traffic",
            "migrate-backend-traffic", "migrate-frontend-traffic",
        }
        assert ids == expected

    def test_builds_run_parallel(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert steps["build-backend"]["waitFor"] == ["-"]
        assert steps["build-frontend"]["waitFor"] == ["-"]

    def test_builds_use_kaniko(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert "kaniko" in steps["build-backend"]["name"]
        assert "kaniko" in steps["build-frontend"]["name"]

    def test_kaniko_cache_enabled(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        for step_id in ["build-backend", "build-frontend"]:
            args = _kaniko_args_dict(steps[step_id]["args"])
            assert "--cache" in args, f"{step_id} must enable kaniko cache"

    def test_deploy_no_traffic_waits_for_build(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert "build-backend" in steps["deploy-backend-no-traffic"]["waitFor"]
        assert "write-backend-env" in steps["deploy-backend-no-traffic"]["waitFor"]
        assert "test-backend" in steps["deploy-backend-no-traffic"]["waitFor"]
        assert "build-frontend" in steps["deploy-frontend-no-traffic"]["waitFor"]
        assert "test-frontend" in steps["deploy-frontend-no-traffic"]["waitFor"]

    def test_deploy_uses_no_traffic_flag(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert "--no-traffic" in steps["deploy-backend-no-traffic"]["args"]
        assert "--no-traffic" in steps["deploy-frontend-no-traffic"]["args"]

    def test_migrate_waits_for_no_traffic_deploy(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert "deploy-backend-no-traffic" in steps["migrate-backend-traffic"]["waitFor"]
        assert "deploy-frontend-no-traffic" in steps["migrate-frontend-traffic"]["waitFor"]

    def test_migrate_uses_to_latest(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert "--to-latest" in steps["migrate-backend-traffic"]["args"]
        assert "--to-latest" in steps["migrate-frontend-traffic"]["args"]


# ---------------------------------------------------------------------------
# Backend pipeline (cloudbuild-backend.yaml)
# ---------------------------------------------------------------------------

class TestBackendPipeline:
    """cloudbuild-backend.yaml — backend only with no-traffic + migrate."""

    def test_step_count(self, backend_pipeline):
        # test-backend, build-backend, write-backend-env,
        # deploy-backend-no-traffic, migrate-backend-traffic
        assert len(backend_pipeline["steps"]) == 5

    def test_step_ids(self, backend_pipeline):
        ids = {s["id"] for s in backend_pipeline["steps"]}
        assert ids == {"test-backend", "build-backend", "write-backend-env",
                       "deploy-backend-no-traffic", "migrate-backend-traffic"}

    def test_build_runs_first(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert steps["build-backend"]["waitFor"] == ["-"]

    def test_build_uses_kaniko(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "kaniko" in steps["build-backend"]["name"]

    def test_kaniko_cache_enabled(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        args = _kaniko_args_dict(steps["build-backend"]["args"])
        assert "--cache" in args

    def test_kaniko_pushes_sha_and_latest(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        args = _kaniko_args_dict(steps["build-backend"]["args"])
        destinations = args.get("--destination", [])
        assert len(destinations) == 2
        dest_str = " ".join(destinations)
        assert "$SHORT_SHA" in dest_str
        assert "latest" in dest_str

    def test_deploy_no_traffic_waits_for_build(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "build-backend" in steps["deploy-backend-no-traffic"]["waitFor"]
        assert "write-backend-env" in steps["deploy-backend-no-traffic"]["waitFor"]
        assert "test-backend" in steps["deploy-backend-no-traffic"]["waitFor"]

    def test_deploy_uses_no_traffic_flag(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "--no-traffic" in steps["deploy-backend-no-traffic"]["args"]

    def test_deploy_uses_cloud_sdk(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert steps["deploy-backend-no-traffic"]["name"] == "gcr.io/google.com/cloudsdktool/cloud-sdk"

    def test_deploy_uses_sha_tag(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        args = steps["deploy-backend-no-traffic"]["args"]
        image_idx = args.index("--image") + 1
        assert "$SHORT_SHA" in args[image_idx]
        assert "latest" not in args[image_idx]

    def test_deploy_has_service_account_flag(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "--service-account" in steps["deploy-backend-no-traffic"]["args"]

    def test_deploy_uses_env_vars_file(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "--env-vars-file" in steps["deploy-backend-no-traffic"]["args"]

    def test_write_env_step_sets_cors(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        args = steps["write-backend-env"]["args"]
        script = args[1] if len(args) > 1 else ""
        assert "CORS_ALLOWED_ORIGINS" in script

    def test_migrate_waits_for_no_traffic_deploy(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "deploy-backend-no-traffic" in steps["migrate-backend-traffic"]["waitFor"]

    def test_migrate_uses_to_latest(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "--to-latest" in steps["migrate-backend-traffic"]["args"]

    def test_no_frontend_steps(self, backend_pipeline):
        ids = {s["id"] for s in backend_pipeline["steps"]}
        assert not any("frontend" in sid for sid in ids)

    def test_substitutions_use_variables(self, backend_pipeline):
        subs = backend_pipeline.get("substitutions", {})
        assert "_REGION" in subs
        assert "_PROJECT_ID" in subs
        assert "_BACKEND_SERVICE" in subs

    def test_no_deploy_wait_substitutions(self, backend_pipeline):
        """Option A polling variables must not be present."""
        subs = backend_pipeline.get("substitutions", {})
        assert "_DEPLOY_WAIT_RETRIES" not in subs
        assert "_DEPLOY_WAIT_INTERVAL" not in subs


# ---------------------------------------------------------------------------
# Frontend pipeline (cloudbuild-frontend.yaml)
# ---------------------------------------------------------------------------

class TestFrontendPipeline:
    """cloudbuild-frontend.yaml — frontend only with no-traffic + migrate."""

    def test_step_count(self, frontend_pipeline):
        # test-frontend, build-frontend, write-frontend-env,
        # deploy-frontend-no-traffic, migrate-frontend-traffic
        assert len(frontend_pipeline["steps"]) == 5

    def test_step_ids(self, frontend_pipeline):
        ids = {s["id"] for s in frontend_pipeline["steps"]}
        assert ids == {"test-frontend", "build-frontend", "write-frontend-env",
                       "deploy-frontend-no-traffic",
                       "migrate-frontend-traffic"}

    def test_build_runs_first(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert steps["build-frontend"]["waitFor"] == ["-"]

    def test_build_uses_kaniko(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert "kaniko" in steps["build-frontend"]["name"]

    def test_kaniko_cache_enabled(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        args = _kaniko_args_dict(steps["build-frontend"]["args"])
        assert "--cache" in args

    def test_kaniko_pushes_sha_and_latest(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        args = _kaniko_args_dict(steps["build-frontend"]["args"])
        destinations = args.get("--destination", [])
        assert len(destinations) == 2
        dest_str = " ".join(destinations)
        assert "$SHORT_SHA" in dest_str
        assert "latest" in dest_str

    def test_deploy_no_traffic_waits_for_build(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert "build-frontend" in steps["deploy-frontend-no-traffic"]["waitFor"]
        assert "test-frontend" in steps["deploy-frontend-no-traffic"]["waitFor"]

    def test_deploy_uses_no_traffic_flag(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert "--no-traffic" in steps["deploy-frontend-no-traffic"]["args"]

    def test_deploy_uses_cloud_sdk(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert steps["deploy-frontend-no-traffic"]["name"] == "gcr.io/google.com/cloudsdktool/cloud-sdk"

    def test_deploy_uses_sha_tag(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        args = steps["deploy-frontend-no-traffic"]["args"]
        image_idx = args.index("--image") + 1
        assert "$SHORT_SHA" in args[image_idx]
        assert "latest" not in args[image_idx]

    def test_deploy_has_service_account_flag(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert "--service-account" in steps["deploy-frontend-no-traffic"]["args"]

    def test_migrate_waits_for_no_traffic_deploy(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert "deploy-frontend-no-traffic" in steps["migrate-frontend-traffic"]["waitFor"]

    def test_migrate_uses_to_latest(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert "--to-latest" in steps["migrate-frontend-traffic"]["args"]

    def test_no_backend_steps(self, frontend_pipeline):
        ids = {s["id"] for s in frontend_pipeline["steps"]}
        assert not any("backend" in sid for sid in ids)

    def test_build_passes_firebase_build_args(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        args = " ".join(steps["build-frontend"]["args"])
        assert "NEXT_PUBLIC_FIREBASE_API_KEY" in args
        assert "NEXT_PUBLIC_FIREBASE_PROJECT_ID" in args
        assert "NEXT_PUBLIC_FIREBASE_APP_ID" in args

    def test_frontend_deploy_sets_backend_url(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        args = steps["deploy-frontend-no-traffic"]["args"]
        assert "--env-vars-file" in args

    def test_substitutions_use_variables(self, frontend_pipeline):
        subs = frontend_pipeline.get("substitutions", {})
        assert "_REGION" in subs
        assert "_PROJECT_ID" in subs
        assert "_FRONTEND_SERVICE" in subs

    def test_no_deploy_wait_substitutions(self, frontend_pipeline):
        """Option A polling variables must not be present."""
        subs = frontend_pipeline.get("substitutions", {})
        assert "_DEPLOY_WAIT_RETRIES" not in subs
        assert "_DEPLOY_WAIT_INTERVAL" not in subs
