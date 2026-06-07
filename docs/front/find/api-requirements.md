# 발견 화면 API 요구사항

이 문서는 `src/app/(tabs)/(find)` 화면에서 사용하는 더미데이터를 실제 API로 대체하기 위해 필요한 API를 정리한다.

## 현재 화면 구성

발견 화면은 상단 탭별로 서로 다른 랭킹 데이터를 보여주고, 나머지 영역은 공통 컴포넌트를 사용한다.

- 거래대금 상위
- 거래량 상위
- 급상승 상위
- 급하락 상위

공통으로 필요한 데이터는 다음과 같다.

- 랭킹 테이블 30개 종목
- KOSPI, KOSDAQ 지수 요약
- 상승/하락 종목 수 게이지
- 인기 검색 종목
- 데이터 기준 시각 또는 업데이트 상태

`FindGuidePanel`에 들어가는 안내 문구는 정적 콘텐츠이므로 API가 필수는 아니다.

## 1. 발견 화면 상태 API

화면 상단의 업데이트 상태와 기준 시각을 표시하기 위한 API다.

```http
GET /api/market/discovery/status
```

### 응답 예시

```json
{
  "status_label": "실시간 업데이트",
  "basis_label": "당일 기준",
  "display_time": "14:35",
  "latest_snapshot_at": "2026-06-07T14:35:00+09:00",
  "is_delayed": false
}
```

### 화면 매핑

- `status_label` -> `FindStatusBar.statusLabel`
- `basis_label` -> `FindStatusBar.basisLabel`
- `display_time` -> `FindStatusBar.time`

## 2. 발견 랭킹 API

각 탭의 랭킹 테이블을 대체하기 위한 핵심 API다. 현재 화면은 최대 30개 종목을 보여주므로 `limit=30`을 기본으로 사용한다.

```http
GET /api/market/discovery/rankings?type=trading_value&limit=30
GET /api/market/discovery/rankings?type=trading_volume&limit=30
GET /api/market/discovery/rankings?type=top_gainers&limit=30
GET /api/market/discovery/rankings?type=top_losers&limit=30
```

### Query

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `type` | string | `trading_value`, `trading_volume`, `top_gainers`, `top_losers` |
| `limit` | number | 표시할 종목 수. 발견 화면은 `30` 필요 |
| `market` | string | 선택값. `all`, `kospi`, `kosdaq` 등 시장 필터가 필요할 경우 사용 |
| `snapshot_at` | string | 선택값. 특정 기준 시각 데이터 조회가 필요할 경우 사용 |

### 응답 예시

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

### 화면 매핑

| API 필드 | 화면 필드 |
| --- | --- |
| `rank` | `FindRankingItem.rank` |
| `name` | `FindRankingItem.name` |
| `price` | `FindRankingItem.price` |
| `trade_amount` 또는 `volume` | `FindRankingItem.metric` |
| `change_rate` | `FindRankingItem.change` |
| `direction` | `FindRankingItem.direction` |

### 탭별 metric 기준

| 탭 | `type` | metric 표시값 |
| --- | --- | --- |
| 거래대금 상위 | `trading_value` | 거래대금 |
| 거래량 상위 | `trading_volume` | 거래량 |
| 급상승 상위 | `top_gainers` | 거래대금 또는 보조 지표 |
| 급하락 상위 | `top_losers` | 거래대금 또는 보조 지표 |

`change_rate`는 `%` 없이 숫자로 내려주는 것이 좋다. 현재 UI에서 `%` 문자를 붙여 표시하도록 정리되어 있기 때문이다.

## 3. 시장 요약 API

KOSPI, KOSDAQ 지수 카드 영역을 대체하기 위한 API다.

```http
GET /api/market/discovery/market-summary
```

### 응답 예시

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

## 4. 상승/하락 종목 수 API

`AdvanceDeclineBar`의 게이지와 상승/하락 종목 수를 대체하기 위한 API다.

```http
GET /api/market/discovery/advance-decline
```

### 응답 예시

```json
{
  "up_count": 654,
  "up_delta": 3,
  "down_count": 218,
  "down_delta": 2,
  "unchanged_count": 87,
  "basis_time": "2026-06-07T14:35:00+09:00"
}
```

### 화면 매핑

- `up_count` -> `AdvanceDeclineBar.upCount`
- `up_delta` -> `AdvanceDeclineBar.upDelta`
- `down_count` -> `AdvanceDeclineBar.downCount`
- `down_delta` -> `AdvanceDeclineBar.downDelta`

현재 게이지는 상승/하락 종목 수 비율에 따라 유동적으로 변하도록 구현되어 있으므로, API는 실제 종목 수만 내려주면 된다.

## 5. 인기 검색 종목 API

발견 화면 하단의 인기 검색 종목 리스트를 대체하기 위한 API다.

```http
GET /api/market/discovery/popular-searches?limit=3
```

### 응답 예시

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

### 화면 매핑

- `rank` -> `PopularStockItem.rank`
- `name` -> `PopularStockItem.name`
- `change_rate` -> `PopularStockItem.change`
- `direction` -> `PopularStockItem.direction`

이 API도 `change_rate`는 `%` 없이 숫자로 내려주는 것이 좋다.

## 6. 통합 조회 API 선택안

화면 진입 시 여러 API를 동시에 호출하는 대신, 발견 화면에 필요한 데이터를 한 번에 내려주는 통합 API를 둘 수도 있다.

```http
GET /api/market/discovery/overview?ranking_type=trading_value&ranking_limit=30&popular_limit=3
```

### 응답 예시

```json
{
  "status": {
    "status_label": "실시간 업데이트",
    "basis_label": "당일 기준",
    "display_time": "14:35"
  },
  "ranking": {
    "type": "trading_value",
    "items": []
  },
  "market_summary": {
    "indices": []
  },
  "advance_decline": {
    "up_count": 654,
    "up_delta": 3,
    "down_count": 218,
    "down_delta": 2
  },
  "popular_searches": {
    "items": []
  }
}
```

통합 API를 사용하면 화면 첫 로딩에 필요한 호출 수를 줄일 수 있다. 다만 탭 전환 시 랭킹 데이터만 다시 받아오면 되므로, 랭킹 API는 별도로 유지하는 것이 좋다.

## 우선순위

더미데이터를 제거하기 위한 최소 API 우선순위는 다음과 같다.

1. `GET /api/market/discovery/rankings`
2. `GET /api/market/discovery/market-summary`
3. `GET /api/market/discovery/advance-decline`
4. `GET /api/market/discovery/popular-searches`
5. `GET /api/market/discovery/status`

가장 먼저 필요한 것은 랭킹 API다. 이 API가 30개 종목을 내려주면 `createDummyRankingItems`로 더미데이터를 30개까지 늘리는 임시 로직을 제거할 수 있다.

## 구현 상태

백엔드에는 discovery 전용 라우터가 별도로 구현되어 있다.

Base URL:

```text
/api/market/discovery
```

구현된 API:

| API | 구현 상태 | 비고 |
| --- | --- | --- |
| `GET /status` | 구현됨 | KST 현재 시각 기준 `실시간 업데이트`, `당일 기준` 반환 |
| `GET /rankings?type=trading_value&limit=30` | 구현됨 | KIS 거래대금 상위 API 사용 |
| `GET /rankings?type=trading_volume&limit=30` | 구현됨 | KIS 거래량 상위 API 사용 |
| `GET /rankings?type=top_gainers&limit=30` | 구현됨 | KIS 급상승 API 사용 |
| `GET /rankings?type=top_losers&limit=30` | 구현됨 | KIS 급하락 API 사용 |
| `GET /market-summary` | 구현됨 | KIS 국내 업종 현재 지수 API로 KOSPI/KOSDAQ 조회 |
| `GET /advance-decline` | 구현됨 | KOSPI/KOSDAQ 지수 응답의 상승/보합/하락 종목 수 합산 |
| `GET /popular-searches?limit=3` | 구현됨 | KIS HTS 조회상위20종목을 현재가 API로 보강 |
| `GET /overview` | 구현됨 | status, ranking, market-summary, advance-decline, popular-searches 통합 응답 |

현재 제한사항:

- `rankings`의 `market` 쿼리는 현재 `all`만 지원한다. `kospi`, `kosdaq`은 KIS 랭킹 파라미터 확정 후 별도 보강이 필요하다.
- `advance-decline`의 `up_delta`, `down_delta`는 이전 시점 대비 비교 데이터가 없어 현재 `0`으로 내려간다.
- `popular-searches`는 `hts-top-view`가 종목코드만 제공하므로 각 종목별 현재가 API를 추가 호출해 종목명, 등락률을 보강한다.
