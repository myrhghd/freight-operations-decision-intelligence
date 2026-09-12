from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Text must contain a non-whitespace character")
    return value


# Keep whitespace validation local: Ollama 0.12.3 rejects the unanchored
# regex pattern in the structured output schema.
NonEmptyText = Annotated[str, StringConstraints(min_length=1), AfterValidator(_require_nonblank)]


class LLMEvidence(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    evidence_id: NonEmptyText
    source: NonEmptyText
    text: NonEmptyText


class SOPGenerationRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    question: NonEmptyText
    evidence: list[LLMEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_evidence_ids(self) -> "SOPGenerationRequest":
        ids = [item.evidence_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Evidence IDs must be unique")
        return self


class SOPGenerationResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    answer: Annotated[NonEmptyText, StringConstraints(max_length=1200)]
    cited_evidence_ids: list[NonEmptyText] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_citations(self) -> "SOPGenerationResult":
        if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
            raise ValueError("Cited evidence IDs must be unique")
        return self
