from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values, set_key

from app.core.config import Settings
from app.schemas.market import (
    MarketIndexItem,
    StockDailyPrice,
    StockIntradayQuote,
    StockRankItem,
)


logger = logging.getLogger(__name__)


class KisConfigurationError(RuntimeError):
    pass


class KisClient:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def fetch_volume_top(self, *, top_n: int) -> list[StockRankItem]:
        _validate_required_param_keys(
            self._settings.kis_volume_top_params,
            (
                "FID_COND_MRKT_DIV_CODE",
                "FID_COND_SCR_DIV_CODE",
                "FID_INPUT_ISCD",
                "FID_DIV_CLS_CODE",
                "FID_BLNG_CLS_CODE",
                "FID_TRGT_CLS_CODE",
                "FID_TRGT_EXLS_CLS_CODE",
                "FID_INPUT_PRICE_1",
                "FID_INPUT_PRICE_2",
                "FID_VOL_CNT",
            ),
            "volume-rank",
        )
        return await self._fetch_ranking(
            path=self._settings.kis_volume_top_path,
            tr_id=self._settings.kis_volume_top_tr_id,
            params=self._settings.kis_volume_top_params,
            top_n=top_n,
        )

    async def fetch_trade_amount_top(self, *, top_n: int) -> list[StockRankItem]:
        _validate_required_param_keys(
            self._settings.kis_trade_amount_top_params,
            (
                "FID_COND_MRKT_DIV_CODE",
                "FID_COND_SCR_DIV_CODE",
                "FID_INPUT_ISCD",
                "FID_DIV_CLS_CODE",
                "FID_BLNG_CLS_CODE",
                "FID_TRGT_CLS_CODE",
                "FID_TRGT_EXLS_CLS_CODE",
                "FID_INPUT_PRICE_1",
                "FID_INPUT_PRICE_2",
                "FID_VOL_CNT",
            ),
            "trade-amount-rank",
        )
        return await self._fetch_ranking(
            path=self._settings.kis_volume_top_path,
            tr_id=self._settings.kis_volume_top_tr_id,
            params=self._settings.kis_trade_amount_top_params,
            top_n=top_n,
        )

    async def fetch_risers(self, *, top_n: int) -> list[StockRankItem]:
        _validate_fluctuation_params(self._settings.kis_risers_params, "risers")
        return await self._fetch_ranking(
            path=self._settings.kis_risers_path,
            tr_id=self._settings.kis_risers_tr_id,
            params=self._settings.kis_risers_params,
            top_n=top_n,
        )

    async def fetch_fallers(self, *, top_n: int) -> list[StockRankItem]:
        _validate_fluctuation_params(self._settings.kis_fallers_params, "fallers")
        return await self._fetch_ranking(
            path=self._settings.kis_fallers_path,
            tr_id=self._settings.kis_fallers_tr_id,
            params=self._settings.kis_fallers_params,
            top_n=top_n,
        )

    async def fetch_hts_top_view(self, *, top_n: int) -> list[StockRankItem]:
        if not self._settings.kis_hts_top_view_path:
            raise KisConfigurationError("KIS HTS top-view path must be configured")
        if not self._settings.kis_hts_top_view_tr_id:
            raise KisConfigurationError("KIS HTS top-view TR ID must be configured")

        payload = await self._get(
            self._settings.kis_hts_top_view_path,
            tr_id=self._settings.kis_hts_top_view_tr_id,
            params=None,
        )
        records = _extract_records(payload)
        return [_normalize_hts_top_view_item(record) for record in records[:top_n]]

    async def fetch_current_price(self, *, short_code: str) -> StockIntradayQuote:
        if not self._settings.kis_inquire_price_path:
            raise KisConfigurationError("KIS inquire-price path must be configured")
        if not self._settings.kis_inquire_price_tr_id:
            raise KisConfigurationError("KIS inquire-price TR ID must be configured")

        normalized_code = short_code[1:] if short_code.startswith("A") else short_code
        params = {
            "FID_COND_MRKT_DIV_CODE": self._settings.kis_inquire_price_market_div_code,
            "FID_INPUT_ISCD": normalized_code,
        }
        payload = await self._get(
            self._settings.kis_inquire_price_path,
            tr_id=self._settings.kis_inquire_price_tr_id,
            params=params,
        )
        output = payload.get("output")
        if not isinstance(output, dict):
            raise RuntimeError("KIS inquire-price response did not include output")
        return _normalize_intraday_quote(normalized_code, output)

    async def fetch_daily_prices(
        self,
        *,
        short_code: str,
        start_date: date,
        end_date: date,
        market_div_code: str | None = None,
    ) -> list[StockDailyPrice]:
        if not self._settings.kis_daily_itemchart_price_path:
            raise KisConfigurationError("KIS daily itemchart price path must be configured")
        if not self._settings.kis_daily_itemchart_price_tr_id:
            raise KisConfigurationError("KIS daily itemchart price TR ID must be configured")
        if start_date > end_date:
            raise ValueError("start_date must be earlier than or equal to end_date")

        normalized_code = short_code[1:] if short_code.startswith("A") else short_code
        resolved_market_div_code = (
            market_div_code or self._settings.kis_daily_itemchart_price_market_div_code
        )
        params = {
            "FID_COND_MRKT_DIV_CODE": resolved_market_div_code,
            "FID_INPUT_ISCD": normalized_code,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": (
                self._settings.kis_daily_itemchart_price_period_div_code
            ),
            "FID_ORG_ADJ_PRC": self._settings.kis_daily_itemchart_price_org_adj_prc,
        }
        payload = await self._get(
            self._settings.kis_daily_itemchart_price_path,
            tr_id=self._settings.kis_daily_itemchart_price_tr_id,
            params=params,
        )
        records = payload.get("output2")
        if not isinstance(records, list):
            raise RuntimeError("KIS daily itemchart response did not include output2")
        return [
            _normalize_daily_price(normalized_code, record)
            for record in records
            if isinstance(record, dict)
        ]

    async def fetch_market_indices(self) -> list[MarketIndexItem]:
        return [
            await self.fetch_index_price(name=name, code=code)
            for name, code in self._settings.kis_index_codes.items()
        ]

    async def fetch_index_price(self, *, name: str, code: str) -> MarketIndexItem:
        if not self._settings.kis_index_price_path:
            raise KisConfigurationError("KIS index-price path must be configured")
        if not self._settings.kis_index_price_tr_id:
            raise KisConfigurationError("KIS index-price TR ID must be configured")
        if not self._settings.kis_index_price_market_div_code:
            raise KisConfigurationError("KIS index-price market code must be configured")

        params = {
            "FID_COND_MRKT_DIV_CODE": self._settings.kis_index_price_market_div_code,
            "FID_INPUT_ISCD": code,
        }
        payload = await self._get(
            self._settings.kis_index_price_path,
            tr_id=self._settings.kis_index_price_tr_id,
            params=params,
        )
        output = payload.get("output")
        if not isinstance(output, dict):
            raise RuntimeError("KIS index-price response did not include output")
        return _normalize_market_index(name=name, code=code, record=output)

    async def _fetch_ranking(
        self, *, path: str, tr_id: str, params: dict[str, str], top_n: int
    ) -> list[StockRankItem]:
        if not path or not tr_id:
            raise KisConfigurationError("KIS ranking path and TR ID must be configured")

        payload = await self._get(path, tr_id=tr_id, params=params)
        records = _extract_records(payload)
        return [_normalize_rank_item(record) for record in records[:top_n]]

    async def _get(
        self, path: str, *, tr_id: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._get_with_token_retry(path, tr_id=tr_id, params=params, retried=False)

    async def _get_with_token_retry(
        self,
        path: str,
        *,
        tr_id: str,
        params: dict[str, Any] | None,
        retried: bool,
    ) -> dict[str, Any]:
        token = await self._get_access_token()
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self._settings.kis_app_key,
            "appsecret": self._settings.kis_app_secret,
            "tr_id": tr_id,
            "custtype": self._settings.kis_customer_type,
            "content-type": "application/json; charset=utf-8",
        }
        async with httpx.AsyncClient(
            base_url=self._settings.kis_base_url,
            timeout=self._settings.kis_timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.get(path, headers=headers, params=params or {})
            if response.status_code in (401, 403, 500) and not retried:
                await self._refresh_access_token_for_retry(
                    path=path,
                    tr_id=tr_id,
                    reason=f"HTTP {response.status_code}",
                )
                return await self._get_with_token_retry(
                    path, tr_id=tr_id, params=params, retried=True
                )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(_http_error_message(response)) from exc
            data = response.json()

        if data.get("rt_cd") not in (None, "0"):
            if _is_token_error(data) and not retried:
                await self._refresh_access_token_for_retry(
                    path=path,
                    tr_id=tr_id,
                    reason=str(data.get("msg1") or data.get("msg_cd") or "token error"),
                )
                return await self._get_with_token_retry(
                    path, tr_id=tr_id, params=params, retried=True
                )
            message = data.get("msg1") or data.get("msg_cd") or "KIS API returned an error"
            raise RuntimeError(message)
        return data

    async def _refresh_access_token_for_retry(
        self, *, path: str, tr_id: str, reason: str
    ) -> None:
        try:
            await self._issue_access_token()
        except Exception:
            logger.exception(
                "Failed to refresh KIS access token after API error. "
                "path=%s tr_id=%s reason=%s token_key=%s expires_at_key=%s",
                path,
                tr_id,
                reason,
                self._settings.kis_access_token_cache_key,
                self._settings.kis_access_token_expires_at_cache_key,
            )
            raise

    async def _get_access_token(self) -> str:
        if self._access_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at:
                return self._access_token

        cached_token, cached_expires_at = self._load_cached_access_token()
        if cached_token and cached_expires_at:
            if datetime.now(timezone.utc) < cached_expires_at:
                self._access_token = cached_token
                self._token_expires_at = cached_expires_at
                return cached_token

        return await self._issue_access_token()

    async def _issue_access_token(self) -> str:
        if not self._settings.kis_app_key or not self._settings.kis_app_secret:
            raise KisConfigurationError("KIS_APP_KEY and KIS_APP_SECRET are required")

        body = {
            "grant_type": "client_credentials",
            "appkey": self._settings.kis_app_key,
            "appsecret": self._settings.kis_app_secret,
        }
        async with httpx.AsyncClient(
            base_url=self._settings.kis_base_url,
            timeout=self._settings.kis_timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.post(self._settings.kis_token_path, json=body)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(_http_error_message(response)) from exc
            data = response.json()

        token = data["access_token"]
        expires_at = _parse_token_expires_at(data)
        self._access_token = token
        self._token_expires_at = expires_at
        self._save_cached_access_token(token, expires_at)
        return token

    def _load_cached_access_token(self) -> tuple[str | None, datetime | None]:
        token = self._settings.kis_access_token
        expires_at_text = self._settings.kis_access_token_expires_at

        env_path = self._settings.kis_token_cache_env_file
        if env_path:
            values = dotenv_values(env_path)
            token = str(
                values.get(self._settings.kis_access_token_cache_key) or token or ""
            )
            expires_at_text = str(
                values.get(self._settings.kis_access_token_expires_at_cache_key)
                or expires_at_text
                or ""
            )

        expires_at = _parse_datetime(expires_at_text)
        if not token or expires_at is None:
            return None, None
        return token, expires_at

    def _save_cached_access_token(self, token: str, expires_at: datetime) -> None:
        env_path = self._settings.kis_token_cache_env_file
        if not env_path:
            return

        path = Path(env_path)
        if not path.exists():
            path.touch()

        expires_at_text = expires_at.isoformat()
        set_key(str(path), self._settings.kis_access_token_cache_key, token)
        set_key(
            str(path),
            self._settings.kis_access_token_expires_at_cache_key,
            expires_at_text,
        )


def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("output", "output1", "output2"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _parse_token_expires_at(data: dict[str, Any]) -> datetime:
    explicit_expiry = data.get("access_token_token_expired")
    if explicit_expiry:
        parsed = _parse_datetime(str(explicit_expiry))
        if parsed is not None:
            return parsed - timedelta(seconds=60)

    expires_in = int(data.get("expires_in") or 60 * 60 * 6)
    return datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(normalized, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_token_error(data: dict[str, Any]) -> bool:
    msg_cd = str(data.get("msg_cd") or "")
    msg = str(data.get("msg1") or "").lower()
    return (
        msg_cd in {"EGW00121", "EGW00123", "EGW00133"}
        or "token" in msg
        or "토큰" in msg
        or "authorization" in msg
    )


def _http_error_message(response: httpx.Response) -> str:
    body_message = _response_body_message(response)
    if body_message:
        return body_message
    return (
        f"KIS API HTTP {response.status_code} error for "
        f"{response.request.method} {response.request.url.path}"
    )


def _response_body_message(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else None

    if isinstance(data, dict):
        parts = [
            str(data[key])
            for key in ("msg1", "msg_cd", "rt_cd")
            if data.get(key) not in (None, "")
        ]
        if parts:
            return " / ".join(parts)
    text = response.text.strip()
    return text[:500] if text else None


def _validate_fluctuation_params(params: dict[str, str], label: str) -> None:
    _validate_required_param_keys(
        params,
        (
            "fid_rsfl_rate2",
            "fid_cond_mrkt_div_code",
            "fid_cond_scr_div_code",
            "fid_input_iscd",
            "fid_rank_sort_cls_code",
            "fid_input_cnt_1",
            "fid_prc_cls_code",
            "fid_input_price_1",
            "fid_input_price_2",
            "fid_vol_cnt",
            "fid_trgt_cls_code",
            "fid_trgt_exls_cls_code",
            "fid_div_cls_code",
            "fid_rsfl_rate1",
        ),
        label,
    )


def _validate_required_param_keys(
    params: dict[str, str], required_keys: tuple[str, ...], label: str
) -> None:
    missing = [key for key in required_keys if key not in params]
    if missing:
        raise KisConfigurationError(
            f"KIS {label} params are missing required keys: {', '.join(missing)}"
        )


def _normalize_rank_item(record: dict[str, Any]) -> StockRankItem:
    short_code = _first_text(record, "mksc_shrn_iscd", "stck_shrn_iscd", "pdno", "code")
    if short_code.startswith("A") and len(short_code) == 7:
        short_code = short_code[1:]

    return StockRankItem(
        short_code=short_code,
        name=_first_optional_text(record, "hts_kor_isnm", "prdt_name", "name"),
        price=_first_decimal(record, "stck_prpr", "prpr", "price"),
        change_rate=_first_decimal(record, "prdy_ctrt", "fluctuation_rate", "change_rate"),
        trade_volume=_first_int(record, "acml_vol", "cntg_vol", "trade_volume", "volume"),
        trade_amount=_first_decimal(record, "acml_tr_pbmn", "trade_amount"),
        raw=record,
    )


def _normalize_hts_top_view_item(record: dict[str, Any]) -> StockRankItem:
    short_code = _first_text(record, "mksc_shrn_iscd", "stck_shrn_iscd", "pdno")
    if short_code.startswith("A") and len(short_code) == 7:
        short_code = short_code[1:]

    return StockRankItem(
        short_code=short_code,
        market=_first_optional_text(record, "mrkt_div_cls_code", "mrkt_div_cls_name"),
        raw=record,
    )


def _normalize_intraday_quote(
    short_code: str, record: dict[str, Any]
) -> StockIntradayQuote:
    price = _first_decimal(record, "stck_prpr", "prpr", "price")
    accumulated_volume = _first_int(record, "acml_vol", "volume")
    accumulated_trade_amount = _first_decimal(
        record, "acml_tr_pbmn", "trade_amount", "acml_tr_pbmn"
    )

    if price is None:
        raise RuntimeError(f"KIS inquire-price response missing price for {short_code}")
    if accumulated_volume is None:
        raise RuntimeError(
            f"KIS inquire-price response missing accumulated volume for {short_code}"
        )
    if accumulated_trade_amount is None:
        raise RuntimeError(
            f"KIS inquire-price response missing accumulated trade amount for {short_code}"
        )

    return StockIntradayQuote(
        short_code=short_code,
        price=price,
        accumulated_volume=accumulated_volume,
        accumulated_trade_amount=accumulated_trade_amount,
        change_rate=_first_decimal(record, "prdy_ctrt", "change_rate"),
        raw=record,
    )


def _normalize_daily_price(short_code: str, record: dict[str, Any]) -> StockDailyPrice:
    trading_date_text = _first_text(record, "stck_bsop_date")
    try:
        trading_date = datetime.strptime(trading_date_text, "%Y%m%d").date()
    except ValueError as exc:
        raise RuntimeError(
            f"KIS daily itemchart response missing valid trading date for {short_code}"
        ) from exc

    open_price = _first_decimal(record, "stck_oprc")
    high_price = _first_decimal(record, "stck_hgpr")
    low_price = _first_decimal(record, "stck_lwpr")
    close_price = _first_decimal(record, "stck_clpr")
    accumulated_volume = _first_int(record, "acml_vol")
    accumulated_trade_amount = _first_decimal(record, "acml_tr_pbmn")
    change_amount = _first_decimal(record, "prdy_vrss")
    change_rate = _first_decimal(record, "prdy_ctrt")

    if open_price is None:
        raise RuntimeError(f"KIS daily itemchart response missing open price for {short_code}")
    if high_price is None:
        raise RuntimeError(f"KIS daily itemchart response missing high price for {short_code}")
    if low_price is None:
        raise RuntimeError(f"KIS daily itemchart response missing low price for {short_code}")
    if close_price is None:
        raise RuntimeError(f"KIS daily itemchart response missing close price for {short_code}")
    if accumulated_volume is None:
        raise RuntimeError(
            f"KIS daily itemchart response missing accumulated volume for {short_code}"
        )
    if accumulated_trade_amount is None:
        raise RuntimeError(
            f"KIS daily itemchart response missing accumulated trade amount for {short_code}"
        )

    if change_rate is None and change_amount is not None:
        previous_close = close_price - change_amount
        if previous_close:
            change_rate = (change_amount / previous_close) * Decimal("100")

    return StockDailyPrice(
        short_code=short_code,
        trading_date=trading_date,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        accumulated_volume=accumulated_volume,
        accumulated_trade_amount=accumulated_trade_amount,
        change_amount=change_amount,
        change_rate=change_rate,
        raw=record,
    )


def _normalize_market_index(
    *, name: str, code: str, record: dict[str, Any]
) -> MarketIndexItem:
    price = _first_decimal(record, "bstp_nmix_prpr")
    if price is None:
        raise RuntimeError(f"KIS index-price response missing price for {name}")

    return MarketIndexItem(
        code=code,
        name=name,
        price=price,
        change=_first_decimal(record, "bstp_nmix_prdy_vrss"),
        change_sign=_first_optional_text(record, "prdy_vrss_sign"),
        change_rate=_first_decimal(record, "bstp_nmix_prdy_ctrt"),
        accumulated_volume=_first_int(record, "acml_vol"),
        accumulated_trade_amount=_first_decimal(record, "acml_tr_pbmn"),
        open_price=_first_decimal(record, "bstp_nmix_oprc"),
        high_price=_first_decimal(record, "bstp_nmix_hgpr"),
        low_price=_first_decimal(record, "bstp_nmix_lwpr"),
        rising_stock_count=_first_int(record, "ascn_issu_cnt"),
        unchanged_stock_count=_first_int(record, "stnr_issu_cnt"),
        falling_stock_count=_first_int(record, "down_issu_cnt"),
        raw=record,
    )


def _first_text(record: dict[str, Any], *keys: str) -> str:
    value = _first_optional_text(record, *keys)
    return value or ""


def _first_optional_text(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _first_decimal(record: dict[str, Any], *keys: str) -> Decimal | None:
    value = _first_optional_text(record, *keys)
    if value is None:
        return None
    try:
        return Decimal(value.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def _first_int(record: dict[str, Any], *keys: str) -> int | None:
    value = _first_optional_text(record, *keys)
    if value is None:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None
