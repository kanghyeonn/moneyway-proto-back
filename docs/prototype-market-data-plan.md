# Prototype Market Data Plan

이 문서는 moneyway 프로토타입에서 한국투자증권 OpenAPI와 내부 DB를 어떻게 나눠 사용할지 정리한 내용입니다.

## 목표

프로토타입에서는 초단위 WebSocket 수집 대신, 한국투자증권 `주식현재가 시세` REST API로 전체 활성 종목의 스냅샷을 저장하고, 최신 스냅샷의 당일 누적 거래대금과 전일 대비 등락률로 당일 주도 섹터/테마를 계산합니다.

특정일의 주도 섹터/테마를 과거 데이터로 계산하기 위해 한국투자증권 `국내주식기간별시세(일/주/월/년)` REST API의 일봉 데이터는 별도 원천 테이블에 저장합니다.

## API로 바로 전달할 데이터

다음 데이터는 한국투자증권 OpenAPI에서 받아 백엔드가 가공한 뒤 프론트에 바로 전달합니다.

- 거래량 상위 종목
- 거래대금 상위 종목
- 급상승 종목 상위
- 급하락 종목 상위

이 데이터는 프로토타입 단계에서 DB에 별도 저장하지 않습니다.

## 내부에서 계산할 데이터

당일 주도 섹터/테마는 `public.stock_intraday_snapshot`의 최신 배치 하나를 사용합니다.

종목별 계산:

```text
trade_amount = accumulated_trade_amount
change_rate = change_rate / 100
```

섹터/테마별 계산:

```text
trade_amount
weighted_change_rate
advance_ratio
up_trade_amount_ratio
decline_ratio
down_trade_amount_ratio
top1_trade_amount_share
concentration_penalty
```

## DB 사용 범위

기존 테이블은 분류 기준으로 사용합니다.

- `public.stock`
- `public.sector`
- `public.stock_sector`
- `public.theme`
- `public.stock_theme`

수집 원천 테이블:

- `public.market_snapshot_batch`
- `public.stock_intraday_snapshot`
- `public.stock_daily_price`

당일 리더십 결과를 저장할 경우 사용하는 테이블:

- `public.sector_daily_leadership_snapshot`
- `public.sector_daily_leadership_stock`
- `public.theme_daily_leadership_snapshot`
- `public.theme_daily_leadership_stock`

기존 `public.stock_trade_amount_snapshot`은 구형 실시간 거래대금 실험 테이블이었고, 현재 스키마에서는 제거되었습니다.

## 처리 흐름

```text
1. 스냅샷 수집 실행
   - public.stock의 active 종목 전체 조회
   - KIS 주식현재가 시세 REST 호출
   - 현재가, 누적거래량, 누적거래대금, 전일 대비율 저장
   - public.stock_intraday_snapshot

2. 프론트가 당일 주도 섹터/테마 API 호출
   - 최신 snapshot_batch_at 조회
   - 최신 배치의 stock_intraday_snapshot 조회
   - stock_sector, stock_theme 조인
   - 카테고리 누적 거래대금 1000억 원 이상만 후보로 사용
   - 상승/하락 주도 점수 계산
   - score 순 top N 반환

3. 과거 일봉 수집 실행
   - public.stock의 active 종목 조회
   - KIS 국내주식기간별시세 REST 호출
   - 거래일, 시가, 고가, 저가, 종가, 누적거래량, 누적거래대금, 전일 대비 금액, 전일 대비율 저장
   - public.stock_daily_price

4. 특정일 주도 섹터/테마 계산
   - trading_date 기준 stock_daily_price 조회
   - stock_sector, stock_theme 조인
   - 카테고리 누적 거래대금 1000억 원 이상만 후보로 사용
   - 상승/하락 주도 점수 계산
   - score 순 top N 반환
```

## 수집 API

전체 종목 스냅샷 수집에는 한국투자증권 `주식현재가 시세` API를 사용합니다.

```text
GET /uapi/domestic-stock/v1/quotations/inquire-price
TR_ID: FHKST01010100
```

필수 응답 필드:

```text
stck_prpr       현재가
acml_vol        누적 거래량
acml_tr_pbmn    누적 거래대금
prdy_ctrt       전일 대비율
```

거래대금은 `현재가 * 거래량`으로 계산하지 않고, API가 제공하는 `acml_tr_pbmn`을 저장합니다.

## 과거 일봉 수집 API

특정일 주도 섹터/테마 계산을 위한 과거 일봉 저장에는 한국투자증권 `국내주식기간별시세(일/주/월/년)` API를 사용합니다.

```text
GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
TR_ID: FHKST03010100
```

필수 응답 필드:

```text
stck_bsop_date 거래일
stck_oprc      시가
stck_hgpr      고가
stck_lwpr      저가
stck_clpr      종가
acml_vol       누적 거래량
acml_tr_pbmn   누적 거래대금
prdy_vrss      전일 대비 금액
```

저장 테이블:

```text
public.stock_daily_price
```

`output2`의 일자별 데이터에는 전일 대비율이 직접 없으므로 `close_price`와 `change_amount`로 계산해 저장합니다.

```text
previous_close_price = close_price - change_amount
change_rate = change_amount / previous_close_price * 100
```

## 상승 주도 점수

```text
bullish_score =
  log1p(trade_amount)
  * max(weighted_change_rate, 0)
  * up_trade_amount_ratio
  * breadth_factor
  * concentration_penalty
```

```text
breadth_factor = min(1, advance_ratio / 0.6)
```

## 하락 주도 점수

```text
bearish_score =
  log1p(trade_amount)
  * abs(min(weighted_change_rate, 0))
  * down_trade_amount_ratio
  * decline_breadth_factor
  * concentration_penalty
```

```text
decline_breadth_factor = min(1, decline_ratio / 0.6)
```

## 대형주 쏠림 보정

거래대금을 핵심 가중치로 쓰면 대형주가 속한 섹터/테마가 과대표현될 수 있습니다. 이를 완화하기 위해 상위 1개 종목 거래대금 비중에 페널티를 적용합니다.

```text
top1_trade_amount_share <= 0.4 -> concentration_penalty = 1.0
top1_trade_amount_share >= 0.8 -> concentration_penalty = 0.5
0.4~0.8 구간 -> 1.0에서 0.5까지 선형 감점
```

최소 필터:

```text
stock_count >= 3
trade_amount > 0
bullish: weighted_change_rate > 0
bearish: weighted_change_rate < 0
```

## 설계 판단

- 당일 주도 섹터/테마는 최신 스냅샷 하나만 있으면 계산할 수 있습니다.
- 장마감 후에도 당일 누적 거래대금과 전일 대비율이 남아 있으므로 결과를 계산할 수 있습니다.
- 이 지표는 “최근 구간 주도”가 아니라 “오늘 현재까지의 누적 주도”를 의미합니다.
- 특정일 주도 섹터/테마는 `stock_daily_price`의 확정 일봉 데이터 기준이므로 장중 스냅샷 기반 당일 주도와 원천 데이터가 다릅니다.
- 정확한 초단위 실시간 리더십이 필요해지면 WebSocket 체결 데이터 수집으로 별도 확장합니다.
