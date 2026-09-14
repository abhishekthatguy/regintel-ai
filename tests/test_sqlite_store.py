import pytest

from app.schemas.conversation import Conversation, Message, MessageRole
from app.stores.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "test.db")
    s.init_schema()
    return s


def test_conversation_roundtrip(store):
    conv = Conversation(user_id="e001", usecase_id="it_support", title="Test")
    store.create_conversation(conv)
    loaded = store.get_conversation(conv.conversation_id)
    assert loaded is not None
    assert loaded.user_id == "e001"
    assert loaded.title == "Test"


def test_messages_roundtrip_ordered(store):
    conv = store.create_conversation(Conversation(user_id="e001", usecase_id="it_support"))
    store.add_message(Message(conversation_id=conv.conversation_id, role=MessageRole.USER, content="hi"))
    store.add_message(
        Message(conversation_id=conv.conversation_id, role=MessageRole.ASSISTANT, content="hello")
    )
    loaded = store.get_conversation(conv.conversation_id)
    assert [m.role for m in loaded.messages] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert loaded.messages[1].content == "hello"


def test_list_conversations_scoped_to_user(store):
    store.create_conversation(Conversation(user_id="e001", usecase_id="it_support"))
    store.create_conversation(Conversation(user_id="e002", usecase_id="it_support"))
    assert len(store.list_conversations("e001")) == 1
    assert len(store.list_conversations("e002")) == 1
    assert len(store.list_conversations("e999")) == 0


def test_get_missing_returns_none(store):
    assert store.get_conversation("nope") is None


def test_ping(store):
    assert store.ping() is True
