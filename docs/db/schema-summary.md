# Schema Summary

moneyway-proto PostgreSQL 스키마 요약 문서입니다.

## Database

| 항목 | 값 |
| --- | --- |
| Database | `moneyway-proto` |
| Schema | `public` |

## Tables

```text
public.stock
public.sector
public.stock_sector
public.theme
public.stock_theme
public.market_snapshot_batch
public.stock_intraday_snapshot
public.stock_daily_price
public.users
public.user_password_credentials
public.user_oauth_accounts
public.auth_refresh_tokens
public.phone_verification_codes
public.sector_daily_leadership_snapshot
public.sector_daily_leadership_stock
public.theme_daily_leadership_snapshot
public.theme_daily_leadership_stock
```

## Entity Relationship

```text
public.stock
  1 ── N public.stock_intraday_snapshot
  1 ── N public.stock_daily_price

public.users
  1 ── 1 public.user_password_credentials
  1 ── N public.user_oauth_accounts
  1 ── N public.auth_refresh_tokens

public.sector
  1 ── N public.sector_daily_leadership_snapshot

public.theme
  1 ── N public.theme_daily_leadership_snapshot

public.sector_daily_leadership_snapshot
  1 ── N public.sector_daily_leadership_stock

public.theme_daily_leadership_snapshot
  1 ── N public.theme_daily_leadership_stock

public.stock
  N ── N public.sector
        via public.stock_sector

public.stock
  N ── N public.theme
        via public.stock_theme
```

## Authentication Tables

로그인/회원가입 최소 구성은 아래 SQL로 생성합니다.

```text
sql/20260608_auth_minimum_tables.sql
```

현재 화면 기준으로 지원해야 하는 인증 흐름:

- 이메일 또는 휴대폰 번호 + 비밀번호 로그인
- Google 회원가입/로그인
- 자동 로그인용 refresh token
- 휴대폰 번호 인증
- Apple 회원가입/로그인은 추후 `user_oauth_accounts.provider='apple'`로 확장

### `public.users`

서비스 사용자 본체 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `email` | `VARCHAR(255)` | NULL 가능, 소문자 기준 unique index |
| `phone_number` | `VARCHAR(32)` | NULL 가능, unique index |
| `name` | `VARCHAR(80)` | 사용자 이름 |
| `profile_image_url` | `TEXT` | 소셜 프로필 이미지 등 |
| `status` | `VARCHAR(32)` | `active`, `inactive`, `blocked`, `deleted` |
| `marketing_agreed` | `BOOLEAN` | 마케팅 수신 동의 여부 |
| `last_login_at` | `TIMESTAMPTZ` | 마지막 로그인 시각 |
| `created_at` | `TIMESTAMPTZ` | 생성 시각 |
| `updated_at` | `TIMESTAMPTZ` | 수정 시각 |

제약:

```text
email IS NOT NULL OR phone_number IS NOT NULL
```

### `public.user_password_credentials`

일반 비밀번호 로그인용 credential 테이블입니다. 비밀번호 원문은 저장하지 않고 hash만 저장합니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `user_id` | `BIGINT` | PK, FK -> `public.users(id)` |
| `password_hash` | `TEXT` | bcrypt/argon2 등으로 해시한 비밀번호 |
| `password_updated_at` | `TIMESTAMPTZ` | 비밀번호 변경 시각 |
| `failed_login_count` | `INTEGER` | 실패 횟수 |
| `locked_until` | `TIMESTAMPTZ` | 임시 잠금 해제 시각 |
| `created_at` | `TIMESTAMPTZ` | 생성 시각 |

### `public.user_oauth_accounts`

Google 로그인/회원가입 및 추후 Apple 로그인을 위한 외부 계정 연결 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `user_id` | `BIGINT` | FK -> `public.users(id)` |
| `provider` | `VARCHAR(32)` | `google`, `apple` |
| `provider_user_id` | `VARCHAR(255)` | Google/Apple의 고유 사용자 식별자. Google은 ID token의 `sub` |
| `email` | `VARCHAR(255)` | provider에서 받은 이메일 |
| `email_verified` | `BOOLEAN` | provider 기준 이메일 검증 여부 |
| `raw_profile` | `JSONB` | provider profile 원문 일부 |
| `created_at` | `TIMESTAMPTZ` | 생성 시각 |
| `updated_at` | `TIMESTAMPTZ` | 수정 시각 |

기본 중복 방지:

```text
UNIQUE (provider, provider_user_id)
```

Google 로그인 성공 후에는 Google token을 서비스 API 인증에 직접 쓰지 않고, 백엔드가 Moneyway access token과 refresh token을 발급합니다. DB에는 refresh token의 hash만 저장합니다.

### `public.auth_refresh_tokens`

자동 로그인과 access token 재발급을 위한 refresh token 저장 테이블입니다. refresh token 원문은 저장하지 않고 hash만 저장합니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `user_id` | `BIGINT` | FK -> `public.users(id)` |
| `token_hash` | `TEXT` | UNIQUE, refresh token hash |
| `device_id` | `VARCHAR(255)` | 앱 디바이스 식별자 |
| `user_agent` | `TEXT` | 클라이언트 user agent |
| `ip_address` | `INET` | 발급 IP |
| `expires_at` | `TIMESTAMPTZ` | 만료 시각 |
| `revoked_at` | `TIMESTAMPTZ` | 폐기 시각 |
| `created_at` | `TIMESTAMPTZ` | 생성 시각 |

### `public.phone_verification_codes`

회원가입 화면의 휴대폰 인증번호 발급/검증용 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `phone_number` | `VARCHAR(32)` | 인증 대상 휴대폰 번호 |
| `code_hash` | `TEXT` | 인증번호 hash |
| `purpose` | `VARCHAR(32)` | `signup`, `password_reset` |
| `expires_at` | `TIMESTAMPTZ` | 만료 시각 |
| `verified_at` | `TIMESTAMPTZ` | 검증 완료 시각 |
| `attempt_count` | `INTEGER` | 검증 시도 횟수 |
| `created_at` | `TIMESTAMPTZ` | 생성 시각 |

### 추가 권장 테이블

초기 최소 구현에는 포함하지 않았지만, 기능을 확장할 때 추가하면 좋은 테이블입니다.

| 테이블 | 용도 | 추가 시점 |
| --- | --- | --- |
| `public.password_reset_tokens` | 비밀번호 찾기/재설정 링크 또는 코드 관리 | 비밀번호 찾기 기능 구현 시 |
| `public.terms` | 이용약관, 개인정보 처리방침, 마케팅 동의 문서 버전 관리 | 약관 버전 이력이 필요할 때 |
| `public.user_terms_agreements` | 사용자별 약관 동의 이력 | 약관 동의 감사/이력 보존이 필요할 때 |
| `public.user_login_events` | 로그인 성공/실패 이력, 보안 감사 | 보안 모니터링이 필요할 때 |
| `public.user_devices` | 사용자 기기 관리, 기기별 로그아웃 | 멀티 디바이스 관리가 필요할 때 |

## `public.stock`

주식/ETF/ETN 종목 기본 정보 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `short_code` | `VARCHAR(7)` | UNIQUE, `^[0-9A-Z]{6,7}$` |
| `name` | `VARCHAR(120)` | NOT NULL, 종목약명 |
| `market` | `VARCHAR(32)` | NOT NULL, 시장구분 |
| `stock_type` | `VARCHAR(32)` | NOT NULL, 주식종류 또는 상품유형 (`보통주`, `구형우선주`, `신형우선주`, `종류주권`, `ETF`, `ETN` 등) |
| `listed_at` | `DATE` | 상장일 |
| `is_active` | `BOOLEAN` | NOT NULL, default `true` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

인덱스:

```text
stock_short_code_unique
stock_market_idx
stock_stock_type_idx
stock_active_market_idx
```

## `public.sector`

토스 기반 기본 섹터/카테고리 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `name` | `VARCHAR(120)` | UNIQUE, NOT NULL |
| `source` | `VARCHAR(32)` | NOT NULL, default `toss` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

## `public.stock_sector`

종목과 섹터의 다대다 관계 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `stock_id` | `BIGINT` | PK, FK -> `public.stock(id)` |
| `sector_id` | `BIGINT` | PK, FK -> `public.sector(id)` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

기본 키:

```text
(stock_id, sector_id)
```

인덱스:

```text
stock_sector_sector_id_idx
```

## `public.theme`

주달 기반 테마 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `name` | `VARCHAR(120)` | UNIQUE, NOT NULL |
| `description` | `TEXT` | NULL 가능 |
| `source` | `VARCHAR(32)` | NOT NULL, default `judal` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

## `public.stock_theme`

종목과 테마의 다대다 관계 테이블입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `stock_id` | `BIGINT` | PK, FK -> `public.stock(id)` |
| `theme_id` | `BIGINT` | PK, FK -> `public.theme(id)` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

기본 키:

```text
(stock_id, theme_id)
```

인덱스:

```text
stock_theme_theme_id_idx
```

## `public.market_snapshot_batch`

전체 종목 현재가 수집 배치의 상태를 기록합니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `snapshot_batch_at` | `TIMESTAMPTZ` | UNIQUE, 배치 기준 시각 |
| `interval_minutes` | `INTEGER` | NOT NULL, default `30`, `> 0` |
| `status` | `VARCHAR(32)` | NOT NULL, `running`, `completed`, `partial`, `failed` |
| `target_stock_count` | `INTEGER` | NOT NULL, 수집 대상 종목 수 |
| `success_stock_count` | `INTEGER` | NOT NULL, 수집 성공 종목 수 |
| `failed_stock_count` | `INTEGER` | NOT NULL, 수집 실패 종목 수 |
| `started_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |
| `finished_at` | `TIMESTAMPTZ` | 완료 시각 |
| `error_message` | `TEXT` | 실패/부분 실패 사유 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

인덱스:

```text
market_snapshot_batch_time_idx
market_snapshot_batch_status_idx
```

## `public.stock_intraday_snapshot`

종목별 장중 현재가 스냅샷입니다. 당일 주도 섹터/테마 계산의 원천입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `stock_id` | `BIGINT` | FK -> `public.stock(id)` |
| `snapshot_batch_at` | `TIMESTAMPTZ` | NOT NULL, 배치 기준 시각 |
| `observed_at` | `TIMESTAMPTZ` | NOT NULL, 실제 API 응답 관측 시각 |
| `price` | `NUMERIC(18, 2)` | NOT NULL, 현재가, `>= 0` |
| `accumulated_volume` | `BIGINT` | NOT NULL, 누적 거래량, `>= 0` |
| `accumulated_trade_amount` | `NUMERIC(24, 2)` | NOT NULL, 누적 거래대금, `>= 0` |
| `change_rate` | `NUMERIC(10, 4)` | 전일 대비율 |
| `source` | `VARCHAR(32)` | NOT NULL, default `kis_inquire_price` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

기본 중복 방지:

```text
UNIQUE (stock_id, snapshot_batch_at)
```

인덱스:

```text
stock_intraday_snapshot_batch_idx
stock_intraday_snapshot_stock_batch_idx
stock_intraday_snapshot_amount_idx
stock_intraday_snapshot_observed_idx
```

## `public.stock_daily_price`

종목별 과거 일봉 원천 데이터입니다. 한국투자증권 `국내주식기간별시세(일/주/월/년)` API의 일봉 데이터를 저장해 특정일의 주도 섹터/테마를 계산할 때 사용합니다.

적용 SQL:

```text
sql/20260607_stock_daily_price.sql
```

원천 API:

```text
GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
TR_ID: FHKST03010100
```

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `stock_id` | `BIGINT` | FK -> `public.stock(id)` |
| `trading_date` | `DATE` | NOT NULL, 거래일 |
| `open_price` | `NUMERIC(18, 2)` | NOT NULL, 시가, `>= 0` |
| `high_price` | `NUMERIC(18, 2)` | NOT NULL, 고가, `>= 0` |
| `low_price` | `NUMERIC(18, 2)` | NOT NULL, 저가, `>= 0` |
| `close_price` | `NUMERIC(18, 2)` | NOT NULL, 종가, `>= 0` |
| `accumulated_volume` | `BIGINT` | NOT NULL, 누적 거래량, `>= 0` |
| `accumulated_trade_amount` | `NUMERIC(24, 2)` | NOT NULL, 누적 거래대금, `>= 0` |
| `change_amount` | `NUMERIC(18, 2)` | 전일 대비 금액 |
| `change_rate` | `NUMERIC(10, 4)` | 전일 대비율 |
| `source` | `VARCHAR(64)` | NOT NULL, default `kis_inquire_daily_itemchartprice` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

기본 중복 방지:

```text
UNIQUE (stock_id, trading_date)
```

인덱스:

```text
stock_daily_price_date_idx
stock_daily_price_stock_date_idx
stock_daily_price_trade_amount_idx
```

## `public.sector_daily_leadership_snapshot`

섹터별 당일 주도 점수 계산 결과입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `id` | `BIGINT` | PK, identity |
| `snapshot_batch_at` | `TIMESTAMPTZ` | NOT NULL, 계산 기준 배치 시각 |
| `trading_date` | `DATE` | NOT NULL, 거래일 |
| `sector_id` | `BIGINT` | FK -> `public.sector(id)` |
| `side` | `VARCHAR(16)` | NOT NULL, `bullish` 또는 `bearish` |
| `score` | `NUMERIC(24, 8)` | NOT NULL, 주도 점수 |
| `trade_amount` | `NUMERIC(24, 2)` | NOT NULL, 당일 누적 거래대금 |
| `weighted_change_rate` | `NUMERIC(12, 8)` | 거래대금 가중 전일 대비 수익률 |
| `advance_ratio` | `NUMERIC(8, 6)` | 상승 종목 비율 |
| `up_trade_amount_ratio` | `NUMERIC(8, 6)` | 상승 종목 거래대금 비율 |
| `decline_ratio` | `NUMERIC(8, 6)` | 하락 종목 비율 |
| `down_trade_amount_ratio` | `NUMERIC(8, 6)` | 하락 종목 거래대금 비율 |
| `stock_count` | `INTEGER` | NOT NULL, 계산 포함 종목 수 |
| `top1_trade_amount_share` | `NUMERIC(8, 6)` | 1위 종목 거래대금 집중도 |
| `concentration_penalty` | `NUMERIC(8, 6)` | 대형주 쏠림 보정 계수 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` |

기본 중복 방지:

```text
UNIQUE (snapshot_batch_at, sector_id, side)
```

## `public.theme_daily_leadership_snapshot`

테마별 당일 주도 점수 계산 결과입니다. 컬럼 구조는 `public.sector_daily_leadership_snapshot`과 같고 `theme_id`가 `public.theme(id)`를 참조합니다.

기본 중복 방지:

```text
UNIQUE (snapshot_batch_at, theme_id, side)
```

## `public.sector_daily_leadership_stock`

섹터 주도 점수에 기여한 종목별 구성 데이터입니다.

| 컬럼 | 타입 | 제약/설명 |
| --- | --- | --- |
| `sector_daily_leadership_snapshot_id` | `BIGINT` | PK, FK -> `public.sector_daily_leadership_snapshot(id)` |
| `stock_id` | `BIGINT` | PK, FK -> `public.stock(id)` |
| `trade_amount` | `NUMERIC(24, 2)` | NOT NULL, 당일 누적 거래대금 |
| `change_rate` | `NUMERIC(12, 8)` | 전일 대비 수익률 |
| `contribution_ratio` | `NUMERIC(8, 6)` | 해당 섹터 점수 내 기여 비중 |

## `public.theme_daily_leadership_stock`

테마 주도 점수에 기여한 종목별 구성 데이터입니다. 컬럼 구조는 `public.sector_daily_leadership_stock`과 같고 `theme_daily_leadership_snapshot_id`가 `public.theme_daily_leadership_snapshot(id)`를 참조합니다.

## Triggers

`public.stock`, `public.sector`, `public.theme`, `public.stock_daily_price`, `public.users`, `public.user_oauth_accounts`는 update 시 `updated_at`을 자동 갱신합니다.

공용 함수:

```text
public.set_updated_at()
```

일봉 전용 함수:

```text
public.set_stock_daily_price_updated_at()
```

인증 전용 함수:

```text
public.set_auth_updated_at()
```

트리거:

```text
set_stock_updated_at
set_sector_updated_at
set_theme_updated_at
set_stock_daily_price_updated_at
set_users_updated_at
set_user_oauth_accounts_updated_at
```

## Source Data Mapping

| 원천 데이터 | 대상 테이블 |
| --- | --- |
| `data/data_0950_20260603.csv` | `public.stock` |
| `data/kospi_code.mst` (`EF`, `EN`) | `public.stock` ETF/ETN |
| `data/toss_sector.json` | `public.sector`, `public.stock_sector` |
| `data/judal_common.json` | `public.theme`, `public.stock_theme` |
| KIS `주식현재가 시세` REST | `public.stock_intraday_snapshot` |
| KIS `국내주식기간별시세(일/주/월/년)` REST | `public.stock_daily_price` |
| 로그인/회원가입 API | `public.users`, `public.user_password_credentials`, `public.user_oauth_accounts`, `public.auth_refresh_tokens`, `public.phone_verification_codes` |
| 당일 섹터/테마 계산 결과 | `public.sector_daily_leadership_snapshot`, `public.theme_daily_leadership_snapshot` |

## Notes

- `sector`는 토스 기반 기본 섹터/업종성 분류입니다.
- `theme`은 주달 기반 테마/이슈성 분류입니다.
- `sector`와 `theme`은 앱에서 다르게 사용할 수 있도록 분리합니다.
- JSON 종목코드는 `A005930` 형식이고, DB의 `stock.short_code`는 `005930` 형식입니다.
- ETF 코드는 `0000D0`처럼 6자리, ETN 코드는 `Q500061`처럼 7자리까지 저장합니다.
- ETF/ETN은 `public.stock.stock_type`을 각각 `ETF`, `ETN`으로 저장합니다.
- 당일 주도 섹터/테마는 최신 `stock_intraday_snapshot`의 `accumulated_trade_amount`와 `change_rate`를 함께 사용합니다.
- 최신 스냅샷 하나만 있으면 당일 주도 섹터/테마를 계산할 수 있습니다.
- 특정일 주도 섹터/테마는 `stock_daily_price`의 `trading_date` 기준 일봉 데이터를 `stock_sector`, `stock_theme`과 조인해 계산할 수 있습니다.

## Currently Unused Tables

현재 앱 코드에서 읽거나 쓰지 않는 테이블입니다.

| 테이블 | 상태 | 판단 |
| --- | --- | --- |
| `public.sector_daily_leadership_snapshot` | 향후 사용 | 계산 결과 저장용 테이블입니다. 현재 API는 `stock_intraday_snapshot`에서 on-demand로 계산합니다. |
| `public.sector_daily_leadership_stock` | 향후 사용 | 저장된 섹터 리더십 결과의 구성 종목 테이블입니다. |
| `public.theme_daily_leadership_snapshot` | 향후 사용 | 계산 결과 저장용 테이블입니다. 현재 API는 `stock_intraday_snapshot`에서 on-demand로 계산합니다. |
| `public.theme_daily_leadership_stock` | 향후 사용 | 저장된 테마 리더십 결과의 구성 종목 테이블입니다. |

삭제된 레거시 테이블:

```text
public.stock_trade_amount_snapshot
```

`stock_trade_amount_snapshot`은 구형 실시간 거래대금 실험 테이블이었고, 현재 당일 주도 섹터/테마 계산은 `stock_intraday_snapshot`을 사용합니다. daily leadership 결과 테이블은 배치 계산 결과를 영속화하기 전까지는 미사용 상태로 두거나, 실제 저장 로직을 구현할 때 사용합니다.
