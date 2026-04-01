"""Verify cloudbuild.yaml pipeline definition (Req 1.1–1.4, 4.3, 5.1–5.3, 6.1–6.3, 9.1–9.4)."""

import os
import pytest
import yaml


@pytest.fixture(scope="module")
def pipeline(repo_root):
    path = os.path.join(repo_root, "cloudbuild.yaml")
    assert os.path.isfile(path), "cloudbuild.yaml must exist at repo root"
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def steps(pipeline):
    return {s["id"]: s for s in pipeline["steps"]}


class TestPipelineStructure:
    """Req 1.1: cloudbuild.yaml exists with correct structure."""

    def test_has_steps(self, pipeline):
        assert "steps" in pipeline
        assert len(pipeline["steps"]) == 6

    def test_has_images_field(self, pipeline):
        assert "images" in pipeline, "Pipeline must use images field for automatic push"

    def test_four_images_declared(self, pipeline):
        assert len(pipeline["images"]) == 4

    def test_step_ids(self, steps):
        expected = {"build-backend", "build-frontend", "push-backend", "push-frontend", "deploy-backend", "deploy-frontend"}
        assert set(steps.keys()) == expected


class TestBuildSteps:
    """Req 9.4: Build steps run in parallel."""

    def test_build_backend_parallel(self, steps):
        assert steps["build-backend"]["waitFor"] == ["-"]

    def test_build_frontend_parallel(self, steps):
        assert steps["build-frontend"]["waitFor"] == ["-"]

    def test_build_backend_uses_docker_builder(self, steps):
        assert steps["build-backend"]["name"] == "gcr.io/cloud-builders/docker"

    def test_build_frontend_uses_docker_builder(self, steps):
        assert steps["build-frontend"]["name"] == "gcr.io/cloud-builders/docker"


class TestPushSteps:
    """Push steps must run between build and deploy to ensure images exist in Artifact Registry."""

    def test_push_backend_waits_for_build(self, steps):
        assert steps["push-backend"]["waitFor"] == ["build-backend"]

    def test_push_frontend_waits_for_build(self, steps):
        assert steps["push-frontend"]["waitFor"] == ["build-frontend"]

    def test_push_backend_uses_docker_builder(self, steps):
        assert steps["push-backend"]["name"] == "gcr.io/cloud-builders/docker"

    def test_push_frontend_uses_docker_builder(self, steps):
        assert steps["push-frontend"]["name"] == "gcr.io/cloud-builders/docker"

    def test_push_backend_pushes_all_tags(self, steps):
        args = steps["push-backend"]["args"]
        assert "push" in args
        assert "--all-tags" in args

    def test_push_frontend_pushes_all_tags(self, steps):
        args = steps["push-frontend"]["args"]
        assert "push" in args
        assert "--all-tags" in args


class TestDeploySteps:
    """Req 9.2, 9.3: Deploy steps depend on their push step."""

    def test_deploy_backend_waits_for_push(self, steps):
        assert steps["deploy-backend"]["waitFor"] == ["push-backend"]

    def test_deploy_frontend_waits_for_push(self, steps):
        assert steps["deploy-frontend"]["waitFor"] == ["push-frontend"]

    def test_deploy_backend_uses_cloud_sdk(self, steps):
        assert steps["deploy-backend"]["name"] == "gcr.io/google.com/cloudsdktool/cloud-sdk"

    def test_deploy_frontend_uses_cloud_sdk(self, steps):
        assert steps["deploy-frontend"]["name"] == "gcr.io/google.com/cloudsdktool/cloud-sdk"

    def test_deploy_backend_uses_sha_tag(self, steps):
        args = " ".join(steps["deploy-backend"]["args"])
        assert "$SHORT_SHA" in args, "Deploy must use $SHORT_SHA tag"
        # Ensure 'latest' is NOT in the --image argument
        image_idx = steps["deploy-backend"]["args"].index("--image") + 1
        image_arg = steps["deploy-backend"]["args"][image_idx]
        assert "latest" not in image_arg, "Deploy must not use latest tag"

    def test_deploy_frontend_uses_sha_tag(self, steps):
        args = " ".join(steps["deploy-frontend"]["args"])
        assert "$SHORT_SHA" in args
        image_idx = steps["deploy-frontend"]["args"].index("--image") + 1
        image_arg = steps["deploy-frontend"]["args"][image_idx]
        assert "latest" not in image_arg

    def test_deploy_backend_has_service_account_flag(self, steps):
        assert "--service-account" in steps["deploy-backend"]["args"]

    def test_deploy_frontend_has_service_account_flag(self, steps):
        assert "--service-account" in steps["deploy-frontend"]["args"]


class TestSubstitutionVariables:
    """Req 1.2: No hardcoded project IDs or regions in step args."""

    def test_build_steps_use_substitutions(self, steps):
        for step_id in ["build-backend", "build-frontend"]:
            args = " ".join(steps[step_id]["args"])
            assert "$_REGION" in args or "${_REGION}" in args
            assert "$_PROJECT_ID" in args or "${_PROJECT_ID}" in args
            assert "$_REPO_NAME" in args or "${_REPO_NAME}" in args

    def test_deploy_steps_use_substitutions(self, steps):
        for step_id in ["deploy-backend", "deploy-frontend"]:
            args = " ".join(steps[step_id]["args"])
            assert "$_REGION" in args or "${_REGION}" in args


class TestImageTags:
    """Req 1.3, 1.4: Both SHA and latest tags in images field."""

    def test_backend_sha_tag_in_images(self, pipeline):
        images = " ".join(pipeline["images"])
        assert "backend:$SHORT_SHA" in images

    def test_backend_latest_tag_in_images(self, pipeline):
        images = " ".join(pipeline["images"])
        assert "backend:latest" in images

    def test_frontend_sha_tag_in_images(self, pipeline):
        images = " ".join(pipeline["images"])
        assert "frontend:$SHORT_SHA" in images

    def test_frontend_latest_tag_in_images(self, pipeline):
        images = " ".join(pipeline["images"])
        assert "frontend:latest" in images
