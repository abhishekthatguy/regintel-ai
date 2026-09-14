from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    generation: str = "stub"
    enrichment: str | None = None
    embedding: str = "local"
    rerank: str = "simple"


class ToolConfig(BaseModel):
    name: str
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class FilterConfig(BaseModel):
    department: str | None = None
    allowed_sources: list[str] = Field(default_factory=list)


class GuardrailConfig(BaseModel):
    input_checks: list[str] = Field(default_factory=list)
    output_checks: list[str] = Field(default_factory=list)


class CostTags(BaseModel):
    department: str | None = None
    usecase: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class UseCaseConfig(BaseModel):
    """Versioned assistant configuration (FR-03). Loaded from YAML locally,
    DynamoDB USECASE partition in Phase 3."""

    tenant_id: str = "default"
    usecase_id: str
    name: str
    description: str = ""
    version: int = 1
    department: str | None = None
    system_prompt: str = "You are RegIntel AI, an enterprise knowledge and operations assistant."
    models: ModelConfig = Field(default_factory=ModelConfig)
    tools: list[ToolConfig] = Field(default_factory=list)
    filters: FilterConfig = Field(default_factory=FilterConfig)
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    cost_tags: CostTags = Field(default_factory=CostTags)

    def enabled_tools(self) -> list[str]:
        return [t.name for t in self.tools if t.enabled]
