# Auth API

로그인, 회원가입 화면에서 사용하는 인증 API 명세입니다.

Base URL:

```text
/api/auth
```

## 공통 규칙

- 모든 시각은 ISO 8601 datetime 문자열입니다.
- 인증이 필요한 API는 `Authorization: Bearer <access_token>` 헤더를 사용합니다.
- `access_token`은 API 호출용 짧은 만료 토큰입니다.
- `refresh_token`은 자동 로그인과 토큰 재발급용 긴 만료 토큰입니다. 앱 secure storage에 저장합니다.
- 백엔드는 refresh token 원문을 저장하지 않고 hash만 DB에 저장합니다.
- 에러는 기본적으로 `{ "detail": "..." }` 형태로 응답합니다.

공통 인증 응답:

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "phone_number": "01012345678",
    "name": "홍길동",
    "profile_image_url": null,
    "status": "active",
    "marketing_agreed": false,
    "created_at": "2026-06-08T10:00:00.000000+09:00"
  },
  "tokens": {
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "token_type": "Bearer",
    "expires_in": 1800
  }
}
```

공통 사용자 필드:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `id` | number | 사용자 ID |
| `email` | string \| null | 이메일 |
| `phone_number` | string \| null | 휴대폰 번호 |
| `name` | string \| null | 사용자 이름 |
| `profile_image_url` | string \| null | 프로필 이미지 URL |
| `status` | string | `active`, `inactive`, `blocked`, `deleted` |
| `marketing_agreed` | boolean | 마케팅 수신 동의 여부 |
| `created_at` | datetime | 가입 시각 |

공통 토큰 필드:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `access_token` | string | API 호출용 Bearer token |
| `refresh_token` | string | 자동 로그인/재발급용 token |
| `token_type` | string | 현재 `Bearer` |
| `expires_in` | number | access token 만료까지 남은 초 |

## 1. 회원가입

이메일 또는 휴대폰 번호와 비밀번호로 회원가입합니다.

```http
POST /api/auth/signup
```

Request:

```json
{
  "email": "user@example.com",
  "phone_number": "01012345678",
  "password": "password123",
  "name": "홍길동",
  "marketing_agreed": false,
  "phone_verification_code": "123456",
  "device_id": "expo-device-id"
}
```

필드:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `email` | string | no | 이메일. `email` 또는 `phone_number` 중 하나는 필수 |
| `phone_number` | string | no | 휴대폰 번호. 입력 시 휴대폰 인증 필요 |
| `password` | string | yes | 비밀번호. 최소 8자 |
| `name` | string | no | 사용자 이름 |
| `marketing_agreed` | boolean | no | 마케팅 수신 동의. 기본 `false` |
| `phone_verification_code` | string | no | 휴대폰 인증번호. `phone_number` 회원가입 시 필요 |
| `device_id` | string | no | 앱 기기 식별자 |

Response:

```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "phone_number": "01012345678",
    "name": "홍길동",
    "profile_image_url": null,
    "status": "active",
    "marketing_agreed": false,
    "created_at": "2026-06-08T10:00:00.000000+09:00"
  },
  "tokens": {
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "token_type": "Bearer",
    "expires_in": 1800
  }
}
```

주의:

- 휴대폰 번호로 가입하는 경우 `POST /api/auth/phone-verifications`와 `POST /api/auth/phone-verifications/confirm`을 먼저 호출하거나, `phone_verification_code`를 회원가입 요청에 함께 보낼 수 있습니다.
- 이미 가입된 이메일 또는 휴대폰 번호는 `409`로 응답합니다.

## 2. 로그인

이메일 또는 휴대폰 번호와 비밀번호로 로그인합니다.

```http
POST /api/auth/login
```

Request:

```json
{
  "identifier": "user@example.com",
  "password": "password123",
  "device_id": "expo-device-id"
}
```

필드:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `identifier` | string | yes | 이메일 또는 휴대폰 번호 |
| `password` | string | yes | 비밀번호 |
| `device_id` | string | no | 앱 기기 식별자 |

Response는 회원가입과 같은 공통 인증 응답입니다.

## 3. Google 로그인

프론트에서 Google 로그인 후 받은 Google ID token을 백엔드로 전달합니다. 백엔드는 Google token을 검증하고 Moneyway access token과 refresh token을 발급합니다.

```http
POST /api/auth/oauth/google
```

Request:

```json
{
  "id_token": "google-id-token",
  "device_id": "expo-device-id",
  "marketing_agreed": false
}
```

필드:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `id_token` | string | yes | Google OAuth ID token |
| `device_id` | string | no | 앱 기기 식별자 |
| `marketing_agreed` | boolean | no | 최초 가입 시 마케팅 수신 동의. 기본 `false` |

Response는 회원가입과 같은 공통 인증 응답입니다.

주의:

- 프론트는 Google access token이 아니라 ID token을 전달해야 합니다.
- `GOOGLE_OAUTH_CLIENT_ID`가 서버에 설정되어 있으면 token의 audience가 해당 client id와 일치해야 합니다.
- Apple 로그인은 추후 같은 패턴으로 `/api/auth/oauth/apple`을 추가할 예정입니다.

## 4. 토큰 재발급

refresh token으로 새 access token과 새 refresh token을 발급합니다. 기존 refresh token은 폐기됩니다.

```http
POST /api/auth/refresh
```

Request:

```json
{
  "refresh_token": "refresh-token",
  "device_id": "expo-device-id"
}
```

필드:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `refresh_token` | string | yes | 기존 refresh token |
| `device_id` | string | no | 앱 기기 식별자 |

Response는 회원가입과 같은 공통 인증 응답입니다.

프론트 처리:

- API 호출이 `401`이면 먼저 `/api/auth/refresh`를 호출합니다.
- refresh 성공 시 저장된 access token과 refresh token을 모두 교체합니다.
- refresh 실패 시 저장된 토큰을 삭제하고 로그인 화면으로 이동합니다.

## 5. 로그아웃

refresh token을 폐기합니다.

```http
POST /api/auth/logout
```

Request:

```json
{
  "refresh_token": "refresh-token"
}
```

Response:

```json
{
  "revoked": true
}
```

필드:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `revoked` | boolean | 서버에서 refresh token이 폐기됐는지 여부 |

프론트는 응답 성공 여부와 관계없이 로컬에 저장된 access token과 refresh token을 삭제하는 것을 권장합니다.

## 6. 현재 사용자 조회

저장된 access token이 유효한지 확인하고 현재 사용자 정보를 조회합니다.

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

Response:

```json
{
  "id": 1,
  "email": "user@example.com",
  "phone_number": "01012345678",
  "name": "홍길동",
  "profile_image_url": null,
  "status": "active",
  "marketing_agreed": false,
  "created_at": "2026-06-08T10:00:00.000000+09:00"
}
```

프론트 사용처:

- 앱 시작 시 자동 로그인 상태 확인
- 프로필/마이페이지 진입 전 사용자 정보 확인

## 7. 휴대폰 인증번호 요청

회원가입 또는 비밀번호 재설정용 휴대폰 인증번호를 생성합니다.

```http
POST /api/auth/phone-verifications
```

Request:

```json
{
  "phone_number": "01012345678",
  "purpose": "signup"
}
```

필드:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `phone_number` | string | yes | 휴대폰 번호 |
| `purpose` | string | no | `signup`, `password_reset`. 기본 `signup` |

Response:

```json
{
  "phone_number": "01012345678",
  "purpose": "signup",
  "expires_at": "2026-06-08T10:05:00.000000+09:00",
  "development_code": null
}
```

필드:

| 이름 | 타입 | 설명 |
| --- | --- | --- |
| `phone_number` | string | 휴대폰 번호 |
| `purpose` | string | 인증 목적 |
| `expires_at` | datetime | 인증번호 만료 시각 |
| `development_code` | string \| null | 로컬 개발용 인증번호. 서버 `AUTH_EXPOSE_DEV_CODES=1`일 때만 반환 |

주의:

- 현재 SMS 발송 provider는 아직 연결되어 있지 않습니다.
- 실제 서비스 환경에서는 `development_code`를 노출하지 않습니다.

## 8. 휴대폰 인증번호 확인

사용자가 입력한 휴대폰 인증번호를 확인합니다.

```http
POST /api/auth/phone-verifications/confirm
```

Request:

```json
{
  "phone_number": "01012345678",
  "purpose": "signup",
  "code": "123456"
}
```

필드:

| 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `phone_number` | string | yes | 휴대폰 번호 |
| `purpose` | string | no | `signup`, `password_reset`. 기본 `signup` |
| `code` | string | yes | 사용자가 입력한 인증번호 |

Response:

```json
{
  "verified": true
}
```

## 에러 응답

| HTTP status | 상황 | 예시 |
| --- | --- | --- |
| `400` | 요청 값이 부족하거나 휴대폰 인증이 되지 않음 | `{ "detail": "phone_number is not verified" }` |
| `401` | 로그인 실패, 잘못된 token, 잘못된 인증번호 | `{ "detail": "invalid identifier or password" }` |
| `409` | 이미 가입된 이메일 또는 휴대폰 번호 | `{ "detail": "email or phone_number already exists" }` |
| `422` | request body validation 실패 | FastAPI 기본 validation error |
| `503` | DB 설정 누락 또는 외부 Google token 검증 실패 등 서버 의존성 오류 | `{ "detail": "..." }` |

## 프론트 권장 플로우

회원가입:

```text
휴대폰 번호 입력
  -> POST /api/auth/phone-verifications
  -> 인증번호 입력
  -> POST /api/auth/phone-verifications/confirm
  -> POST /api/auth/signup
  -> access_token / refresh_token 저장
```

로그인:

```text
identifier/password 입력
  -> POST /api/auth/login
  -> access_token / refresh_token 저장
```

Google 로그인:

```text
Expo Google login
  -> Google ID token 획득
  -> POST /api/auth/oauth/google
  -> access_token / refresh_token 저장
```

자동 로그인:

```text
앱 시작
  -> 저장된 access_token으로 GET /api/auth/me
  -> 401이면 POST /api/auth/refresh
  -> refresh 성공 시 token 교체 후 진입
  -> refresh 실패 시 token 삭제 후 로그인 화면
```
