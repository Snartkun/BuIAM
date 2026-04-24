from __future__ import annotations

from app.protocol import Capability


KNOWN_CAPABILITIES = {
    "report:write",
    "feishu.contact:read",
    "feishu.wiki:read",
    "feishu.bitable:read",
    "web.public:read",
}


def parse_capabilities(raw_capabilities: list[Capability]) -> set[str]:
    parsed = set(raw_capabilities)
    unknown = parsed - KNOWN_CAPABILITIES
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
