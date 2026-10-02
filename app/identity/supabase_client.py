"""Thin httpx wrapper around Supabase Auth (GoTrue) + PostgREST.

All Supabase credentials stay server-side — the UI only ever talks to our
/v1/auth/* endpoints. Every method takes an injectable httpx.Client so
tests can use httpx.MockTransport without network access.
"""

from typing import Any

import httpx

AUTH_V1 = "/auth/v1"
REST_V1 = "/rest/v1"


class SupabaseAuthError(Exception):
    def __init__(self, reason: str, status: int = 502):
        super().__init__(reason)
        self.reason = reason
        self.status = status


class SupabaseClient:
    def __init__(
        self,
        url: str,
        publishable_key: str,
        secret_key: str,
        http: httpx.Client | None = None,
    ):
        self._url = url.rstrip("/")
        self._anon = publishable_key
        self._secret = secret_key
        self._http = http or httpx.Client(timeout=10)

    @property
    def base_url(self) -> str:
        return self._url

    # --- GoTrue (anon key — same surface as a browser client) ----------

    def signup(self, email: str, password: str, data: dict | None = None) -> dict:
        return self._auth(
            "POST",
            f"{AUTH_V1}/signup",
            json={"email": email, "password": password, "data": data or {}},
        )

    def signin_password(self, email: str, password: str) -> dict:
        return self._auth(
            "POST",
            f"{AUTH_V1}/token?grant_type=password",
            json={"email": email, "password": password},
        )

    def recover(self, email: str) -> dict:
        return self._auth("POST", f"{AUTH_V1}/recover", json={"email": email})

    def logout(self, access_token: str) -> dict:
        return self._auth(
            "POST", f"{AUTH_V1}/logout", bearer=access_token, expect_json=False
        )

    def get_auth_user(self, access_token: str) -> dict:
        """Server-side token check — also the HS256 fallback for projects
        without asymmetric signing keys (per Supabase JWT docs)."""
        return self._auth("GET", f"{AUTH_V1}/user", bearer=access_token)

    # --- PostgREST (service key — profiles table, admin-assigns flow) ---

    def get_profile(self, auth_user_id: str) -> dict | None:
        rows = self._rest(
            "GET",
            f"{REST_V1}/profiles?auth_user_id=eq.{auth_user_id}&select=*",
        )
        return rows[0] if rows else None

    def upsert_profile(self, profile: dict) -> dict:
        return self._rest(
            "POST",
            f"{REST_V1}/profiles",
            json=profile,
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )

    def list_pending_profiles(self) -> list[dict]:
        return self._rest(
            "GET",
            f"{REST_V1}/profiles?approved=eq.false&select=auth_user_id,email,created_at",
        )

    def update_profile(self, auth_user_id: str, patch: dict) -> dict | None:
        rows = self._rest(
            "PATCH",
            f"{REST_V1}/profiles?auth_user_id=eq.{auth_user_id}",
            json=patch,
            headers={"Prefer": "return=representation"},
        )
        return rows[0] if rows else None

    # --- transport -------------------------------------------------------

    def _auth(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        bearer: str | None = None,
        expect_json: bool = True,
    ) -> Any:
        headers = {"apikey": self._anon}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        resp = self._http.request(method, f"{self._url}{path}", json=json, headers=headers)
        if resp.status_code >= 400:
            raise SupabaseAuthError(_error_reason(resp), status=resp.status_code)
        if not expect_json:
            return {"ok": True}
        return resp.json()

    def _rest(self, method: str, path: str, json: dict | None = None, headers: dict | None = None) -> Any:
        h = {
            "apikey": self._secret,
            "Authorization": f"Bearer {self._secret}",
            **(headers or {}),
        }
        resp = self._http.request(method, f"{self._url}{path}", json=json, headers=h)
        if resp.status_code >= 400:
            raise SupabaseAuthError(_error_reason(resp), status=resp.status_code)
        return resp.json() if resp.content else None


def _error_reason(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return (
            body.get("msg")
            or body.get("message")
            or body.get("error_description")
            or f"http_{resp.status_code}"
        )
    except Exception:
        return f"http_{resp.status_code}"
