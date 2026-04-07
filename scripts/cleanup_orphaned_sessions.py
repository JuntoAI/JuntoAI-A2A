"""One-off script to delete orphaned negotiation sessions from Firestore.

Usage:
    source .venv/bin/activate
    python scripts/cleanup_orphaned_sessions.py [--dry-run]

Requires GOOGLE_CLOUD_PROJECT or FIRESTORE_PROJECT_ID env var (or default GCP credentials).
"""

import asyncio
import argparse
from google.cloud.firestore import AsyncClient

EMAILS_TO_CLEAN = [
    "markus@juntoai.org",
    "markus@juntoai.rog",
    "markus.schmidberger@gmail.com",
]


async def cleanup(dry_run: bool = False) -> None:
    db = AsyncClient()
    total_deleted = 0

    for email in EMAILS_TO_CLEAN:
        query = db.collection("negotiation_sessions").where("owner_email", "==", email)
        count = 0
        async for doc in query.stream():
            count += 1
            if not dry_run:
                await doc.reference.delete()
            print(f"  {'[DRY RUN] Would delete' if dry_run else 'Deleted'}: {doc.id} (owner: {email})")
        total_deleted += count
        print(f"  → {email}: {count} session(s) {'found' if dry_run else 'deleted'}")

    print(f"\nTotal: {total_deleted} session(s) {'would be deleted' if dry_run else 'deleted'}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up orphaned negotiation sessions")
    parser.add_argument("--dry-run", action="store_true", help="List sessions without deleting")
    args = parser.parse_args()

    asyncio.run(cleanup(dry_run=args.dry_run))
