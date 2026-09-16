"""FR-16 query rewriting: short/anaphoric follow-ups ("what about the card
limit?") are expanded with conversation context before retrieval. Local
rewriter is deterministic; the Bedrock path delegates to Haiku when
credentials exist (models.enrichment in use-case config)."""

import re
from typing import Any, Protocol

FOLLOWUP_RE = re.compile(r"^(what about|how about|and for|and what|what if|also)", re.IGNORECASE)


class QueryRewriter(Protocol):
    def rewrite(self, query: str, context: dict[str, Any]) -> str: ...


class LocalQueryRewriter:
    """Expand a follow-up with the last retrieval topic + the previous user
    turn — enough for the deterministic pipeline to stay grounded."""

    def rewrite(self, query: str, context: dict[str, Any]) -> str:
        needs_context = FOLLOWUP_RE.match(query) or len(query.split()) <= 3
        if not needs_context:
            return query
        parts = []
        if context.get("last_topic"):
            parts.append(context["last_topic"])
        history = context.get("history") or []
        prev_user = next(
            (m["content"] for m in reversed(history) if m.get("role") == "user"), None
        )
        if prev_user and prev_user != query:
            parts.append(prev_user[:120])
        return " ".join(parts + [query]) if parts else query


class HaikuQueryRewriter:
    """Bedrock Haiku rewrite — real paraphrase/context expansion when a
    client is configured; falls back to local otherwise."""

    def __init__(self, model=None):
        self._model = model
        self._local = LocalQueryRewriter()

    def rewrite(self, query: str, context: dict[str, Any]) -> str:
        if not self._model or not getattr(self._model, "available", False):
            return self._local.rewrite(query, context)
        # Real path: single cheap Haiku call producing a standalone query.
        prompt = (
            "Rewrite the follow-up question as a standalone search query "
            f"using the topic.\nTopic: {context.get('last_topic','')}\n"
            f"Question: {query}\nStandalone query:"
        )
        try:
            return self._model.generate([{"role": "user", "content": prompt}]).strip() or query
        except Exception:
            return self._local.rewrite(query, context)


def get_rewriter(configured: str | None = None, model=None) -> QueryRewriter:
    if configured and configured != "local":
        return HaikuQueryRewriter(model)
    return LocalQueryRewriter()
