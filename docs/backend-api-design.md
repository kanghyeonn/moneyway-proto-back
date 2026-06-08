# Backend API Design

한국투자증권 OpenAPI와 내부 PostgreSQL 스키마를 연결하는 FastAPI 백엔드 설계입니다.

## 역할 분리

```text
KIS REST 순위 API
  -> 거래량 상위, 거래대금 상위, 급상승, 급하락
  -> 백엔드 정규화
  -> 프론트 응답

KIS 주식현재가 시세 REST
  -> 전체 종목 snapshot 저장
  -> 최신 배치의 당일 누적 거래대금과 전일 대비 등락률 집계
  -> 당일 상승/하락 주도 섹터/테마 계산
  -> 프론트 응답

KIS 국내주식기간별시세 REST
  -> 종목별 과거 일봉 저장
  -> 특정일 기준 거래량, 거래대금, OHLC, 등락률 조회
  -> 특정일 주도 섹터/테마 계산 원천으로 사용
```

코드 계층:

```text
app/api/market_discovery.py
  -> app/services/market_discovery_service.py
  -> app/kis/client.py

app/api/market_snapshots.py
  -> app/services/market_service.py
  -> app/repositories/market_repository.py

app/api/market_leadership.py
  -> app/services/market_leadership_service.py
  -> app/repositories/market_leadership_repository.py

app/api/auth.py
  -> app/services/auth_service.py
  -> app/repositories/auth_repository.py
```

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/health` | 헬스 체크 |
| `POST` | `/api/auth/signup` | 이메일/휴대폰 비밀번호 회원가입 |
| `POST` | `/api/auth/login` | 이메일 또는 휴대폰 번호 기반 로그인 |
| `POST` | `/api/auth/oauth/google` | Google ID token 기반 회원가입/로그인 |
| `POST` | `/api/auth/refresh` | refresh token 회전 및 access token 재발급 |
| `POST` | `/api/auth/logout` | refresh token 폐기 |
| `GET` | `/api/auth/me` | access token 기반 현재 사용자 조회 |
| `POST` | `/api/auth/phone-verifications` | 휴대폰 인증번호 생성 |
| `POST` | `/api/auth/phone-verifications/confirm` | 휴대폰 인증번호 확인 |
| `GET` | `/api/market/discovery/status` | 발견 화면 상태/기준 시각 |
| `GET` | `/api/market/discovery/rankings` | 발견 화면 거래대금/거래량/급상승/급하락 랭킹 |
| `GET` | `/api/market/discovery/market-summary` | KOSPI/KOSDAQ 지수 요약 |
| `GET` | `/api/market/discovery/advance-decline` | KOSPI/KOSDAQ 합산 상승/하락 종목 수 |
| `GET` | `/api/market/discovery/popular-searches` | HTS 조회상위 종목 현재가 보강 결과 |
| `GET` | `/api/market/discovery/overview` | 발견 화면 통합 조회 |
| `POST` | `/api/market/intraday-snapshots/run` | KIS 현재가 API 기반 스냅샷 수동 수집 |
| `GET` | `/api/market/leadership/snapshots` | 주도 섹터/테마 조회 가능한 스냅샷 목록 |
| `GET` | `/api/market/leadership/snapshots/latest` | 날짜별 최신 리더십 스냅샷 |
| `GET` | `/api/market/leadership/status` | 리더십 화면 상태/기준 날짜 |
| `GET` | `/api/market/leadership/sectors/summary` | 섹터 페이지 상단 요약 |
| `GET` | `/api/market/leadership/themes/summary` | 테마 페이지 상단 요약 |
| `GET` | `/api/market/leadership/sectors` | 당일 상승/하락 주도 섹터 조회 |
| `GET` | `/api/market/leadership/themes` | 당일 상승/하락 주도 테마 조회 |
| `GET` | `/api/market/leadership/sectors/{sector_id}/stocks` | 섹터 소속 종목 등락률 정렬 조회 |
| `GET` | `/api/market/leadership/themes/{theme_id}/stocks` | 테마 소속 종목 등락률 정렬 조회 |

공통 query:

```text
top_n: 1-100, 기본 DEFAULT_TOP_N
side: bullish | bearish, 기본 bullish
sort: score_desc | trade_amount_desc | weighted_change_rate_desc | weighted_change_rate_asc
snapshot_batch_at: 선택, 생략하면 최신 스냅샷
date: 선택, KST 기준 조회 날짜. 해당일 스냅샷이 없고 거래일이면 에러, 주말/휴장일이면 직전 거래일 스냅샷 사용
```

## 발견 화면 API

`GET /api/market/discovery/rankings`는 `type` 값에 따라 KIS 순위 API를 호출합니다.

```text
type=trading_value  -> 거래량순위 API + FID_BLNG_CLS_CODE=3
type=trading_volume -> 거래량순위 API
type=top_gainers    -> 등락률 순위 API 상승 정렬
type=top_losers     -> 등락률 순위 API 하락 정렬
```

`GET /api/market/discovery/market-summary`와 `GET /api/market/discovery/advance-decline`은 한국투자증권 `국내업종 현재지수` REST API를 사용해 KOSPI/KOSDAQ 현재 지수와 상승/보합/하락 종목 수를 반환합니다.

KIS 원천 API:

```text
GET /uapi/domestic-stock/v1/quotations/inquire-index-price
TR_ID: FHPUP02100000
```

기본 요청 파라미터:

```text
FID_COND_MRKT_DIV_CODE=U
FID_INPUT_ISCD=0001  # KOSPI
FID_INPUT_ISCD=1001  # KOSDAQ
```

관련 설정:

```text
KIS_INDEX_PRICE_PATH
KIS_INDEX_PRICE_TR_ID
KIS_INDEX_PRICE_MARKET_DIV_CODE
KIS_INDEX_CODES
```

`GET /api/market/discovery/popular-searches`는 한국투자증권 `HTS조회상위20종목` REST API로 종목코드를 받은 뒤, DB `stock` 테이블에서 종목명을 매핑하고 각 종목의 현재가 API로 등락률을 보강합니다.

KIS 조회상위 원천 API:

```text
GET /uapi/domestic-stock/v1/ranking/hts-top-view
TR_ID: HHMCM000100C0
```

원천 API는 별도 query parameter가 없고 최대 20개 종목을 반환합니다. 응답에는 시장구분과 종목코드만 포함됩니다. 종목명은 KIS 현재가 응답에 의존하지 않고 내부 DB `stock.short_code`, `stock.name` 매핑을 사용합니다.

관련 설정:

```text
KIS_HTS_TOP_VIEW_PATH
KIS_HTS_TOP_VIEW_TR_ID
```

## 당일 리더십 집계 기준

당일 주도 섹터/테마는 `stock_intraday_snapshot`의 최신 배치 하나를 사용합니다.
섹터/테마의 당일 누적 거래대금이 1000억 원 이상인 경우만 주도 후보로 반환합니다.

종목별 계산:

```text
trade_amount = current.accumulated_trade_amount
change_rate = current.change_rate / 100
```

섹터/테마별 주요 지표:

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

상승 주도 점수:

```text
score =
  log1p(trade_amount)
  * max(weighted_change_rate, 0)
  * up_trade_amount_ratio
  * min(1, advance_ratio / 0.6)
  * concentration_penalty
```

하락 주도 점수:

```text
score =
  log1p(trade_amount)
  * abs(min(weighted_change_rate, 0))
  * down_trade_amount_ratio
  * min(1, decline_ratio / 0.6)
  * concentration_penalty
```

`concentration_penalty`는 1개 대형주의 거래대금 쏠림을 완화합니다.

```text
top1_trade_amount_share <= 0.4 -> 1.0
top1_trade_amount_share >= 0.8 -> 0.5
0.4~0.8 구간 -> 1.0에서 0.5까지 선형 감점
```

## 과거 일봉 저장 기준

특정일의 주도 섹터/테마를 계산하려면 종목별 과거 일봉 원천 데이터를 저장합니다.

적용 SQL:

```text
sql/20260607_stock_daily_price.sql
```

저장 테이블:

```text
public.stock_daily_price
```

수집 원천 API:

```text
GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
TR_ID: FHKST03010100
```

필수 요청 파라미터:

```text
FID_COND_MRKT_DIV_CODE  J: KRX, NX: NXT, UN: 통합
FID_INPUT_ISCD          종목코드
FID_INPUT_DATE_1        조회 시작일자
FID_INPUT_DATE_2        조회 종료일자
FID_PERIOD_DIV_CODE     D: 일봉, W: 주봉, M: 월봉, Y: 년봉
FID_ORG_ADJ_PRC         0: 수정주가, 1: 원주가
```

현재 일봉 수집 worker는 NXT 마스터 파일에 있는 종목은 `UN`, 그 외 종목은 `J`로 조회합니다. `UN`만 사용하면 NXT 마스터 외 KOSPI/KOSDAQ 종목에서 `output2`가 비거나 일부 기간만 내려오는 경우가 있어, 전체 종목 수집에는 종목별 시장 구분 분기가 필요합니다.

저장 필드:

```text
stck_bsop_date -> trading_date
stck_oprc      -> open_price
stck_hgpr      -> high_price
stck_lwpr      -> low_price
stck_clpr      -> close_price
acml_vol       -> accumulated_volume
acml_tr_pbmn   -> accumulated_trade_amount
prdy_vrss      -> change_amount
```

`output2`에는 전일 대비율이 직접 포함되지 않으므로 `close_price`와 `change_amount`로 계산해 `change_rate`에 저장합니다.

```text
previous_close_price = close_price - change_amount
change_rate = change_amount / previous_close_price * 100
```

특정일 주도 섹터/테마는 `stock_daily_price.trading_date`를 기준으로 `stock_sector`, `stock_theme`을 조인해 계산합니다.

## 인증 DB 설계 기준

로그인/회원가입 최소 테이블은 아래 SQL로 생성합니다.

```text
sql/20260608_auth_minimum_tables.sql
```

최소 구성:

```text
public.users
public.user_password_credentials
public.user_oauth_accounts
public.auth_refresh_tokens
public.phone_verification_codes
```

화면 기준 지원 범위:

- 이메일 또는 휴대폰 번호 + 비밀번호 로그인
- Google 회원가입/로그인
- 자동 로그인
- 휴대폰 인증번호
- Apple 회원가입/로그인은 추후 `user_oauth_accounts.provider='apple'`로 확장

토큰 설계:

```text
Moneyway access token
- 짧은 만료 시간
- API Authorization Bearer 토큰
- 일반적으로 DB에 저장하지 않음

Moneyway refresh token
- 긴 만료 시간
- 앱 secure storage에 원문 저장
- DB에는 auth_refresh_tokens.token_hash만 저장
```

Google 로그인은 Google ID token을 백엔드에서 검증한 뒤, `user_oauth_accounts.provider='google'`, `provider_user_id=<Google sub>`로 사용자를 찾거나 생성합니다. 이후 앱에는 Google token이 아니라 Moneyway access token과 refresh token을 발급합니다.

구현된 인증 endpoint:

```text
POST /api/auth/signup
{
  "email": "user@example.com",
  "phone_number": "01012345678",
  "password": "password123",
  "name": "홍길동",
  "marketing_agreed": false,
  "phone_verification_code": "123456",
  "device_id": "expo-device-id"
}

POST /api/auth/login
{
  "identifier": "user@example.com",
  "password": "password123",
  "device_id": "expo-device-id"
}

POST /api/auth/oauth/google
{
  "id_token": "<google-id-token>",
  "device_id": "expo-device-id",
  "marketing_agreed": false
}

POST /api/auth/refresh
{
  "refresh_token": "<refresh-token>",
  "device_id": "expo-device-id"
}

POST /api/auth/logout
{
  "refresh_token": "<refresh-token>"
}

GET /api/auth/me
Authorization: Bearer <access-token>

POST /api/auth/phone-verifications
{
  "phone_number": "01012345678",
  "purpose": "signup"
}

POST /api/auth/phone-verifications/confirm
{
  "phone_number": "01012345678",
  "purpose": "signup",
  "code": "123456"
}
```

`signup`, `login`, `oauth/google`, `refresh`는 동일한 응답 형태를 반환합니다.

```text
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "phone_number": "01012345678",
    "name": "홍길동",
    "profile_image_url": null,
    "status": "active",
    "marketing_agreed": false,
    "created_at": "2026-06-08T00:00:00Z"
  },
  "tokens": {
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "Bearer",
    "expires_in": 1800
  }
}
```

휴대폰 인증번호는 `AUTH_EXPOSE_DEV_CODES=1`인 로컬 개발 환경에서만 응답의 `development_code`로 노출합니다. 실제 서비스에서는 SMS 발송 provider를 붙이고 이 값을 노출하지 않습니다.

관련 설정:

```text
AUTH_TOKEN_SECRET
AUTH_ACCESS_TOKEN_MINUTES
AUTH_REFRESH_TOKEN_DAYS
AUTH_PHONE_VERIFICATION_TTL_MINUTES
AUTH_EXPOSE_DEV_CODES
GOOGLE_OAUTH_CLIENT_ID
```

추가 권장 테이블:

| 테이블 | 용도 |
| --- | --- |
| `public.password_reset_tokens` | 비밀번호 찾기/재설정 |
| `public.terms` | 약관/개인정보/마케팅 동의 문서 버전 |
| `public.user_terms_agreements` | 사용자별 약관 동의 이력 |
| `public.user_login_events` | 로그인 성공/실패 감사 로그 |
| `public.user_devices` | 기기별 세션/로그아웃 관리 |

## KIS 설정과 필수 파라미터

KIS 순위 endpoint와 TR ID는 공식 문서 기본값을 코드에 넣고, `.env`에서 덮어쓸 수 있게 둡니다.

```text
KIS_VOLUME_TOP_PATH=/uapi/domestic-stock/v1/quotations/volume-rank
KIS_VOLUME_TOP_TR_ID=FHPST01710000
KIS_VOLUME_TOP_PARAMS={}
KIS_TRADE_AMOUNT_TOP_PARAMS={}

KIS_RISERS_PATH=/uapi/domestic-stock/v1/ranking/fluctuation
KIS_RISERS_TR_ID=FHPST01700000
KIS_RISERS_PARAMS={}

KIS_FALLERS_PATH=/uapi/domestic-stock/v1/ranking/fluctuation
KIS_FALLERS_TR_ID=FHPST01700000
KIS_FALLERS_PARAMS={}

KIS_INQUIRE_PRICE_PATH=/uapi/domestic-stock/v1/quotations/inquire-price
KIS_INQUIRE_PRICE_TR_ID=FHKST01010100
KIS_INQUIRE_PRICE_MARKET_DIV_CODE=J
KIS_REQUEST_INTERVAL_SECONDS=0.4
MARKET_SNAPSHOT_INTERVAL_MINUTES=60
```

`*_PARAMS`는 JSON object 문자열입니다. 값을 비워두면 코드의 공식 문서 기준 기본 파라미터가 적용되고, 지정한 key만 기본값 위에 merge됩니다.

거래량순위 필수 query key:

```text
FID_COND_MRKT_DIV_CODE
FID_COND_SCR_DIV_CODE
FID_INPUT_ISCD
FID_DIV_CLS_CODE
FID_BLNG_CLS_CODE
FID_TRGT_CLS_CODE
FID_TRGT_EXLS_CLS_CODE
FID_INPUT_PRICE_1
FID_INPUT_PRICE_2
FID_VOL_CNT
```

프로토타입 거래량순위 기본값은 프론트 탐색용으로 `FID_DIV_CLS_CODE=0`(전체)과 `FID_TRGT_EXLS_CLS_CODE=0000000000`(제외 없음)을 사용합니다. 내부 DB의 `stock` 테이블은 일반 주식뿐 아니라 ETF/ETN도 포함할 수 있으며, ETF는 6자리 코드, ETN은 7자리 코드까지 저장합니다.

`/uapi/domestic-stock/v1/quotations/volume-rank`의 `FID_COND_MRKT_DIV_CODE`는 `J`(KRX) 또는 `NX`(NXT)를 사용합니다. `UN`(통합)은 일부 다른 KIS endpoint에서 보이는 값이지만 이 거래량순위 endpoint에서는 `ERROR INVALID FID_COND_MRKT_DIV_CODE`가 발생합니다.

`/api/market/discovery/rankings?type=trading_value`는 같은 KIS 거래량순위 API를 호출하되 `KIS_TRADE_AMOUNT_TOP_PARAMS` 기본값의 `FID_BLNG_CLS_CODE=3`을 사용해 거래금액순 결과를 받습니다. 응답의 `acml_tr_pbmn`을 `trade_amount`로 정규화합니다.

등락률 순위 필수 query key:

```text
fid_rsfl_rate2
fid_cond_mrkt_div_code
fid_cond_scr_div_code
fid_input_iscd
fid_rank_sort_cls_code
fid_input_cnt_1
fid_prc_cls_code
fid_input_price_1
fid_input_price_2
fid_vol_cnt
fid_trgt_cls_code
fid_trgt_exls_cls_code
fid_div_cls_code
fid_rsfl_rate1
```

급상승은 `fid_rank_sort_cls_code=0`, 급하락은 `fid_rank_sort_cls_code=1`을 기본값으로 사용합니다.

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

DB 기반 endpoint는 `DATABASE_URL`이 필요합니다. KIS 프록시 endpoint는 `KIS_APP_KEY`, `KIS_APP_SECRET`, 각 ranking path/TR ID/params가 필요합니다.

## 당일 리더십 수집/계산 테이블

당일 주도 섹터/테마 구현에는 아래 SQL을 적용합니다.

```text
sql/20260606_daily_leadership_snapshots.sql
```

추가 테이블:

```text
public.market_snapshot_batch
public.stock_intraday_snapshot
public.stock_daily_price
public.sector_daily_leadership_snapshot
public.sector_daily_leadership_stock
public.theme_daily_leadership_snapshot
public.theme_daily_leadership_stock
```

현재 앱 코드에서 사용하지 않는 테이블:

```text
public.sector_daily_leadership_snapshot
public.sector_daily_leadership_stock
public.theme_daily_leadership_snapshot
public.theme_daily_leadership_stock
```

삭제된 레거시 테이블:

```text
public.stock_trade_amount_snapshot
```

`public.stock_trade_amount_snapshot`은 구형 거래대금 실험 테이블이었고, 현재 스키마에서는 제거되었습니다. daily leadership 결과 테이블은 현재 API가 on-demand 계산을 사용하므로 아직 읽거나 쓰지 않지만, 향후 계산 결과를 저장할 때 사용할 수 있습니다.

수집 원천 API:

```text
GET /uapi/domestic-stock/v1/quotations/inquire-price
TR_ID: FHKST01010100
```

저장 필드:

```text
stck_prpr    -> price
acml_vol     -> accumulated_volume
acml_tr_pbmn -> accumulated_trade_amount
prdy_ctrt    -> change_rate
```

`snapshot_batch_at`은 배치 기준 시각이고, `observed_at`은 개별 종목의 실제 API 응답 관측 시각입니다.

수동 수집 API:

```text
POST /api/market/intraday-snapshots/run
```

query:

```text
limit: 선택, 수집할 활성 종목 수 제한
dry_run: 선택, true면 KIS 호출만 하고 DB에 저장하지 않음
snapshot_batch_at: 선택, 생략하면 현재 시각을 설정된 스냅샷 간격 단위로 내림
```

초기 검증은 아래처럼 작은 범위부터 실행합니다.

```bash
curl -X POST "http://localhost:8000/api/market/intraday-snapshots/run?limit=5&dry_run=true"
```

전체 수집은 `public.stock`의 활성 종목 전체를 대상으로 하며, `KIS_REQUEST_INTERVAL_SECONDS=0.4` 기준 약 2.5건/초로 호출합니다.

## OAuth 토큰 캐시

프로토타입에서는 KIS OAuth 토큰 발급 제한을 줄이기 위해 `.env`에 토큰을 캐시합니다.

```text
KIS_ACCESS_TOKEN=
KIS_ACCESS_TOKEN_EXPIRES_AT=
KIS_TOKEN_CACHE_ENV_FILE=.env
```

동작 방식:

```text
1. 메모리에 유효한 토큰이 있으면 재사용
2. 없으면 KIS_TOKEN_CACHE_ENV_FILE의 KIS_ACCESS_TOKEN과 KIS_ACCESS_TOKEN_EXPIRES_AT 확인
3. .env 토큰이 아직 유효하면 재사용
4. 토큰이 없거나 만료됐으면 /oauth2/tokenP로 재발급
5. 새 토큰과 만료시각을 .env에 저장
6. API 호출 중 401/403 또는 토큰 만료 응답이 오면 1회 강제 재발급 후 재시도
```

`KIS_ACCESS_TOKEN_EXPIRES_AT`은 ISO datetime 문자열을 사용합니다.

## 테스트

기본 테스트는 외부 API를 호출하지 않습니다.

```bash
.venv/bin/python -m pytest -q
```

실계정 KIS API 통합 테스트는 명시적으로 켠 경우에만 실행합니다.

```bash
RUN_KIS_INTEGRATION_TESTS=1 .venv/bin/python -m pytest -q -m integration
```

통합 테스트는 `.env`의 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_BASE_URL`, KIS 순위 API 설정을 사용합니다.
