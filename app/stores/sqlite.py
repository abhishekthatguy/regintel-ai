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

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    source_system TEXT,
    version TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(doc_id),
    title TEXT NOT NULL,
    section TEXT,
    text TEXT NOT NULL,
    department TEXT,
    acl_json TEXT NOT NULL DEFAULT '[]',
    version TEXT,
    source_system TEXT,
    source_ref TEXT,
    source_url TEXT,
    vector_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_dept ON chunks(department);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    ingested INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    error TEXT,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    error TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
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

    # --- chunk store / ingestion (Phase 2) ---

    def document_checksum(self, doc_id: str) -> str | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT checksum FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        return row["checksum"] if row else None

    def replace_document_chunks(self, doc_id: str, chunks, vectors: dict, checksum: str) -> None:
        """Idempotent re-ingestion: delete stale chunks, insert fresh ones."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        with self._session() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO documents (doc_id, checksum, source_system, version, ingested_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    doc_id,
                    checksum,
                    chunks[0].source_system if chunks else "",
                    chunks[0].version if chunks else "",
                    now,
                ),
            )
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            for c in chunks:
                conn.execute(
                    """INSERT INTO chunks
                       (chunk_id, document_id, title, section, text, department,
                        acl_json, version, source_system, source_ref, source_url,
                        vector_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        c.chunk_id,
                        c.document_id,
                        c.title,
                        c.section,
                        c.text,
                        c.department,
                        json.dumps(c.acl),
                        c.version,
                        c.source_system,
                        c.source_ref,
                        c.source_url,
                        json.dumps(vectors.get(c.chunk_id, [])),
                        now,
                    ),
                )

    def all_chunks(self):
        from app.retrieval.corpus import Chunk

        with self._session() as conn:
            rows = conn.execute("SELECT * FROM chunks").fetchall()
        return [
            Chunk(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                title=r["title"],
                section=r["section"] or "",
                text=r["text"],
                department=r["department"] or "",
                acl=json.loads(r["acl_json"]),
                version=r["version"] or "1",
                source_system=r["source_system"] or "local_files",
                source_ref=r["source_ref"] or "",
                source_url=r["source_url"] or "",
            )
            for r in rows
        ]

    def chunk_vectors(self) -> dict[str, list[float]]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT chunk_id, vector_json FROM chunks WHERE vector_json IS NOT NULL"
            ).fetchall()
        return {r["chunk_id"]: json.loads(r["vector_json"]) for r in rows}

    def create_ingestion_job(self, job: dict) -> None:
        with self._session() as conn:
            conn.execute(
                """INSERT INTO ingestion_jobs (job_id, source, status, started_at)
                   VALUES (?, ?, ?, ?)""",
                (job["job_id"], job["source"], job["status"], job.get("started_at")),
            )

    def finish_ingestion_job(
        self, job_id: str, status: str, ingested: int, failed: int, error: str | None = None
    ) -> None:
        from datetime import UTC, datetime

        with self._session() as conn:
            conn.execute(
                """UPDATE ingestion_jobs
                   SET status = ?, ingested = ?, failed = ?, error = ?, finished_at = ?
                   WHERE job_id = ?""",
                (status, ingested, failed, error, datetime.now(UTC).isoformat(), job_id),
            )

    def add_ingestion_failure(self, job_id: str, doc_id: str, error: str) -> None:
        from datetime import UTC, datetime

        with self._session() as conn:
            conn.execute(
                "INSERT INTO ingestion_failures (job_id, doc_id, error, created_at) VALUES (?, ?, ?, ?)",
                (job_id, doc_id, error, datetime.now(UTC).isoformat()),
            )

    def get_ingestion_job(self, job_id: str) -> dict | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_ingestion_jobs(self, limit: int = 20) -> list[dict]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT * FROM ingestion_jobs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def ingestion_failures(self, job_id: str) -> list[dict]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT doc_id, error, created_at FROM ingestion_failures WHERE job_id = ?",
                (job_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- audit (Phase 3, NFR-12) ---

    def add_audit_record(self, actor: str, action: str, outcome: str, detail: dict) -> None:
        from datetime import UTC, datetime

        with self._session() as conn:
            conn.execute(
                "INSERT INTO audit_log (actor, action, outcome, detail_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (actor, action, outcome, json.dumps(detail), datetime.now(UTC).isoformat()),
            )

    def list_audit_records(self, limit: int = 100) -> list[dict]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT actor, action, outcome, detail_json, created_at "
                "FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**r, "detail": json.loads(r.pop("detail_json"))} for r in map(dict, rows)]

    # --- analytics (Phase 4, FR-25) ---

    def analytics_summary(self) -> dict:
        with self._session() as conn:
            convs = conn.execute("SELECT COUNT(*) AS n FROM conversations").fetchone()["n"]
            msgs = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(json_extract(usage_json,'$.total_tokens')),0) AS tok,"
                " COALESCE(AVG(json_extract(usage_json,'$.latency_ms')),0) AS lat"
                " FROM messages WHERE role = 'assistant'"
            ).fetchone()
            tickets = conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]
            fb = conn.execute(
                "SELECT COALESCE(SUM(rating='up'),0) AS up, COALESCE(SUM(rating='down'),0) AS dn"
                " FROM feedback"
            ).fetchone()
        return {
            "conversations": convs,
            "assistant_messages": msgs["n"],
            "total_tokens": msgs["tok"],
            "avg_latency_ms": round(msgs["lat"], 1),
            "tickets": tickets,
            "feedback_up": fb["up"],
            "feedback_down": fb["dn"],
        }

    def analytics_by_usecase(self) -> list[dict]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT c.usecase_id, COUNT(DISTINCT c.conversation_id) AS conversations,"
                " COUNT(m.message_id) AS messages"
                " FROM conversations c LEFT JOIN messages m"
                "   ON m.conversation_id = c.conversation_id AND m.role = 'assistant'"
                " GROUP BY c.usecase_id"
            ).fetchall()
        return [dict(r) for r in rows]

    def analytics_daily(self, days: int = 14) -> list[dict]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS messages"
                " FROM messages WHERE role = 'assistant'"
                " GROUP BY day ORDER BY day DESC LIMIT ?",
                (days,),
            ).fetchall()
        return [dict(r) for r in rows]

    def analytics_not_found(self, limit: int = 50) -> list[dict]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT actor, detail_json, created_at FROM audit_log"
                " WHERE action = 'knowledge_not_found' ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "actor": r["actor"],
                "query": json.loads(r["detail_json"]).get("query", ""),
                "usecase": json.loads(r["detail_json"]).get("usecase", ""),
                "at": r["created_at"],
            }
            for r in rows
        ]

    def analytics_by_department(self) -> list[dict]:
        """Cost attribution: usage grouped by the caller's department."""
        with self._session() as conn:
            rows = conn.execute(
                "SELECT COALESCE(e.department, 'unknown') AS department,"
                " COUNT(DISTINCT c.conversation_id) AS conversations,"
                " COUNT(m.message_id) AS messages,"
                " COALESCE(SUM(json_extract(m.usage_json,'$.total_tokens')),0) AS tokens,"
                " COALESCE(SUM(json_extract(m.usage_json,'$.estimated_cost_usd')),0) AS cost_usd"
                " FROM conversations c"
                " LEFT JOIN employees e ON e.employee_id = c.user_id"
                " LEFT JOIN messages m ON m.conversation_id = c.conversation_id"
                "   AND m.role = 'assistant'"
                " GROUP BY department"
            ).fetchall()
        return [dict(r) for r in rows]

    def analytics_funnel(self) -> dict:
        """Adoption funnel: active users → conversations → messages → feedback."""
        with self._session() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT c.user_id) AS users,"
                " COUNT(DISTINCT c.conversation_id) AS conversations,"
                " (SELECT COUNT(*) FROM messages WHERE role='user') AS user_messages,"
                " (SELECT COUNT(*) FROM feedback) AS feedback"
                " FROM conversations c"
            ).fetchone()
        return dict(row)

    def analytics_unmet_needs(self, limit: int = 10) -> list[dict]:
        """Cluster not-found queries by shared dominant term — the content-gap
        signal for knowledge managers."""
        queries = [r["query"].lower() for r in self.analytics_not_found(limit=200)]
        stop = {
            "the", "a", "an", "how", "do", "i", "to", "is", "what", "my", "can",
            "for", "of", "in", "on", "and", "me", "it", "does", "are", "there",
            "get", "you", "we", "this", "that", "when", "where", "why",
        }
        clusters: dict[str, list[str]] = {}
        for q in queries:
            terms = [t for t in q.split() if t not in stop and len(t) > 3]
            for t in terms:
                clusters.setdefault(t, []).append(q)
        ranked = sorted(
            (
                {"term": t, "count": len(qs), "sample_queries": sorted(set(qs))[:3]}
                for t, qs in clusters.items()
            ),
            key=lambda c: -c["count"],
        )
        return [c for c in ranked if c["count"] > 1][:limit]

    def department_documents(self, department: str) -> list[dict]:
        """Distinct documents carrying this department's metadata — title/ACL
        live on chunks, so aggregate to one row per document."""
        with self._session() as conn:
            rows = conn.execute(
                "SELECT document_id AS doc_id, title, department, acl_json AS acl,"
                " version, source_system"
                " FROM chunks WHERE department = ? GROUP BY document_id"
                " ORDER BY doc_id",
                (department,),
            ).fetchall()
        return [dict(r) for r in rows]

    def usecase_usage(self, usecase_id: str) -> dict:
        with self._session() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT c.conversation_id) AS conversations,"
                " COUNT(m.message_id) AS messages"
                " FROM conversations c LEFT JOIN messages m"
                "   ON m.conversation_id = c.conversation_id AND m.role = 'assistant'"
                " WHERE c.usecase_id = ?",
                (usecase_id,),
            ).fetchone()
        return dict(row)

    def analytics_feedback_recent(self, limit: int = 20) -> list[dict]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT rating, reason, comment, created_at FROM feedback"
                " ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

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
