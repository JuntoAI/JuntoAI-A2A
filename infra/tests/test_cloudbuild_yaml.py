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
        assert len(fullstack_pipeline["steps"]) == 14

    def test_step_ids(self, fullstack_pipeline):
        ids = {s["id"] for s in fullstack_pipeline["steps"]}
        expected = {
            "build-test-image", "build-frontend-test-image",
            "test-backend", "test-frontend",
            "build-backend", "build-frontend",
            "write-backend-env", "write-frontend-env",
            "deploy-backend-no-traffic", "deploy-frontend-no-traffic",
            "migrate-backend-traffic", "migrate-frontend-traffic",
            "remove-backend-canary-tag", "remove-frontend-canary-tag",
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
        assert len(backend_pipeline["steps"]) == 7

    def test_step_ids(self, backend_pipeline):
        ids = {s["id"] for s in backend_pipeline["steps"]}
        assert ids == {"build-test-image", "test-backend", "build-backend", "write-backend-env",
                       "deploy-backend-no-traffic", "migrate-backend-traffic",
                       "remove-backend-canary-tag"}

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
        assert "cloudsdktool/cloud-sdk" in steps["deploy-backend-no-traffic"]["name"]

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
        assert len(frontend_pipeline["steps"]) == 7

    def test_step_ids(self, frontend_pipeline):
        ids = {s["id"] for s in frontend_pipeline["steps"]}
        assert ids == {"build-test-image", "test-frontend", "build-frontend",
                       "write-frontend-env", "deploy-frontend-no-traffic",
                       "migrate-frontend-traffic", "remove-frontend-canary-tag"}

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
        assert "cloudsdktool/cloud-sdk" in steps["deploy-frontend-no-traffic"]["name"]

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


# ---------------------------------------------------------------------------
# Cost regression guards (applies to every pipeline)
# ---------------------------------------------------------------------------
#
# In Apr-Aug 2026 an abandoned `canary`-tagged revision with min-instances=1 and
# CPU always allocated ran 24/7 at 0% traffic and became ~66% of the GCP bill.
#
# Three independent mistakes combined:
#   1. `--tag canary` was applied on every deploy and never removed.
#      `update-traffic --to-latest` moves traffic but leaves the tag pinned, and
#      a tagged revision keeps its own URL, so Cloud Run honours its
#      min-instances indefinitely.
#   2. `--min-instances 1 --no-cpu-throttling` were set to chase SSE stability.
#   3. Removing those flags from the pipeline did NOT reset them, because
#      `gcloud run deploy` inherits any unspecified flag from the previous
#      revision. They must be pinned explicitly to be reversed.
#
# These tests fail if any of the three regress.
# ---------------------------------------------------------------------------

def _deploy_steps(pipeline):
    """Every `gcloud run deploy` step in a pipeline, keyed by step id."""
    return {
        s["id"]: s
        for s in pipeline["steps"]
        if s.get("args") and s["args"][:2] == ["run", "deploy"]
    }


def _flag_value(args, flag):
    """Value following `flag` in a gcloud arg list, or None if absent."""
    if flag not in args:
        return None
    idx = args.index(flag)
    return args[idx + 1] if idx + 1 < len(args) else None


PIPELINE_FIXTURES = ["fullstack_pipeline", "backend_pipeline", "frontend_pipeline"]


@pytest.mark.parametrize("pipeline_name", PIPELINE_FIXTURES)
class TestCanaryTagCleanup:
    """Any pipeline that tags a canary revision must also untag it."""

    def test_canary_tag_is_removed(self, pipeline_name, request):
        pipeline = request.getfixturevalue(pipeline_name)
        steps = pipeline["steps"]

        tagging = [
            s for s in steps
            if s.get("args") and "--tag" in s["args"]
            and _flag_value(s["args"], "--tag") == "canary"
        ]
        if not tagging:
            pytest.skip("pipeline does not tag a canary revision")

        untagging = [
            s for s in steps
            if s.get("args")
            and "--remove-tags" in s["args"]
            and _flag_value(s["args"], "--remove-tags") == "canary"
        ]
        assert len(untagging) >= len(tagging), (
            f"{len(tagging)} step(s) apply the canary tag but only "
            f"{len(untagging)} remove it. An orphaned tagged revision keeps its "
            "min-instances alive at 0% traffic and bills 24/7."
        )

    def test_untag_runs_after_traffic_migration(self, pipeline_name, request):
        pipeline = request.getfixturevalue(pipeline_name)
        steps = _steps_by_id(pipeline)

        for step_id, step in steps.items():
            if not step.get("args") or "--remove-tags" not in step["args"]:
                continue
            deps = step.get("waitFor", [])
            assert any("migrate" in d for d in deps), (
                f"{step_id} must waitFor the traffic migration step; removing "
                "the tag before traffic has moved can break the deploy."
            )


@pytest.mark.parametrize("pipeline_name", PIPELINE_FIXTURES)
class TestDeployScalingPinned:
    """Scaling and CPU allocation must be explicit, never inherited."""

    def test_min_instances_is_zero(self, pipeline_name, request):
        pipeline = request.getfixturevalue(pipeline_name)
        for step_id, step in _deploy_steps(pipeline).items():
            value = _flag_value(step["args"], "--min-instances")
            assert value is not None, (
                f"{step_id} must pin --min-instances explicitly; gcloud inherits "
                "it from the previous revision otherwise."
            )
            assert str(value) == "0", (
                f"{step_id} sets --min-instances={value}. Anything above 0 keeps "
                "an instance billing 24/7. Scale to zero is the MVP default."
            )

    def test_cpu_throttling_enabled(self, pipeline_name, request):
        pipeline = request.getfixturevalue(pipeline_name)
        for step_id, step in _deploy_steps(pipeline).items():
            args = step["args"]
            assert "--no-cpu-throttling" not in args, (
                f"{step_id} sets --no-cpu-throttling, which bills the full "
                "instance lifetime. CPU is already allocated during an open SSE "
                "stream, so this buys nothing. Stream drain is handled by "
                "--timeout and --session-affinity."
            )
            assert "--cpu-throttling" in args, (
                f"{step_id} must pin --cpu-throttling explicitly; gcloud inherits "
                "CPU allocation from the previous revision otherwise."
            )

    def test_max_instances_pinned(self, pipeline_name, request):
        pipeline = request.getfixturevalue(pipeline_name)
        for step_id, step in _deploy_steps(pipeline).items():
            value = _flag_value(step["args"], "--max-instances")
            assert value is not None, f"{step_id} must pin --max-instances"
            assert int(value) > 0
