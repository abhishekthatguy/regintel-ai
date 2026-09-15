"""Bedrock chat model (FR-18): Claude Sonnet 4.5 generation / Haiku 4.5
enrichment via the Converse API. Config-resolved model ID with a fallback
list (OQ-05); when boto3/credentials are absent it delegates to
LocalChatModel so the local demo never breaks."""

import logging
import os
from typing import Any

from app.llm.local import LocalChatModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
FALLBACK_MODELS = [
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "amazon.nova-pro-v1:0",
]


class BedrockChatModel:
    """Implements the ChatModel contract. Generation calls go through the
    Bedrock Converse API; classify/extract_fields keep the deterministic
    local logic so routing stays testable offline."""

    def __init__(self, model_id: str = DEFAULT_MODEL):
        self.model_id = model_id
        self._fallback = LocalChatModel()
        try:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1")
            )
        except Exception:
            self._client = None
            logger.warning("bedrock unavailable — falling back to local model")

    @property
    def available(self) -> bool:
        return self._client is not None

    # Deterministic routing stays local — cheap, testable, no latency cost.
    def classify(self, message: str, context: dict[str, Any]) -> str:
        return self._fallback.classify(message, context)

    def extract_fields(self, message: str, fields: dict[str, Any]) -> dict[str, Any]:
        return self._fallback.extract_fields(message, fields)

    def respond(self, template: str, **kwargs) -> str:
        return self._fallback.respond(template, **kwargs)

    def generate_grounded(self, evidence: list[dict[str, Any]]) -> str:
        if not self._client:
            return self._fallback.generate_grounded(evidence)
        import json

        context = "\n\n".join(
            f"[{i}] {item['chunk']['title']} — {item['chunk']['section']}\n"
            f"{item['chunk']['text']}"
            for i, item in enumerate(evidence, 1)
        )
        resp = self._client.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": "Answer using ONLY this evidence; tag each "
                            f"claim with its [cN] marker.\n\n{context}"
                        }
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.0},
        )
        return resp["output"]["message"]["content"][0]["text"]

    def generate(self, messages: list[dict[str, str]]) -> str:
        if not self._client:
            return self._fallback.generate(messages)
        import json  # noqa: F401

        resp = self._client.converse(
            modelId=self.model_id,
            messages=[
                {"role": m["role"], "content": [{"text": m["content"]}]}
                for m in messages
            ],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.0},
        )
        return resp["output"]["message"]["content"][0]["text"]
