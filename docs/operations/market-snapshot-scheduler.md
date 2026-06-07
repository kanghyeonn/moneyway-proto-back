# Market Snapshot Scheduler Next Steps

주도 섹터/테마 계산에 필요한 종목 현재가 스냅샷 수집 자동화 진행사항입니다.

## 현재 상태

현재 수집 로직은 FastAPI와 분리된 worker로 구현되어 있습니다.

```text
app/workers/market_snapshot_worker.py
scripts/run_market_snapshot.py

app/workers/stock_daily_price_worker.py
scripts/run_stock_daily_prices.py
```

FastAPI에는 수동 트리거 API도 유지되어 있습니다.

```http
POST /api/market/intraday-snapshots/run
```

이 API는 KIS `주식현재가 시세` REST API를 사용해 활성 종목의 현재가, 누적 거래량, 누적 거래대금, 전일 대비 등락률을 수집하고 `public.stock_intraday_snapshot`에 저장합니다.

`scripts/run_market_snapshot.py`로 실행하는 장중 현재가 스냅샷 worker는 별도 KIS credential/token 세트를 사용합니다.

```text
KIS_APP_KEY_2
KIS_APP_SECRET_2
KIS_ACCESS_TOKEN_2
KIS_ACCESS_TOKEN_EXPIRES_AT_2
```

토큰이 없거나 만료되면 `KIS_APP_KEY_2`, `KIS_APP_SECRET_2`로 새 토큰을 발급하고 `.env`의 `KIS_ACCESS_TOKEN_2`, `KIS_ACCESS_TOKEN_EXPIRES_AT_2`에 저장합니다. 다른 KIS API 호출은 기존 `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCESS_TOKEN` 세트를 계속 사용합니다.

주도 섹터/테마 API는 최신 `stock_intraday_snapshot` 배치를 읽어서 계산합니다.

```text
주기적으로 수집 실행
  -> public.stock_intraday_snapshot 저장
  -> /api/market/leadership/* 호출
  -> 최신 snapshot_batch_at 기준으로 당일 주도 섹터/테마 계산
```

중요한 점:

- 현재 주도 섹터/테마는 “최근 30분 변화”가 아니라 “해당 시점까지의 당일 누적값” 기준입니다.
- 현재 운영 계획은 장중 1시간 단위로 현재가 스냅샷 worker를 실행하는 것입니다.
- 30분 단위 실행도 가능하지만, 현재는 KIS 유량 제한과 전체 종목 수집 시간을 고려해 1시간 단위 최신화를 기본으로 둡니다.
- FastAPI 서버를 실행하는 것만으로는 자동 수집이 실행되지 않습니다.
- 과거 일봉 수집도 같은 이유로 FastAPI가 아니라 worker에서 실행합니다. 일봉 수집 결과는 `public.stock_daily_price`에 저장되고, 특정일 주도 섹터/테마 계산의 원천 데이터로 사용합니다.

## 필요한 작업

주기적 최신화를 하려면 worker script를 실행하는 별도 스케줄러가 필요합니다.

## 선택지

### 1. crontab

가장 단순한 방식입니다. 현재 운영 기준은 1시간마다 worker script를 실행하는 것입니다.

상시 1시간마다 실행하는 예시:

```bash
0 * * * * cd /Users/kanghyeon/workspace/moneyway_back && .venv/bin/python scripts/run_market_snapshot.py --request-interval-seconds 1 >> logs/market_snapshot.log 2>&1
```

평일 장 시간대에만 1시간마다 실행하는 예시:

```bash
0 8-15 * * 1-5 cd /Users/kanghyeon/workspace/moneyway_back && .venv/bin/python scripts/run_market_snapshot.py --request-interval-seconds 1 >> logs/market_snapshot.log 2>&1
```

NXT 시작 이후 8시 30분부터 매시간 실행하는 예시:

```bash
30 8-15 * * 1-5 cd /Users/kanghyeon/workspace/moneyway_back && .venv/bin/python scripts/run_market_snapshot.py --request-interval-seconds 1 >> logs/market_snapshot.log 2>&1
```

30분마다 실행하려면 아래처럼 바꿀 수 있지만 현재 기본 운영안은 아닙니다.

```bash
*/30 8-15 * * 1-5 cd /Users/kanghyeon/workspace/moneyway_back && .venv/bin/python scripts/run_market_snapshot.py --request-interval-seconds 1 >> logs/market_snapshot.log 2>&1
```

장점:

- 구현이 빠릅니다.
- FastAPI 서버가 떠 있지 않아도 수집할 수 있습니다.
- API 요청 타임아웃과 무관하게 장시간 수집할 수 있습니다.

주의:

- 공휴일 여부는 cron만으로 판단하기 어렵습니다.
- 실패 로그와 재시도 정책을 별도로 설계해야 합니다.

### 2. 별도 Python batch script

FastAPI HTTP 라우트를 거치지 않고 Python script에서 worker를 실행합니다.

현재 구현:

```text
scripts/run_market_snapshot.py
  -> app/workers/market_snapshot_worker.py
  -> app/services/market_service.py
  -> app/repositories/market_repository.py
  -> app/kis/client.py

scripts/run_stock_daily_prices.py
  -> app/workers/stock_daily_price_worker.py
  -> app/services/market_service.py
  -> app/repositories/market_repository.py
  -> app/kis/client.py
```

장점:

- API 서버와 배치 작업 책임을 분리할 수 있습니다.
- 수집 실패 처리, 거래일 체크, 로깅, 재시도 정책을 코드로 관리하기 쉽습니다.
- 운영 구조로 확장하기 좋습니다.

주의:

- 별도 실행 진입점과 실행 환경 설정이 필요합니다.

### 3. FastAPI 내부 scheduler

`APScheduler` 같은 라이브러리를 FastAPI lifespan에 붙여 서버 내부에서 주기 실행합니다.

장점:

- 프로토타입에서는 빠르게 붙일 수 있습니다.
- 별도 cron 설정 없이 앱 코드 안에서 스케줄을 관리할 수 있습니다.

주의:

- 운영에서 FastAPI 프로세스가 여러 개 뜨면 같은 수집 작업이 중복 실행될 수 있습니다.
- API 서버와 배치 실행 책임이 섞입니다.

## 권장 방향

프로토타입 단계에서는 `scripts/run_market_snapshot.py`를 `crontab`에 등록하는 방식으로 시작합니다.

전체 종목 수집은 KIS 유량 제한, 거래일/장 시간, 실패 재시도 처리가 중요하므로 FastAPI 내부 scheduler나 API curl 호출보다 별도 worker script 방식이 적절합니다.

권장 순서:

1. `crontab`으로 1시간 단위 worker script 실행을 자동화합니다.
2. 수집 로그와 실패 종목 로그를 파일 또는 DB에 남깁니다.
3. 거래일/공휴일/장 시간 체크 로직을 추가합니다.
4. 필요하면 `market_snapshot_batch`의 상태를 모니터링하는 운영 API나 관리자 화면을 추가합니다.

## 다음 구현 후보

### A. crontab용 실행 명령 정리

환경별 프로젝트 경로와 로그 경로를 정합니다.

```text
local project: /Users/kanghyeon/workspace/moneyway_back
local log:     logs/market_snapshot.log
```

기본 실행:

```bash
cd /Users/kanghyeon/workspace/moneyway_back
.venv/bin/python scripts/run_market_snapshot.py
```

초기 검증용:

```bash
.venv/bin/python scripts/run_market_snapshot.py --limit 5 --dry-run
```

일봉 수집:

```bash
.venv/bin/python scripts/run_stock_daily_prices.py --start-date 2026-06-01 --end-date 2026-06-05
```

일봉 수집 초기 검증용:

```bash
.venv/bin/python scripts/run_stock_daily_prices.py --start-date 2026-06-01 --end-date 2026-06-05 --limit 5 --dry-run
```

### B. worker/script 구조

구현 파일:

```text
app/workers/market_snapshot_worker.py
scripts/run_market_snapshot.py
app/workers/stock_daily_price_worker.py
scripts/run_stock_daily_prices.py
```

역할:

- `app/workers/market_snapshot_worker.py`
  - 설정 로드
  - DB pool 초기화
  - DB advisory lock 기반 중복 실행 방지
  - `KisClient`, `MarketRepository`, `MarketService` 생성
  - `run_intraday_snapshot()` 실행
- `scripts/run_market_snapshot.py`
  - CLI argument parsing
  - 진행상황 출력
  - 결과 JSON 출력
  - 실패 시 non-zero exit code 반환
- `app/workers/stock_daily_price_worker.py`
  - 설정 로드
  - DB pool 초기화
  - DB advisory lock 기반 중복 실행 방지
  - `KisClient`, `MarketRepository`, `MarketService` 생성
  - `run_daily_price_collection()` 실행
- `scripts/run_stock_daily_prices.py`
  - 조회 시작일/종료일 argument parsing
  - 진행상황 출력
  - 결과 JSON 출력
  - 실패 시 non-zero exit code 반환

### C. 거래일/장 시간 체크

초기 기준:

```text
weekday: 월-금
time: 08:00-15:30 KST
```

추후 보강:

- 한국거래소 휴장일 캘린더
- NXT/정규장 구분
- 장 마감 후 마지막 스냅샷 1회 수집 여부

### D. 스케줄 실행 중복 방지

중복 실행을 막기 위해 아래 중 하나를 고려합니다.

- DB advisory lock. 현재 worker에 구현되어 있습니다.
- `market_snapshot_batch.snapshot_batch_at` unique 제약 활용
- batch status가 `running`인 동일 배치가 있으면 skip

## 현재 관련 설정

```text
MARKET_SNAPSHOT_INTERVAL_MINUTES=60
KIS_REQUEST_INTERVAL_SECONDS=1
KIS_APP_KEY_2=...
KIS_APP_SECRET_2=...
KIS_ACCESS_TOKEN_2=...
KIS_ACCESS_TOKEN_EXPIRES_AT_2=...
DATABASE_URL=postgresql://...
```

`KIS_REQUEST_INTERVAL_SECONDS`는 KIS 유량 제한을 피하기 위한 종목별 요청 간격입니다.

## 완료 기준

주기 실행 자동화의 1차 완료 기준:

- 장 시간대에 설정한 주기대로 수집이 실행됩니다.
- `market_snapshot_batch`에 배치 상태가 기록됩니다.
- `stock_intraday_snapshot`에 해당 배치의 종목별 스냅샷이 저장됩니다.
- `/api/market/leadership/status`와 `/api/market/leadership/*`가 최신 배치를 기준으로 응답합니다.
- 수집 실패 종목과 실패 사유를 확인할 수 있습니다.
