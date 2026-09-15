"""Entra ID / JWT identity provider (FR-01, FR-02).

Two modes, selected by settings:
- Dev/local: HS256 token signed with `jwt_secret` — real cryptographic
  validation locally, so security tests exercise the actual code path.
  `scripts/mint_dev_token.py` mints tokens.
- Enterprise: RS256 via JWKS endpoint (`jwt_jwks_url` — e.g. Entra
  https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys).

Every token is verified for signature, issuer, audience and expiry; missing
required claims are rejected. Claim→department/role mapping happens here,
server-side — prompts can never override it.
"""

import logging
from typing import Any

import jwt
from jwt import PyJWKClient

from app.schemas.identity import UserContext

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication failure — surfaced to the API layer as 401."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


REQUIRED_CLAIMS = ("sub", "department")


class JWTIdentityProvider:
    def __init__(
        self,
        issuer: str,
        audience: str,
        secret: str = "",
        jwks_url: str = "",
        algorithms: tuple[str, ...] = ("HS256", "RS256"),
    ):
        self._issuer = issuer
        self._audience = audience
        self._secret = secret
        self._algorithms = list(algorithms)
        self._jwks = PyJWKClient(jwks_url) if jwks_url else None

    def _signing_key(self, token: str) -> Any:
        if self._jwks:
            return self._jwks.get_signing_key_from_jwt(token).key
        if self._secret:
            return self._secret
        raise AuthError("no_verification_key")

    def _decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._signing_key(token),
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token_expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthError("invalid_audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthError("invalid_issuer") from exc
        except jwt.PyJWTError as exc:
            raise AuthError(f"invalid_token:{exc.__class__.__name__}") from exc

    async def resolve(
        self, demo_employee: str | None = None, bearer_token: str | None = None
    ) -> UserContext:
        if not bearer_token:
            raise AuthError("missing_token")
        claims = self._decode(bearer_token)

        missing = [c for c in REQUIRED_CLAIMS if not claims.get(c)]
        if missing:
            raise AuthError(f"missing_claims:{','.join(missing)}")

        user = UserContext(
            employee_id=claims["sub"],
            name=claims.get("name", claims["sub"]),
            department=claims["department"],
            email=claims.get("email", ""),
            roles=list(claims.get("roles", ["employee"])),
            claims={
                "department": claims["department"],
                "iss": claims.get("iss"),
                "auth": "jwt",
            },
        )
        logger.debug(
            "resolved jwt identity",
            extra={"actor": user.employee_id, "action": "auth", "outcome": "ok"},
        )
        return user
