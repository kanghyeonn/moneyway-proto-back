# Auth Future Work

로그인/회원가입 기능에서 현재 미구현 상태이거나 운영 전에 보강해야 할 항목입니다.

## 현재 구현된 범위

- 이메일 또는 휴대폰 번호 + 비밀번호 회원가입
- 이메일 또는 휴대폰 번호 + 비밀번호 로그인
- Google ID token 기반 회원가입/로그인
- Moneyway access token 발급
- Moneyway refresh token 발급 및 DB hash 저장
- refresh token 회전
- 로그아웃 시 refresh token 폐기
- access token 기반 현재 사용자 조회
- 휴대폰 인증번호 생성, DB 저장, 만료시간 저장
- 휴대폰 인증번호 확인 및 `verified_at` 저장

## 1. SMS 발송 연동

현재 휴대폰 인증번호는 DB에 저장되지만 실제 문자 발송은 하지 않습니다.

추후 구현:

- SMS provider 선정
- 인증번호 문자 발송
- 발송 성공/실패 처리
- provider 장애 시 에러 응답 정책
- 발송 요청/응답 로그 저장

후보 provider:

| Provider | 비고 |
| --- | --- |
| Solapi/Nurigo | 국내 서비스에서 많이 사용 |
| AWS SNS | AWS 인프라 사용 시 검토 가능 |
| Toast/NHN Cloud SMS | 국내 발송 운영 검토 가능 |

## 2. 인증번호 재요청 제한

현재는 같은 휴대폰 번호로 인증번호를 반복 요청할 수 있습니다.

추후 구현:

- 같은 번호 기준 재요청 최소 간격 적용
- 예: 60초 이내 재요청 차단
- 일정 시간 내 최대 발송 횟수 제한
- 예: 10분 내 5회, 1일 20회
- 제한 초과 시 `429 Too Many Requests` 반환

예상 응답:

```json
{
  "detail": "too many verification requests"
}
```

## 3. 인증번호 입력 시도 제한

현재 `attempt_count`는 증가하지만, 시도 횟수 제한 정책은 적용하지 않습니다.

추후 구현:

- 인증번호 5회 오입력 시 해당 인증번호 만료 처리
- 일정 시간 동안 같은 번호 인증 제한
- 제한 초과 시 `429 Too Many Requests` 또는 `401` 반환

예상 응답:

```json
{
  "detail": "too many verification attempts"
}
```

## 4. Rate Limit

현재 인증 API 전체에 대한 rate limit이 없습니다.

추후 적용 대상:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/oauth/google`
- `POST /api/auth/refresh`
- `POST /api/auth/phone-verifications`
- `POST /api/auth/phone-verifications/confirm`

권장 기준:

| 대상 | 기준 |
| --- | --- |
| IP | 짧은 시간 내 과도한 요청 차단 |
| 휴대폰 번호 | 인증번호 발송 남용 차단 |
| 이메일 | 로그인/회원가입 시도 남용 차단 |
| device_id | 앱 기기 단위 남용 차단 |

## 5. 로그인 실패 잠금

현재 비밀번호 로그인 실패 시 `failed_login_count`와 `locked_until`을 사용하지 않습니다.

추후 구현:

- 로그인 실패 시 `failed_login_count` 증가
- 성공 시 `failed_login_count` 초기화
- 일정 횟수 이상 실패 시 `locked_until` 설정
- 잠금 상태에서 로그인 시 `401` 또는 `423 Locked` 반환

## 6. 비밀번호 재설정

현재 `phone_verification_codes.purpose='password_reset'` 값은 준비되어 있지만 실제 비밀번호 재설정 API는 없습니다.

추후 구현 API:

```http
POST /api/auth/password-reset/phone-verifications
POST /api/auth/password-reset/confirm
POST /api/auth/password-reset
```

필요한 추가 테이블 후보:

```text
public.password_reset_tokens
```

## 7. 약관 동의 이력

현재는 `users.marketing_agreed`만 저장합니다.

추후 구현:

- 서비스 이용약관 버전 관리
- 개인정보 처리방침 버전 관리
- 마케팅 수신 동의 버전 관리
- 사용자별 약관 동의 이력 저장

필요한 추가 테이블 후보:

```text
public.terms
public.user_terms_agreements
```

## 8. 로그인 감사 로그

현재 로그인 성공/실패 이력을 별도 테이블에 저장하지 않습니다.

추후 구현:

- 로그인 성공 로그
- 로그인 실패 로그
- OAuth 로그인 로그
- refresh token 재발급 로그
- 로그아웃 로그
- IP, user-agent, device_id 저장

필요한 추가 테이블 후보:

```text
public.user_login_events
```

## 9. 기기/세션 관리

현재 refresh token에는 `device_id`, `user_agent`, `ip_address`를 저장하지만 기기 단위 세션 관리 테이블은 없습니다.

추후 구현:

- 사용자별 로그인 기기 목록 조회
- 특정 기기 로그아웃
- 전체 기기 로그아웃
- 기기명, OS, 앱 버전 저장

필요한 추가 테이블 후보:

```text
public.user_devices
```

## 10. Apple 로그인

현재 Apple 로그인은 DB 설계상 `user_oauth_accounts.provider='apple'`로 확장 가능하지만 API는 없습니다.

추후 구현 API:

```http
POST /api/auth/oauth/apple
```

구현 시 고려사항:

- Apple identity token 검증
- Apple `sub`를 `provider_user_id`로 저장
- 최초 로그인 시에만 전달되는 email/name 처리

## 11. Token 보안 강화

현재 access token은 HMAC 서명 기반 자체 token입니다.

추후 검토:

- 표준 JWT 라이브러리 도입
- `kid` 기반 key rotation
- refresh token 재사용 탐지
- 탈취 의심 시 사용자 전체 refresh token 폐기
- production 환경에서 `AUTH_TOKEN_SECRET` 강제 검증

## 우선순위 제안

| 우선순위 | 항목 | 이유 |
| --- | --- | --- |
| P0 | SMS 발송 연동 | 휴대폰 회원가입을 실제로 사용하려면 필수 |
| P0 | 인증번호 재요청 제한 | 문자 발송 비용과 남용 방지 |
| P0 | 인증번호 입력 시도 제한 | brute force 방지 |
| P1 | 로그인 실패 잠금 | 비밀번호 공격 방지 |
| P1 | Rate Limit | 인증 API 전체 보호 |
| P1 | 비밀번호 재설정 | 일반 사용자 계정 복구 |
| P2 | 약관 동의 이력 | 서비스 운영/컴플라이언스 |
| P2 | 로그인 감사 로그 | 보안 추적 |
| P2 | 기기/세션 관리 | 사용자 보안 UX |
| P3 | Apple 로그인 | iOS 배포 전 필요 |
