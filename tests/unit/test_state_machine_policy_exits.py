import unittest

from aivp.state.machine import (
    RunState,
    can_transition,
)


class PolicyExitTransitionTests(
    unittest.TestCase
):
    def test_policy_gated_states_can_exit_to_policy_terminals(
        self,
    ):
        sources = (
            RunState.GENERATING,
            RunState.VERIFYING,
            RunState.REPAIRING,
            RunState.REVIEWING,
            RunState.RISK_ASSESSING,
        )

        terminals = (
            RunState.HUMAN_REQUIRED,
            RunState.DENIED,
        )

        for source in sources:
            for target in terminals:
                with self.subTest(
                    source=source,
                    target=target,
                ):
                    self.assertTrue(
                        can_transition(
                            source,
                            target,
                        )
                    )


if __name__ == "__main__":
    unittest.main()
