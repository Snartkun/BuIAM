from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.delegation.capabilities import intersect_capabilities, parse_capabilities
from app.main import app
from app.protocol import DelegationEnvelope


def test_capability_parser_and_intersection() -> None:
    requested = parse_capabilities(["feishu.contact:read", "feishu.wiki:read"])
    effective = intersect_capabilities(
        requested,
        frozenset({"feishu.contact:read", "web.public:read"}),
    )
    assert effective == {"feishu.contact:read"}


def test_envelope_validation_requires_core_fields() -> None:
    with pytest.raises(Exception):
        DelegationEnvelope.model_validate({"trace_id": "missing-other-fields"})


def test_doc_agent_delegation_is_allowed() -> None:
    client = TestClient(app)
    response = client.post(
        "/agents/doc_agent/tasks",
        json={"task_type": "generate_report", "payload": {"topic": "测试报告"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "doc_agent"
    assert "report" in body["result"]

    trace_logs = client.get(f"/audit/traces/{body['trace_id']}").json()
    assert any(log["decision"] == "allow" for log in trace_logs)


def test_external_search_agent_delegation_is_denied() -> None:
    client = TestClient(app)
    response = client.post(
        "/agents/external_search_agent/tasks",
        json={"task_type": "attempt_enterprise_data_access", "payload": {}},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "delegation_denied"

    logs = client.get("/audit/logs").json()
    assert any(
        log["caller_agent_id"] == "external_search_agent" and log["decision"] == "deny"
        for log in logs
    )


def test_agents_do_not_import_authorization_service() -> None:
    for module_name in [
        "app.agents.doc",
        "app.agents.enterprise_data",
        "app.agents.external_search",
    ]:
        module = importlib.import_module(module_name)
        assert "app.delegation.service" not in repr(module.__dict__.values())
