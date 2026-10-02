"""Auth endpoints (Phase 9): real backend authentication via Supabase.

The UI never touches Supabase directly — these endpoints proxy GoTrue
with server-side keys, so tokens/secrets never reach the browser beyond
the user's own access token.

Admin-assigns model: signup creates the auth account + a pending
profiles row; an admin links it to an employee record before it can act.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import IdentityDep, SettingsDep, StoreDep
from app.identity.supabase_client import SupabaseAuthError, SupabaseClient
from app.schemas.identity import UserContext
from app.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _client(settings: Settings) -> SupabaseClient:
    if settings.auth_mode != "supabase" or not settings.supabase_url:
        raise HTTPException(
            status_code=503,
            detail="Supabase auth is not configured (REGINTEL_AUTH_MODE=supabase "
            "+ REGINTEL_SUPABASE_URL/keys)",
        )
    return SupabaseClient(
        url=settings.supabase_url,
        publishable_key=settings.supabase_publishable_key,
        secret_key=settings.supabase_secret_key,
    )


def _sb_error(exc: SupabaseAuthError) -> HTTPException:
    status = exc.status if 400 <= exc.status < 500 else 502
    return HTTPException(status_code=status, detail=exc.reason)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=120)


class SigninRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotRequest(BaseModel):
    email: EmailStr


@router.post("/signup", status_code=201)
def signup(req: SignupRequest, settings: SettingsDep) -> dict:
    """Create the auth account + pending profile. Access stays denied until
    an admin links the account to an employee record."""
    sb = _client(settings)
    try:
        resp = sb.signup(req.email, req.password, data={"name": req.name})
    except SupabaseAuthError as exc:
        raise _sb_error(exc) from exc
    auth_user_id = (resp.get("user") or {}).get("id") or resp.get("id")
    if not auth_user_id:
        raise HTTPException(502, "signup response missing user id")
    try:
        sb.upsert_profile(
            {
                "auth_user_id": auth_user_id,
                "email": req.email,
                "name": req.name,
                "approved": False,
            }
        )
    except SupabaseAuthError as exc:
        raise _sb_error(exc) from exc
    return {
        "status": "pending_approval",
        "message": "Account created. An administrator must link your account "
        "to an employee profile before you can sign in.",
    }


@router.post("/signin")
def signin(req: SigninRequest, settings: SettingsDep) -> dict:
    sb = _client(settings)
    try:
        resp = sb.signin_password(req.email, req.password)
    except SupabaseAuthError as exc:
        raise _sb_error(exc) from exc
    token = resp.get("access_token")
    if not token:
        raise HTTPException(502, "signin response missing access token")
    auth_user_id = (resp.get("user") or {}).get("id")
    profile = sb.get_profile(auth_user_id) if auth_user_id else None
    approved = bool(profile and profile.get("approved") and profile.get("employee_id"))
    return {
        "access_token": token,
        "refresh_token": resp.get("refresh_token"),
        "token_type": "bearer",
        "expires_in": resp.get("expires_in"),
        "approved": approved,
        "employee_id": (profile or {}).get("employee_id"),
        "message": None if approved else "Account pending admin approval.",
    }


@router.post("/forgot-password", status_code=202)
def forgot_password(req: ForgotRequest, settings: SettingsDep) -> dict:
    """Always 202 — never leaks whether the account exists."""
    sb = _client(settings)
    try:
        sb.recover(req.email)
    except SupabaseAuthError:
        pass
    return {"message": "If that email is registered, a reset link is on its way."}


@router.post("/signout")
def signout(
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    sb = _client(settings)
    token = (
        authorization.removeprefix("Bearer ").strip()
        if authorization and authorization.startswith("Bearer ")
        else None
    )
    if token:
        try:
            sb.logout(token)
        except SupabaseAuthError:
            pass
    return {"status": "signed_out"}


@router.get("/me")
def me(user: IdentityDep) -> dict:
    """The resolved identity for the current bearer token — works in every
    auth mode so the UI can confirm who it's acting as."""
    return {
        "employee_id": user.employee_id,
        "name": user.name,
        "department": user.department,
        "email": user.email,
        "roles": user.roles,
        "auth": user.claims.get("auth"),
    }


# --- admin: link pending accounts to employees ---------------------------

from app.api.routes_admin import require_admin  # noqa: E402


class AssignRequest(BaseModel):
    auth_user_id: str
    employee_id: str


@router.get("/pending-users")
def pending_users(
    _admin: Annotated[UserContext, Depends(require_admin)],
    settings: SettingsDep,
) -> dict:
    sb = _client(settings)
    try:
        return {"pending": sb.list_pending_profiles()}
    except SupabaseAuthError as exc:
        raise _sb_error(exc) from exc


@router.post("/assign-employee")
def assign_employee(
    req: AssignRequest,
    admin: Annotated[UserContext, Depends(require_admin)],
    store: StoreDep,
    settings: SettingsDep,
) -> dict:
    """Link a pending Supabase account to an employee record — the
    admin-assigns gate. Department/roles are copied from the employee
    record, never from user-editable data."""
    sb = _client(settings)
    employee = store.get_employee(req.employee_id)
    if not employee:
        raise HTTPException(404, f"employee {req.employee_id} not found")
    try:
        profile = sb.update_profile(
            req.auth_user_id,
            {
                "employee_id": employee["employee_id"],
                "department": employee["department"],
                "roles": employee.get("roles") or ["employee"],
                "approved": True,
            },
        )
    except SupabaseAuthError as exc:
        raise _sb_error(exc) from exc
    if not profile:
        raise HTTPException(404, "no pending profile for that auth_user_id")
    from app.audit import record_audit

    record_audit(
        store,
        actor=admin.employee_id,
        action="auth_assign_employee",
        outcome=req.auth_user_id,
        detail={"employee_id": req.employee_id},
    )
    return {"status": "approved", "auth_user_id": req.auth_user_id, "employee_id": req.employee_id}
