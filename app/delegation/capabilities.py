from __future__ import annotations

from app.config.agents import AGENTS
from app.protocol import Capability


def known_capabilities() -> set[str]:
    capabilities: set[str] = set()
    for agent in AGENTS.values():
        capabilities.update(agent.static_capabilities)
        capabilities.update(agent.delegatable_capabilities)
    return capabilities


def parse_capabilities(raw_capabilities: list[Capability]) -> set[str]:
    parsed = set(raw_capabilities)
    unknown = parsed - known_capabilities()
    if unknown:
        raise ValueError(f"unknown capabilities: {sorted(unknown)}")
    return parsed


def intersect_capabilities(*capability_sets: set[str] | frozenset[str]) -> set[str]:
    if not capability_sets:
        return set()
    result = set(capability_sets[0])
    for capability_set in capability_sets[1:]:
        result &= set(capability_set)
    return result
