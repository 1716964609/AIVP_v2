import unittest

from aivp.cache import (
    context_cache_identity,
)
from aivp.errors import AIVPError


class ContextCacheIdentityTests(
    unittest.TestCase
):
    def _identity(self, **overrides):
        values = {
            "repo_sha": "abc123",
            "task_text": "change setting",
            "compiler_version": "1.0.0",
            "max_files": 20,
            "max_chars": 120_000,
        }
        values.update(overrides)

        return context_cache_identity(
            **values
        )

    def test_identity_is_deterministic(self):
        first = self._identity()
        second = self._identity()

        self.assertEqual(
            first,
            second,
        )
        self.assertEqual(
            first.key,
            second.key,
        )

    def test_task_change_invalidates(self):
        first = self._identity(
            task_text="change setting"
        )
        second = self._identity(
            task_text="change another setting"
        )

        self.assertNotEqual(
            first.key,
            second.key,
        )

    def test_repo_change_invalidates(self):
        first = self._identity(
            repo_sha="abc123"
        )
        second = self._identity(
            repo_sha="def456"
        )

        self.assertNotEqual(
            first.key,
            second.key,
        )

    def test_compiler_change_invalidates(self):
        first = self._identity(
            compiler_version="1.0.0"
        )
        second = self._identity(
            compiler_version="1.1.0"
        )

        self.assertNotEqual(
            first.key,
            second.key,
        )

    def test_budget_change_invalidates(self):
        baseline = self._identity()

        changed_files = self._identity(
            max_files=21
        )
        changed_chars = self._identity(
            max_chars=120_001
        )

        self.assertNotEqual(
            baseline.key,
            changed_files.key,
        )
        self.assertNotEqual(
            baseline.key,
            changed_chars.key,
        )

    def test_payload_contains_no_task_text(self):
        identity = self._identity(
            task_text="private task text"
        )

        payload = identity.payload()

        self.assertNotIn(
            "task_text",
            payload,
        )
        self.assertNotIn(
            "private task text",
            str(payload),
        )

    def test_invalid_values_fail_closed(self):
        with self.assertRaises(
            AIVPError
        ):
            self._identity(
                repo_sha=""
            )

        with self.assertRaises(
            AIVPError
        ):
            self._identity(
                compiler_version=""
            )

        with self.assertRaises(
            AIVPError
        ):
            self._identity(
                max_files=0
            )

        with self.assertRaises(
            AIVPError
        ):
            self._identity(
                max_chars=0
            )


if __name__ == "__main__":
    unittest.main()
