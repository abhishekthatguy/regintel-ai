"""Supabase auth boundary — mocked HTTP, no network. Covers the proxy
endpoints and the identity provider's admin-assigns flow."""

import asyncio

import httpx
import pytest

from app.identity.supabase import SupabaseIdentityProvider
from app.identity.supabase_client import SupabaseAuthError, SupabaseClient

SB_URL = "https://regintel-test.supabase.co"


def make_client(handler) -> SupabaseClient:
    transport = httpx.MockTransport(handler)
    return SupabaseClient(
        url=SB_URL,
        publishable_key="sb_publishable_test",
        secret_key="sb_secret_test",
        http=httpx.Client(transport=transport),
    )


def test_client_calls_gotrue_with_anon_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["apikey"] = request.headers["apikey"]
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})

    c = make_client(handler)
    out = c.signin_password("a@b.co", "hunter2secret")
    assert out["access_token"] == "tok"
    assert seen["url"] == f"{SB_URL}/auth/v1/token?grant_type=password"
    assert seen["apikey"] == "sb_publishable_test"


def test_client_profiles_use_secret_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["apikey"] = request.headers["apikey"]
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json=[{"auth_user_id": "u1", "approved": False}])

    c = make_client(handler)
    rows = c.get_profile("u1")
    assert rows["auth_user_id"] == "u1"
    assert seen["apikey"] == "sb_secret_test"
    assert seen["auth"] == "Bearer sb_secret_test"


def test_client_error_maps_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"msg": "Invalid login credentials"})

    c = make_client(handler)
    with pytest.raises(SupabaseAuthError) as err:
        c.signin_password("a@b.co", "wrong")
    assert err.value.reason == "Invalid login credentials"


def test_provider_resolves_approved_profile():
    """JWKS fetch fails offline → falls back to /auth/v1/user, then the
    profiles table supplies the employee mapping."""
    profiles = {
        "user-uuid-1": {
            "auth_user_id": "user-uuid-1", "email": "asha@corp.example",
            "employee_id": "e001", "name": "Asha Verma", "department": "IT",
            "roles": ["employee"], "approved": True,
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "user-uuid-1", "email": "asha@corp.example"})
        if request.url.path == "/rest/v1/profiles":
            uid = request.url.params["auth_user_id"].removeprefix("eq.")
            p = profiles.get(uid)
            return httpx.Response(200, json=[p] if p else [])
        return httpx.Response(404)

    provider = SupabaseIdentityProvider(make_client(handler))
    user = asyncio.run(provider.resolve(bearer_token="any-token"))
    assert user.employee_id == "e001"
    assert user.department == "IT"
    assert user.claims["auth"] == "supabase"


def test_provider_rejects_pending_and_missing_profiles():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "user-uuid-2"})
        if request.url.path == "/rest/v1/profiles":
            return httpx.Response(200, json=[{"auth_user_id": "user-uuid-2", "approved": False}])
        return httpx.Response(404)

    provider = SupabaseIdentityProvider(make_client(handler))
    from app.identity.jwt import AuthError

    with pytest.raises(AuthError) as err:
        asyncio.run(provider.resolve(bearer_token="tok"))
    assert err.value.reason == "account_pending_approval"

    def empty_profile(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "user-uuid-3"})
        if request.url.path == "/rest/v1/profiles":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    provider = SupabaseIdentityProvider(make_client(empty_profile))
    with pytest.raises(AuthError) as err:
        asyncio.run(provider.resolve(bearer_token="tok"))
    assert err.value.reason == "profile_not_found"


def test_provider_rejects_invalid_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"msg": "bad token"})

    provider = SupabaseIdentityProvider(make_client(handler))
    from app.identity.jwt import AuthError

    with pytest.raises(AuthError) as err:
        asyncio.run(provider.resolve(bearer_token="bad"))
    assert "invalid_token" in err.value.reason


# --- HTTP routes (API-level, mocked Supabase) ----------------------------


def _routes_client(handler):
    return make_client(handler)


def test_signup_creates_pending_profile(client, monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/auth/v1/signup":
            return httpx.Response(200, json={"user": {"id": "new-uuid"}})
        if request.url.path == "/rest/v1/profiles":
            return httpx.Response(201, json=[{"auth_user_id": "new-uuid"}])
        return httpx.Response(404)

    monkeypatch.setenv("REGINTEL_AUTH_MODE", "supabase")
    monkeypatch.setenv("REGINTEL_SUPABASE_URL", SB_URL)
    monkeypatch.setenv("REGINTEL_SUPABASE_PUBLISHABLE_KEY", "pub")
    monkeypatch.setenv("REGINTEL_SUPABASE_SECRET_KEY", "sec")
    from app.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.routes_auth._client", lambda settings: _routes_client(handler)
    )
    resp = client.post(
        "/v1/auth/signup",
        json={"email": "new@corp.example", "password": "password123", "name": "New Person"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending_approval"
    assert ("POST", "/auth/v1/signup") in calls
    assert ("POST", "/rest/v1/profiles") in calls
    get_settings.cache_clear()


def test_signin_returns_token_and_pending_flag(client, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "grant_type=password" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "access_token": "real-token",
                    "refresh_token": "rt",
                    "expires_in": 3600,
                    "user": {"id": "u-1"},
                },
            )
        if request.url.path == "/rest/v1/profiles":
            return httpx.Response(200, json=[{"approved": False}])
        return httpx.Response(404)

    monkeypatch.setenv("REGINTEL_AUTH_MODE", "supabase")
    monkeypatch.setenv("REGINTEL_SUPABASE_URL", SB_URL)
    monkeypatch.setenv("REGINTEL_SUPABASE_PUBLISHABLE_KEY", "pub")
    monkeypatch.setenv("REGINTEL_SUPABASE_SECRET_KEY", "sec")
    from app.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.routes_auth._client", lambda settings: _routes_client(handler)
    )
    resp = client.post(
        "/v1/auth/signin", json={"email": "a@b.co", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "real-token"
    assert body["approved"] is False
    get_settings.cache_clear()


def test_forgot_password_never_leaks(client, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"msg": "user not found"})

    monkeypatch.setenv("REGINTEL_AUTH_MODE", "supabase")
    monkeypatch.setenv("REGINTEL_SUPABASE_URL", SB_URL)
    monkeypatch.setenv("REGINTEL_SUPABASE_PUBLISHABLE_KEY", "pub")
    monkeypatch.setenv("REGINTEL_SUPABASE_SECRET_KEY", "sec")
    from app.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.routes_auth._client", lambda settings: _routes_client(handler)
    )
    resp = client.post("/v1/auth/forgot-password", json={"email": "ghost@x.co"})
    assert resp.status_code == 202
    get_settings.cache_clear()


def test_assign_employee_validates_employee(client, monkeypatch, auth_headers):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"auth_user_id": "u-9"}])

    monkeypatch.setenv("REGINTEL_AUTH_MODE", "stub")  # admin via stub header
    monkeypatch.setenv("REGINTEL_SUPABASE_URL", SB_URL)
    monkeypatch.setenv("REGINTEL_SUPABASE_PUBLISHABLE_KEY", "pub")
    monkeypatch.setenv("REGINTEL_SUPABASE_SECRET_KEY", "sec")
    from app.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.routes_auth._client", lambda settings: _routes_client(handler)
    )
    # nonexistent employee → 404
    resp = client.post(
        "/v1/auth/assign-employee",
        json={"auth_user_id": "u-9", "employee_id": "e404"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    # real employee → approved, audit logged
    resp = client.post(
        "/v1/auth/assign-employee",
        json={"auth_user_id": "u-9", "employee_id": "e001"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == "e001"
    get_settings.cache_clear()


def test_auth_endpoints_503_without_supabase_mode(client):
    resp = client.post(
        "/v1/auth/signin", json={"email": "a@b.co", "password": "x"}
    )
    assert resp.status_code == 503
