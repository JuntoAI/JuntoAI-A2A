#!/usr/bin/env python3
"""Prune old, inactive Cloud Run revisions.

WHY THIS EXISTS
---------------
Cloud Run retains every revision indefinitely. Each revision pins its container
image, and Artifact Registry cannot delete an image that a live revision still
references. That is why the `delete-old-untagged` cleanup policy on
`juntoai-docker` reclaims nothing: ~170 backend and ~290 frontend revisions hold
their images hostage, keeping the repo at ~65 GiB.

Pruning revisions is the prerequisite for the AR cleanup policy to do its job.

SAFETY
------
Dry-run by default. Pass --apply to actually delete. A revision is skipped if it:
  * serves any traffic (percent > 0)
  * carries a tag (a tagged revision has its own URL and stays warm)
  * is the service's latestReadyRevision
  * is within the --keep most recent revisions

Usage
-----
    python scripts/prune_cloud_run_revisions.py                 # dry run, all services
    python scripts/prune_cloud_run_revisions.py --keep 5
    python scripts/prune_cloud_run_revisions.py --apply
    python scripts/prune_cloud_run_revisions.py --service juntoai-backend --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

DEFAULT_PROJECT = "juntoai-a2a-mvp"
DEFAULT_REGION = "europe-west1"
DEFAULT_SERVICES = ("juntoai-backend", "juntoai-frontend")
DEFAULT_KEEP = 10


def _gcloud_binary() -> str:
    """Resolve the gcloud entrypoint.

    On Windows gcloud ships as `gcloud.cmd` / `gcloud.ps1` rather than a real
    executable, so a bare "gcloud" is not resolvable by CreateProcess.
    """
    for candidate in ("gcloud", "gcloud.cmd", "gcloud.exe"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(
        "gcloud not found on PATH. Install the Google Cloud SDK and authenticate "
        "with `gcloud auth login`."
    )


def run_gcloud(args: list[str]) -> str:
    """Invoke gcloud with an argument list (never a shell string)."""
    proc = subprocess.run(
        [_gcloud_binary(), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gcloud {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout


def describe_service(service: str, project: str, region: str) -> dict:
    out = run_gcloud(
        [
            "run", "services", "describe", service,
            "--project", project,
            "--region", region,
            "--format", "json",
        ]
    )
    return json.loads(out)


def list_revisions(service: str, project: str, region: str) -> list[dict]:
    out = run_gcloud(
        [
            "run", "revisions", "list",
            "--service", service,
            "--project", project,
            "--region", region,
            "--format", "json",
        ]
    )
    revisions = json.loads(out)
    # Newest first. gcloud usually returns this order already; sort defensively.
    revisions.sort(
        key=lambda r: r.get("metadata", {}).get("creationTimestamp", ""),
        reverse=True,
    )
    return revisions


def protected_revisions(svc: dict) -> tuple[set[str], set[str], str | None]:
    """Return (serving_traffic, tagged, latest_ready) revision names."""
    serving: set[str] = set()
    tagged: set[str] = set()

    for target in svc.get("status", {}).get("traffic", []) or []:
        name = target.get("revisionName")
        if not name:
            continue
        if target.get("percent"):
            serving.add(name)
        if target.get("tag"):
            tagged.add(name)

    latest_ready = svc.get("status", {}).get("latestReadyRevisionName")
    return serving, tagged, latest_ready


def prune_service(
    service: str, project: str, region: str, keep: int, apply: bool
) -> int:
    print(f"\n=== {service} ({project}/{region}) ===")

    svc = describe_service(service, project, region)
    serving, tagged, latest_ready = protected_revisions(svc)
    revisions = list_revisions(service, project, region)

    print(f"revisions: {len(revisions)}  keep-newest: {keep}")
    if serving:
        print(f"serving traffic: {', '.join(sorted(serving))}")
    if tagged:
        print(f"tagged (kept warm): {', '.join(sorted(tagged))}")
    if latest_ready:
        print(f"latestReady: {latest_ready}")

    recent = {
        r.get("metadata", {}).get("name")
        for r in revisions[:keep]
    }

    deletable: list[str] = []
    for rev in revisions:
        name = rev.get("metadata", {}).get("name")
        if not name:
            continue
        if name in recent:
            continue
        if name in serving:
            continue
        if name in tagged:
            continue
        if name == latest_ready:
            continue
        deletable.append(name)

    if not deletable:
        print("nothing to prune")
        return 0

    print(f"\n{len(deletable)} revision(s) eligible for deletion:")
    for name in deletable:
        print(f"  {name}")

    if not apply:
        print("\nDRY RUN - nothing deleted. Re-run with --apply to delete.")
        return 0

    deleted = 0
    for name in deletable:
        try:
            run_gcloud(
                [
                    "run", "revisions", "delete", name,
                    "--project", project,
                    "--region", region,
                    "--quiet",
                ]
            )
            print(f"deleted {name}")
            deleted += 1
        except RuntimeError as exc:
            print(f"FAILED {name}: {exc}", file=sys.stderr)
    print(f"\ndeleted {deleted}/{len(deletable)}")
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument(
        "--service",
        action="append",
        dest="services",
        help="Service to prune. Repeatable. Defaults to backend + frontend.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"Number of most recent revisions to always retain (default {DEFAULT_KEEP}).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete. Without this flag the script only reports.",
    )
    args = parser.parse_args()

    if args.keep < 1:
        parser.error("--keep must be at least 1")

    services = args.services or list(DEFAULT_SERVICES)

    for service in services:
        try:
            prune_service(service, args.project, args.region, args.keep, args.apply)
        except RuntimeError as exc:
            print(f"ERROR on {service}: {exc}", file=sys.stderr)
            return 1

    if not args.apply:
        print(
            "\nAfter pruning, Artifact Registry's `delete-old-untagged` policy can "
            "finally reclaim the unreferenced images."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
