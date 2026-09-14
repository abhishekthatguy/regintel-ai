"""Seed the local SQLite DB with demo employees and tickets.

Usage: .venv/bin/python scripts/seed_db.py
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.settings import get_settings
from app.stores.sqlite import SQLiteStore

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"


def main() -> None:
    settings = get_settings()
    store = SQLiteStore(settings.db_path)
    store.init_schema()

    employees = json.loads((SEED_DIR / "employees.json").read_text())
    tickets = json.loads((SEED_DIR / "tickets.json").read_text())

    conn = sqlite3.connect(settings.db_path)
    with conn:
        for e in employees:
            conn.execute(
                """INSERT OR REPLACE INTO employees
                   (employee_id, name, department, email, roles_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (e["employee_id"], e["name"], e["department"], e["email"], json.dumps(e["roles"])),
            )
        for t in tickets:
            conn.execute(
                """INSERT OR REPLACE INTO tickets
                   (ticket_id, employee_id, category, description, status,
                    priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    t["ticket_id"],
                    t["employee_id"],
                    t["category"],
                    t["description"],
                    t["status"],
                    t["priority"],
                    t["created_at"],
                    t["updated_at"],
                ),
            )
    conn.close()
    print(f"Seeded {len(employees)} employees and {len(tickets)} tickets into {settings.db_path}")


if __name__ == "__main__":
    main()
