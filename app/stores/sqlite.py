import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.schemas.conversation import Conversation, ConversationStatus, Message

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    usecase_id TEXT NOT NULL,
    usecase_version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    usage_json TEXT,
    correlation_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    email TEXT,
    roles_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickets_employee ON tickets(employee_id, status);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    rating TEXT NOT NULL,
    reason TEXT,
    comment TEXT,
    correlation_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_message ON feedback(message_id);
"""


class SQLiteStore:
    """Local persistence for conversations/messages (+ Phase 1 demo tables).
    Phase 3 swaps to DynamoDB behind the same methods."""

    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _session(self):
        """Connection that commits on success and always closes."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._session() as conn:
            conn.executescript(SCHEMA)
        logger.info("sqlite schema initialized", extra={"action": "db_init"})

    def ping(self) -> bool:
        try:
            with self._session() as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def create_conversation(self, conversation: Conversation) -> Conversation:
        with self._session() as conn:
            conn.execute(
                """INSERT INTO conversations
                   (conversation_id, user_id, title, usecase_id, usecase_version,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    conversation.conversation_id,
                    conversation.user_id,
                    conversation.title,
                    conversation.usecase_id,
                    conversation.usecase_version,
                    conversation.status.value,
                    conversation.created_at.isoformat(),
                    conversation.updated_at.isoformat(),
                ),
            )
        return conversation

    def add_message(self, message: Message) -> Message:
        with self._session() as conn:
            conn.execute(
                """INSERT INTO messages
                   (message_id, conversation_id, role, content, citations_json,
                    usage_json, correlation_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.message_id,
                    message.conversation_id,
                    message.role.value,
                    message.content,
                    json.dumps([c.model_dump(mode="json") for c in message.citations]),
                    message.usage.model_dump_json() if message.usage else None,
                    message.correlation_id,
                    message.created_at.isoformat(),
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (message.created_at.isoformat(), message.conversation_id),
            )
        return message

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                return None
            messages = [
                self._row_to_message(m)
                for m in conn.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
                    (conversation_id,),
                ).fetchall()
            ]
        return Conversation(
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            title=row["title"],
            usecase_id=row["usecase_id"],
            usecase_version=row["usecase_version"],
            status=ConversationStatus(row["status"]),
            messages=messages,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_conversations(self, user_id: str) -> list[Conversation]:
        with self._session() as conn:
            rows = conn.execute(
                """SELECT * FROM conversations
                   WHERE user_id = ? AND status = 'active'
                   ORDER BY updated_at DESC""",
                (user_id,),
            ).fetchall()
        return [
            Conversation(
                conversation_id=r["conversation_id"],
                user_id=r["user_id"],
                title=r["title"],
                usecase_id=r["usecase_id"],
                usecase_version=r["usecase_version"],
                status=ConversationStatus(r["status"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        with self._session() as conn:
            conn.execute(
                "UPDATE conversations SET title = ? WHERE conversation_id = ?",
                (title, conversation_id),
            )

    def set_conversation_status(self, conversation_id: str, status: str) -> None:
        with self._session() as conn:
            conn.execute(
                "UPDATE conversations SET status = ? WHERE conversation_id = ?",
                (status, conversation_id),
            )

    # --- tickets (Phase 1 demo store; enterprise ITSM adapter later) ---

    def list_tickets(self, employee_id: str, open_only: bool = False) -> list[dict]:
        query = "SELECT * FROM tickets WHERE employee_id = ?"
        if open_only:
            query += " AND status IN ('open', 'in_progress')"
        with self._session() as conn:
            return [dict(r) for r in conn.execute(query, (employee_id,)).fetchall()]

    def find_duplicate_ticket(
        self, employee_id: str, category: str, idempotency_key: str | None = None
    ) -> dict | None:
        """An open ticket in the same category counts as a duplicate (FR-09)."""
        with self._session() as conn:
            row = conn.execute(
                """SELECT * FROM tickets
                   WHERE employee_id = ? AND category = ? AND status IN ('open', 'in_progress')
                   ORDER BY created_at DESC LIMIT 1""",
                (employee_id, category),
            ).fetchone()
        return dict(row) if row else None

    def next_ticket_id(self) -> str:
        with self._session() as conn:
            row = conn.execute(
                "SELECT ticket_id FROM tickets ORDER BY ticket_id DESC LIMIT 1"
            ).fetchone()
        seq = int(row["ticket_id"].split("-")[1]) + 1 if row else 1001
        return f"TCK-{seq}"

    def create_ticket(self, ticket: dict) -> dict:
        with self._session() as conn:
            conn.execute(
                """INSERT INTO tickets
                   (ticket_id, employee_id, category, description, status,
                    priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket["ticket_id"],
                    ticket["employee_id"],
                    ticket["category"],
                    ticket["description"],
                    ticket["status"],
                    ticket["priority"],
                    ticket["created_at"],
                    ticket["updated_at"],
                ),
            )
        return ticket

    # --- feedback (FR-20) ---

    def add_feedback(self, feedback: dict) -> dict:
        with self._session() as conn:
            conn.execute(
                """INSERT INTO feedback
                   (feedback_id, message_id, conversation_id, user_id, rating,
                    reason, comment, correlation_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    feedback["feedback_id"],
                    feedback["message_id"],
                    feedback["conversation_id"],
                    feedback["user_id"],
                    feedback["rating"],
                    feedback.get("reason"),
                    feedback.get("comment"),
                    feedback.get("correlation_id"),
                    feedback["created_at"],
                ),
            )
        return feedback

    def get_message(self, message_id: str) -> Message | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
        return self._row_to_message(row) if row else None

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        from app.schemas.agent import UsageSummary
        from app.schemas.conversation import Citation, MessageRole

        return Message(
            message_id=row["message_id"],
            conversation_id=row["conversation_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            citations=[Citation.model_validate(c) for c in json.loads(row["citations_json"])],
            usage=(
                UsageSummary.model_validate(json.loads(row["usage_json"]))
                if row["usage_json"]
                else None
            ),
            correlation_id=row["correlation_id"],
            created_at=row["created_at"],
        )
