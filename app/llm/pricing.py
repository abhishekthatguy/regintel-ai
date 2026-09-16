"""Token cost estimates per generation model (USD per 1K tokens).
Local/stub is free; cloud rates let `estimated_cost_usd` carry real numbers
when a provider is configured. Rates are approximations for demo reporting —
finance-grade attribution comes from Bedrock usage metadata in cloud mode."""

MODEL_PRICING: dict[str, dict[str, float]] = {
    # id substring -> {input, output} per 1K tokens
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5": {"input": 0.0008, "output": 0.004},
    "nova-pro": {"input": 0.0008, "output": 0.0032},
}


def estimate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    for key, rate in MODEL_PRICING.items():
        if key in model_id:
            return round(
                prompt_tokens * rate["input"] / 1000
                + completion_tokens * rate["output"] / 1000,
                6,
            )
    return 0.0
