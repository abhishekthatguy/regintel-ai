"""DynamoDBStore against moto-mocked DynamoDB — no AWS account needed.
Covers the full SQLiteStore surface parity: conversations, tickets,
chunks, feedback, jobs, audit, analytics."""

from datetime import datetime

import pytest

moto = pytest.importorskip("moto")

from moto import mock_aws  # noqa: E402

from app.schemas.conversation import (  # noqa: E402
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
)
from app.stores.dynamodb import BackendNotConfiguredError, DynamoDBStore  # noqa: E402


@pytest.fixture
def store():
    with mock_aws():
        s = DynamoDBStore(table_prefix="regintel-test", region="us-east-1")
        s.init_schema()
        yield s


def _conv(cid: str, user: str = "e001", ts: str = "2025-01-01T10:00:00+00:00") -> Conversation:
    return Conversation(
        conversation_id=cid,
        user_id=user,
        title="test",
        usecase_id="it_support",
        usecase_version=1,
        status=ConversationStatus.ACTIVE,
        created_at=datetime.fromisoformat(ts),
        updated_at=datetime.fromisoformat(ts),
    )


def _msg(mid: str, cid: str, role: MessageRole, content: str, ts: str) -> Message:
    return Message(
        message_id=mid,
        conversation_id=cid,
        role=role,
        content=content,
        created_at=datetime.fromisoformat(ts),
    )


def test_schema_and_ping(store):
    assert store.ping() is True


def test_conversation_message_roundtrip(store):
    store.create_conversation(_conv("c1"))
    store.add_message(_msg("m1", "c1", MessageRole.USER, "hi", "2025-01-01T10:00:01+00:00"))
    store.add_message(_msg("m2", "c1", MessageRole.ASSISTANT, "answer", "2025-01-01T10:00:02+00:00"))

    conv = store.get_conversation("c1")
    assert conv.conversation_id == "c1"
    assert conv.user_id == "e001"
    assert [m.message_id for m in conv.messages] == ["m1", "m2"]
    assert conv.messages[1].content == "answer"

    # updated_at bubbled up to the latest message ts
    assert conv.updated_at.isoformat() == "2025-01-01T10:00:02+00:00"

    # point lookup via GSI
    msg = store.get_message("m2")
    assert msg is not None and msg.conversation_id == "c1"


def test_get_conversation_missing_returns_none(store):
    assert store.get_conversation("nope") is None
    assert store.get_message("nope") is None


def test_list_conversations_ordered_by_updated(store):
    store.create_conversation(_conv("old", ts="2025-01-01T09:00:00+00:00"))
    store.create_conversation(_conv("new", ts="2025-01-02T09:00:00+00:00"))
    store.create_conversation(_conv("other-user", user="e002"))
    convs = store.list_conversations("e001")
    assert [c.conversation_id for c in convs] == ["new", "old"]


def test_conversation_title_and_status(store):
    store.create_conversation(_conv("c1"))
    store.update_conversation_title("c1", "renamed")
    assert store.get_conversation("c1").title == "renamed"
    store.set_conversation_status("c1", "archived")
    assert store.get_conversation("c1").status == ConversationStatus.ARCHIVED
    assert store.list_conversations("e001") == []  # archived filtered out


def test_tickets_roundtrip_and_dedupe(store):
    tid = store.next_ticket_id()
    assert tid == "TCK-1001"
    ticket = {
        "ticket_id": tid, "employee_id": "e001", "category": "vpn",
        "description": "vpn down", "status": "open", "priority": "high",
        "created_at": "2025-01-01T10:00:00+00:00",
        "updated_at": "2025-01-01T10:00:00+00:00",
    }
    store.create_ticket(ticket)
    assert store.next_ticket_id() == "TCK-1002"  # atomic counter, not a scan

    tickets = store.list_tickets("e001")
    assert len(tickets) == 1 and tickets[0]["ticket_id"] == tid
    assert store.list_tickets("e001", open_only=True)[0]["category"] == "vpn"
    assert store.list_tickets("e999") == []

    dup = store.find_duplicate_ticket("e001", "vpn")
    assert dup["ticket_id"] == tid
    assert store.find_duplicate_ticket("e001", "hardware") is None


def test_feedback(store):
    fb = {
        "feedback_id": "f1", "message_id": "m1", "conversation_id": "c1",
        "user_id": "e001", "rating": "up", "reason": None, "comment": "good",
        "correlation_id": None, "created_at": "2025-01-01T10:05:00+00:00",
    }
    store.add_feedback(fb)
    recent = store.analytics_feedback_recent()
    assert recent[0]["rating"] == "up" and recent[0]["comment"] == "good"


def test_chunks_checksum_reingestion(store):
    from app.retrieval.corpus import Chunk

    chunk = Chunk(
        chunk_id="ch1", document_id="KB-IT-001", title="VPN Guide",
        section="Overview", text="connect via SecureLink", department="IT",
        acl=["it"], version="1", source_system="local_files",
        source_ref="data/knowledge/it/vpn.md", source_url="",
    )
    store.replace_document_chunks("KB-IT-001", [chunk], {"ch1": [0.1, 0.2]}, "abc123")

    assert store.document_checksum("KB-IT-001") == "abc123"
    chunks = store.all_chunks()
    assert len(chunks) == 1 and chunks[0].title == "VPN Guide"
    assert chunks[0].acl == ["it"]
    assert store.chunk_vectors() == {"ch1": [0.1, 0.2]}

    # re-ingest replaces, doesn't duplicate
    store.replace_document_chunks("KB-IT-001", [chunk], {"ch1": [0.3]}, "def456")
    assert len(store.all_chunks()) == 1
    assert store.chunk_vectors() == {"ch1": [0.3]}
    assert store.document_checksum("KB-IT-001") == "def456"

    docs = store.department_documents("IT")
    assert docs[0]["doc_id"] == "KB-IT-001" and docs[0]["title"] == "VPN Guide"
    assert store.department_documents("HR") == []


def test_ingestion_jobs(store):
    store.create_ingestion_job(
        {"job_id": "j1", "source": "local_files", "status": "running",
         "started_at": "2025-01-01T10:00:00+00:00"}
    )
    store.add_ingestion_failure("j1", "KB-IT-099", "bad yaml")
    store.finish_ingestion_job("j1", "completed", ingested=5, failed=1)

    job = store.get_ingestion_job("j1")
    assert job["status"] == "completed" and job["ingested"] == 5
    assert job["finished_at"] is not None
    failures = store.ingestion_failures("j1")
    assert failures[0]["doc_id"] == "KB-IT-099"
    assert store.list_ingestion_jobs()[0]["job_id"] == "j1"
    assert store.get_ingestion_job("missing") is None


def test_audit_records(store):
    store.add_audit_record("e001", "ingestion_run", "j1", {"n": 3})
    store.add_audit_record("e002", "auth_failure", "expired", {})
    records = store.list_audit_records()
    assert len(records) == 2
    assert records[0]["created_at"] >= records[1]["created_at"]  # newest first
    assert records[1]["detail"] == {"n": 3}


def test_analytics(store):
    store.create_conversation(_conv("c1"))
    store.create_conversation(_conv("c2", ts="2025-01-02T09:00:00+00:00"))
    store.add_message(_msg("m1", "c1", MessageRole.USER, "hi", "2025-01-01T10:00:01+00:00"))
    store.add_message(_msg("m2", "c1", MessageRole.ASSISTANT, "ok", "2025-01-01T10:00:02+00:00"))

    summary = store.analytics_summary()
    assert summary["conversations"] == 2
    assert summary["assistant_messages"] == 1
    assert summary["tickets"] == 0

    by_uc = store.analytics_by_usecase()
    assert by_uc[0]["usecase_id"] == "it_support" and by_uc[0]["conversations"] == 2

    daily = store.analytics_daily()
    assert daily[0]["day"] == "2025-01-01" and daily[0]["messages"] == 1

    funnel = store.analytics_funnel()
    assert funnel == {"users": 1, "conversations": 2, "user_messages": 1, "feedback": 0}

    assert store.usecase_usage("it_support") == {"conversations": 2, "messages": 1}
    assert store.usecase_usage("hr_support") == {"conversations": 0, "messages": 0}


def test_unconfigured_store_fails_closed():
    s = DynamoDBStore()  # no prefix
    with pytest.raises(BackendNotConfiguredError):
        s.init_schema()
    with pytest.raises(BackendNotConfiguredError):
        s.list_tickets("e001")
