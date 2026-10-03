import tempfile
import unittest

from pathlib import Path

from aivp.cache import (
    ContentAddressedCache,
)
from aivp.errors import (
    StateIntegrityError,
)
from aivp.state.hashing import (
    sha256_bytes,
)


class ContentAddressedCacheTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        self.root = (
            Path(self.tempdir.name)
            / "cache"
        )

        self.cache = (
            ContentAddressedCache(
                self.root
            )
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_put_and_get_round_trip(self):
        data = b"hello cache"

        stored = (
            self.cache.put_bytes(
                data
            )
        )

        self.assertEqual(
            stored.sha256,
            sha256_bytes(data),
        )
        self.assertEqual(
            stored.size_bytes,
            len(data),
        )
        self.assertEqual(
            self.cache.get_bytes(
                stored.sha256
            ),
            data,
        )

    def test_path_is_content_addressed(self):
        data = b"content"
        digest = sha256_bytes(
            data
        )

        stored = (
            self.cache.put_bytes(
                data
            )
        )

        self.assertEqual(
            stored.path,
            (
                self.root
                / "sha256"
                / digest[:2]
                / digest
            ),
        )

    def test_same_content_is_deduplicated(self):
        first = (
            self.cache.put_text(
                "same content"
            )
        )

        second = (
            self.cache.put_text(
                "same content"
            )
        )

        self.assertEqual(
            first.sha256,
            second.sha256,
        )
        self.assertEqual(
            first.path,
            second.path,
        )

    def test_different_content_has_different_key(
        self,
    ):
        first = (
            self.cache.put_text(
                "first"
            )
        )

        second = (
            self.cache.put_text(
                "second"
            )
        )

        self.assertNotEqual(
            first.sha256,
            second.sha256,
        )
        self.assertNotEqual(
            first.path,
            second.path,
        )

    def test_missing_object_is_cache_miss(self):
        missing = "0" * 64

        self.assertIsNone(
            self.cache.get_bytes(
                missing
            )
        )

    def test_corruption_fails_closed(self):
        stored = (
            self.cache.put_text(
                "original"
            )
        )

        stored.path.write_text(
            "tampered",
            encoding="utf-8",
        )

        with self.assertRaises(
            StateIntegrityError
        ):
            self.cache.get_text(
                stored.sha256
            )

        with self.assertRaises(
            StateIntegrityError
        ):
            self.cache.put_text(
                "original"
            )

    def test_invalid_digest_fails_closed(self):
        for digest in (
            "",
            "../escape",
            "ABC",
            "g" * 64,
            "0" * 63,
        ):
            with self.subTest(
                digest=digest
            ):
                with self.assertRaises(
                    StateIntegrityError
                ):
                    self.cache.get_bytes(
                        digest
                    )


if __name__ == "__main__":
    unittest.main()
