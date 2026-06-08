from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg


class AuthRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_password_user(
        self,
        *,
        email: str | None,
        phone_number: str | None,
        name: str | None,
        password_hash: str,
        marketing_agreed: bool,
    ) -> asyncpg.Record:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                user = await connection.fetchrow(
                    """
                    INSERT INTO public.users (
                        email,
                        phone_number,
                        name,
                        marketing_agreed
                    )
                    VALUES ($1, $2, $3, $4)
                    RETURNING *
                    """,
                    email,
                    phone_number,
                    name,
                    marketing_agreed,
                )
                await connection.execute(
                    """
                    INSERT INTO public.user_password_credentials (
                        user_id,
                        password_hash
                    )
                    VALUES ($1, $2)
                    """,
                    user["id"],
                    password_hash,
                )
                return user

    async def find_user_by_identifier_with_password(
        self, identifier: str
    ) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            """
            SELECT
                users.*,
                password_credentials.password_hash,
                password_credentials.locked_until
            FROM public.users AS users
            JOIN public.user_password_credentials AS password_credentials
                ON password_credentials.user_id = users.id
            WHERE
                lower(users.email) = lower($1)
                OR users.phone_number = $1
            LIMIT 1
            """,
            identifier,
        )

    async def get_user_by_id(self, user_id: int) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            """
            SELECT *
            FROM public.users
            WHERE id = $1
            LIMIT 1
            """,
            user_id,
        )

    async def touch_last_login(self, user_id: int) -> None:
        await self._pool.execute(
            """
            UPDATE public.users
            SET last_login_at = now()
            WHERE id = $1
            """,
            user_id,
        )

    async def upsert_oauth_user(
        self,
        *,
        provider: str,
        provider_user_id: str,
        email: str | None,
        email_verified: bool,
        name: str | None,
        profile_image_url: str | None,
        raw_profile: dict[str, Any],
        marketing_agreed: bool,
    ) -> asyncpg.Record:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                existing = await connection.fetchrow(
                    """
                    SELECT users.*
                    FROM public.user_oauth_accounts AS oauth
                    JOIN public.users AS users
                        ON users.id = oauth.user_id
                    WHERE oauth.provider = $1
                        AND oauth.provider_user_id = $2
                    LIMIT 1
                    """,
                    provider,
                    provider_user_id,
                )
                if existing is not None:
                    await connection.execute(
                        """
                        UPDATE public.user_oauth_accounts
                        SET
                            email = $3,
                            email_verified = $4,
                            raw_profile = $5
                        WHERE provider = $1
                            AND provider_user_id = $2
                        """,
                        provider,
                        provider_user_id,
                        email,
                        email_verified,
                        json.dumps(raw_profile, ensure_ascii=False),
                    )
                    return existing

                user = None
                if email:
                    user = await connection.fetchrow(
                        """
                        SELECT *
                        FROM public.users
                        WHERE lower(email) = lower($1)
                        LIMIT 1
                        """,
                        email,
                    )

                if user is None:
                    user = await connection.fetchrow(
                        """
                        INSERT INTO public.users (
                            email,
                            name,
                            profile_image_url,
                            marketing_agreed
                        )
                        VALUES ($1, $2, $3, $4)
                        RETURNING *
                        """,
                        email,
                        name,
                        profile_image_url,
                        marketing_agreed,
                    )
                else:
                    user = await connection.fetchrow(
                        """
                        UPDATE public.users
                        SET
                            name = COALESCE(public.users.name, $2),
                            profile_image_url = COALESCE(
                                public.users.profile_image_url,
                                $3
                            )
                        WHERE id = $1
                        RETURNING *
                        """,
                        user["id"],
                        name,
                        profile_image_url,
                    )

                await connection.execute(
                    """
                    INSERT INTO public.user_oauth_accounts (
                        user_id,
                        provider,
                        provider_user_id,
                        email,
                        email_verified,
                        raw_profile
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (provider, provider_user_id)
                    DO UPDATE SET
                        email = EXCLUDED.email,
                        email_verified = EXCLUDED.email_verified,
                        raw_profile = EXCLUDED.raw_profile
                    """,
                    user["id"],
                    provider,
                    provider_user_id,
                    email,
                    email_verified,
                    json.dumps(raw_profile, ensure_ascii=False),
                )
                return user

    async def create_refresh_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        device_id: str | None,
        user_agent: str | None,
        ip_address: str | None,
        expires_at: datetime,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO public.auth_refresh_tokens (
                user_id,
                token_hash,
                device_id,
                user_agent,
                ip_address,
                expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_id,
            token_hash,
            device_id,
            user_agent,
            ip_address,
            expires_at,
        )

    async def consume_refresh_token(self, token_hash: str) -> asyncpg.Record | None:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                token = await connection.fetchrow(
                    """
                    SELECT *
                    FROM public.auth_refresh_tokens
                    WHERE token_hash = $1
                        AND revoked_at IS NULL
                        AND expires_at > now()
                    FOR UPDATE
                    """,
                    token_hash,
                )
                if token is None:
                    return None
                await connection.execute(
                    """
                    UPDATE public.auth_refresh_tokens
                    SET revoked_at = now()
                    WHERE id = $1
                    """,
                    token["id"],
                )
                return token

    async def revoke_refresh_token(self, token_hash: str) -> bool:
        result = await self._pool.execute(
            """
            UPDATE public.auth_refresh_tokens
            SET revoked_at = now()
            WHERE token_hash = $1
                AND revoked_at IS NULL
            """,
            token_hash,
        )
        return result.endswith("1")

    async def create_phone_verification_code(
        self,
        *,
        phone_number: str,
        code_hash: str,
        purpose: str,
        expires_at: datetime,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO public.phone_verification_codes (
                phone_number,
                code_hash,
                purpose,
                expires_at
            )
            VALUES ($1, $2, $3, $4)
            """,
            phone_number,
            code_hash,
            purpose,
            expires_at,
        )

    async def verify_phone_code(
        self,
        *,
        phone_number: str,
        code_hash: str,
        purpose: str,
    ) -> bool:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """
                    SELECT id
                    FROM public.phone_verification_codes
                    WHERE phone_number = $1
                        AND purpose = $2
                        AND verified_at IS NULL
                        AND expires_at > now()
                    ORDER BY created_at DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    phone_number,
                    purpose,
                )
                if row is None:
                    return False

                matched = await connection.fetchrow(
                    """
                    UPDATE public.phone_verification_codes
                    SET
                        verified_at = now(),
                        attempt_count = attempt_count + 1
                    WHERE id = $1
                        AND code_hash = $2
                    RETURNING id
                    """,
                    row["id"],
                    code_hash,
                )
                if matched is not None:
                    return True

                await connection.execute(
                    """
                    UPDATE public.phone_verification_codes
                    SET attempt_count = attempt_count + 1
                    WHERE id = $1
                    """,
                    row["id"],
                )
                return False

    async def has_verified_phone_code(
        self,
        *,
        phone_number: str,
        purpose: str,
    ) -> bool:
        return bool(
            await self._pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public.phone_verification_codes
                    WHERE phone_number = $1
                        AND purpose = $2
                        AND verified_at IS NOT NULL
                        AND expires_at > now()
                    LIMIT 1
                )
                """,
                phone_number,
                purpose,
            )
        )
