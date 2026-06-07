# Stock Daily Price Collection Result - 2026-06-07

## Summary

2026년 1월 1일부터 2026년 6월 5일까지의 종목별 일봉 데이터를 한국투자증권 OpenAPI로 수집해 `public.stock_daily_price`에 저장했습니다.

## Command

```bash
.venv/bin/python scripts/run_stock_daily_prices.py \
  --start-date 2026-01-01 \
  --end-date 2026-06-05 \
  --request-interval-seconds 1
```

## KIS Request Settings

```text
KIS_DAILY_ITEMCHART_PRICE_MARKET_DIV_CODE=UN
KIS_DAILY_ITEMCHART_PRICE_PERIOD_DIV_CODE=D
KIS_DAILY_ITEMCHART_PRICE_ORG_ADJ_PRC=0
```

## Worker Result

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-06-05",
  "target_stock_count": 2877,
  "success_stock_count": 2877,
  "failed_stock_count": 0,
  "saved_price_count": 66091,
  "skipped_unknown_stock": 0,
  "dry_run": false,
  "status": "completed",
  "errors": []
}
```

## DB Verification

```text
rows:     66091
stocks:   699
min_date: 2026-01-02
max_date: 2026-06-05
```

Recent date counts:

```text
2026-06-05  639
2026-06-04  639
2026-06-02  639
2026-06-01  639
2026-05-29  639
2026-05-28  641
2026-05-27  642
2026-05-26  642
2026-05-22  644
2026-05-21  644
```

## Notes

- API 호출 기준으로는 전체 2877개 종목이 실패 없이 처리되었습니다.
- 실제 저장된 일봉 데이터는 699개 종목, 66091개 row입니다.
- 진행 로그의 `ok`는 KIS API 호출이 예외 없이 끝났다는 의미입니다. `output2`가 빈 종목은 실패로 집계되지 않았지만 저장 row는 없습니다.
- `2026-01-01`은 저장되지 않았습니다. DB에 저장된 최소 거래일은 `2026-01-02`입니다.
- 이 데이터는 특정일 주도 섹터/테마 계산 시 거래일 여부를 판단하는 기준 데이터로 사용할 수 있습니다.
