from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str


class ErrorBody(StrictModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(StrictModel):
    error: ErrorBody


class EngineeringGroup(StrictModel):
    group_id: str = Field(min_length=1)
    engineering_description: str = Field(min_length=1, max_length=500)


class EngineeringGroupExtraction(StrictModel):
    engineering_groups: list[EngineeringGroup] = Field(min_length=1, max_length=20)


class EngineeringType(StrictModel):
    type_id: str = Field(min_length=1)
    type_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    enabled: bool = True


class MatchCandidate(StrictModel):
    type_id: str
    type_name: str
    match_score: int = Field(ge=0, le=100)
    above_threshold: bool
    matched_keywords: list[str] = Field(default_factory=list)


class EngineeringCandidateGroup(StrictModel):
    group_id: str
    engineering_description: str
    candidates: list[MatchCandidate]
    network_fallback_required: bool


class IntentMatchRequest(StrictModel):
    session_id: str | None = Field(default=None, max_length=100)
    employee_input: str = Field(min_length=1, max_length=2000)


class IntentMatchResponse(StrictModel):
    request_id: str
    top_k: int
    match_threshold: int
    engineering_groups: list[EngineeringCandidateGroup]


class IntentSelection(StrictModel):
    group_id: str = Field(min_length=1)
    type_id: str | None = None
    use_network_fallback: bool = False

    @model_validator(mode="after")
    def validate_choice(self) -> "IntentSelection":
        if bool(self.type_id) == self.use_network_fallback:
            raise ValueError("type_id与use_network_fallback必须且只能选择一个")
        return self


class IntentConfirmRequest(StrictModel):
    request_id: str = Field(min_length=1)
    selections: list[IntentSelection] = Field(min_length=1)


class ConfirmedEngineeringType(StrictModel):
    group_id: str
    type_id: str | None = None
    type_name: str | None = None
    use_network_fallback: bool = False
    search_query: str | None = None


class IntentConfirmResponse(StrictModel):
    request_id: str
    confirmed_types: list[ConfirmedEngineeringType]
    next_action: Literal["retrieve", "network_fallback", "mixed_retrieve"]


class IssueReportRequest(StrictModel):
    request_id: str | None = None
    issue_type: Literal["missing_engineering_type"] = "missing_engineering_type"
    missing_type_name: str = Field(min_length=1, max_length=200)
    employee_description: str = Field(min_length=1, max_length=2000)
    original_input: str | None = Field(default=None, max_length=2000)


class IssueReportResponse(StrictModel):
    report_id: str
    status: Literal["pending"] = "pending"
    message: str


class KnowledgeRetrieveRequest(StrictModel):
    request_id: str = Field(min_length=1)
    allow_network_fallback: bool = True


class KnowledgeItem(StrictModel):
    document_id: str
    group_id: str
    type_id: str | None = None
    type_name: str
    title: str
    content: str
    source_type: Literal["local", "network"]
    source_name: str
    source_version: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    warning: str | None = None


class MissingKnowledgeItem(StrictModel):
    group_id: str
    type_id: str | None = None
    type_name: str | None = None
    search_query: str
    reason: str


class KnowledgeRetrieveResponse(StrictModel):
    request_id: str
    status: Literal["ready", "fallback_required"]
    output_mode: Literal["direct", "compose", "unavailable"]
    contains_external_content: bool
    items: list[KnowledgeItem]
    missing_items: list[MissingKnowledgeItem]


class ComposeRequest(StrictModel):
    request_id: str = Field(min_length=1)


class ComposeResponse(StrictModel):
    request_id: str
    status: Literal["success", "degraded"]
    output_mode: Literal["composed", "separate"]
    content: str | None = None
    items: list[KnowledgeItem] = Field(default_factory=list)
    contains_external_content: bool
    warnings: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class CapabilitiesResponse(StrictModel):
    top_k: int
    match_threshold: int
    judge_model_provider: str
    compose_model_provider: str
    knowledge_provider: str
    network_search_enabled: bool
    network_search_provider: str
    multi_project_compose_enabled: bool
    issue_report_enabled: bool
