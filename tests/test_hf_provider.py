"""HF provider: HFChatModel + HFEmbedder against mocked HTTP — token-gated
provider must degrade to the local model/embedder when unconfigured, and
use real calls when configured."""

from app.llm.base import INTENT_KNOWLEDGE, INTENT_TICKET_CREATE, OFFER_LINES
from app.llm.hf import HFChatModel
from app.retrieval.embeddings import HFEmbedder, get_embedder


def _mock_client(payload, monkeypatch_obj=None):
    """Build a fake httpx.Client whose .post returns payload."""

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **k):
            self.posts = []

        def post(self, url, json=None):
            self.posts.append((url, json))
            return _Resp()

    return _Client


def _chat_payload(text):
    return {"choices": [{"message": {"content": text}}]}


# --- availability / fallback ------------------------------------------------


def test_hf_model_unavailable_without_token(monkeypatch):
    monkeypatch.delenv("REGINTEL_HF_TOKEN", raising=False)
    m = HFChatModel(token="")
    assert not m.available
    # Falls back to deterministic local behavior.
    assert m.classify("show my tickets", {"pending_action": None}) != ""


def test_hf_embedder_unavailable_without_token(monkeypatch):
    monkeypatch.delenv("REGINTEL_HF_TOKEN", raising=False)
    e = HFEmbedder(token="")
    assert not e.available
    v = e.embed("vpn trouble")
    assert len(v) == 384  # hashing fallback vector


# --- classify / extraction via mocked API ------------------------------------


def test_hf_classify_parses_intent(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client", _mock_client(_chat_payload("ticket_create")))
    m = HFChatModel(token="hf_x")
    assert m.classify("open a ticket please", {}) == INTENT_TICKET_CREATE


def test_hf_classify_invalid_label_falls_back(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client", _mock_client(_chat_payload("gibberish")))
    m = HFChatModel(token="hf_x")
    assert m.classify("how do I connect to the vpn", {}) == INTENT_KNOWLEDGE


def test_hf_extract_fields_parses_json(monkeypatch):
    import httpx

    monkeypatch.setattr(
        httpx,
        "Client",
        _mock_client(_chat_payload('{"category": "vpn", "description": "vpn keeps dropping daily"}')),
    )
    m = HFChatModel(token="hf_x")
    fields = m.extract_fields("my vpn keeps dropping daily", {})
    assert fields["category"] == "vpn"
    assert "dropping" in fields["description"]


def test_hf_generate_grounded_appends_offer(monkeypatch):
    import httpx

    monkeypatch.setattr(
        httpx, "Client", _mock_client(_chat_payload("Use SecureLink for VPN access [c1]."))
    )
    m = HFChatModel(token="hf_x")
    out = m.generate_grounded(
        [{"chunk": {"title": "VPN", "section": "Overview", "text": "Use SecureLink."}}],
        offer="lookup",
        question="how do I get on vpn",
    )
    assert "[c1]" in out
    assert OFFER_LINES["lookup"] in out


def test_hf_generate_grounded_falls_back_on_http_error(monkeypatch):
    import httpx

    class _BadClient:
        def __init__(self, *a, **k):
            pass

        def post(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(httpx, "Client", _BadClient)
    m = HFChatModel(token="hf_x")
    out = m.generate_grounded(
        [{"chunk": {"title": "VPN", "section": "Overview", "text": "Use SecureLink."}}],
        question="vpn?",
    )
    assert "knowledge base" in out  # local extractive answer


def test_hf_respond_is_template_deterministic():
    """Write confirmations stay deterministic even with a live provider."""
    m = HFChatModel(token="")
    assert "Confirm" in m.respond("confirm", category="vpn", priority="high", description="x")


# --- embedder ----------------------------------------------------------------


def test_hf_embedder_uses_api_vector(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client", _mock_client([[0.5] * 384]))
    e = HFEmbedder(token="hf_x")
    v = e.embed("annual leave")
    assert v == [0.5] * 384


def test_hf_embedder_mean_pools_token_embeddings(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "Client", _mock_client([[[1.0] * 384, [3.0] * 384]]))
    e = HFEmbedder(token="hf_x")
    v = e.embed("leave")
    assert v == [2.0] * 384


def test_get_embedder_hf_selection(monkeypatch):
    from app.settings import get_settings

    monkeypatch.setenv("REGINTEL_EMBEDDER", "hf")
    monkeypatch.delenv("REGINTEL_HF_TOKEN", raising=False)
    get_settings.cache_clear()
    e = get_embedder("local")
    assert isinstance(e, HFEmbedder)
    assert e.model_id == HFEmbedder.DEFAULT_MODEL
    get_settings.cache_clear()


def test_factory_selects_hf_provider(monkeypatch):
    from app.llm.factory import get_chat_model
    from app.settings import get_settings

    monkeypatch.setenv("REGINTEL_LLM_PROVIDER", "hf")
    get_settings.cache_clear()
    get_chat_model.cache_clear()
    m = get_chat_model()
    assert isinstance(m, HFChatModel)
    get_chat_model.cache_clear()


def test_hf_usage_in_prompt_includes_question(monkeypatch):
    import httpx

    client_cls = _mock_client(_chat_payload("ok"))
    captured = []

    class _CapClient(client_cls):
        def post(self, url, json=None):
            captured.append(json)
            return super().post(url, json=json)

    monkeypatch.setattr(httpx, "Client", _CapClient)
    m = HFChatModel(token="hf_x")
    m.generate_grounded(
        [{"chunk": {"title": "T", "section": "S", "text": "body"}}],
        question="what about vpn",
    )
    assert captured[0]["messages"][-1]["content"] == "what about vpn"
