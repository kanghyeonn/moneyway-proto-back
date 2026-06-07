# Find API

발견 화면에서 사용하는 API 명세입니다.

Base URL:

```text
/api/market/discovery
```

## 공통 규칙

- 모든 시각은 ISO 8601 datetime 문자열입니다.
- `display_time`은 KST 기준 `HH:MM` 문자열입니다.
- `change_rate`는 `%` 문자를 제외한 숫자입니다. 예: `3.82`
- `direction`은 `up`, `down`, `flat` 중 하나입니다.
- KIS 설정 또는 호출 오류가 발생하면 `503`과 `{ "detail": "..." }` 형태로 응답합니다.
- 현재 `market` 필터는 `all`만 지원합니다. `kospi`, `kosdaq` 요청은 `503`으로 응답합니다.

## 1. 발견 화면 상태

화면 상단의 업데이트 상태와 기준 시각을 반환합니다.

```http
GET /api/market/discovery/status
```

Response:

```json
{
  "status_label": "실시간 업데이트",
  "basis_label": "당일 기준",
  "display_time": "14:35",
  "latest_snapshot_at": "2026-06-07T14:35:00+09:00",
  "is_delayed": false
}
```

필드:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `status_label` | string | 업데이트 상태 라벨 |
| `basis_label` | string | 데이터 기준 라벨 |
| `display_time` | string | 화면 표시용 기준 시각 |
| `latest_snapshot_at` | datetime | 상태 생성 시각 |
| `is_delayed` | boolean | 지연 여부. 현재는 실시간 호출 기준이라 `false` |

## 2. 발견 랭킹

거래대금 상위, 거래량 상위, 급상승, 급하락 탭의 종목 랭킹을 반환합니다.

```http
GET /api/market/discovery/rankings
```

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `type` | string | yes | - | `trading_value`, `trading_volume`, `top_gainers`, `top_losers` |
| `limit` | number | no | `30` | 반환 종목 수. `1-100` |
| `market` | string | no | `all` | 현재는 `all`만 지원 |

`type`별 원천:

| `type` | 의미 | KIS 호출 |
| --- | --- | --- |
| `trading_value` | 거래대금 상위 | 거래량순위 API + 거래금액순 파라미터 |
| `trading_volume` | 거래량 상위 | 거래량순위 API |
| `top_gainers` | 급상승 상위 | 등락률 순위 API 상승 정렬 |
| `top_losers` | 급하락 상위 | 등락률 순위 API 하락 정렬 |

Example:

```http
GET /api/market/discovery/rankings?type=trading_value&limit=30
```

Response:

```json
{
  "type": "trading_value",
  "basis_time": "2026-06-07T14:35:00+09:00",
  "items": [
    {
      "rank": 1,
      "short_code": "005930",
      "name": "삼성전자",
      "price": 78400,
      "trade_amount": 184230000000,
      "volume": 2341200,
      "change_rate": 3.82,
      "direction": "up"
    }
  ]
}
```

`items[]` 필드:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `rank` | number | 1부터 시작하는 순위 |
| `short_code` | string | 종목코드 |
| `name` | string | 종목명. 원천 응답에 없으면 종목코드 |
| `price` | number \| null | 현재가 |
| `trade_amount` | number \| null | 누적 거래대금 |
| `volume` | number \| null | 누적 거래량 |
| `change_rate` | number \| null | 전일 대비 등락률 |
| `direction` | string | `up`, `down`, `flat` |

## 3. 시장 요약

KOSPI, KOSDAQ 지수 요약을 반환합니다.

```http
GET /api/market/discovery/market-summary
```

Response:

```json
{
  "indices": [
    {
      "code": "KOSPI",
      "label": "KOSPI",
      "value": 2748.56,
      "change": 18.24,
      "change_rate": 0.67,
      "direction": "up"
    },
    {
      "code": "KOSDAQ",
      "label": "KOSDAQ",
      "value": 841.22,
      "change": -4.12,
      "change_rate": -0.49,
      "direction": "down"
    }
  ]
}
```

원천은 KIS `국내업종 현재지수` API입니다.

## 4. 상승/하락 종목 수

KOSPI, KOSDAQ의 상승/하락/보합 종목 수를 합산해 반환합니다.

```http
GET /api/market/discovery/advance-decline
```

Response:

```json
{
  "up_count": 654,
  "up_delta": 0,
  "down_count": 218,
  "down_delta": 0,
  "unchanged_count": 87,
  "basis_time": "2026-06-07T14:35:00+09:00"
}
```

필드:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `up_count` | number | KOSPI + KOSDAQ 상승 종목 수 |
| `up_delta` | number | 이전 기준 대비 상승 종목 수 변화. 현재는 비교 데이터가 없어 `0` |
| `down_count` | number | KOSPI + KOSDAQ 하락 종목 수 |
| `down_delta` | number | 이전 기준 대비 하락 종목 수 변화. 현재는 비교 데이터가 없어 `0` |
| `unchanged_count` | number | KOSPI + KOSDAQ 보합 종목 수 |
| `basis_time` | datetime | 응답 기준 시각 |

## 5. 인기 검색 종목

KIS HTS 조회상위 종목을 현재가 API로 보강해 반환합니다.

```http
GET /api/market/discovery/popular-searches
```

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `limit` | number | no | `3` | 반환 종목 수. `1-20` |

Example:

```http
GET /api/market/discovery/popular-searches?limit=3
```

Response:

```json
{
  "items": [
    {
      "rank": 1,
      "short_code": "005930",
      "name": "삼성전자",
      "change_rate": 2.14,
      "direction": "up"
    }
  ]
}
```

구현 방식:

```text
KIS HTS조회상위20종목
  -> 종목코드 추출
  -> 종목별 KIS 주식현재가 시세 호출
  -> 종목명, 등락률, 방향 보강
```

주의:

- 인기 검색 종목은 종목별 현재가 API를 추가 호출하므로 `limit`이 클수록 KIS 호출 수가 증가합니다.
- 현재가 응답에서 종목명을 찾지 못하면 종목코드를 `name`으로 반환합니다.

## 6. 발견 화면 통합 조회

발견 화면 첫 로딩에 필요한 데이터를 한 번에 반환합니다.

```http
GET /api/market/discovery/overview
```

Query:

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `ranking_type` | string | no | `trading_value` | 랭킹 타입 |
| `ranking_limit` | number | no | `30` | 랭킹 종목 수. `1-100` |
| `popular_limit` | number | no | `3` | 인기 검색 종목 수. `1-20` |
| `market` | string | no | `all` | 현재는 `all`만 지원 |

Example:

```http
GET /api/market/discovery/overview?ranking_type=trading_value&ranking_limit=30&popular_limit=3
```

Response:

```json
{
  "status": {
    "status_label": "실시간 업데이트",
    "basis_label": "당일 기준",
    "display_time": "14:35",
    "latest_snapshot_at": "2026-06-07T14:35:00+09:00",
    "is_delayed": false
  },
  "ranking": {
    "type": "trading_value",
    "basis_time": "2026-06-07T14:35:00+09:00",
    "items": []
  },
  "market_summary": {
    "indices": []
  },
  "advance_decline": {
    "up_count": 654,
    "up_delta": 0,
    "down_count": 218,
    "down_delta": 0,
    "unchanged_count": 87,
    "basis_time": "2026-06-07T14:35:00+09:00"
  },
  "popular_searches": {
    "items": []
  }
}
```

## 화면 호출 권장 흐름

첫 진입:

```text
GET /api/market/discovery/overview?ranking_type=trading_value&ranking_limit=30&popular_limit=3
```

탭 전환:

```text
GET /api/market/discovery/rankings?type=trading_volume&limit=30
GET /api/market/discovery/rankings?type=top_gainers&limit=30
GET /api/market/discovery/rankings?type=top_losers&limit=30
```

## 현재 제한사항

- `market=kospi`, `market=kosdaq`은 아직 지원하지 않습니다.
- `up_delta`, `down_delta`는 이전 기준 시각 데이터가 없어 현재 `0`입니다.
- `status`는 실제 지연 판단이 아니라 KST 현재 시각 기준 상태입니다.
- `popular-searches`는 `limit`만큼 현재가 API를 추가 호출합니다.
