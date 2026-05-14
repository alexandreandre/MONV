"""Schémas Pydantic pour l'API Super Admin / agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BlockOverrideIn(BaseModel):
    """Override JSON pour un bloc LLM (clé = block_id)."""

    enabled: bool = True
    model: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class AgentVersionCreate(BaseModel):
    label: str = ""
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AgentVersionOut(BaseModel):
    id: str
    agent_id: str
    version_number: int
    label: str
    overrides_json: dict[str, Any]
    created_by: str | None
    created_at: datetime
    is_active: bool
    parent_version_id: str | None = None


class AgentSummaryOut(BaseModel):
    agent_id: str
    label: str
    active_version_id: str | None = None
    active_version_number: int | None = None
    last_modified_at: datetime | None = None
    primary_model: str = ""
    errors_24h: int = 0
    runs_7d: int = 0


class AgentGraphOut(BaseModel):
    agent_id: str
    label: str
    graph: dict[str, Any]
    active_version: AgentVersionOut | None = None


class AdminMeOut(BaseModel):
    is_admin: bool = True
    email: str


class AdminSettingsOut(BaseModel):
    models: dict[str, str]
    api_keys_present: dict[str, bool]
    flags: dict[str, bool]


class AgentTestRequest(BaseModel):
    message: str = "Je cherche des PME du BTP à Lyon"
    full_pipeline: bool = False


class AgentTestResponse(BaseModel):
    run_id: str
    status: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
