import re
from typing import Any

from app.llm.base import (
    INTENT_CANCEL,
    INTENT_CONFIRM,
    INTENT_DIRECT,
    INTENT_KNOWLEDGE,
    INTENT_TICKET_CREATE,
    INTENT_TICKET_LOOKUP,
)

CONFIRM_WORDS = {"yes", "y", "confirm", "confirmed", "proceed", "ok", "okay", "sure", "go ahead"}
CANCEL_WORDS = {"no", "n", "cancel", "stop", "nevermind", "never mind", "abort", "don't"}

CATEGORY_KEYWORDS = {
    "vpn": {"vpn", "securelink", "remote access"},
    "hardware": {
        "laptop", "battery", "keyboard", "monitor", "hardware",
        "screen", "computer", "mouse", "headset",
    },
    "software": {"software", "install", "application", "app", "license", "excel", "vscode"},
    "access": {"access", "permission", "permissions", "role", "rights", "folder", "workspace", "shared"},
    "network": {"wifi", "wi-fi", "network", "internet", "ethernet", "connection"},
    "email": {"email", "outlook", "mail", "mailbox", "phishing"},
    "account": {"password", "account", "login", "locked", "lockout", "mfa", "credentials"},
}

PRIORITY_KEYWORDS = {
    "urgent": {"urgent", "emergency", "critical", "asap", "immediately", "down"},
    "high": {"high", "important", "soon", "blocking"},
    "low": {"low", "whenever", "minor"},
}

TICKET_CREATE_RE = re.compile(
    r"\b(create|open|raise|file|submit|log|new)\b.*\b(ticket|issue|request|incident)\b"
    r"|\b(ticket|issue|request|incident)\b.*\b(create|open|raise|file|submit|new)\b",
    re.IGNORECASE,
)
TICKET_LOOKUP_RE = re.compile(
    r"\b(ticket|tickets)\b.*\b(status|show|list|check|where|progress|update)\b"
    r"|\b(status|show|list|check|my)\b.*\b(ticket|tickets)\b"
    r"|\bTCK-\d+\b|\bmy (open )?tickets\b",
    re.IGNORECASE,
)
DIRECT_RE = re.compile(
    r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|thanks|thank you|bye|help)\b",
    re.IGNORECASE,
)
FOLLOWUP_RE = re.compile(r"^(what about|how about|and for|and what|what if|also)", re.IGNORECASE)


class LocalChatModel:
    """Deterministic stand-in for the LLM: rule-based intent classification
    and extractive grounded generation. Zero external calls — the demo and
    rubric suite are fully reproducible. Swap via REGINTEL_LLM_PROVIDER."""

    model_id = "local-deterministic"

    # --- classification -------------------------------------------------

    def classify(self, message: str, context: dict[str, Any]) -> str:
        pending = context.get("pending_action")
        if pending:
            if self._is_confirm(message):
                return INTENT_CONFIRM
            if self._is_cancel(message):
                return INTENT_CANCEL
            if pending.get("awaiting_confirmation"):
                # Unrecognized reply while awaiting confirmation: re-ask.
                return INTENT_CONFIRM if self._is_confirm(message) else "reconfirm"
            return INTENT_TICKET_CREATE  # treat as field collection
        if TICKET_LOOKUP_RE.search(message):
            return INTENT_TICKET_LOOKUP
        if TICKET_CREATE_RE.search(message):
            return INTENT_TICKET_CREATE
        if DIRECT_RE.match(message):
            return INTENT_DIRECT
        return INTENT_KNOWLEDGE

    @staticmethod
    def _is_confirm(message: str) -> bool:
        return message.strip().lower().rstrip("!.") in CONFIRM_WORDS

    @staticmethod
    def _is_cancel(message: str) -> bool:
        return message.strip().lower().rstrip("!.") in CANCEL_WORDS

    # --- field extraction -----------------------------------------------

    def extract_fields(self, message: str, fields: dict[str, Any]) -> dict[str, Any]:
        merged = dict(fields)
        lowered = message.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                merged["category"] = category
                break
        for priority, keywords in PRIORITY_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                merged["priority"] = priority
                break
        # Treat a free-text message as the description when one is missing.
        if "description" not in merged and not self._looks_like_command(message):
            merged["description"] = message.strip()
        elif "description" not in merged:
            # Strip the command words; keep the substance as description.
            desc = TICKET_CREATE_RE.sub("", message).strip(" .:-")
            desc = re.sub(r"^(for|to|about|regarding|that)\s+", "", desc)
            if len(desc) >= 15:
                merged["description"] = desc
        return merged

    @staticmethod
    def _looks_like_command(message: str) -> bool:
        return bool(TICKET_CREATE_RE.search(message) or TICKET_LOOKUP_RE.search(message))

    # --- generation -----------------------------------------------------

    def generate_grounded(
        self, evidence: list[dict[str, Any]], language: str = "en"
    ) -> str:
        """Extractive grounded answer: every claim comes from a retrieved
        chunk, each tagged with its citation marker (FR-15 contract).
        Non-English requests are recorded and surfaced honestly — real
        translation needs a cloud LLM (Bedrock model path)."""
        parts = ["Here's what I found in the approved knowledge base:\n"]
        for i, item in enumerate(evidence, start=1):
            chunk = item["chunk"]
            parts.append(f"**{chunk['title']} — {chunk['section']}** [c{i}]\n{chunk['text']}\n")
        parts.append("Let me know if you'd like me to create a ticket for anything unresolved.")
        if language != "en":
            parts.append(
                f"\n_(requested language: {language} — this deployment's local model "
                "responds in English; a cloud LLM would translate with citations preserved)_"
            )
        return "\n".join(parts)

    def respond(self, template_key: str, **kwargs: Any) -> str:
        return TEMPLATES[template_key].format(**kwargs)


TEMPLATES = {
    "greeting": (
        "Hi {name}! I can answer questions from approved knowledge, check your "
        "ticket status, or create a support ticket. What do you need?"
    ),
    "clarify": (
        "I can create that ticket — I still need: {missing}. "
        "Please provide it and I'll continue."
    ),
    "confirm": (
        "I'll create a **{priority}** priority **{category}** ticket:\n"
        "> {description}\n\nConfirm? (yes/no)"
    ),
    "reconfirm": "Please reply **yes** to create the ticket or **no** to cancel.",
    "created": (
        "Done — ticket **{ticket_id}** created ({category}, {priority} priority). "
        "The support team will pick it up. Anything else?"
    ),
    "cancelled": "Okay, I've cancelled that. No ticket was created.",
    "duplicate": (
        "You already have an open {category} ticket: **{ticket_id}** "
        "({status}, {priority} priority) — “{description}”. "
        "I've reused it instead of creating a duplicate."
    ),
    "ticket_list": "{lines}",
    "ticket_none": "You have no {scope}tickets on record.",
    "not_found": (
        "I couldn't find evidence for that in the approved knowledge base, so I "
        "won't guess. You can ask me to create a support ticket and a human "
        "will pick it up."
    ),
    "refusal": (
        "I can't help with that request. I can answer questions about approved "
        "knowledge topics or help with IT tickets."
    ),
    "tool_error": (
        "Sorry — the {tool} system isn't responding right now. Please try again "
        "in a moment; I haven't guessed or made anything up."
    ),
    "tool_disabled": (
        "That capability isn't enabled for this use case. "
        "I can help with: {available}."
    ),
    "error": "Something went wrong on my side. Please try again.",
}
