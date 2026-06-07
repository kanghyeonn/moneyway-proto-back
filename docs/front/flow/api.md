# Market Leadership API

섹터/테마 페이지에서 사용하는 주도 섹터, 주도 테마 API 명세입니다.

Base URL:

```text
/api/market/leadership
```

## 공통 규칙

- 모든 시각은 ISO 8601 datetime 문자열입니다.
- `snapshot_batch_at`을 생략하면 DB에 저장된 최신 스냅샷 배치를 기준으로 조회합니다.
- `date`를 지정하면 KST 기준 해당 날짜의 스냅샷을 조회합니다. 해당 날짜가 주말이거나 DB 일봉 데이터 기준 휴장일이면 직전 거래일 스냅샷을 사용합니다.
- 주도 섹터/테마는 당일 누적 거래대금이 `100000000000`원 이상인 카테고리만 반환합니다.
- `weighted_change_rate`, `advance_ratio` 같은 비율 값은 소수입니다. 프론트에서 퍼센트로 표시할 때는 `value * 100`을 사용합니다.
- DB 스냅샷이 없으면 `503`과 `{ "detail": "No stock_intraday_snapshot batches are available" }` 형태로 응답합니다.

## 용어

| 필드 | 의미 |
| --- | --- |
| `score` | 거래대금, 거래대금 가중 등락률, 상승/하락 확산도, 대형주 쏠림 보정을 조합한 주도 점수 |
| `trade_amount` | 해당 섹터/테마 소속 종목들의 당일 누적 거래대금 합계 |
| `weighted_change_rate` | 거래대금 가중 전일 대비 등락률 |
| `advance_ratio` | 상승 종목 비율 |
| `up_trade_amount_ratio` | 상승 종목 거래대금 비율 |
| `decline_ratio` | 하락 종목 비율 |
| `down_trade_amount_ratio` | 하락 종목 거래대금 비율 |
| `top1_trade_amount_share` | 카테고리 내 거래대금 1위 종목의 거래대금 비중 |
| `concentration_penalty` | 대형주 쏠림 보정 계수 |
| `min_trade_amount` | 주도 후보 최소 거래대금 기준. 현재 `100000000000` |

## 1. 스냅샷 목록

주도 섹터/테마를 조회할 수 있는 스냅샷 배치 목록을 최신순으로 반환합니다.

```http
GET /api/market/leadership/snapshots
```

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `limit` | number | no | `30` | 조회할 스냅샷 수. `1-365` |
| `date` | string | no | - | KST 기준 조회 날짜. `YYYY-MM-DD` |

Example:

```http
GET /api/market/leadership/snapshots?limit=10
```

Response:

```json
{
  "as_of": "2026-06-07T03:00:00.000000Z",
  "items": [
    {
      "snapshot_batch_at": "2026-06-05T06:00:00.000000Z",
      "stock_count": 2877,
      "status": "completed"
    }
  ]
}
```

## 2. 날짜별 최신 스냅샷

특정 날짜의 최신 스냅샷 배치 하나를 반환합니다. 날짜는 한국 주식 화면 기준이므로 KST 날짜로 해석합니다.
요청한 날짜에 스냅샷이 없고 해당 날짜가 거래일이면 `503` 에러를 반환합니다.
요청한 날짜가 주말이거나 DB 일봉 데이터 기준 휴장일이면 직전 거래일 스냅샷을 반환합니다.
DB에 스냅샷이 아예 없으면 `snapshot_batch_at=null`, `stock_count=0`, `status="empty"`를 반환합니다.

```http
GET /api/market/leadership/snapshots/latest
```

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `date` | string | no | 최신 스냅샷 | KST 기준 조회 날짜. `YYYY-MM-DD` |

Example:

```http
GET /api/market/leadership/snapshots/latest?date=2026-06-05
```

Response:

```json
{
  "snapshot_batch_at": "2026-06-05T06:00:00.000000Z",
  "stock_count": 2877,
  "status": "completed"
}
```

초기 데이터가 없는 경우:

```json
{
  "snapshot_batch_at": null,
  "stock_count": 0,
  "status": "empty"
}
```

## 3. 화면 상태

화면 기준 날짜와 최신 스냅샷 상태를 반환합니다.

```http
GET /api/market/leadership/status
```

Response:

```json
{
  "as_of": "2026-06-07T03:00:00.000000Z",
  "mode": "daily",
  "display_time": "2026.06.05 기준",
  "is_delayed": true,
  "delay_minutes": 2700,
  "latest_snapshot_batch_at": "2026-06-05T06:00:00.000000Z",
  "latest_snapshot_date": "2026-06-05",
  "stock_count": 2877,
  "status": "completed"
}
```

`is_delayed`는 최신 스냅샷의 KST 날짜가 오늘보다 이전이면 `true`입니다. 주말이나 장 시작 전에는 직전 거래일 스냅샷을 표시할 수 있습니다.
스냅샷이 전혀 없으면 `display_time="데이터 없음"`, `latest_snapshot_batch_at=null`, `latest_snapshot_date=null`, `stock_count=0`, `status="empty"`를 반환합니다.

## 4. 섹터 요약

섹터 페이지 상단 카드용 요약 데이터입니다.

```http
GET /api/market/leadership/sectors/summary
```

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `snapshot_batch_at` | datetime | no | 최신 스냅샷 | 조회 기준 스냅샷 |
| `date` | string | no | 최신 스냅샷 | KST 기준 조회 날짜. `snapshot_batch_at`이 있으면 무시됨 |

Example:

```http
GET /api/market/leadership/sectors/summary
```

Response:

```json
{
  "as_of": "2026-06-07T03:00:00.000000Z",
  "snapshot_batch_at": "2026-06-05T06:00:00.000000Z",
  "scope": "daily",
  "category_type": "sector",
  "min_trade_amount": "100000000000",
  "bullish_count": 6,
  "bearish_count": 4,
  "top_bullish": {
    "id": 12,
    "name": "반도체",
    "side": "bullish",
    "score": "0.824",
    "trade_amount": "1840000000000",
    "weighted_change_rate": "0.0188",
    "advance_ratio": "0.72",
    "up_trade_amount_ratio": "0.81",
    "decline_ratio": "0.28",
    "down_trade_amount_ratio": "0.19",
    "stock_count": 32,
    "top1_trade_amount_share": "0.34",
    "concentration_penalty": "1.0"
  },
  "top_bearish": {
    "id": 7,
    "name": "2차전지",
    "side": "bearish",
    "score": "0.412",
    "trade_amount": "1260000000000",
    "weighted_change_rate": "-0.0142",
    "advance_ratio": "0.25",
    "up_trade_amount_ratio": "0.20",
    "decline_ratio": "0.75",
    "down_trade_amount_ratio": "0.80",
    "stock_count": 18,
    "top1_trade_amount_share": "0.38",
    "concentration_penalty": "1.0"
  }
}
```

## 5. 테마 요약

테마 페이지 상단 카드용 요약 데이터입니다.

```http
GET /api/market/leadership/themes/summary
```

Query는 섹터 요약과 같습니다.

Example:

```http
GET /api/market/leadership/themes/summary?snapshot_batch_at=2026-06-05T06:00:00Z
```

Response는 섹터 요약과 같은 구조이며 `category_type`이 `theme`입니다.

## 6. 주도 섹터 목록

상승 또는 하락 주도 섹터 랭킹을 반환합니다.

```http
GET /api/market/leadership/sectors
```

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `top_n` | number | no | `DEFAULT_TOP_N` | 반환 개수. `1-100` |
| `side` | string | no | `bullish` | `bullish` 또는 `bearish` |
| `sort` | string | no | `score_desc` | 정렬 기준 |
| `snapshot_batch_at` | datetime | no | 최신 스냅샷 | 조회 기준 스냅샷 |
| `date` | string | no | 최신 스냅샷 | KST 기준 조회 날짜. `snapshot_batch_at`이 있으면 무시됨 |
| `include_top_stocks` | number | no | `0` | 각 섹터에 포함할 TOP 종목 수. `0-10` |

`sort` 값:

| 값 | 의미 |
| --- | --- |
| `score_desc` | 주도 점수 높은 순 |
| `trade_amount_desc` | 거래대금 높은 순 |
| `weighted_change_rate_desc` | 거래대금 가중 등락률 높은 순 |
| `weighted_change_rate_asc` | 거래대금 가중 등락률 낮은 순 |

Example:

```http
GET /api/market/leadership/sectors?side=bullish&top_n=20&sort=score_desc&include_top_stocks=3
```

Response:

```json
{
  "as_of": "2026-06-07T03:00:00.000000Z",
  "snapshot_batch_at": "2026-06-05T06:00:00.000000Z",
  "scope": "daily",
  "side": "bullish",
  "top_n": 20,
  "min_trade_amount": "100000000000",
  "sort": "score_desc",
  "items": [
    {
      "id": 12,
      "name": "반도체",
      "side": "bullish",
      "score": "0.824",
      "trade_amount": "1840000000000",
      "weighted_change_rate": "0.0188",
      "advance_ratio": "0.72",
      "up_trade_amount_ratio": "0.81",
      "decline_ratio": "0.28",
      "down_trade_amount_ratio": "0.19",
      "stock_count": 32,
      "top1_trade_amount_share": "0.34",
      "concentration_penalty": "1.0",
      "top_stocks": [
        {
          "short_code": "000660",
          "name": "SK하이닉스",
          "price": "207000",
          "change_rate": "3.15",
          "accumulated_volume": 5358900,
          "accumulated_trade_amount": "1100000000000"
        }
      ]
    }
  ]
}
```

`include_top_stocks=0`이면 `top_stocks`는 `null`입니다. `include_top_stocks`로 포함되는 종목은 등락률 높은 순, 거래대금 높은 순, 종목코드 순으로 정렬됩니다.

## 7. 주도 테마 목록

상승 또는 하락 주도 테마 랭킹을 반환합니다.

```http
GET /api/market/leadership/themes
```

Query와 Response는 주도 섹터 목록과 같습니다. `items[].id`는 `theme_id`입니다. `include_top_stocks`를 사용할 수 있습니다.

Example:

```http
GET /api/market/leadership/themes?side=bullish&top_n=20&sort=trade_amount_desc
```

## 8. 섹터 소속 종목

특정 섹터에 속한 종목들을 등락률 기준으로 정렬해 반환합니다.

```http
GET /api/market/leadership/sectors/{sector_id}/stocks
```

Path:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `sector_id` | number | 섹터 ID |

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `sort` | string | no | `change_rate_desc` | `change_rate_desc` 또는 `change_rate_asc` |
| `snapshot_batch_at` | datetime | no | 최신 스냅샷 | 조회 기준 스냅샷 |
| `date` | string | no | 최신 스냅샷 | KST 기준 조회 날짜. `snapshot_batch_at`이 있으면 무시됨 |

Example:

```http
GET /api/market/leadership/sectors/12/stocks?sort=change_rate_desc
```

Response:

```json
{
  "as_of": "2026-06-07T03:00:00.000000Z",
  "snapshot_batch_at": "2026-06-05T06:00:00.000000Z",
  "category_type": "sector",
  "category_id": 12,
  "category_name": "반도체",
  "sort": "change_rate_desc",
  "items": [
    {
      "short_code": "000660",
      "name": "SK하이닉스",
      "price": "207000",
      "change_rate": "3.15",
      "accumulated_volume": 5358900,
      "accumulated_trade_amount": "1100000000000"
    }
  ]
}
```

## 9. 테마 소속 종목

특정 테마에 속한 종목들을 등락률 기준으로 정렬해 반환합니다.

```http
GET /api/market/leadership/themes/{theme_id}/stocks
```

Path:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `theme_id` | number | 테마 ID |

Query와 Response는 섹터 소속 종목 API와 같습니다. `category_type`은 `theme`입니다.

Example:

```http
GET /api/market/leadership/themes/31/stocks?sort=change_rate_desc
```

## 프론트 사용 예시

당일 섹터 화면:

```text
1. GET /api/market/leadership/status
2. GET /api/market/leadership/sectors/summary
3. GET /api/market/leadership/sectors?side=bullish&top_n=20&sort=score_desc&include_top_stocks=3
```

당일 테마 화면:

```text
1. GET /api/market/leadership/status
2. GET /api/market/leadership/themes/summary
3. GET /api/market/leadership/themes?side=bullish&top_n=20&sort=score_desc&include_top_stocks=3
```

날짜 선택 시:

```text
1. GET /api/market/leadership/snapshots/latest?date=YYYY-MM-DD
2. snapshot_batch_at=응답의 snapshot_batch_at
3. summary, ranking, stocks API에 같은 snapshot_batch_at 전달
```
