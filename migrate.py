#!/usr/bin/env python3
"""Apply MongoDB schema indexes for the configured database (default: poll-live-feed)."""

import asyncio

from app.migrate import run_migration


async def main() -> None:
    db_name = await run_migration()
    print(f"Schema ready in database: {db_name}")


if __name__ == "__main__":
    asyncio.run(main())
