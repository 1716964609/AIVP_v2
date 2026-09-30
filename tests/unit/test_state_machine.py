import unittest

from aivp.state.machine import (
    RunState,
    TERMINAL_STATES,
    can_transition,
)


class StateMachineTests(unittest.TestCase):
    def test_generation_happy_path(self):
        self.assertTrue(
            can_transition(
                RunState.CONTEXT_READY,
                RunState.GENERATING,
            )
        )

        self.assertTrue(
            can_transition(
                RunState.GENERATING,
                RunState.GENERATED,
            )
        )

        self.assertTrue(
            can_transition(
                RunState.GENERATED,
                RunState.VERIFYING,
            )
        )

    def test_repair_loop_is_explicit(self):
        self.assertTrue(
            can_transition(
                RunState.VERIFYING,
                RunState.REPAIRING,
            )
        )

        self.assertTrue(
            can_transition(
                RunState.REPAIRING,
                RunState.VERIFYING,
            )
        )

    def test_illegal_transition_is_rejected(self):
        self.assertFalse(
            can_transition(
                RunState.CREATED,
                RunState.AUTO_FINISHED,
            )
        )

        self.assertFalse(
            can_transition(
                RunState.GENERATED,
                RunState.RISK_ASSESSED,
            )
        )

    def test_terminal_states_are_explicit(self):
        self.assertIn(
            RunState.AUTO_FINISHED,
            TERMINAL_STATES,
        )

        self.assertIn(
            RunState.HUMAN_REQUIRED,
            TERMINAL_STATES,
        )

        self.assertNotIn(
            RunState.GENERATED,
            TERMINAL_STATES,
        )


if __name__ == "__main__":
    unittest.main()
