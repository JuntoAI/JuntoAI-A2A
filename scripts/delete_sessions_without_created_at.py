"""One-off script: delete negotiation sessions for a specific user that lack a created_at field.

Usage:
    # Dry run (default) — shows what would be deleted
    python scripts/delete_sessions_without_created_at.py

    # Actually delete
    python scripts/delete_sessions_without_created_at.py --confirm
"""

import argparse
import asyncio

from google.cloud import firestore

TARGET_EMAIL = "markus@turtletrafo.de"
COLLECTION = "negotiation_sessions"


async def main(confirm: bool) -> None:
    db = firestore.AsyncClient()
    col = db.collection(COLLECTION)

    query = col.where("owner_email", "==", TARGET_EMAIL)

    to_delete: list[tuple[str, dict]] = []
    total_for_user = 0

    async for doc in query.stream():
        total_for_user += 1
        data = doc.to_dict()
        if not data.get("created_at"):
            to_delete.append((doc.id, data))

    print(f"Total sessions for {TARGET_EMAIL}: {total_for_user}")
    print(f"Sessions WITHOUT created_at: {len(to_delete)}")
    print()

    for doc_id, data in to_delete:
        print(
            f"  {doc_id}  scenario={data.get('scenario_id', '?'):<20}  "
            f"status={data.get('deal_status', '?'):<12}  "
            f"turns={data.get('turn_count', 0)}"
        )

    if not to_delete:
        print("Nothing to delete.")
        return

    if not confirm:
        print(f"\nDry run — pass --confirm to delete these {len(to_delete)} sessions.")
        return

    print(f"\nDeleting {len(to_delete)} sessions...")
    for doc_id, _ in to_delete:
        await col.document(doc_id).delete()
        print(f"  ✓ deleted {doc_id}")

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Actually delete (default is dry run)")
    args = parser.parse_args()
    asyncio.run(main(confirm=args.confirm))
