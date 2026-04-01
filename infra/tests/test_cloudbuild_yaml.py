"""Verify cloudbuild YAML pipeline definitions — split per-service pipelines."""

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


# ---------------------------------------------------------------------------
# Fullstack pipeline (cloudbuild.yaml)
# ---------------------------------------------------------------------------

class TestFullstackPipeline:
    """cloudbuild.yaml — builds and deploys both services."""

    def test_has_seven_steps(self, fullstack_pipeline):
        assert len(fullstack_pipeline["steps"]) == 7

    def test_has_images_field(self, fullstack_pipeline):
        assert "images" in fullstack_pipeline

    def test_four_images_declared(self, fullstack_pipeline):
        assert len(fullstack_pipeline["images"]) == 4

    def test_step_ids(self, fullstack_pipeline):
        ids = {s["id"] for s in fullstack_pipeline["steps"]}
        expected = {"build-backend", "build-frontend", "push-backend",
                    "push-frontend", "write-backend-env", "deploy-backend",
                    "deploy-frontend"}
        assert ids == expected

    def test_builds_run_parallel(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert steps["build-backend"]["waitFor"] == ["-"]
        assert steps["build-frontend"]["waitFor"] == ["-"]

    def test_deploy_waits_for_push(self, fullstack_pipeline):
        steps = _steps_by_id(fullstack_pipeline)
        assert "push-backend" in steps["deploy-backend"]["waitFor"]
        assert "write-backend-env" in steps["deploy-backend"]["waitFor"]
        assert steps["deploy-frontend"]["waitFor"] == ["push-frontend"]


# ---------------------------------------------------------------------------
# Backend pipeline (cloudbuild-backend.yaml)
# ---------------------------------------------------------------------------

class TestBackendPipeline:
    """cloudbuild-backend.yaml — backend only."""

    def test_has_four_steps(self, backend_pipeline):
        assert len(backend_pipeline["steps"]) == 4

    def test_step_ids(self, backend_pipeline):
        ids = {s["id"] for s in backend_pipeline["steps"]}
        assert ids == {"build-backend", "push-backend", "write-backend-env", "deploy-backend"}

    def test_has_images_field(self, backend_pipeline):
        assert "images" in backend_pipeline

    def test_two_images_declared(self, backend_pipeline):
        assert len(backend_pipeline["images"]) == 2

    def test_build_runs_first(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert steps["build-backend"]["waitFor"] == ["-"]

    def test_push_waits_for_build(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert steps["push-backend"]["waitFor"] == ["build-backend"]

    def test_deploy_waits_for_push(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "push-backend" in steps["deploy-backend"]["waitFor"]
        assert "write-backend-env" in steps["deploy-backend"]["waitFor"]

    def test_build_uses_docker_builder(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert steps["build-backend"]["name"] == "gcr.io/cloud-builders/docker"

    def test_deploy_uses_cloud_sdk(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert steps["deploy-backend"]["name"] == "gcr.io/google.com/cloudsdktool/cloud-sdk"

    def test_deploy_uses_sha_tag(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        args = steps["deploy-backend"]["args"]
        image_idx = args.index("--image") + 1
        assert "$SHORT_SHA" in args[image_idx]
        assert "latest" not in args[image_idx]

    def test_deploy_has_service_account_flag(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "--service-account" in steps["deploy-backend"]["args"]

    def test_deploy_uses_env_vars_file(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        assert "--env-vars-file" in steps["deploy-backend"]["args"]

    def test_write_env_step_sets_cors(self, backend_pipeline):
        steps = _steps_by_id(backend_pipeline)
        args = steps["write-backend-env"]["args"]
        script = args[1] if len(args) > 1 else ""
        assert "CORS_ALLOWED_ORIGINS" in script

    def test_no_frontend_steps(self, backend_pipeline):
        ids = {s["id"] for s in backend_pipeline["steps"]}
        assert not any("frontend" in sid for sid in ids)

    def test_substitutions_use_variables(self, backend_pipeline):
        subs = backend_pipeline.get("substitutions", {})
        assert "_REGION" in subs
        assert "_PROJECT_ID" in subs
        assert "_BACKEND_SERVICE" in subs

    def test_images_use_substitutions(self, backend_pipeline):
        images = " ".join(backend_pipeline["images"])
        assert "backend:$SHORT_SHA" in images
        assert "backend:latest" in images


# ---------------------------------------------------------------------------
# Frontend pipeline (cloudbuild-frontend.yaml)
# ---------------------------------------------------------------------------

class TestFrontendPipeline:
    """cloudbuild-frontend.yaml — frontend only."""

    def test_has_three_steps(self, frontend_pipeline):
        assert len(frontend_pipeline["steps"]) == 3

    def test_step_ids(self, frontend_pipeline):
        ids = {s["id"] for s in frontend_pipeline["steps"]}
        assert ids == {"build-frontend", "push-frontend", "deploy-frontend"}

    def test_has_images_field(self, frontend_pipeline):
        assert "images" in frontend_pipeline

    def test_two_images_declared(self, frontend_pipeline):
        assert len(frontend_pipeline["images"]) == 2

    def test_build_runs_first(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert steps["build-frontend"]["waitFor"] == ["-"]

    def test_push_waits_for_build(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert steps["push-frontend"]["waitFor"] == ["build-frontend"]

    def test_deploy_waits_for_push(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert steps["deploy-frontend"]["waitFor"] == ["push-frontend"]

    def test_build_uses_docker_builder(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert steps["build-frontend"]["name"] == "gcr.io/cloud-builders/docker"

    def test_deploy_uses_cloud_sdk(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert steps["deploy-frontend"]["name"] == "gcr.io/google.com/cloudsdktool/cloud-sdk"

    def test_deploy_uses_sha_tag(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        args = steps["deploy-frontend"]["args"]
        image_idx = args.index("--image") + 1
        assert "$SHORT_SHA" in args[image_idx]
        assert "latest" not in args[image_idx]

    def test_deploy_has_service_account_flag(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        assert "--service-account" in steps["deploy-frontend"]["args"]

    def test_no_backend_steps(self, frontend_pipeline):
        ids = {s["id"] for s in frontend_pipeline["steps"]}
        assert not any("backend" in sid for sid in ids)

    def test_build_passes_firebase_build_args(self, frontend_pipeline):
        steps = _steps_by_id(frontend_pipeline)
        args = " ".join(steps["build-frontend"]["args"])
        assert "NEXT_PUBLIC_FIREBASE_API_KEY" in args
        assert "NEXT_PUBLIC_FIREBASE_PROJECT_ID" in args
        assert "NEXT_PUBLIC_FIREBASE_APP_ID" in args
        assert "NEXT_PUBLIC_API_URL" in args

    def test_substitutions_use_variables(self, frontend_pipeline):
        subs = frontend_pipeline.get("substitutions", {})
        assert "_REGION" in subs
        assert "_PROJECT_ID" in subs
        assert "_FRONTEND_SERVICE" in subs

    def test_images_use_substitutions(self, frontend_pipeline):
        images = " ".join(frontend_pipeline["images"])
        assert "frontend:$SHORT_SHA" in images
        assert "frontend:latest" in images
