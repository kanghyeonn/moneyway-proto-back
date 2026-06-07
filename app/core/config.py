from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def _str_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


DEFAULT_VOLUME_TOP_PARAMS = {
    "FID_COND_MRKT_DIV_CODE": "J",
    "FID_COND_SCR_DIV_CODE": "20171",
    "FID_INPUT_ISCD": "0000",
    "FID_DIV_CLS_CODE": "0",
    "FID_BLNG_CLS_CODE": "0",
    "FID_TRGT_CLS_CODE": "111111111",
    "FID_TRGT_EXLS_CLS_CODE": "0000000000",
    "FID_INPUT_PRICE_1": "",
    "FID_INPUT_PRICE_2": "",
    "FID_VOL_CNT": "",
}

DEFAULT_TRADE_AMOUNT_TOP_PARAMS = {
    **DEFAULT_VOLUME_TOP_PARAMS,
    "FID_BLNG_CLS_CODE": "3",
    "FID_TRGT_EXLS_CLS_CODE": "0000001100"
}

DEFAULT_RISERS_PARAMS = {
    "fid_rsfl_rate2": "",
    "fid_cond_mrkt_div_code": "J",
    "fid_cond_scr_div_code": "20170",
    "fid_input_iscd": "0000",
    "fid_rank_sort_cls_code": "0",
    "fid_input_cnt_1": "0",
    "fid_prc_cls_code": "1",
    "fid_input_price_1": "",
    "fid_input_price_2": "",
    "fid_vol_cnt": "",
    "fid_trgt_cls_code": "0",
    "fid_trgt_exls_cls_code": "0",
    "fid_div_cls_code": "0",
    "fid_rsfl_rate1": "",
    "fid_rsfl_rate2": "",
}

DEFAULT_FALLERS_PARAMS = {
    **DEFAULT_RISERS_PARAMS,
    "fid_rank_sort_cls_code": "1",
}

DEFAULT_INDEX_CODES = {
    "KOSPI": "0001",
    "KOSDAQ": "1001",
}


def _json_env(name: str, default: dict[str, str] | None = None) -> dict[str, str]:
    value = os.getenv(name)
    if not value:
        return dict(default or {})
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must be a JSON object")
    merged = dict(default or {})
    merged.update({str(key): str(item) for key, item in parsed.items()})
    return merged


@dataclass(frozen=True)
class Settings:
    app_name: str = _str_env("APP_NAME", "moneyway-back")
    database_url: str = _str_env("DATABASE_URL", "")

    kis_base_url: str = _str_env(
        "KIS_BASE_URL", "https://openapi.koreainvestment.com:9443"
    )
    kis_app_key: str = _str_env("KIS_APP_KEY", "")
    kis_app_secret: str = _str_env("KIS_APP_SECRET", "")
    kis_customer_type: str = _str_env("KIS_CUSTOMER_TYPE", "P")
    kis_token_path: str = _str_env("KIS_TOKEN_PATH", "/oauth2/tokenP")
    kis_access_token: str = _str_env("KIS_ACCESS_TOKEN", "")
    kis_access_token_expires_at: str = _str_env("KIS_ACCESS_TOKEN_EXPIRES_AT", "")
    kis_token_cache_env_file: str = _str_env("KIS_TOKEN_CACHE_ENV_FILE", ".env")

    kis_volume_top_path: str = _str_env(
        "KIS_VOLUME_TOP_PATH", "/uapi/domestic-stock/v1/quotations/volume-rank"
    )
    kis_risers_path: str = _str_env(
        "KIS_RISERS_PATH", "/uapi/domestic-stock/v1/ranking/fluctuation"
    )
    kis_fallers_path: str = _str_env(
        "KIS_FALLERS_PATH", "/uapi/domestic-stock/v1/ranking/fluctuation"
    )
    kis_hts_top_view_path: str = _str_env(
        "KIS_HTS_TOP_VIEW_PATH",
        "/uapi/domestic-stock/v1/ranking/hts-top-view",
    )
    kis_volume_top_tr_id: str = _str_env("KIS_VOLUME_TOP_TR_ID", "FHPST01710000")
    kis_risers_tr_id: str = _str_env("KIS_RISERS_TR_ID", "FHPST01700000")
    kis_fallers_tr_id: str = _str_env("KIS_FALLERS_TR_ID", "FHPST01700000")
    kis_hts_top_view_tr_id: str = _str_env(
        "KIS_HTS_TOP_VIEW_TR_ID", "HHMCM000100C0"
    )
    kis_inquire_price_path: str = _str_env(
        "KIS_INQUIRE_PRICE_PATH", "/uapi/domestic-stock/v1/quotations/inquire-price"
    )
    kis_inquire_price_tr_id: str = _str_env(
        "KIS_INQUIRE_PRICE_TR_ID", "FHKST01010100"
    )
    kis_inquire_price_market_div_code: str = _str_env(
        "KIS_INQUIRE_PRICE_MARKET_DIV_CODE", "UN"
    )
    kis_index_price_path: str = _str_env(
        "KIS_INDEX_PRICE_PATH",
        "/uapi/domestic-stock/v1/quotations/inquire-index-price",
    )
    kis_index_price_tr_id: str = _str_env(
        "KIS_INDEX_PRICE_TR_ID", "FHPUP02100000"
    )
    kis_index_price_market_div_code: str = _str_env(
        "KIS_INDEX_PRICE_MARKET_DIV_CODE", "U"
    )
    kis_volume_top_params: dict[str, str] = None  # type: ignore[assignment]
    kis_trade_amount_top_params: dict[str, str] = None  # type: ignore[assignment]
    kis_risers_params: dict[str, str] = None  # type: ignore[assignment]
    kis_fallers_params: dict[str, str] = None  # type: ignore[assignment]
    kis_index_codes: dict[str, str] = None  # type: ignore[assignment]

    default_top_n: int = _int_env("DEFAULT_TOP_N", 20)
    kis_timeout_seconds: int = _int_env("KIS_TIMEOUT_SECONDS", 10)
    kis_request_interval_seconds: float = _float_env(
        "KIS_REQUEST_INTERVAL_SECONDS", 1
    )
    market_snapshot_interval_minutes: int = _int_env(
        "MARKET_SNAPSHOT_INTERVAL_MINUTES", 30
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "kis_volume_top_params",
            _json_env("KIS_VOLUME_TOP_PARAMS", DEFAULT_VOLUME_TOP_PARAMS),
        )
        object.__setattr__(
            self,
            "kis_trade_amount_top_params",
            _json_env("KIS_TRADE_AMOUNT_TOP_PARAMS", DEFAULT_TRADE_AMOUNT_TOP_PARAMS),
        )
        object.__setattr__(
            self, "kis_risers_params", _json_env("KIS_RISERS_PARAMS", DEFAULT_RISERS_PARAMS)
        )
        object.__setattr__(
            self,
            "kis_fallers_params",
            _json_env("KIS_FALLERS_PARAMS", DEFAULT_FALLERS_PARAMS),
        )
        object.__setattr__(
            self,
            "kis_index_codes",
            _json_env("KIS_INDEX_CODES", DEFAULT_INDEX_CODES),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
