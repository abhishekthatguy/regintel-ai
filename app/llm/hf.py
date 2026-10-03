"""Hugging Face Inference Providers chat model (production LLM boundary).

OpenAI-compatible chat-completions endpoint — works with any instruct model
hosted on HF Inference Providers (Llama, Mistral, Qwen, ...).

    REGINTEL_LLM_PROVIDER=hf
    REGINTEL_HF_TOKEN=hf_...           # from hf.co/settings/tokens
    REGINTEL_HF_MODEL=meta-llama/Llama-3.1-8B-Instruct

Design: the LLM handles the *probabilistic* work (intent classification,
field extraction, grounded answer composition). Write confirmations,
clarify prompts, and refusals stay template-deterministic via the
LocalChatModel fallback — safety-critical text is never freeform. If the
token is absent or the API errors, every method degrades to the local
deterministic model so the deployed demo never breaks.
"""

import json
import logging
import re
from typing import Any

from app.llm.base import (
    INTENT_CANCEL,
    INTENT_CONFIRM,
    INTENT_CRM_CASE_CREATE,
    INTENT_CRM_LOOKUP,
    INTENT_DIRECT,
    INTENT_KNOWLEDGE,
    INTENT_TICKET_CREATE,
    INTENT_TICKET_LOOKUP,
    OFFER_LINES,
    is_cancellation,
    is_confirmation,
)
from app.llm.local import LocalChatModel

logger = logging.getLogger(__name__)

HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
TIMEOUT = 30.0

_INTENTS = (
    INTENT_KNOWLEDGE,
    INTENT_TICKET_LOOKUP,
    INTENT_TICKET_CREATE,
    INTENT_CRM_LOOKUP,
    INTENT_CRM_CASE_CREATE,
    INTENT_DIRECT,
    INTENT_CONFIRM,
    INTENT_CANCEL,
)

_CLASSIFY_PROMPT = """You are the intent classifier for an enterprise support assistant.
Classify the user's latest message into exactly one intent label.

Intents:
- knowledge_query: questions or statements about policies/how-to/facilities
- ticket_lookup: wants to see or check their support tickets
- ticket_create: wants to create/open/raise a support ticket or report an issue for fixing
- crm_lookup: wants to see or check CRM/customer cases
- crm_case_create: wants to create/open/log a CRM case
- direct: greeting, thanks, small talk, or asking what the assistant can do
- confirm: replying yes/ok/confirm to a pending action
- cancel: replying no/cancel/stop to a pending action

Context: pending_action={pending}
Reply with ONLY the intent label, nothing else."""

_EXTRACT_TICKET_PROMPT = """Extract ticket fields from the user's message as strict JSON.
Fields: category (one of: vpn, hardware, software, access, network, email,
account, other), priority (one of: low, medium, high, urgent),
description (the substantive issue text, min 15 chars).
Omit fields that are not present. Already-collected fields: {fields}
User message: {message}
Reply with ONLY the JSON object."""

_EXTRACT_CASE_PROMPT = """Extract CRM case fields from the user's message as strict JSON.
Fields: subject (short title, max 80 chars), description (the substantive
issue text), priority (one of: low, medium, high, urgent).
Omit fields that are not present. Already-collected fields: {fields}
User message: {message}
Reply with ONLY the JSON object."""

_GROUNDED_PROMPT = """{lang}You are RegIntel AI, an enterprise support assistant.
Answer the user's question using ONLY the evidence below. Tag every claim
with its citation marker [c1], [c2], ... matching the evidence index. If
the evidence does not contain the answer, say you could not find it —
never invent facts. Keep the answer concise and actionable.

Evidence:
{context}"""


class HFChatModel:
    """ChatModel implementation backed by Hugging Face Inference Providers."""

    def __init__(
        self,
        model_id: str | None = None,
        token: str | None = None,
        base_url: str = HF_CHAT_URL,
    ):
        from app.settings import get_settings

        settings = get_settings()
        self.model_id = model_id or settings.hf_model or DEFAULT_MODEL
        self._token = token if token is not None else settings.hf_token
        self._base_url = base_url
        self._fallback = LocalChatModel()
        self._client = None
        if self._token:
            import httpx

            self._client = httpx.Client(
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=TIMEOUT,
            )

    @property
    def available(self) -> bool:
        return self._client is not None

    def _chat(self, system: str, user: str, max_tokens: int = 512) -> str | None:
        """Single chat-completion call; None on any failure (caller falls back)."""
        if not self._client:
            return None
        try:
            resp = self._client.post(
                self._base_url,
                json={
                    "model": self.model_id,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning(
                "hf chat call failed; using local fallback",
                extra={"action": "hf_chat", "outcome": f"fallback:{exc}"},
            )
            return None

    @staticmethod
    def _json_block(text: str) -> dict[str, Any]:
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}

    # --- ChatModel contract ------------------------------------------------

    def classify(self, message: str, context: dict[str, Any]) -> str:
        pending = context.get("pending_action")
        # Cheap deterministic paths first — a pending write never needs an
        # LLM call, and bare yes/no with no pending is handled upstream.
        if pending:
            if is_confirmation(message):
                return INTENT_CONFIRM
            if is_cancellation(message):
                return INTENT_CANCEL
        # Greetings / capability questions are deterministic — an LLM label
        # of "knowledge_query" here would dump random docs into the reply.
        if self._fallback.classify(message, context) == INTENT_DIRECT:
            return INTENT_DIRECT
        if not self._client:
            return self._fallback.classify(message, context)
        out = self._chat(
            _CLASSIFY_PROMPT.format(pending=json.dumps(pending) if pending else "none"),
            message,
            max_tokens=8,
        )
        label = (out or "").strip().lower().strip("`'\". ")
        if label in _INTENTS:
            return label
        return self._fallback.classify(message, context)

    def extract_fields(self, message: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not self._client:
            return self._fallback.extract_fields(message, fields)
        out = self._chat(
            _EXTRACT_TICKET_PROMPT.format(fields=json.dumps(fields), message=message),
            message,
            max_tokens=128,
        )
        parsed = self._json_block(out or "")
        merged = {**fields, **parsed} if parsed else self._fallback.extract_fields(message, fields)
        return merged

    def extract_case_fields(self, message: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not self._client:
            return self._fallback.extract_case_fields(message, fields)
        out = self._chat(
            _EXTRACT_CASE_PROMPT.format(fields=json.dumps(fields), message=message),
            message,
            max_tokens=160,
        )
        parsed = self._json_block(out or "")
        merged = {**fields, **parsed} if parsed else self._fallback.extract_case_fields(message, fields)
        return merged

    def generate_grounded(
        self,
        evidence: list[dict[str, Any]],
        language: str = "en",
        offer: str = "create",
        question: str = "",
    ) -> str:
        if not self._client:
            return self._fallback.generate_grounded(
                evidence, language=language, offer=offer, question=question
            )
        context = "\n\n".join(
            f"[c{i}] {item['chunk']['title']} — {item['chunk'].get('section') or ''}\n"
            f"{item['chunk']['text']}"
            for i, item in enumerate(evidence, 1)
        )
        lang = f"Respond in language '{language}'. " if language != "en" else ""
        out = self._chat(
            _GROUNDED_PROMPT.format(lang=lang, context=context),
            question or "Summarize the evidence.",
            max_tokens=1024,
        )
        if not out:
            return self._fallback.generate_grounded(
                evidence, language=language, offer=offer, question=question
            )
        return f"{out}\n\n{OFFER_LINES.get(offer, OFFER_LINES['create'])}"

    def respond(self, template_key: str, **kwargs: Any) -> str:
        # Write confirmations, clarifications and refusals stay
        # template-deterministic — safety-critical text is never freeform.
        return self._fallback.respond(template_key, **kwargs)

    def generate(self, messages: list[dict[str, str]]) -> str:
        if not self._client:
            return self._fallback.generate(messages)
        try:
            resp = self._client.post(
                self._base_url,
                json={
                    "model": self.model_id,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return self._fallback.generate(messages)
