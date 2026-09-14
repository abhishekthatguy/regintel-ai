import pytest
from pydantic import ValidationError

from app.schemas.config import UseCaseConfig
from app.schemas.conversation import (
    Citation,
    Conversation,
    Message,
    MessageRole,
    SendMessageRequest,
)
from app.schemas.events import EventType, StreamEvent


def test_usecase_defaults():
    config = UseCaseConfig(usecase_id="x", name="X")
    assert config.version == 1
    assert config.tenant_id == "default"
    assert config.enabled_tools() == []


def test_message_requires_content():
    with pytest.raises(ValidationError):
        Message(conversation_id="c1", role=MessageRole.USER)


def test_citation_minimal_contract():
    c = Citation(citation_id="c1", document_id="d1", title="Doc", source_system="local_files")
    assert c.access_granted is True
    assert c.retrieval_score is None


def test_send_message_rejects_empty():
    with pytest.raises(ValidationError):
        SendMessageRequest(content="")


def test_stream_event_serializes_ndjson():
    event = StreamEvent(type=EventType.STATUS, data={"stage": "x"})
    line = event.to_ndjson()
    assert line.endswith("\n")
    assert '"type":"status"' in line


def test_conversation_defaults():
    c = Conversation(user_id="e001", usecase_id="it_support")
    assert c.status == "active"
    assert c.messages == []
