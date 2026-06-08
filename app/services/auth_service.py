from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import httpx

from app.core.config import Settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    generate_numeric_code,
    hash_password,
    hash_token,
    verify_password,
)
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import (
    AuthResponse,
    AuthTokens,
    AuthUser,
    GoogleAuthRequest,
    LoginRequest,
    PhoneVerificationConfirmRequest,
    PhoneVerificationConfirmResponse,
    PhoneVerificationRequest,
    PhoneVerificationResponse,
    RefreshTokenRequest,
    SignupRequest,
)


class AuthError(ValueError):
    status_code = 400


class InvalidCredentialsError(AuthError):
    status_code = 401


class AuthConflictError(AuthError):
    status_code = 409


class AuthConfigurationError(AuthError):
    status_code = 503


class AuthService:
    def __init__(self, repository: AuthRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    async def signup(
        self,
        request: SignupRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthResponse:
        if not request.email and not request.phone_number:
            raise AuthError("email or phone_number is required")
        if request.phone_number:
            if request.phone_verification_code:
                is_verified = await self._repository.verify_phone_code(
                    phone_number=request.phone_number,
                    code_hash=hash_token(request.phone_verification_code),
                    purpose="signup",
                )
            else:
                is_verified = await self._repository.has_verified_phone_code(
                    phone_number=request.phone_number,
                    purpose="signup",
                )
            if not is_verified:
                raise AuthError("phone_number is not verified")

        try:
            user = await self._repository.create_password_user(
                email=str(request.email) if request.email else None,
                phone_number=request.phone_number,
                name=request.name,
                password_hash=hash_password(request.password),
                marketing_agreed=request.marketing_agreed,
            )
        except asyncpg.UniqueViolationError as exc:
            raise AuthConflictError("email or phone_number already exists") from exc

        return await self._issue_response(
            user,
            device_id=request.device_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    async def login(
        self,
        request: LoginRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthResponse:
        user = await self._repository.find_user_by_identifier_with_password(
            request.identifier
        )
        if user is None or not verify_password(request.password, user["password_hash"]):
            raise InvalidCredentialsError("invalid identifier or password")
        if user["status"] != "active":
            raise InvalidCredentialsError("user is not active")

        await self._repository.touch_last_login(user["id"])
        return await self._issue_response(
            user,
            device_id=request.device_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    async def google_auth(
        self,
        request: GoogleAuthRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthResponse:
        profile = await self._validate_google_id_token(request.id_token)
        provider_user_id = profile.get("sub")
        if not provider_user_id:
            raise InvalidCredentialsError("invalid google id token")

        email = profile.get("email")
        email_verified = str(profile.get("email_verified", "")).lower() == "true"
        if email and not email_verified:
            raise InvalidCredentialsError("google email is not verified")

        user = await self._repository.upsert_oauth_user(
            provider="google",
            provider_user_id=str(provider_user_id),
            email=str(email) if email else None,
            email_verified=email_verified,
            name=profile.get("name"),
            profile_image_url=profile.get("picture"),
            raw_profile=profile,
            marketing_agreed=request.marketing_agreed,
        )
        await self._repository.touch_last_login(user["id"])
        return await self._issue_response(
            user,
            device_id=request.device_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    async def refresh(
        self,
        request: RefreshTokenRequest,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthResponse:
        old_token = await self._repository.consume_refresh_token(
            hash_token(request.refresh_token)
        )
        if old_token is None:
            raise InvalidCredentialsError("invalid refresh token")

        user = await self._repository.get_user_by_id(old_token["user_id"])
        if user is None or user["status"] != "active":
            raise InvalidCredentialsError("user is not active")

        return await self._issue_response(
            user,
            device_id=request.device_id or old_token["device_id"],
            user_agent=user_agent,
            ip_address=ip_address,
        )

    async def logout(self, refresh_token: str) -> dict[str, bool]:
        revoked = await self._repository.revoke_refresh_token(hash_token(refresh_token))
        return {"revoked": revoked}

    async def me(self, access_token: str) -> AuthUser:
        try:
            payload = decode_access_token(
                access_token,
                secret=self._settings.auth_token_secret,
            )
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError, TokenError) as exc:
            raise InvalidCredentialsError("invalid access token") from exc

        user = await self._repository.get_user_by_id(user_id)
        if user is None or user["status"] != "active":
            raise InvalidCredentialsError("user is not active")
        return _to_auth_user(user)

    async def request_phone_verification(
        self,
        request: PhoneVerificationRequest,
    ) -> PhoneVerificationResponse:
        code = generate_numeric_code()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.auth_phone_verification_ttl_minutes
        )
        await self._repository.create_phone_verification_code(
            phone_number=request.phone_number,
            code_hash=hash_token(code),
            purpose=request.purpose,
            expires_at=expires_at,
        )
        return PhoneVerificationResponse(
            phone_number=request.phone_number,
            purpose=request.purpose,
            expires_at=expires_at,
            development_code=code if self._settings.auth_expose_dev_codes else None,
        )

    async def confirm_phone_verification(
        self,
        request: PhoneVerificationConfirmRequest,
    ) -> PhoneVerificationConfirmResponse:
        verified = await self._repository.verify_phone_code(
            phone_number=request.phone_number,
            code_hash=hash_token(request.code),
            purpose=request.purpose,
        )
        if not verified:
            raise InvalidCredentialsError("invalid phone verification code")
        return PhoneVerificationConfirmResponse(verified=True)

    async def _issue_response(
        self,
        user: asyncpg.Record,
        *,
        device_id: str | None,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthResponse:
        access_expires = timedelta(minutes=self._settings.auth_access_token_minutes)
        refresh_expires_at = datetime.now(timezone.utc) + timedelta(
            days=self._settings.auth_refresh_token_days
        )
        refresh_token = create_refresh_token()
        await self._repository.create_refresh_token(
            user_id=user["id"],
            token_hash=hash_token(refresh_token),
            device_id=device_id,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=refresh_expires_at,
        )
        return AuthResponse(
            user=_to_auth_user(user),
            tokens=AuthTokens(
                access_token=create_access_token(
                    user_id=user["id"],
                    secret=self._settings.auth_token_secret,
                    expires_delta=access_expires,
                ),
                refresh_token=refresh_token,
                expires_in=int(access_expires.total_seconds()),
            ),
        )

    async def _validate_google_id_token(self, id_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._settings.kis_timeout_seconds) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
            )
        if response.status_code != 200:
            raise InvalidCredentialsError("invalid google id token")
        profile = response.json()
        client_id = self._settings.google_oauth_client_id
        if client_id and profile.get("aud") != client_id:
            raise InvalidCredentialsError("google token audience mismatch")
        return profile


def _to_auth_user(row: asyncpg.Record) -> AuthUser:
    return AuthUser(
        id=row["id"],
        email=row["email"],
        phone_number=row["phone_number"],
        name=row["name"],
        profile_image_url=row["profile_image_url"],
        status=row["status"],
        marketing_agreed=row["marketing_agreed"],
        created_at=row["created_at"],
    )
