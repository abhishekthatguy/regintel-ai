"""Bootstrap/admin tool: link a Supabase auth user to an employee record.

Chicken-and-egg solver — POST /v1/auth/assign-employee needs an approved
admin, so the FIRST admin link happens here with the secret key. Employee
department/roles are copied from the local employees table (same data the
assign endpoint uses) so the profile carries complete identity claims.

Usage:
    REGINTEL_SUPABASE_URL=https://<ref>.supabase.co \
    REGINTEL_SUPABASE_SECRET_KEY=sb_secret_... \
    .venv/bin/python scripts/supabase_link_user.py <auth-user-uuid> e999
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.identity.supabase_client import SupabaseClient  # noqa: E402
from app.settings import get_settings  # noqa: E402
from app.stores.sqlite import SQLiteStore  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: supabase_link_user.py <auth_user_uuid> <employee_id>")
    auth_user_id, employee_id = sys.argv[1], sys.argv[2]

    employee = SQLiteStore(get_settings().db_path).get_employee(employee_id)
    if not employee:
        raise SystemExit(f"employee {employee_id} not in the employees table — seed first")

    sb = SupabaseClient(
        url=os.environ["REGINTEL_SUPABASE_URL"],
        publishable_key="",
        secret_key=os.environ["REGINTEL_SUPABASE_SECRET_KEY"],
    )
    if not sb.get_profile(auth_user_id):
        raise SystemExit(f"no profile for auth_user_id={auth_user_id} — sign up first")
    sb.update_profile(
        auth_user_id,
        {
            "employee_id": employee["employee_id"],
            "department": employee["department"],
            "roles": employee.get("roles") or ["employee"],
            "approved": True,
        },
    )
    print(f"linked {auth_user_id} -> {employee_id} ({employee['name']}, approved)")


if __name__ == "__main__":
    main()
