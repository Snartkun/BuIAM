from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    name: str
    static_capabilities: frozenset[str]
    delegatable_capabilities: frozenset[str]


AGENTS: dict[str, AgentConfig] = {
    "doc_agent": AgentConfig(
        agent_id="doc_agent",
        name="飞书文档助手 Agent",
        static_capabilities=frozenset({"report:write"}),
        delegatable_capabilities=frozenset(
            {
                "report:write",
                "feishu.contact:read",
                "feishu.wiki:read",
                "feishu.bitable:read",
                "web.public:read",
            }
        ),
    ),
    "enterprise_data_agent": AgentConfig(
        agent_id="enterprise_data_agent",
        name="企业数据 Agent",
        static_capabilities=frozenset(
            {"feishu.contact:read", "feishu.wiki:read", "feishu.bitable:read"}
        ),
        delegatable_capabilities=frozenset(
            {"feishu.contact:read", "feishu.wiki:read", "feishu.bitable:read"}
        ),
    ),
    "external_search_agent": AgentConfig(
        agent_id="external_search_agent",
        name="外部检索 Agent",
        static_capabilities=frozenset({"web.public:read"}),
        delegatable_capabilities=frozenset({"web.public:read"}),
    ),
}


def get_agent_config(agent_id: str) -> AgentConfig | None:
    return AGENTS.get(agent_id)
