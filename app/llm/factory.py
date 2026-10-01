import os
from functools import lru_cache

from app.llm.base import ChatModel
from app.llm.local import LocalChatModel


@lru_cache
def get_chat_model() -> ChatModel:
    """Provider selected by REGINTEL_LLM_PROVIDER (default: local deterministic).

    - "bedrock": BedrockChatModel (Converse API; needs AWS credentials)
    - "hf":      HFChatModel (HF Inference Providers; needs REGINTEL_HF_TOKEN,
                 model via REGINTEL_HF_MODEL — Llama-3.1-8B default)

    Every provider self-degrades to LocalChatModel when its credentials are
    absent, so the local demo and eval suite always run offline.
    """
    from app.settings import get_settings

    settings = get_settings()
    provider = settings.llm_provider
    if provider == "bedrock":
        from app.llm.bedrock import BedrockChatModel

        model_id = os.getenv("REGINTEL_LLM_MODEL_ID", "")
        return BedrockChatModel(model_id=model_id) if model_id else BedrockChatModel()
    if provider == "hf":
        from app.llm.hf import HFChatModel

        return HFChatModel(model_id=settings.hf_model)
    return LocalChatModel()
