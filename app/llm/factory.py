import os
from functools import lru_cache

from app.llm.base import ChatModel
from app.llm.local import LocalChatModel


@lru_cache
def get_chat_model() -> ChatModel:
    """Provider selected by REGINTEL_LLM_PROVIDER (default: local deterministic).
    Bedrock/OpenAI implementations plug in here in Phase 3."""
    provider = os.getenv("REGINTEL_LLM_PROVIDER", "local")
    if provider != "local":
        # Phase 3: instantiate the configured provider. Until then fall back
        # to local so the demo never breaks on missing credentials.
        pass
    return LocalChatModel()
