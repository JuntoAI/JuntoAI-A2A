#!/usr/bin/env python3
"""CLI script to provision a new integration org with a token.

Usage:
    python scripts/create_integration_org.py \
        --org-name "Acme Corp" \
        --domain "acme.com" \
        --email "admin@juntoai.org" \
        --rate-limit-daily 500

The script prints the raw token once. Save it — it cannot be retrieved later.
Pass it to the CRM admin to configure in their EspoCRM plugin.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db import get_api_key_store
from app.services.api_key_service import ApiKeyService


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision a new integration org with a token."
    )
    parser.add_argument(
        "--org-name",
        required=True,
        help="Organization name (e.g., 'Acme Corp')",
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Email domain for this org (e.g., 'acme.com'). "
        "Only users with emails @this-domain can use the token.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email of the admin creating this org (for audit trail)",
    )
    parser.add_argument(
        "--rate-limit-daily",
        type=int,
        default=None,
        help="Daily simulation limit for this org (default: 100 cloud / 1000 local)",
    )
    parser.add_argument(
        "--rate-limit-per-minute",
        type=int,
        default=None,
        help="Per-minute request limit (default: 10)",
    )

    args = parser.parse_args()

    store = get_api_key_store()
    service = ApiKeyService(store)

    raw_token, record = await service.generate_key(
        org_name=args.org_name,
        domain=args.domain,
        created_by_email=args.email,
        rate_limit_daily=args.rate_limit_daily,
        rate_limit_per_minute=args.rate_limit_per_minute,
    )

    print()
    print("=" * 60)
    print("  Integration Org Created Successfully")
    print("=" * 60)
    print()
    print(f"  Org Name:        {record['org_name']}")
    print(f"  Domain:          {record['domain']}")
    print(f"  Key ID:          {record['key_id']}")
    print(f"  Daily Limit:     {record['rate_limit_daily']}")
    print(f"  Per-Min Limit:   {record['rate_limit_per_minute']}")
    print(f"  Created At:      {record['created_at']}")
    print()
    print(f"  Integration Token:")
    print(f"  {raw_token}")
    print()
    print("  ⚠️  Save this token now. It will NOT be shown again.")
    print()
    print("  CRM Admin Configuration:")
    print(f"  - API URL:   https://api.juntoai.org/api/v1/integrations")
    print(f"  - Token:     (the token above)")
    print(f"  - Users must have @{record['domain']} email addresses")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
