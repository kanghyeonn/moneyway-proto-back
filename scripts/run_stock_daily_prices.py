from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.workers.stock_daily_price_worker import StockDailyPriceWorker


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run KIS daily stock price collection.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--request-interval-seconds", type=float, default=None)
    parser.add_argument("--no-lock", action="store_true")
    return parser.parse_args()


def _parse_date(value: str) -> date:
    normalized = value.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"Invalid date: {value}")


def _json_default(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _print_progress(done: int, total: int, short_code: str, success: bool) -> None:
    status = "ok" if success else "failed"
    print(f"[{done}/{total}] {short_code} {status}", flush=True)


async def _run() -> int:
    args = _parse_args()
    result = await StockDailyPriceWorker().run(
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        limit=args.limit,
        dry_run=args.dry_run,
        request_interval_seconds=args.request_interval_seconds,
        progress_callback=_print_progress,
        use_advisory_lock=not args.no_lock,
    )
    payload = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    print(json.dumps(payload, ensure_ascii=False, default=_json_default))
    return 0 if result.status in {"completed", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
