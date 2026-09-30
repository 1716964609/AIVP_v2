import unittest

from aivp.errors import StateIntegrityError
from aivp.state.checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
    validate_checkpoint_schema_version,
)


class CheckpointSchemaTests(
    unittest.TestCase
):
    def test_current_version_is_accepted(
        self,
    ):
        validate_checkpoint_schema_version(
            {
                "checkpoint_schema_version":
                    CHECKPOINT_SCHEMA_VERSION
            }
        )

    def test_missing_version_fails_closed(
        self,
    ):
        with self.assertRaises(
            StateIntegrityError
        ):
            validate_checkpoint_schema_version(
                {}
            )

    def test_future_version_fails_closed(
        self,
    ):
        with self.assertRaises(
            StateIntegrityError
        ):
            validate_checkpoint_schema_version(
                {
                    "checkpoint_schema_version":
                        (
                            CHECKPOINT_SCHEMA_VERSION
                            + 1
                        )
                }
            )

    def test_non_integer_version_fails_closed(
        self,
    ):
        with self.assertRaises(
            StateIntegrityError
        ):
            validate_checkpoint_schema_version(
                {
                    "checkpoint_schema_version":
                        "1"
                }
            )


if __name__ == "__main__":
    unittest.main()
