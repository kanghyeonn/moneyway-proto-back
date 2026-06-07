# Flow API 추가 요구사항

현재 `(flow)` 화면의 더미데이터를 API 데이터로 대체하기 위해 필요한 API 보완 사항입니다.

## 현재 API로 대체 가능한 데이터

현재 명세의 `/api/market/leadership` API만으로 아래 데이터는 대체 가능합니다.

| 화면 데이터 | 사용 API | 매핑 |
| --- | --- | --- |
| 상승 섹터/테마 수 | `GET /sectors/summary`, `GET /themes/summary` | `bullish_count` |
| 하락 섹터/테마 수 | `GET /sectors/summary`, `GET /themes/summary` | `bearish_count` |
| 랭킹 이름 | `GET /sectors`, `GET /themes` | `items[].name` |
| 랭킹 점수 | `GET /sectors`, `GET /themes` | `Number(score) * 100` |
| 랭킹 등락률 | `GET /sectors`, `GET /themes` | `Number(weighted_change_rate) * 100` |
| 랭킹 방향 | `GET /sectors`, `GET /themes` | `side === "bullish" ? "up" : "down"` |
| TOP 종목 | `GET /sectors/{sector_id}/stocks`, `GET /themes/{theme_id}/stocks` | `name`, `price`, `change_rate` |

## 추가로 필요하거나 있으면 좋은 API

### 1. 날짜별 snapshot 선택 API

일자별 화면에서 특정 날짜를 선택했을 때 해당 날짜의 스냅샷을 쉽게 찾기 위한 API가 필요합니다.

현재는 아래 API만 있어 프론트에서 날짜별 스냅샷을 직접 골라야 합니다.

```http
GET /api/market/leadership/snapshots?limit=30
```

권장 API:

```http
GET /api/market/leadership/snapshots?date=2026-06-05
```

또는:

```http
GET /api/market/leadership/snapshots/latest?date=2026-06-05
```

예상 응답:

```json
{
  "snapshot_batch_at": "2026-06-05T06:00:00.000000Z",
  "stock_count": 2877,
  "status": "completed"
}
```

### 2. 랭킹과 TOP 종목을 함께 반환하는 API

현재 TOP 종목을 구성하려면 랭킹 상위 카테고리마다 추가 API 호출이 필요합니다.

예:

```http
GET /api/market/leadership/sectors?side=bullish&top_n=20&sort=score_desc
GET /api/market/leadership/sectors/{sector_id}/stocks?sort=change_rate_desc
GET /api/market/leadership/sectors/{sector_id}/stocks?sort=change_rate_desc
GET /api/market/leadership/sectors/{sector_id}/stocks?sort=change_rate_desc
```

이를 줄이기 위해 랭킹 응답에 TOP 종목을 포함할 수 있는 옵션이 있으면 좋습니다.

권장 API:

```http
GET /api/market/leadership/sectors?side=bullish&top_n=20&sort=score_desc&include_top_stocks=3
GET /api/market/leadership/themes?side=bullish&top_n=20&sort=score_desc&include_top_stocks=3
```

또는 별도 API:

```http
GET /api/market/leadership/sectors/top-stocks?category_top_n=3&stock_top_n=3
GET /api/market/leadership/themes/top-stocks?category_top_n=3&stock_top_n=3
```

예상 응답 구조:

```json
{
  "items": [
    {
      "id": 12,
      "name": "반도체",
      "score": "0.824",
      "weighted_change_rate": "0.0188",
      "top_stocks": [
        {
          "short_code": "000660",
          "name": "SK하이닉스",
          "price": "207000",
          "change_rate": "3.15",
          "accumulated_trade_amount": "1100000000000"
        }
      ]
    }
  ]
}
```

### 3. 화면 기준 시각 및 상태 API

화면에는 `09:30 기준`, `일자별`, `2024.05.24 (금)` 같은 기준 정보가 표시됩니다.

현재는 `snapshot_batch_at` 또는 `as_of`로 어느 정도 표현할 수 있지만, 장중/마감/지연 여부를 정확히 보여주려면 별도 상태 API가 있으면 좋습니다.

권장 API:

```http
GET /api/market/leadership/status
```

예상 응답:

```json
{
  "mode": "intraday",
  "display_time": "09:30 기준",
  "is_delayed": true,
  "delay_minutes": 2,
  "latest_snapshot_batch_at": "2026-06-05T00:30:00Z"
}
```

## 권장 호출 흐름

### 당일 섹터 화면

```text
1. GET /api/market/leadership/status
2. GET /api/market/leadership/sectors/summary
3. GET /api/market/leadership/sectors?side=bullish&top_n=20&sort=score_desc&include_top_stocks=3
```

### 당일 테마 화면

```text
1. GET /api/market/leadership/status
2. GET /api/market/leadership/themes/summary
3. GET /api/market/leadership/themes?side=bullish&top_n=20&sort=score_desc&include_top_stocks=3
```

### 일자별 섹터 화면

```text
1. GET /api/market/leadership/snapshots/latest?date=YYYY-MM-DD
2. GET /api/market/leadership/sectors/summary?snapshot_batch_at={snapshot_batch_at}
3. GET /api/market/leadership/sectors?side=bullish&top_n=20&sort=score_desc&snapshot_batch_at={snapshot_batch_at}&include_top_stocks=3
```

### 일자별 테마 화면

```text
1. GET /api/market/leadership/snapshots/latest?date=YYYY-MM-DD
2. GET /api/market/leadership/themes/summary?snapshot_batch_at={snapshot_batch_at}
3. GET /api/market/leadership/themes?side=bullish&top_n=20&sort=score_desc&snapshot_batch_at={snapshot_batch_at}&include_top_stocks=3
```

