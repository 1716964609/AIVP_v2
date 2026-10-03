import tempfile
import unittest

from pathlib import Path

from aivp.application import (
    _cache_root_from_state_db,
)


class ApplicationCacheTests(
    unittest.TestCase
):
    def test_cache_root_is_colocated_with_state_db(
        self,
    ):
        with (
            tempfile.TemporaryDirectory()
            as tempdir
        ):
            root = Path(tempdir)

            state_db = (
                root
                / ".aivp"
                / "state.sqlite"
            )

            cache_root = (
                _cache_root_from_state_db(
                    state_db
                )
            )

            self.assertEqual(
                cache_root,
                (
                    state_db
                    .resolve()
                    .parent
                    / "cache"
                ),
            )

    def test_cache_path_is_not_created_by_helper(
        self,
    ):
        with (
            tempfile.TemporaryDirectory()
            as tempdir
        ):
            state_db = (
                Path(tempdir)
                / ".aivp"
                / "state.sqlite"
            )

            cache_root = (
                _cache_root_from_state_db(
                    state_db
                )
            )

            self.assertFalse(
                cache_root.exists()
            )


if __name__ == "__main__":
    unittest.main()
