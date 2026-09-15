"""Genesys Cloud CX integration boundary (Phase 5, pending OQ-01).

Genesys is the enterprise agentic-AI/CX platform — it isn't a host, it's an
integration surface. Three realistic integration shapes:

1. **Agent Assist / copilot** — Genesys calls `POST /v1/integrations/genesys/
   suggest` with the customer utterance; we return a grounded suggestion +
   citations for the human agent. Stateless, lowest-risk — implemented here.
2. **Data Action** — agent flows call our REST endpoints (knowledge search,
   ticket create) with Genesys OAuth client credentials. Same API, just an
   OAuth-protected caller — no code change needed beyond JWT mode.
3. **Bot Connector** — Genesys bot turns proxy to our conversation API;
   requires a Genesys org + integration approval (enterprise dependency).

The standalone web/Streamlit path stays fully functional regardless —
integration is additive, never a hard dependency.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def suggest(ctx, utterance: str, top_k: int = 3) -> dict[str, Any]:
    """Agent-assist surface: run knowledge retrieval directly (no
    conversation persistence — assist calls are stateless). Returns a
    grounded suggestion with the full citation contract."""
    from app.tools.knowledge import KnowledgeSearchTool

    result = KnowledgeSearchTool(top_k=top_k).run(ctx, utterance)
    if not result["found"]:
        return {
            "suggestion": "No matching knowledge found — consider escalating.",
            "citations": [],
            "confidence": 0.0,
        }
    top = result["evidence"][0]
    return {
        "suggestion": top["chunk"]["text"][:500],
        "citations": [c.model_dump(mode="json") for c in result["citations"]],
        "confidence": top.get("rerank_score", 0.0),
    }
