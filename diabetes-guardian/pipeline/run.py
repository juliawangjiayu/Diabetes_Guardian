"""
pipeline/run.py

Entry point for the data pipeline.
- Default:  start the nightly scheduler
- --backfill --user_id <id>:  backfill historical data for a user

Usage:
    python pipeline/run.py                              # Start scheduler
    python pipeline/run.py --backfill --user_id user_001  # Backfill
"""

import argparse
import asyncio
import sys

# Add project root to path
sys.path.insert(0, ".")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diabetes Guardian Data Pipeline")
    parser.add_argument("--backfill", action="store_true", help="Run backfill instead of scheduler")
    parser.add_argument("--user_id", type=str, help="User ID for backfill")
    args = parser.parse_args()

    if args.backfill:
        if not args.user_id:
            print("Error: --user_id is required when using --backfill")
            sys.exit(1)
        from pipeline.analytics import run_backfill
        asyncio.run(run_backfill(args.user_id))
    else:
        from pipeline.scheduler import start
        asyncio.run(start())


if __name__ == "__main__":
    main()
