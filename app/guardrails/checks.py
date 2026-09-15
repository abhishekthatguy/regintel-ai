import re
from dataclasses import dataclass

INJECTION_PATTERNS = [
    r"ignore (all |any |previous |prior )?instructions",
    r"system prompt",
    r"you are now",
    r"forget (everything|your instructions)",
    r"reveal (your|the) (prompt|instructions)",
    r"<\s*/?\s*(system|tool|function)\s*>",
]

SENSITIVE_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN-like
    r"\b(?:\d[ -]*?){13,16}\b",  # card-like
    r"password\s*[:=]\s*\S+",
]

REFUSAL_MESSAGE = (
    "I can't help with that request. I can answer questions about approved "
    "knowledge topics or help with IT tickets."
)


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""
    message: str = REFUSAL_MESSAGE


def check_input(text: str) -> GuardrailResult:
    """Input guardrails (FR-18): local injection/sensitive-data patterns always
    run; when REGINTEL_GUARDRAIL_ID is configured, the Bedrock ApplyGuardrail
    API adds managed policies (injection, harmful content, PII, off-domain)."""
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return GuardrailResult(allowed=False, reason="prompt_injection")
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            return GuardrailResult(allowed=False, reason="sensitive_data")
    return _bedrock_guardrail(text, source="INPUT") or GuardrailResult(allowed=True)


def check_output(text: str) -> GuardrailResult:
    """Output guardrails: sensitive-data leakage check on generated text,
    plus the managed Bedrock guardrail when configured."""
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            return GuardrailResult(allowed=False, reason="output_sensitive_data")
    return _bedrock_guardrail(text, source="OUTPUT") or GuardrailResult(allowed=True)


def _bedrock_guardrail(text: str, source: str) -> GuardrailResult | None:
    """Managed Bedrock guardrail — only active when REGINTEL_GUARDRAIL_ID is
    set and boto3 + credentials exist. Fail-open locally (local patterns
    still ran); the cloud deploy treats a missing guardrail as a config bug."""
    import os

    guardrail_id = os.getenv("REGINTEL_GUARDRAIL_ID", "")
    if not guardrail_id:
        return None
    try:
        import boto3

        gid, _, version = guardrail_id.partition(":")
        client = boto3.client(
            "bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        resp = client.apply_guardrail(
            guardrailIdentifier=gid,
            guardrailVersion=version or "DRAFT",
            source=source,
            content=[{"text": {"text": text}}],
        )
        if resp.get("action") == "GUARDRAIL_INTERVENED":
            return GuardrailResult(allowed=False, reason="bedrock_guardrail")
    except Exception:
        return None  # local patterns remain the floor; don't break the path
    return None
