# Moneyway Back

한국투자증권 OpenAPI와 PostgreSQL을 사용하는 FastAPI 기반 시장 데이터 백엔드입니다.

현재 주요 기능은 국내 주식 탐색 화면과 주도 섹터/테마 화면에 필요한 데이터를 제공합니다.

## 주요 기능

- 거래량, 거래대금, 급상승, 급하락 종목 조회
- 코스피/코스닥 지수 조회
- 상승/하락 종목 수 집계
- 조회 상위 종목 조회
- 종목 현재가 스냅샷 수집
- 종목 과거 일봉 데이터 수집
- 당일 주도 섹터/테마 계산
- FastAPI API 라우터 제공
- 1시간 단위 스냅샷 수집용 worker script 제공

## 기술 스택

- Python 3.10
- FastAPI
- asyncpg
- httpx
- PostgreSQL
- pytest

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 환경 변수

`.env.example`을 기준으로 `.env`를 생성합니다.

```bash
cp .env.example .env
```

주요 환경 변수:

```text
DATABASE_URL=postgresql://...
KIS_BASE_URL=https://openapi.koreainvestment.com:9443
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCESS_TOKEN=
KIS_ACCESS_TOKEN_EXPIRES_AT=
KIS_REQUEST_INTERVAL_SECONDS=1
MARKET_SNAPSHOT_INTERVAL_MINUTES=60
```

`KIS_ACCESS_TOKEN`은 발급 제한을 고려해 `.env`에 캐시합니다. 기존 토큰이 없거나 유효하지 않으면 재발급 후 `.env`에 저장합니다.

## FastAPI 실행

```bash
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

상태 확인:

```http
GET /health
```

## 주요 API 문서

- 프로젝트 주요 로직 요약: `docs/project-overview.md`
- 탐색/검색 화면 API: `docs/front/find/api.md`
- 플로우 화면 API: `docs/front/flow/api.md`
- 스냅샷 스케줄러 운영 메모: `docs/operations/market-snapshot-scheduler.md`
- DB 및 설계 문서: `docs/db/schema-summary.md`, `docs/backend-api-design.md`

## 스냅샷 수집

주도 섹터/테마 API는 DB에 저장된 최신 종목 현재가 스냅샷을 기준으로 계산합니다.

수동 실행:

```bash
.venv/bin/python scripts/run_market_snapshot.py
```

일부 종목만 테스트:

```bash
.venv/bin/python scripts/run_market_snapshot.py --limit 5 --dry-run
```

요청 간격을 지정해서 실행:

```bash
.venv/bin/python scripts/run_market_snapshot.py --request-interval-seconds 1
```

1시간 단위 최신화는 FastAPI 서버만 실행해서는 동작하지 않습니다. `scripts/run_market_snapshot.py`를 crontab 같은 스케줄러에 등록해야 합니다.
현재 운영 문서는 평일 08:00~20:00 사이 1시간 단위 실행을 기준으로 합니다.
현재가 스냅샷 worker는 두 번째 KIS credential/token 세트인 `KIS_APP_KEY_2`, `KIS_APP_SECRET_2`, `KIS_ACCESS_TOKEN_2`, `KIS_ACCESS_TOKEN_EXPIRES_AT_2`를 사용합니다.

## 과거 일봉 수집

특정일 주도 섹터/테마 계산에 사용할 종목별 일봉 데이터는 별도 worker로 수집합니다.
일봉 수집 worker는 NXT 마스터 파일에 포함된 종목은 `UN`, 그 외 종목은 `J` 시장 구분으로 조회합니다.

```bash
.venv/bin/python scripts/run_stock_daily_prices.py --start-date 2026-06-01 --end-date 2026-06-05
```

일부 종목만 테스트:

```bash
.venv/bin/python scripts/run_stock_daily_prices.py --start-date 2026-06-01 --end-date 2026-06-05 --limit 5 --dry-run
```

요청 간격을 지정해서 실행:

```bash
.venv/bin/python scripts/run_stock_daily_prices.py --start-date 2026-06-01 --end-date 2026-06-05 --request-interval-seconds 1
```

## 테스트

일반 테스트:

```bash
.venv/bin/python -m pytest -q
```

실제 한국투자증권 API를 호출하는 통합 테스트:

```bash
RUN_KIS_INTEGRATION_TESTS=1 .venv/bin/python -m pytest -q -s -m integration
```

통합 테스트는 실계정 키와 토큰을 사용하므로 `.env` 설정이 필요하고, KIS API 유량 제한에 영향을 받을 수 있습니다.

## 프로젝트 구조

```text
app/
  api/            FastAPI router
  core/           환경 설정
  db/             DB pool
  kis/            한국투자증권 OpenAPI client
  repositories/   DB 접근 계층
  schemas/        API schema
  services/       비즈니스 로직
  workers/        배치/스냅샷 worker
scripts/          실행 스크립트
docs/             설계 및 API 문서
tests/            테스트 코드
sql/              DB 변경 SQL
```
