import contextlib
import fcntl
import hashlib
import os
import subprocess
import tempfile

from pathlib import Path
from typing import List

from aivp.errors import AIVPError


def git(
    repo: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if check and cp.returncode != 0:
        raise AIVPError(
            f"git {' '.join(args)} failed:\n"
            f"{cp.stderr}"
        )

    return cp


@contextlib.contextmanager
def repo_lock(repo: Path):
    key = hashlib.sha256(
        str(repo.resolve()).encode()
    ).hexdigest()[:16]

    lock_path = (
        Path(tempfile.gettempdir())
        / f"aivp-{key}.lock"
    )

    fd = os.open(
        lock_path,
        os.O_CREAT
        | os.O_RDWR,
        0o600,
    )

    try:
        try:
            fcntl.flock(
                fd,
                fcntl.LOCK_EX
                | fcntl.LOCK_NB,
            )
        except BlockingIOError as exc:
            try:
                os.lseek(
                    fd,
                    0,
                    os.SEEK_SET,
                )

                owner = os.read(
                    fd,
                    4096,
                ).decode(
                    errors="replace"
                ).strip()

            except OSError:
                owner = ""

            message = (
                "Another AIVP run appears "
                "active for this repository: "
                f"{lock_path}"
            )

            if owner:
                message += (
                    "\nLock owner metadata:\n"
                    + owner
                )

            raise AIVPError(
                message
            ) from exc

        os.ftruncate(
            fd,
            0,
        )

        os.lseek(
            fd,
            0,
            os.SEEK_SET,
        )

        os.write(
            fd,
            (
                f"pid={os.getpid()}\n"
                f"repo={repo.resolve()}\n"
            ).encode(),
        )

        yield

    finally:
        with contextlib.suppress(
            OSError
        ):
            fcntl.flock(
                fd,
                fcntl.LOCK_UN,
            )

        os.close(fd)


def assert_git_repo(
    repo: Path,
) -> None:
    cp = git(
        repo,
        "rev-parse",
        "--is-inside-work-tree",
        check=False,
    )

    if (
        cp.returncode != 0
        or cp.stdout.strip() != "true"
    ):
        raise AIVPError(
            f"Not a Git repository: {repo}"
        )


def assert_clean_repo(
    repo: Path,
) -> None:
    status = git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).stdout

    if status.strip():
        raise AIVPError(
            "Target repository must be clean "
            "before a real run.\n"
            "Commit/stash/remove current "
            "changes first.\n\n"
            + status
        )


def capture_diff(
    repo: Path,
    max_untracked_bytes: int = 200_000,
) -> str:
    parts = []

    diff = git(
        repo,
        "diff",
        "--no-ext-diff",
        "--binary",
    ).stdout

    if diff:
        parts.append(diff)

    cached = git(
        repo,
        "diff",
        "--cached",
        "--no-ext-diff",
        "--binary",
    ).stdout

    if cached:
        parts.append(
            "\n# STAGED DIFF\n"
            + cached
        )

    untracked = git(
        repo,
        "ls-files",
        "--others",
        "--exclude-standard",
    ).stdout.splitlines()

    for rel in untracked:
        path = repo / rel

        if not path.is_file():
            continue

        try:
            raw = path.read_bytes()
        except OSError:
            continue

        if (
            len(raw) > max_untracked_bytes
            or b"\x00" in raw
        ):
            parts.append(
                "\n# UNTRACKED FILE "
                f"(binary/large): {rel}\n"
            )
            continue

        text = raw.decode(
            "utf-8",
            errors="replace",
        )

        parts.append(
            f"\n# UNTRACKED FILE: {rel}\n"
            f"--- /dev/null\n"
            f"+++ b/{rel}\n"
            + "\n".join(
                "+" + line
                for line in text.splitlines()
            )
            + "\n"
        )

    return "\n".join(parts)


def changed_paths(
    repo: Path,
) -> List[str]:
    paths = set()

    for args in [
        (
            "diff",
            "--name-only",
        ),
        (
            "diff",
            "--cached",
            "--name-only",
        ),
        (
            "ls-files",
            "--others",
            "--exclude-standard",
        ),
    ]:
        out = git(
            repo,
            *args,
        ).stdout

        for line in out.splitlines():
            line = line.strip()

            if line:
                paths.add(line)

    return sorted(paths)
