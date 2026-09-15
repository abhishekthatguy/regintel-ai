from typing import Any, Protocol

# Intent labels shared by classifier and graph routing.
INTENT_KNOWLEDGE = "knowledge_query"
INTENT_TICKET_LOOKUP = "ticket_lookup"
INTENT_TICKET_CREATE = "ticket_create"
INTENT_DIRECT = "direct"
INTENT_CONFIRM = "confirm"
INTENT_CANCEL = "cancel"


class ChatModel(Protocol):
    """Model interface behind which real providers (Bedrock Claude, etc.)
    plug in via REGINTEL_LLM_PROVIDER. The local implementation is
    deterministic — no external calls — so the demo runs fully offline."""

    model_id: str

    def classify(self, message: str, context: dict[str, Any]) -> str: ...

    def extract_fields(self, message: str, fields: dict[str, Any]) -> dict[str, Any]: ...

    def generate_grounded(
        self, evidence: list[dict[str, Any]], language: str = "en"
    ) -> str: ...

    def respond(self, template_key: str, **kwargs: Any) -> str: ...
