import unittest

from aivp.errors import (
    HumanApprovalRequired,
    PolicyDenied,
)
from aivp.policy.capability import (
    Capability,
    CapabilityRequest,
    Decision,
    StaticCapabilityPolicy,
    v2_default_policy,
)


class CapabilityPolicyTests(
    unittest.TestCase
):
    def request(
        self,
        capability,
    ):
        return CapabilityRequest(
            capability=capability,
            actor="test",
            action="test-action",
            target="/workspace",
        )

    def test_explicit_allow_is_authorized(
        self,
    ):
        policy = StaticCapabilityPolicy(
            {
                Capability.C1_LOCAL_MUTATE:
                    Decision.ALLOW,
            }
        )

        request = self.request(
            Capability.C1_LOCAL_MUTATE
        )

        self.assertEqual(
            policy.authorize(request),
            Decision.ALLOW,
        )

    def test_unspecified_capability_is_denied(
        self,
    ):
        policy = StaticCapabilityPolicy(
            {
                Capability.C0_OBSERVE:
                    Decision.ALLOW,
            }
        )

        with self.assertRaises(
            PolicyDenied
        ):
            policy.authorize(
                self.request(
                    Capability.C1_LOCAL_MUTATE
                )
            )

    def test_unknown_capability_fails_closed(
        self,
    ):
        policy = StaticCapabilityPolicy(
            {}
        )

        request = CapabilityRequest(
            capability="unknown",
            actor="test",
            action="unknown-action",
        )

        self.assertEqual(
            policy.decide(request),
            Decision.DENY,
        )

        with self.assertRaises(
            PolicyDenied
        ):
            policy.authorize(request)

    def test_v2_default_policy(
        self,
    ):
        policy = v2_default_policy()

        expected = {
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

        for capability, decision in (
            expected.items()
        ):
            self.assertEqual(
                policy.decide(
                    self.request(capability)
                ),
                decision,
            )

    def test_external_write_requires_human(
        self,
    ):
        policy = v2_default_policy()

        request = CapabilityRequest(
            capability=(
                Capability.C3_EXTERNAL_WRITE
            ),
            actor="git",
            action="push",
            target="origin",
        )

        with self.assertRaises(
            HumanApprovalRequired
        ):
            policy.authorize(request)

    def test_sensitive_and_production_are_denied(
        self,
    ):
        policy = v2_default_policy()

        for capability in (
            Capability.C4_SENSITIVE,
            Capability.C5_PRODUCTION,
        ):
            with self.assertRaises(
                PolicyDenied
            ):
                policy.authorize(
                    self.request(capability)
                )


if __name__ == "__main__":
    unittest.main()
