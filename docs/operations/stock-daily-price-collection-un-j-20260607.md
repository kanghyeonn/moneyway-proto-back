# UN/J 분기 일봉 수집 실행 결과

작성일: 2026-06-07

## 실행 조건

- 실행 스크립트: `scripts/run_stock_daily_prices.py`
- 수집 기간: `2026-01-01` ~ `2026-06-05`
- 요청 간격: 1초
- 시장 구분 전략:
  - `docs/kis/종목정보/nxt_kospi_code.mst`, `docs/kis/종목정보/nxt_kosdaq_code.mst`에 있는 종목: `FID_COND_MRKT_DIV_CODE=UN`
  - 위 NXT 마스터에 없는 종목: `FID_COND_MRKT_DIV_CODE=J`

## 실행 결과

1차 전체 실행 결과:

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-06-05",
  "target_stock_count": 2877,
  "success_stock_count": 2876,
  "failed_stock_count": 1,
  "saved_price_count": 286275,
  "skipped_unknown_stock": 0,
  "dry_run": false,
  "status": "partial"
}
```

## 실패 종목 및 재시도

| 코드 | 종목명 | 시장 | 실패 사유 |
|---|---|---|---|
| 001840 | 이화공영 | KOSDAQ | KIS `inquire-daily-itemchartprice` 호출에서 HTTP 500 반환 |

실패 URL의 주요 파라미터:

- `FID_COND_MRKT_DIV_CODE=J`
- `FID_INPUT_ISCD=001840`
- `FID_INPUT_DATE_1=20260101`
- `FID_INPUT_DATE_2=20260605`
- `FID_PERIOD_DIV_CODE=D`
- `FID_ORG_ADJ_PRC=0`

이후 실패 종목만 동일 조건으로 재시도했고 성공했다.

```text
001840 fetched rows: 100
001840 saved rows: 100
skipped unknown stock: 0
```

재시도 후 `001840 이화공영` 저장 상태:

| 코드 | 종목명 | 저장 건수 | 최초 저장일 | 최종 저장일 |
|---|---|---:|---|---|
| 001840 | 이화공영 | 100 | 2026-01-07 | 2026-06-05 |

## DB 검증

재시도까지 완료한 최종 `public.stock_daily_price` 기준:

| 항목 | 값 |
|---|---:|
| 저장 row 수 | 286,555 |
| 저장 종목 수 | 2,877 |
| 최초 거래일 | 2026-01-02 |
| 최종 거래일 | 2026-06-05 |

종목별 저장 건수 분포:

| 저장 건수 | 종목 수 |
|---:|---:|
| 11 | 1 |
| 12 | 1 |
| 15 | 1 |
| 18 | 1 |
| 23 | 1 |
| 24 | 1 |
| 26 | 1 |
| 28 | 1 |
| 42 | 1 |
| 43 | 2 |
| 44 | 1 |
| 45 | 1 |
| 47 | 1 |
| 48 | 1 |
| 49 | 1 |
| 52 | 1 |
| 56 | 1 |
| 61 | 1 |
| 62 | 1 |
| 63 | 1 |
| 83 | 1 |
| 90 | 1 |
| 95 | 2 |
| 100 | 2,792 |
| 103 | 60 |

`103`건 종목이 있는 이유는 이전 `UN` 수집에서 `2026-01-02` ~ `2026-01-06` 일부 데이터가 이미 저장되어 있었고, 이번 `J` 수집의 최근 100건이 추가로 upsert되면서 같은 조회 기간 내 저장 건수가 100건을 초과했기 때문이다.

## 코드 변경 요약

- `KisClient.fetch_daily_prices()`에 `market_div_code` override 파라미터를 추가했다.
- `MarketService.run_daily_price_collection()`이 종목별 시장 구분 resolver를 받아 KIS 호출에 전달하도록 변경했다.
- `StockDailyPriceWorker`가 NXT 마스터 파일을 읽어 종목별로 `UN` 또는 `J`를 결정하도록 변경했다.
