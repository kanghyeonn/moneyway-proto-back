from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dependencies import get_auth_service
from app.schemas.auth import (
    AuthResponse,
    AuthUser,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    PhoneVerificationConfirmRequest,
    PhoneVerificationConfirmResponse,
    PhoneVerificationRequest,
    PhoneVerificationResponse,
    RefreshTokenRequest,
    SignupRequest,
)
from app.services.auth_service import AuthService, InvalidCredentialsError


router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/signup", response_model=AuthResponse)
async def signup(
    payload: SignupRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.signup(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.login(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/oauth/google", response_model=AuthResponse)
async def google_auth(
    payload: GoogleAuthRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.google_auth(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await service.refresh(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, bool]:
    return await service.logout(payload.refresh_token)


@router.get("/me", response_model=AuthUser)
async def me(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: AuthService = Depends(get_auth_service),
) -> AuthUser:
    if credentials is None:
        raise InvalidCredentialsError("authorization bearer token is required")
    return await service.me(credentials.credentials)


@router.post("/phone-verifications", response_model=PhoneVerificationResponse)
async def request_phone_verification(
    payload: PhoneVerificationRequest,
    service: AuthService = Depends(get_auth_service),
) -> PhoneVerificationResponse:
    return await service.request_phone_verification(payload)


@router.post(
    "/phone-verifications/confirm",
    response_model=PhoneVerificationConfirmResponse,
)
async def confirm_phone_verification(
    payload: PhoneVerificationConfirmRequest,
    service: AuthService = Depends(get_auth_service),
) -> PhoneVerificationConfirmResponse:
    return await service.confirm_phone_verification(payload)
