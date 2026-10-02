"""Supabase Auth identity provider (FR-01/FR-02, Phase 9).

Token verification — per Supabase JWT docs:
- Primary: JWKS at {supabase_url}/auth/v1/.well-known/jwks.json
  (asymmetric ES256/RS256 keys on new projects), iss check, aud=authenticated.
- Fallback: GET /auth/v1/user with the bearer token — required for
  projects still on the shared-secret HS256 signing key.

Identity mapping (admin-assigns model): the JWT's `sub` (Supabase user
UUID) resolves to an employee via the public.profiles table. Only
approved profiles map — signup alone never grants access.
"""

import logging
import time
from typing import Any

import jwt
from jwt import PyJWKClient

from app.identity.jwt import AuthError
from app.identity.supabase_client import SupabaseAuthError, SupabaseClient
from app.schemas.identity import UserContext

logger = logging.getLogger(__name__)

PROFILE_CACHE_TTL = 60  # seconds — bounded staleness on role/employee changes


class SupabaseIdentityProvider:
    def __init__(self, client: SupabaseClient):
        self._client = client
        self._jwks = PyJWKClient(f"{client.base_url}/auth/v1/.well-known/jwks.json")
        self._profile_cache: dict[str, tuple[float, dict]] = {}

    async def resolve(
        self, demo_employee: str | None = None, bearer_token: str | None = None
    ) -> UserContext:
        if not bearer_token:
            raise AuthError("missing_token")
        claims = self._decode(bearer_token)
        auth_user_id = claims.get("sub")
        if not auth_user_id:
            raise AuthError("missing_claims:sub")

        profile = self._profile(auth_user_id)
        if profile is None:
            raise AuthError("profile_not_found")
        if not profile.get("approved") or not profile.get("employee_id"):
            raise AuthError("account_pending_approval")

        return UserContext(
            employee_id=profile["employee_id"],
            name=profile.get("name") or claims.get("email") or profile["employee_id"],
            department=profile.get("department") or "",
            email=profile.get("email") or claims.get("email", ""),
            roles=list(profile.get("roles") or ["employee"]),
            claims={"sub": auth_user_id, "iss": claims.get("iss"), "auth": "supabase"},
        )

    def _decode(self, token: str) -> dict[str, Any]:
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                algorithms=["ES256", "RS256", "EdDSA"],
                audience="authenticated",
                issuer=f"{self._client.base_url}/auth/v1",
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token_expired") from exc
        except Exception:
            # HS256-signed tokens (legacy shared-secret projects) aren't in
            # JWKS — and JWKS may be unreachable — verify directly against
            # the Auth server.
            pass
        try:
            user = self._client.get_auth_user(token)
            return {"sub": user["id"], "email": user.get("email")}
        except SupabaseAuthError as exc:
            raise AuthError(f"invalid_token:{exc.reason}") from exc
        except Exception as exc:
            raise AuthError("invalid_token") from exc

    def _profile(self, auth_user_id: str) -> dict | None:
        hit = self._profile_cache.get(auth_user_id)
        if hit and hit[0] > time.time():
            return hit[1]
        try:
            profile = self._client.get_profile(auth_user_id)
        except SupabaseAuthError as exc:
            raise AuthError(f"profile_lookup_failed:{exc.reason}") from exc
        self._profile_cache[auth_user_id] = (time.time() + PROFILE_CACHE_TTL, profile)
        return profile
