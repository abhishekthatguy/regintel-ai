import os
from functools import lru_cache

from app.llm.base import ChatModel
from app.llm.local import LocalChatModel


@lru_cache
def get_chat_model() -> ChatModel:
    """Provider selected by REGINTEL_LLM_PROVIDER (default: local deterministic).
    "bedrock" selects BedrockChatModel (Sonnet 4.5 default, OQ-05 fallbacks);
    it self-degrades to LocalChatModel when boto3/credentials are absent."""
    provider = os.getenv("REGINTEL_LLM_PROVIDER", "local")
    if provider == "bedrock":
        from app.llm.bedrock import BedrockChatModel

        model_id = os.getenv("REGINTEL_LLM_MODEL_ID", "")
        return BedrockChatModel(model_id=model_id) if model_id else BedrockChatModel()
    return LocalChatModel()
