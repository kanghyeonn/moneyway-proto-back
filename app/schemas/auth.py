from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


PhoneVerificationPurpose = Literal["signup", "password_reset"]


class AuthUser(BaseModel):
    id: int
    email: str | None = None
    phone_number: str | None = None
    name: str | None = None
    profile_image_url: str | None = None
    status: str
    marketing_agreed: bool
    created_at: datetime


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class AuthResponse(BaseModel):
    user: AuthUser
    tokens: AuthTokens


class SignupRequest(BaseModel):
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, min_length=8, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=80)
    marketing_agreed: bool = False
    phone_verification_code: str | None = Field(default=None, min_length=4, max_length=12)
    device_id: str | None = Field(default=None, max_length=255)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return "".join(ch for ch in value if ch.isdigit() or ch == "+")


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    device_id: str | None = Field(default=None, max_length=255)


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(min_length=20)
    device_id: str | None = Field(default=None, max_length=255)
    marketing_agreed: bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)
    device_id: str | None = Field(default=None, max_length=255)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class PhoneVerificationRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=32)
    purpose: PhoneVerificationPurpose = "signup"

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        return "".join(ch for ch in value if ch.isdigit() or ch == "+")


class PhoneVerificationResponse(BaseModel):
    phone_number: str
    purpose: PhoneVerificationPurpose
    expires_at: datetime
    development_code: str | None = None


class PhoneVerificationConfirmRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=32)
    purpose: PhoneVerificationPurpose = "signup"
    code: str = Field(min_length=4, max_length=12)

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        return "".join(ch for ch in value if ch.isdigit() or ch == "+")


class PhoneVerificationConfirmResponse(BaseModel):
    verified: bool
