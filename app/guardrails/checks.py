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
    """Input guardrails (FR-18 subset): prompt-injection and sensitive-data
    patterns in user input. Bedrock guardrails replace/extend this in P3."""
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return GuardrailResult(allowed=False, reason="prompt_injection")
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            return GuardrailResult(allowed=False, reason="sensitive_data")
    return GuardrailResult(allowed=True)


def check_output(text: str) -> GuardrailResult:
    """Output guardrails: sensitive-data leakage check on generated text."""
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            return GuardrailResult(allowed=False, reason="output_sensitive_data")
    return GuardrailResult(allowed=True)
