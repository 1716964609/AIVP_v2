from __future__ import annotations

import os
import re
import tempfile

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aivp.errors import (
    StateIntegrityError,
)
from aivp.state.hashing import (
    sha256_bytes,
)


_DIGEST_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


@dataclass(frozen=True)
class CacheObject:
    sha256: str
    path: Path
    size_bytes: int


class ContentAddressedCache:
    def __init__(
        self,
        root: Path,
    ):
        self.root = (
            root.expanduser()
        )

    def path_for(
        self,
        digest: str,
    ) -> Path:
        self._validate_digest(
            digest
        )

        return (
            self.root
            / "sha256"
            / digest[:2]
            / digest
        )

    def put_bytes(
        self,
        data: bytes,
    ) -> CacheObject:
        digest = sha256_bytes(
            data
        )

        path = self.path_for(
            digest
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        if path.exists():
            self._verify_existing(
                path=path,
                digest=digest,
            )

            return CacheObject(
                sha256=digest,
                path=path,
                size_bytes=(
                    path.stat().st_size
                ),
            )

        fd, temp_name = (
            tempfile.mkstemp(
                prefix=".aivp-cache-",
                dir=str(path.parent),
            )
        )

        temp_path = Path(
            temp_name
        )

        try:
            os.fchmod(
                fd,
                0o600,
            )

            with os.fdopen(
                fd,
                "wb",
            ) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temp_path,
                path,
            )

        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass

            try:
                temp_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise

        self._verify_existing(
            path=path,
            digest=digest,
        )

        return CacheObject(
            sha256=digest,
            path=path,
            size_bytes=len(data),
        )

    def put_text(
        self,
        text: str,
    ) -> CacheObject:
        return self.put_bytes(
            text.encode("utf-8")
        )

    def get_bytes(
        self,
        digest: str,
    ) -> Optional[bytes]:
        path = self.path_for(
            digest
        )

        if not path.exists():
            return None

        self._verify_existing(
            path=path,
            digest=digest,
        )

        return path.read_bytes()

    def get_text(
        self,
        digest: str,
    ) -> Optional[str]:
        data = self.get_bytes(
            digest
        )

        if data is None:
            return None

        return data.decode(
            "utf-8"
        )

    def _verify_existing(
        self,
        *,
        path: Path,
        digest: str,
    ) -> None:
        if path.is_symlink():
            raise StateIntegrityError(
                "Cache object must not "
                "be a symlink"
            )

        if not path.is_file():
            raise StateIntegrityError(
                "Cache object path is "
                "not a regular file"
            )

        data = path.read_bytes()

        actual = sha256_bytes(
            data
        )

        if actual != digest:
            raise StateIntegrityError(
                "Cache object hash "
                "mismatch"
            )

    @staticmethod
    def _validate_digest(
        digest: str,
    ) -> None:
        if (
            not isinstance(
                digest,
                str,
            )
            or _DIGEST_RE.fullmatch(
                digest
            )
            is None
        ):
            raise StateIntegrityError(
                "Invalid cache digest"
            )
