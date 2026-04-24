from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.agents import doc, enterprise_data, external_search
from app.protocol import AgentTaskResponse, DelegationEnvelope


AgentHandler = Callable[[DelegationEnvelope], Awaitable[AgentTaskResponse]]


AGENT_HANDLERS: dict[str, AgentHandler] = {
    "doc_agent": doc.handle_task,
    "enterprise_data_agent": enterprise_data.handle_task,
    "external_search_agent": external_search.handle_task,
}


def get_agent_handler(agent_id: str) -> AgentHandler | None:
    return AGENT_HANDLERS.get(agent_id)
