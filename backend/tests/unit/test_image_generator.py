"""Unit tests for the share image generator service."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.image_generator import (
    _FALLBACK_PLACEHOLDER_LOCAL,
    _IMAGE_TIMEOUT_SECONDS,
    _fallback_url,
    _generate_and_store_local,
    generate_share_image,
)


# ---------------------------------------------------------------------------
# _fallback_url
# ---------------------------------------------------------------------------


class TestFallbackUrl:
    """Tests for the _fallback_url helper."""

    def test_local_mode_returns_placeholder(self):
        with patch("app.services.image_generator.settings") as mock_settings:
            mock_settings.RUN_MODE = "local"
            mock_settings.GCS_BUCKET_NAME = ""
            assert _fallback_url("abc12345") == _FALLBACK_PLACEHOLDER_LOCAL

    def test_cloud_mode_with_bucket_returns_gcs_url(self):
        with patch("app.services.image_generator.settings") as mock_settings:
            mock_settings.RUN_MODE = "cloud"
            mock_settings.GCS_BUCKET_NAME = "my-bucket"
            url = _fallback_url("abc12345")
            assert url == "https://storage.googleapis.com/my-bucket/share_images/placeholder.png"

    def test_cloud_mode_without_bucket_returns_local_placeholder(self):
        with patch("app.services.image_generator.settings") as mock_settings:
            mock_settings.RUN_MODE = "cloud"
            mock_settings.GCS_BUCKET_NAME = ""
            assert _fallback_url("abc12345") == _FALLBACK_PLACEHOLDER_LOCAL


# ---------------------------------------------------------------------------
# _generate_and_store_local
# ---------------------------------------------------------------------------


class TestGenerateAndStoreLocal:
    """Tests for local-mode image storage."""

    @pytest.mark.asyncio
    async def test_creates_file_and_returns_api_url(self, tmp_path: Path):
        with patch("app.services.image_generator._LOCAL_IMAGES_DIR", tmp_path):
            url = await _generate_and_store_local("a prompt", "slug1234")

        assert url == "/api/v1/share/images/slug1234.png"
        assert (tmp_path / "slug1234.png").exists()
        # File should be a valid PNG (starts with PNG magic bytes)
        data = (tmp_path / "slug1234.png").read_bytes()
        assert data[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# generate_share_image (integration-level with mocks)
# ---------------------------------------------------------------------------


class TestGenerateShareImage:
    """Tests for the main generate_share_image entry point."""

    @pytest.mark.asyncio
    async def test_local_mode_returns_api_url(self, tmp_path: Path):
        with (
            patch("app.services.image_generator.settings") as mock_settings,
            patch("app.services.image_generator._LOCAL_IMAGES_DIR", tmp_path),
        ):
            mock_settings.RUN_MODE = "local"
            mock_settings.GCS_BUCKET_NAME = ""
            url = await generate_share_image("test prompt", "abcd1234")

        assert url == "/api/v1/share/images/abcd1234.png"
        assert (tmp_path / "abcd1234.png").exists()

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback(self):
        """Simulate a timeout in image generation."""

        async def _slow(*args, **kwargs):
            await asyncio.sleep(60)

        with (
            patch("app.services.image_generator.settings") as mock_settings,
            patch(
                "app.services.image_generator._generate_and_store_local",
                side_effect=_slow,
            ),
            patch(
                "app.services.image_generator._generate_and_store_cloud",
                side_effect=_slow,
            ),
        ):
            mock_settings.RUN_MODE = "local"
            mock_settings.GCS_BUCKET_NAME = ""
            url = await generate_share_image("prompt", "slug0000")

        assert url == _FALLBACK_PLACEHOLDER_LOCAL

    @pytest.mark.asyncio
    async def test_exception_returns_fallback(self):
        """Any exception during generation should return the fallback."""
        with (
            patch("app.services.image_generator.settings") as mock_settings,
            patch(
                "app.services.image_generator._generate_and_store_local",
                side_effect=RuntimeError("boom"),
            ),
        ):
            mock_settings.RUN_MODE = "local"
            mock_settings.GCS_BUCKET_NAME = ""
            url = await generate_share_image("prompt", "slug0000")

        assert url == _FALLBACK_PLACEHOLDER_LOCAL

    @pytest.mark.asyncio
    async def test_cloud_mode_calls_cloud_generator(self):
        """Cloud mode with a bucket should call the cloud path."""
        mock_cloud = AsyncMock(return_value="https://storage.googleapis.com/b/share_images/s.png")
        with (
            patch("app.services.image_generator.settings") as mock_settings,
            patch(
                "app.services.image_generator._generate_and_store_cloud",
                mock_cloud,
            ),
        ):
            mock_settings.RUN_MODE = "cloud"
            mock_settings.GCS_BUCKET_NAME = "b"
            url = await generate_share_image("prompt", "s")

        assert url.startswith("https://storage.googleapis.com/")
        mock_cloud.assert_awaited_once_with("prompt", "s")

    @pytest.mark.asyncio
    async def test_cloud_mode_without_bucket_falls_back_to_local(self, tmp_path: Path):
        """Cloud mode without GCS_BUCKET_NAME should use local path."""
        with (
            patch("app.services.image_generator.settings") as mock_settings,
            patch("app.services.image_generator._LOCAL_IMAGES_DIR", tmp_path),
        ):
            mock_settings.RUN_MODE = "cloud"
            mock_settings.GCS_BUCKET_NAME = ""
            url = await generate_share_image("prompt", "slug1234")

        assert url == "/api/v1/share/images/slug1234.png"


class TestConstants:
    """Verify key constants match spec requirements."""

    def test_timeout_is_15_seconds(self):
        assert _IMAGE_TIMEOUT_SECONDS == 15
