from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.workers.market_discovery_snapshot_worker import (
    MarketDiscoverySnapshotWorker,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect KIS market discovery data and save a DB snapshot.",
    )
    parser.add_argument(
        "--snapshot-batch-at",
        default=None,
        help=(
            "Optional snapshot datetime. ISO 8601 format. "
            "Defaults to current UTC time floored to minute."
        ),
    )
    parser.add_argument(
        "--ranking-limit",
        type=int,
        default=30,
        help="Number of ranking items to collect per ranking type.",
    )
    parser.add_argument(
        "--popular-limit",
        type=int,
        default=20,
        help="Number of popular search items to collect.",
    )
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=None,
        help="Delay between KIS request groups. Defaults to KIS_REQUEST_INTERVAL_SECONDS.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_false",
        dest="progress",
        help="Disable progress output.",
    )
    parser.add_argument(
        "--no-lock",
        action="store_true",
        help="Disable PostgreSQL advisory lock. Use only for local debugging.",
    )
    parser.set_defaults(progress=True)
    return parser.parse_args()


def _parse_snapshot_batch_at(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _print_progress(step: str, success: bool, message: str) -> None:
    status = "ok" if success else "failed"
    suffix = f" - {message}" if message else ""
    print(
        f"[{datetime.now().isoformat(timespec='seconds')}] {step}: {status}{suffix}",
        flush=True,
    )


async def _run() -> int:
    args = _parse_args()
    batch_at = await MarketDiscoverySnapshotWorker().run(
        snapshot_batch_at=_parse_snapshot_batch_at(args.snapshot_batch_at),
        ranking_limit=args.ranking_limit,
        popular_limit=args.popular_limit,
        request_interval_seconds=args.request_interval_seconds,
        progress_callback=_print_progress if args.progress else None,
        use_advisory_lock=not args.no_lock,
    )
    print(f"market discovery snapshot saved: {batch_at.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
