# Project Overview

Moneyway Back은 한국투자증권 OpenAPI와 내부 PostgreSQL 데이터를 연결해 국내 주식 탐색, 주도 섹터/테마, 인증 기능을 제공하는 FastAPI 백엔드입니다.

이 문서는 프로젝트를 처음 보는 사람에게 주요 로직의 흐름을 설명하기 위한 요약입니다. 상세 API 규격은 `docs/front/*/api.md`, DB 구조는 `docs/db/schema-summary.md`, KIS 연동 세부사항은 `docs/backend-api-design.md`를 기준으로 봅니다.

## 전체 구조

```text
FastAPI router
  -> service
  -> repository 또는 KIS client
  -> PostgreSQL / 한국투자증권 OpenAPI
```

주요 계층:

| 계층 | 위치 | 역할 |
| --- | --- | --- |
| API router | `app/api` | HTTP endpoint 정의 |
| Service | `app/services` | 화면/업무 단위 로직 조합 |
| Repository | `app/repositories` | PostgreSQL 조회/저장 |
| KIS client | `app/kis/client.py` | 한국투자증권 OpenAPI 호출/정규화 |
| Worker | `app/workers`, `scripts` | 주기적 수집 작업 |
| Schema | `app/schemas` | API 응답/내부 데이터 모델 |

## 1. KIS OpenAPI 연동

KIS 호출은 `app/kis/client.py`의 `KisClient`가 담당합니다.

주요 기능:

- OAuth access token 발급
- `.env` 기반 access token 캐시
- 토큰 만료 시 재발급
- KIS REST API 호출
- KIS 응답을 내부 schema로 정규화
- KIS 에러 메시지 추출

토큰 처리 흐름:

```text
KisClient._get_access_token()
  -> 메모리 토큰이 유효하면 사용
  -> .env 캐시 토큰이 유효하면 사용
  -> 없거나 만료됐으면 KIS OAuth API로 재발급
  -> 새 토큰과 만료시각을 .env에 저장
```

API 호출 중 `401`, `403`, `500` 또는 KIS token error 응답이 발생하면 토큰을 한 번만 재발급하고 재시도합니다. 재발급 자체가 실패하면 `app.kis.client` logger에 path, TR ID, 원인, token cache key를 남깁니다.

KIS가 제공하는 `msg1`, `msg_cd`, `rt_cd`는 예외 메시지에 포함됩니다. 예를 들어 유량 제한 응답이 오면 수집 실패 로그에는 아래처럼 남습니다.

```text
005930: 유량제한으로 요청 거부되었습니다. / EGW00201 / 1
```

현재 사용하는 KIS API:

| KIS API | Endpoint | 용도 |
| --- | --- | --- |
| OAuth 접근토큰 발급 | `POST /oauth2/tokenP` | 모든 KIS REST 호출용 access token 발급 및 갱신 |
| 거래량순위 | `GET /uapi/domestic-stock/v1/quotations/volume-rank` | 거래량 상위 종목 조회 |
| 거래대금순위 | `GET /uapi/domestic-stock/v1/quotations/volume-rank` | `FID_BLNG_CLS_CODE=3`을 적용해 거래대금 상위 종목 조회 |
| 등락률 순위 | `GET /uapi/domestic-stock/v1/ranking/fluctuation` | 급상승/급하락 종목 조회 |
| HTS 조회상위20종목 | `GET /uapi/domestic-stock/v1/ranking/hts-top-view` | 인기 검색 종목 코드 목록 조회 |
| 주식현재가 시세 | `GET /uapi/domestic-stock/v1/quotations/inquire-price` | 현재가, 누적 거래량, 누적 거래대금, 등락률 조회. 인기검색 보강과 주도 섹터/테마 스냅샷 수집에 사용 |
| 국내주식기간별시세 | `GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | 종목별 일봉 OHLC, 거래량, 거래대금, 등락률 저장 |
| 국내업종 현재지수 | `GET /uapi/domestic-stock/v1/quotations/inquire-index-price` | KOSPI/KOSDAQ 지수와 상승/보합/하락 종목 수 조회 |

## 2. 시장 탐색 API

시장 탐색 화면 로직은 아래 파일들이 담당합니다.

```text
app/api/market_discovery.py
  -> app/services/market_discovery_service.py
  -> app/repositories/market_repository.py
  -> app/repositories/market_discovery_repository.py

scripts/run_market_discovery_snapshot.py
  -> app/workers/market_discovery_snapshot_worker.py
  -> app/services/market_discovery_snapshot_service.py
  -> app/kis/client.py
  -> app/repositories/market_discovery_repository.py
```

제공 데이터:

- 거래대금 상위
- 거래량 상위
- 급상승 종목
- 급하락 종목
- KOSPI/KOSDAQ 지수
- KOSPI/KOSDAQ 합산 상승/하락/보합 종목 수
- 인기 검색 종목
- 발견 화면 통합 조회

프론트 API는 KIS를 직접 호출하지 않고 `market_discovery_*` 스냅샷 테이블의 최신 completed/partial 배치를 조회합니다. KIS 호출은 1분 단위 수집 worker에서만 수행합니다.

수집 worker 흐름:

```text
스케줄러 또는 수동 실행
  -> 거래대금/거래량/급상승/급하락 KIS 순위 API 호출
  -> KOSPI/KOSDAQ 국내업종 현재지수 API 호출
  -> HTS조회상위20종목 API 호출
  -> 인기검색 종목명은 DB public.stock에서 매핑
  -> 인기검색 종목별 현재가 API로 등락률 보강
  -> public.market_discovery_snapshot_batch 저장
  -> public.market_discovery_ranking_snapshot 저장
  -> public.market_discovery_index_snapshot 저장
  -> public.market_discovery_popular_search_snapshot 저장
```

`advance-decline`의 `up_delta`, `down_delta`는 정확히 1분 전 timestamp가 아니라 최신 성공 스냅샷과 직전 성공 스냅샷의 상승/하락 종목 수 차이입니다. 수집이 1분마다 정상 실행되면 1분 변화량처럼 동작하고, 중간 수집 실패가 있으면 직전 성공 배치 대비 변화량이 됩니다.

## 3. 현재가 스냅샷 수집

주도 섹터/테마 계산은 실시간 WebSocket이 아니라 KIS `주식현재가 시세` REST API로 주기적 스냅샷을 저장하는 방식입니다.

관련 파일:

```text
scripts/run_market_snapshot.py
  -> app/workers/market_snapshot_worker.py
  -> app/services/market_service.py
  -> app/repositories/market_repository.py
  -> app/kis/client.py
```

수집 흐름:

```text
스케줄러 또는 수동 실행
  -> public.stock의 active 일반 주식 조회
  -> ETF/ETN 제외
  -> 종목별 KIS 현재가 API 호출
  -> public.market_snapshot_batch 저장
  -> public.stock_intraday_snapshot 저장
```

수집 대상:

```text
public.stock.is_active = true
AND stock_type NOT IN ('ETF', 'ETN')
```

ETF/ETN은 DB 종목 마스터에는 포함될 수 있지만, 주도 섹터/테마 계산용 현재가 스냅샷에서는 제외합니다.

현재 운영 계획은 평일 08:00~20:00 사이 1시간 단위 실행입니다. FastAPI 서버가 켜져 있다고 자동 실행되지는 않으므로 `crontab` 같은 외부 스케줄러에 worker script를 등록해야 합니다.

현재가 스냅샷 worker는 일반 KIS 호출과 별도의 두 번째 credential/token 세트를 사용합니다.

```text
KIS_APP_KEY_2
KIS_APP_SECRET_2
KIS_ACCESS_TOKEN_2
KIS_ACCESS_TOKEN_EXPIRES_AT_2
```

## 4. 주도 섹터/테마 계산

주도 섹터/테마 API는 저장된 최신 현재가 스냅샷을 우선 읽어 on-demand로 계산합니다. 특정 날짜에 장중 스냅샷이 없으면 `stock_daily_price` 일봉 데이터를 같은 계산식에 넣어 계산합니다.

관련 파일:

```text
app/api/market_leadership.py
  -> app/services/market_leadership_service.py
  -> app/repositories/market_leadership_repository.py
```

기준 데이터:

```text
public.stock_intraday_snapshot
public.stock_daily_price
public.stock
public.sector
public.stock_sector
public.theme
public.stock_theme
```

기본 계산 기준:

- 최신 `snapshot_batch_at` 배치 하나를 사용
- 당일 누적 거래대금 사용
- 전일 대비 등락률 사용
- 카테고리 거래대금 1000억 원 이상만 주도 후보
- 상승 주도와 하락 주도를 구분

주요 지표:

| 지표 | 의미 |
| --- | --- |
| `trade_amount` | 섹터/테마 소속 종목들의 누적 거래대금 합계 |
| `weighted_change_rate` | `sum(거래대금 * 수익률) / sum(거래대금)`으로 계산한 거래대금 가중 등락률 |
| `advance_ratio` | 상승 종목 비율 |
| `up_trade_amount_ratio` | 상승 종목 거래대금 비율 |
| `decline_ratio` | 하락 종목 비율 |
| `down_trade_amount_ratio` | 하락 종목 거래대금 비율 |
| `top1_trade_amount_share` | 1개 종목 거래대금 쏠림 정도 |
| `concentration_penalty` | 대형주 쏠림 보정 계수 |
| `score` | 위 지표들을 조합한 주도 점수 |

상승 주도 점수는 거래대금, 양의 가중 등락률, 상승 확산도, 상승 거래대금 비중, 쏠림 보정을 함께 반영합니다. 하락 주도 점수는 음의 가중 등락률과 하락 확산도를 기준으로 계산합니다.

상승 주도 점수:

```text
score =
  ln(1 + trade_amount)
  * max(weighted_change_rate, 0)
  * up_trade_amount_ratio
  * min(1, advance_ratio / 0.6)
  * concentration_penalty
```

하락 주도 점수:

```text
score =
  ln(1 + trade_amount)
  * abs(min(weighted_change_rate, 0))
  * down_trade_amount_ratio
  * min(1, decline_ratio / 0.6)
  * concentration_penalty
```

최종 후보는 `stock_count >= 3`, `trade_amount >= 1000억 원`을 만족해야 합니다. 상승 주도는 `weighted_change_rate > 0`이고 상승 종목 수가 최소 3개 이상이어야 합니다. 하락 주도는 `weighted_change_rate < 0`이고 하락 종목 수가 최소 3개 이상이어야 합니다. 이 필터는 1~2개 종목만 급등 또는 급락해 전체 섹터/테마가 주도 카테고리처럼 보이는 경우를 제외하기 위한 조건입니다.

`concentration_penalty`는 거래대금 1위 종목 쏠림을 줄이는 값입니다. 1위 종목 비중이 40% 이하이면 `1.0`, 80% 이상이면 `0.5`, 그 사이는 선형 감점합니다.

날짜를 지정했을 때 해당 날짜의 장중 스냅샷이 있으면 장중 스냅샷을 사용합니다. 장중 스냅샷이 없으면 해당일 `stock_daily_price` 일봉 데이터를 사용합니다. 해당일 일봉도 없으면 주말/휴장일 조회처럼 직전 일봉 거래일 데이터를 사용합니다.

## 5. 과거 일봉 수집

특정일의 주도 섹터/테마를 계산하거나 과거 데이터를 분석하기 위해 종목별 일봉 데이터를 저장합니다.

관련 파일:

```text
scripts/run_stock_daily_prices.py
  -> app/workers/stock_daily_price_worker.py
  -> app/services/market_service.py
  -> app/repositories/market_repository.py
  -> app/kis/client.py
```

수집 흐름:

```text
수집 기간 지정
  -> public.stock의 active 종목 조회
  -> 종목별 KIS 국내주식기간별시세 API 호출
  -> public.stock_daily_price 저장
```

일봉 worker는 NXT 마스터 파일에 포함된 종목은 KIS 시장구분 `UN`, 그 외 종목은 `J`로 조회합니다. 저장 데이터는 시가, 고가, 저가, 종가, 거래량, 거래대금, 전일 대비 등락률입니다.

## 6. DB 종목 마스터

주요 종목 정보는 `public.stock`에 저장합니다.

현재 정책:

- 일반 주식, ETF, ETN을 같은 `stock` 테이블에 저장
- ETF 코드는 6자리까지 저장
- ETN 코드는 7자리까지 저장
- `stock_type`으로 일반 주식/ETF/ETN을 구분

예:

```text
005930   삼성전자
0000D0   ETF 예시
Q500061  ETN 예시
```

주도 섹터/테마 스냅샷 수집에서는 ETF/ETN을 제외하지만, 탐색 화면이나 랭킹 프록시에서는 KIS 응답에 따라 ETF/ETN이 노출될 수 있습니다.

## 7. 인증 로직

인증 기능은 시장 데이터와 분리된 auth 계층으로 구성되어 있습니다.

관련 파일:

```text
app/api/auth.py
  -> app/services/auth_service.py
  -> app/repositories/auth_repository.py
  -> app/core/security.py
```

지원 범위:

- 이메일/휴대폰 번호 + 비밀번호 회원가입
- 이메일/휴대폰 번호 + 비밀번호 로그인
- Google ID token 기반 회원가입/로그인
- access token 발급
- refresh token 발급 및 DB hash 저장
- refresh token 회전
- 로그아웃 시 refresh token 폐기
- access token 기반 현재 사용자 조회
- 휴대폰 인증번호 생성/검증

Google 로그인은 프론트가 Google ID token을 백엔드로 전달하면, 백엔드가 Google tokeninfo로 검증한 뒤 자체 Moneyway access token과 refresh token을 발급하는 방식입니다. 현재 구조에서는 Google client secret이 필요하지 않고, `GOOGLE_OAUTH_CLIENT_ID`로 audience를 검증합니다.

휴대폰 인증은 인증번호 생성, DB 저장, 검증까지 구현되어 있습니다. 실제 SMS 발송, rate limit, 인증번호 재요청 제한, 비밀번호 재설정은 추후 구현 항목입니다.

## 8. 운영상 중요한 점

- KIS API는 유량 제한이 있으므로 worker 실행 시 `KIS_REQUEST_INTERVAL_SECONDS`를 조정해야 합니다.
- 현재가 스냅샷 worker는 FastAPI 서버와 별개로 실행해야 합니다.
- 스냅샷 worker 중복 실행 방지를 위해 PostgreSQL advisory lock을 사용합니다.
- KIS OAuth token은 `.env`에 캐시되어 재발급 빈도를 줄입니다.
- 스냅샷 worker는 `_2` KIS credential/token 세트를 사용합니다.
- KIS 에러 메시지는 수집 실패 로그에 남도록 처리합니다.
- `tests/`와 `sql/`이 `.gitignore` 대상이면 커밋 시 `git add -f`가 필요할 수 있습니다.

## 9. 주요 문서

| 문서 | 설명 |
| --- | --- |
| `README.md` | 실행 방법과 기본 운영 명령 |
| `docs/backend-api-design.md` | 백엔드 API/계산/수집 설계 |
| `docs/db/schema-summary.md` | DB 테이블 요약 |
| `docs/front/find/api.md` | 탐색 화면 API |
| `docs/front/flow/api.md` | 섹터/테마 화면 API |
| `docs/front/auth/api.md` | 인증 API |
| `docs/front/auth/future-work.md` | 인증 추후 구현 항목 |
| `docs/operations/market-snapshot-scheduler.md` | 스냅샷 worker 운영 계획 |
