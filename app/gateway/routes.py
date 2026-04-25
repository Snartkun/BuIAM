from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
import httpx

from app.delegation.service import delegation_service, raise_for_denied
from app.gateway.local_adapter import call_local_agent
from app.identity.jwt_service import TokenError, verify_token
from app.protocol import AgentTaskResponse, DelegationDecision, DelegationEnvelope
from app.store.audit import record_decision
from app.store.registry import get_agent


router = APIRouter()


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "AUTH_TOKEN_MISSING", "message": "missing Authorization header"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "AUTH_TOKEN_INVALID", "message": "invalid Authorization header"},
        )
    return token


@router.post("/delegate/call")
async def delegate_call(
    envelope: DelegationEnvelope,
    authorization: str | None = Header(default=None),
) -> AgentTaskResponse:
    try:
        auth_context = verify_token(bearer_token(authorization))
    except TokenError as error:
        raise HTTPException(
            status_code=401,
            detail={"error_code": error.error_code, "message": error.message},
        ) from error

    trusted_envelope = envelope.model_copy(
        update={
            "caller_agent_id": auth_context.agent_id,
            "auth_context": auth_context,
        }
    )
    target = get_agent(trusted_envelope.target_agent_id)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "AGENT_NOT_REGISTERED", "agent_id": trusted_envelope.target_agent_id},
        )

    decision = delegation_service.authorize_and_record(trusted_envelope)
    raise_for_denied(decision)
    authorized_envelope = delegation_service.append_hop(
        trusted_envelope,
        decision.effective_capabilities,
    )

    try:
        return await forward_to_agent(target.endpoint, authorized_envelope)
    except HTTPException as error:
        forward_error_decision = DelegationDecision(
            decision="deny",
            reason=f"target agent unreachable or returned error: {error.detail}",
            effective_capabilities=decision.effective_capabilities,
            missing_capabilities=[],
            requested_capabilities=decision.requested_capabilities,
            caller_token_capabilities=decision.caller_token_capabilities,
            target_agent_capabilities=decision.target_agent_capabilities,
            user_capabilities=decision.user_capabilities,
        )
        record_decision(trusted_envelope, forward_error_decision)
        raise


async def forward_to_agent(endpoint: str, envelope: DelegationEnvelope) -> AgentTaskResponse:
    if endpoint.startswith("local://"):
        return await call_local_agent(endpoint, envelope)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(endpoint, json=envelope.model_dump())
            response.raise_for_status()
            return AgentTaskResponse.model_validate(response.json())
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail={"error_code": "TARGET_AGENT_UNREACHABLE", "message": str(error)},
        ) from error
