from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Capability = Literal[
    "report:write",
    "feishu.contact:read",
    "feishu.wiki:read",
    "feishu.bitable:read",
    "web.public:read",
]


class DelegationHop(BaseModel):
    from_actor: str
    to_agent_id: str
    task_type: str
    capabilities: list[Capability] = Field(default_factory=list)


class DelegationEnvelope(BaseModel):
    trace_id: str
    request_id: str
    caller_agent_id: str
    target_agent_id: str
    task_type: str
    requested_capabilities: list[Capability] = Field(default_factory=list)
    delegation_chain: list[DelegationHop] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentTaskRequest(BaseModel):
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentTaskResponse(BaseModel):
    agent_id: str
    trace_id: str
    task_type: str
    result: dict[str, Any]


class DelegationDecision(BaseModel):
    decision: Literal["allow", "deny"]
    reason: str
    effective_capabilities: list[Capability]


class AuditLog(BaseModel):
    id: int
    trace_id: str
    request_id: str
    caller_agent_id: str
    target_agent_id: str
    requested_capabilities: list[str]
    effective_capabilities: list[str]
    decision: str
    reason: str
    delegation_chain: list[dict[str, Any]]
    created_at: str
