from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from aivp.errors import (
    AIVPError,
    HumanApprovalRequired,
    PolicyDenied,
)


class Capability(str, Enum):
    C0_OBSERVE = "c0_observe"
    C1_LOCAL_MUTATE = "c1_local_mutate"
    C2_EXTERNAL_READ = "c2_external_read"
    C3_EXTERNAL_WRITE = "c3_external_write"
    C4_SENSITIVE = "c4_sensitive"
    C5_PRODUCTION = "c5_production"


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    HUMAN_REQUIRED = "human_required"


@dataclass(frozen=True)
class CapabilityRequest:
    capability: Capability
    actor: str
    action: str
    target: str = ""


class StaticCapabilityPolicy:
    def __init__(
        self,
        decisions: Mapping[
            Capability,
            Decision,
        ],
    ):
        normalized = {}

        for capability, decision in (
            decisions.items()
        ):
            if not isinstance(
                capability,
                Capability,
            ):
                raise AIVPError(
                    "Policy contains unknown "
                    "capability"
                )

            if not isinstance(
                decision,
                Decision,
            ):
                raise AIVPError(
                    "Policy contains invalid "
                    "decision"
                )

            normalized[
                capability
            ] = decision

        self._decisions = normalized

    def decide(
        self,
        request: CapabilityRequest,
    ) -> Decision:
        if not isinstance(
            request.capability,
            Capability,
        ):
            return Decision.DENY

        return self._decisions.get(
            request.capability,
            Decision.DENY,
        )

    def authorize(
        self,
        request: CapabilityRequest,
    ) -> Decision:
        decision = self.decide(
            request
        )

        capability = (
            request.capability.value
            if isinstance(
                request.capability,
                Capability,
            )
            else str(
                request.capability
            )
        )

        context = (
            f"capability={capability} "
            f"actor={request.actor} "
            f"action={request.action}"
        )

        if request.target:
            context += (
                f" target={request.target}"
            )

        if decision is Decision.ALLOW:
            return decision

        if (
            decision
            is Decision.HUMAN_REQUIRED
        ):
            raise HumanApprovalRequired(
                "Human approval required: "
                + context
            )

        raise PolicyDenied(
            "Capability denied: "
            + context
        )


def v2_default_policy(
) -> StaticCapabilityPolicy:
    return StaticCapabilityPolicy(
        {
            Capability.C0_OBSERVE:
                Decision.ALLOW,
            Capability.C1_LOCAL_MUTATE:
                Decision.ALLOW,
            Capability.C2_EXTERNAL_READ:
                Decision.DENY,
            Capability.C3_EXTERNAL_WRITE:
                Decision.HUMAN_REQUIRED,
            Capability.C4_SENSITIVE:
                Decision.DENY,
            Capability.C5_PRODUCTION:
                Decision.DENY,
        }
    )
