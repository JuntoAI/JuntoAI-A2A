"""Share image generation — Vertex AI Imagen (cloud) or local placeholder."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_IMAGE_TIMEOUT_SECONDS = 15
_LOCAL_IMAGES_DIR = Path("data/share_images")
_FALLBACK_PLACEHOLDER_LOCAL = "/api/v1/share/images/placeholder.png"


def _fallback_url(share_slug: str) -> str:
    """Return the appropriate fallback placeholder URL for the current run mode."""
    if settings.RUN_MODE == "cloud" and settings.GCS_BUCKET_NAME:
        return (
            f"https://storage.googleapis.com/"
            f"{settings.GCS_BUCKET_NAME}/share_images/placeholder.png"
        )
    return _FALLBACK_PLACEHOLDER_LOCAL


async def _generate_and_store_cloud(prompt: str, share_slug: str) -> str:
    """Call Vertex AI Imagen, upload result to GCS, return public URL."""
    from google.cloud import storage as gcs
    from vertexai.preview.vision_models import ImageGenerationModel

    model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
    response = await asyncio.to_thread(
        model.generate_images,
        prompt=prompt,
        number_of_images=1,
    )

    image = response.images[0]
    image_bytes: bytes = image._image_bytes  # noqa: SLF001

    bucket_name = settings.GCS_BUCKET_NAME
    blob_path = f"share_images/{share_slug}.png"

    client = gcs.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    await asyncio.to_thread(
        blob.upload_from_string, image_bytes, content_type="image/png"
    )

    return f"https://storage.googleapis.com/{bucket_name}/{blob_path}"


async def _generate_and_store_local(prompt: str, share_slug: str) -> str:
    """Store a minimal placeholder PNG locally and return the API path.

    In local mode we don't call any image generation API — we just create
    a tiny 1×1 transparent PNG so the file exists on disk.  The real value
    is the deterministic URL the rest of the system can reference.
    """
    _LOCAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest = _LOCAL_IMAGES_DIR / f"{share_slug}.png"

    # Minimal valid 1×1 transparent PNG (67 bytes).
    _TINY_PNG = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    await asyncio.to_thread(dest.write_bytes, _TINY_PNG)

    return f"/api/v1/share/images/{share_slug}.png"


async def generate_share_image(prompt: str, share_slug: str) -> str:
    """Generate (or fall back to placeholder) a share image.

    * **Cloud mode** — calls Vertex AI Imagen, stores in GCS, returns public URL.
    * **Local mode** — writes a stub PNG to ``data/share_images/``, returns an
      API-relative URL.
    * On *any* failure or timeout (>15 s) the fallback placeholder URL is returned
      so that sharing is never blocked by image generation.
    """
    try:
        if settings.RUN_MODE == "cloud" and settings.GCS_BUCKET_NAME:
            url = await asyncio.wait_for(
                _generate_and_store_cloud(prompt, share_slug),
                timeout=_IMAGE_TIMEOUT_SECONDS,
            )
        else:
            url = await asyncio.wait_for(
                _generate_and_store_local(prompt, share_slug),
                timeout=_IMAGE_TIMEOUT_SECONDS,
            )
        return url
    except asyncio.TimeoutError:
        logger.warning(
            "Image generation timed out after %ds for slug=%s",
            _IMAGE_TIMEOUT_SECONDS,
            share_slug,
        )
        return _fallback_url(share_slug)
    except Exception:
        logger.exception("Image generation failed for slug=%s", share_slug)
        return _fallback_url(share_slug)
