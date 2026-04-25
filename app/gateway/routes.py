from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
import httpx
import time
from uuid import uuid4

from app.delegation.service import delegation_service, raise_for_denied
from app.gateway.local_adapter import call_local_agent
from app.identity.jwt_service import TokenVerificationResult, inspect_token, token_fingerprint
from app.protocol import AgentTaskResponse, DelegationEnvelope
from app.store.registry import get_agent
from app.store.auth_events import record_auth_event


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


def safe_trace_id(envelope: DelegationEnvelope | None) -> str:
    return envelope.trace_id if envelope is not None else f"trace_auth_{uuid4()}"


def safe_request_id(envelope: DelegationEnvelope | None) -> str:
    return envelope.request_id if envelope is not None else f"req_auth_{uuid4()}"


def record_missing_or_invalid_bearer(
    *,
    envelope: DelegationEnvelope,
    authorization: str | None,
    error_code: str,
    reason: str,
) -> None:
    record_auth_event(
        trace_id=safe_trace_id(envelope),
        request_id=safe_request_id(envelope),
        caller_agent_id=envelope.caller_agent_id,
        claimed_agent_id=envelope.caller_agent_id,
        token_fingerprint=token_fingerprint(authorization.partition(" ")[2] if authorization else None),
        verified_at=int(time.time()),
        identity_decision="deny",
        error_code=error_code,
        reason=reason,
    )


def record_token_result(envelope: DelegationEnvelope, result: TokenVerificationResult) -> None:
    auth_context = result.auth_context
    record_auth_event(
        trace_id=envelope.trace_id,
        request_id=envelope.request_id,
        caller_agent_id=auth_context.agent_id if auth_context is not None else result.token_agent_id,
        claimed_agent_id=envelope.caller_agent_id,
        token_jti=result.token_jti,
        token_sub=result.token_sub,
        token_agent_id=result.token_agent_id,
        delegated_user=result.delegated_user,
        token_fingerprint=result.token_fingerprint,
        token_issued_at=result.token_issued_at,
        token_expires_at=result.token_expires_at,
        verified_at=result.verified_at,
        is_expired=result.is_expired,
        is_revoked=result.is_revoked,
        is_jti_registered=result.is_jti_registered,
        signature_valid=result.signature_valid,
        issuer_valid=result.issuer_valid,
        audience_valid=result.audience_valid,
        identity_decision="allow" if result.allowed else "deny",
        error_code=result.error_code,
        reason=result.message,
    )


@router.post("/delegate/call")
async def delegate_call(
    envelope: DelegationEnvelope,
    authorization: str | None = Header(default=None),
) -> AgentTaskResponse:
    try:
        token = bearer_token(authorization)
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {}
        record_missing_or_invalid_bearer(
            envelope=envelope,
            authorization=authorization,
            error_code=str(detail.get("error_code", "AUTH_TOKEN_INVALID")),
            reason=str(detail.get("message", "invalid Authorization header")),
        )
        raise

    token_result = inspect_token(token)
    record_token_result(envelope, token_result)
    if token_result.auth_context is None:
        raise HTTPException(
            status_code=401,
            detail={"error_code": token_result.error_code, "message": token_result.message},
        )

    auth_context = token_result.auth_context

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
    return await forward_to_agent(target.endpoint, authorized_envelope)


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
