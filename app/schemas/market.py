from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class StockRankItem(BaseModel):
    short_code: str
    name: str | None = None
    market: str | None = None
    price: Decimal | None = None
    change_rate: Decimal | None = None
    trade_volume: int | None = None
    trade_amount: Decimal | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class MarketIndexItem(BaseModel):
    code: str
    name: str
    price: Decimal
    change: Decimal | None = None
    change_sign: str | None = None
    change_rate: Decimal | None = None
    accumulated_volume: int | None = None
    accumulated_trade_amount: Decimal | None = None
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    rising_stock_count: int | None = None
    unchanged_stock_count: int | None = None
    falling_stock_count: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class StockIntradayQuote(BaseModel):
    short_code: str = Field(min_length=6, max_length=6)
    price: Decimal = Field(ge=0)
    accumulated_volume: int = Field(ge=0)
    accumulated_trade_amount: Decimal = Field(ge=0)
    change_rate: Decimal | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class StockDailyPrice(BaseModel):
    short_code: str = Field(min_length=6, max_length=6)
    trading_date: date
    open_price: Decimal = Field(ge=0)
    high_price: Decimal = Field(ge=0)
    low_price: Decimal = Field(ge=0)
    close_price: Decimal = Field(ge=0)
    accumulated_volume: int = Field(ge=0)
    accumulated_trade_amount: Decimal = Field(ge=0)
    change_amount: Decimal | None = None
    change_rate: Decimal | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class IntradaySnapshotRunResult(BaseModel):
    snapshot_batch_at: datetime
    interval_minutes: int
    target_stock_count: int
    success_stock_count: int
    failed_stock_count: int
    skipped_unknown_stock: int
    dry_run: bool
    status: str
    errors: list[str] = Field(default_factory=list)


class DailyPriceCollectionResult(BaseModel):
    start_date: date
    end_date: date
    target_stock_count: int
    success_stock_count: int
    failed_stock_count: int
    saved_price_count: int
    skipped_unknown_stock: int
    dry_run: bool
    status: str
    errors: list[str] = Field(default_factory=list)


LeadershipSide = Literal["bullish", "bearish"]
CategoryType = Literal["sector", "theme"]
CategoryStockSort = Literal["change_rate_desc", "change_rate_asc"]
LeadershipSort = Literal[
    "score_desc",
    "trade_amount_desc",
    "weighted_change_rate_desc",
    "weighted_change_rate_asc",
]


class LeadershipItem(BaseModel):
    id: int
    name: str
    side: LeadershipSide
    score: Decimal
    trade_amount: Decimal
    weighted_change_rate: Decimal | None = None
    advance_ratio: Decimal | None = None
    up_trade_amount_ratio: Decimal | None = None
    decline_ratio: Decimal | None = None
    down_trade_amount_ratio: Decimal | None = None
    stock_count: int
    top1_trade_amount_share: Decimal | None = None
    concentration_penalty: Decimal | None = None
    top_stocks: list["CategoryStockItem"] | None = None


class LeadershipResponse(BaseModel):
    as_of: datetime
    snapshot_batch_at: datetime
    scope: Literal["daily"] = "daily"
    side: LeadershipSide
    top_n: int
    min_trade_amount: Decimal
    sort: LeadershipSort
    items: list[LeadershipItem]


class LeadershipSummaryResponse(BaseModel):
    as_of: datetime
    snapshot_batch_at: datetime
    scope: Literal["daily"] = "daily"
    category_type: CategoryType
    min_trade_amount: Decimal
    bullish_count: int
    bearish_count: int
    top_bullish: LeadershipItem | None = None
    top_bearish: LeadershipItem | None = None


class LeadershipSnapshotItem(BaseModel):
    snapshot_batch_at: datetime | None
    stock_count: int
    status: str | None = None


class LeadershipSnapshotsResponse(BaseModel):
    as_of: datetime
    items: list[LeadershipSnapshotItem]


class LeadershipStatusResponse(BaseModel):
    as_of: datetime
    mode: Literal["daily"] = "daily"
    display_time: str
    is_delayed: bool
    delay_minutes: int | None = None
    latest_snapshot_batch_at: datetime | None
    latest_snapshot_date: str | None
    stock_count: int
    status: str | None = None


class CategoryStockItem(BaseModel):
    short_code: str
    name: str
    price: Decimal
    change_rate: Decimal | None = None
    accumulated_volume: int
    accumulated_trade_amount: Decimal


class CategoryStocksResponse(BaseModel):
    as_of: datetime
    snapshot_batch_at: datetime
    category_type: CategoryType
    category_id: int
    category_name: str
    sort: CategoryStockSort
    items: list[CategoryStockItem]
