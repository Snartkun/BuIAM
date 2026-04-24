from __future__ import annotations

from fastapi import HTTPException

from app.config.agents import get_agent_config
from app.delegation.capabilities import intersect_capabilities, parse_capabilities
from app.protocol import DelegationDecision, DelegationEnvelope, DelegationHop
from app.store.audit import record_decision


class DelegationService:
    def authorize(self, envelope: DelegationEnvelope) -> DelegationDecision:
        caller = get_agent_config(envelope.caller_agent_id)
        target = get_agent_config(envelope.target_agent_id)

        if caller is None:
            return DelegationDecision(
                decision="deny",
                reason=f"unknown caller agent: {envelope.caller_agent_id}",
                effective_capabilities=[],
            )
        if target is None:
            return DelegationDecision(
                decision="deny",
                reason=f"unknown target agent: {envelope.target_agent_id}",
                effective_capabilities=[],
            )

        try:
            requested = parse_capabilities(envelope.requested_capabilities)
        except ValueError as error:
            return DelegationDecision(
                decision="deny",
                reason=str(error),
                effective_capabilities=[],
            )

        effective = intersect_capabilities(
            caller.delegatable_capabilities,
            target.static_capabilities,
            requested,
        )
        missing = requested - effective
        if missing:
            return DelegationDecision(
                decision="deny",
                reason=f"requested capabilities not delegated or not held by target: {sorted(missing)}",
                effective_capabilities=sorted(effective),
            )

        return DelegationDecision(
            decision="allow",
            reason="requested capabilities are covered by delegation intersection",
            effective_capabilities=sorted(effective),
        )

    def authorize_and_record(self, envelope: DelegationEnvelope) -> DelegationDecision:
        decision = self.authorize(envelope)
        record_decision(envelope, decision)
        return decision

    def append_hop(self, envelope: DelegationEnvelope) -> DelegationEnvelope:
        hop = DelegationHop(
            from_actor=envelope.caller_agent_id,
            to_agent_id=envelope.target_agent_id,
            task_type=envelope.task_type,
            capabilities=envelope.requested_capabilities,
        )
        return envelope.model_copy(
            update={"delegation_chain": [*envelope.delegation_chain, hop]}
        )


delegation_service = DelegationService()


def raise_for_denied(decision: DelegationDecision) -> None:
    if decision.decision == "deny":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "delegation_denied",
                "reason": decision.reason,
                "effective_capabilities": decision.effective_capabilities,
            },
        )
