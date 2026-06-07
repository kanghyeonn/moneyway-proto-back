from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


DiscoveryRankingType = Literal[
    "trading_value",
    "trading_volume",
    "top_gainers",
    "top_losers",
]
DiscoveryMarket = Literal["all", "kospi", "kosdaq"]
DiscoveryDirection = Literal["up", "down", "flat"]


class DiscoveryStatusResponse(BaseModel):
    status_label: str
    basis_label: str
    display_time: str
    latest_snapshot_at: datetime
    is_delayed: bool


class DiscoveryRankingItem(BaseModel):
    rank: int = Field(ge=1)
    short_code: str
    name: str
    price: float | None = None
    trade_amount: float | None = None
    volume: int | None = None
    change_rate: float | None = None
    direction: DiscoveryDirection


class DiscoveryRankingsResponse(BaseModel):
    type: DiscoveryRankingType
    basis_time: datetime
    items: list[DiscoveryRankingItem]


class DiscoveryIndexItem(BaseModel):
    code: str
    label: str
    value: float
    change: float | None = None
    change_rate: float | None = None
    direction: DiscoveryDirection


class DiscoveryMarketSummaryResponse(BaseModel):
    indices: list[DiscoveryIndexItem]


class DiscoveryAdvanceDeclineResponse(BaseModel):
    up_count: int
    up_delta: int
    down_count: int
    down_delta: int
    unchanged_count: int
    basis_time: datetime


class DiscoveryPopularSearchItem(BaseModel):
    rank: int = Field(ge=1)
    short_code: str
    name: str
    change_rate: float | None = None
    direction: DiscoveryDirection


class DiscoveryPopularSearchesResponse(BaseModel):
    items: list[DiscoveryPopularSearchItem]


class DiscoveryOverviewResponse(BaseModel):
    status: DiscoveryStatusResponse
    ranking: DiscoveryRankingsResponse
    market_summary: DiscoveryMarketSummaryResponse
    advance_decline: DiscoveryAdvanceDeclineResponse
    popular_searches: DiscoveryPopularSearchesResponse
