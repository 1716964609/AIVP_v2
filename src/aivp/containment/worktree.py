from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aivp.errors import AIVPError
from aivp.repository.git import (
    assert_git_repo,
    git,
)


@dataclass(frozen=True)
class RunWorktree:
    canonical_repo: Path
    path: Path
    base_sha: str


def _head_sha(repo: Path) -> str:
    return git(
        repo,
        "rev-parse",
        "HEAD",
    ).stdout.strip()


def resolve_revision(
    repo: Path,
    revision: str,
) -> str:
    repo = repo.expanduser().resolve()

    assert_git_repo(repo)

    revision = revision.strip()

    if not revision:
        raise AIVPError(
            "Repository revision must not be empty"
        )

    cp = git(
        repo,
        "rev-parse",
        "--verify",
        f"{revision}^{{commit}}",
        check=False,
    )

    resolved = cp.stdout.strip()

    if (
        cp.returncode != 0
        or not resolved
    ):
        raise AIVPError(
            "Cannot resolve repository revision: "
            f"{revision}"
        )

    return resolved


def _git_common_dir(repo: Path) -> Path:
    raw = git(
        repo,
        "rev-parse",
        "--git-common-dir",
    ).stdout.strip()

    path = Path(raw)

    if not path.is_absolute():
        path = repo / path

    return path.resolve()


def validate_run_worktree(
    *,
    canonical_repo: Path,
    worktree_path: Path,
    base_sha: str,
) -> RunWorktree:
    canonical_repo = (
        canonical_repo.expanduser().resolve()
    )

    worktree_path = (
        worktree_path.expanduser().resolve()
    )

    assert_git_repo(canonical_repo)

    if not worktree_path.exists():
        raise AIVPError(
            "Run worktree is missing: "
            f"{worktree_path}"
        )

    assert_git_repo(worktree_path)

    canonical_common = _git_common_dir(
        canonical_repo
    )

    worktree_common = _git_common_dir(
        worktree_path
    )

    if canonical_common != worktree_common:
        raise AIVPError(
            "Run worktree does not belong to "
            "the canonical repository"
        )

    current_sha = _head_sha(
        worktree_path
    )

    if current_sha != base_sha:
        raise AIVPError(
            "Run worktree base SHA mismatch: "
            f"expected {base_sha}, "
            f"got {current_sha}"
        )

    return RunWorktree(
        canonical_repo=canonical_repo,
        path=worktree_path,
        base_sha=base_sha,
    )


def create_run_worktree(
    *,
    canonical_repo: Path,
    worktree_path: Path,
    base_revision: Optional[str] = None,
) -> RunWorktree:
    canonical_repo = (
        canonical_repo.expanduser().resolve()
    )

    worktree_path = (
        worktree_path.expanduser().resolve()
    )

    assert_git_repo(canonical_repo)

    if worktree_path == canonical_repo:
        raise AIVPError(
            "Run worktree must not be the "
            "canonical repository"
        )

    if worktree_path.exists():
        raise AIVPError(
            "Run worktree path already exists: "
            f"{worktree_path}"
        )

    base_sha = (
        resolve_revision(
            canonical_repo,
            base_revision,
        )
        if base_revision is not None
        else _head_sha(canonical_repo)
    )

    worktree_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cp = git(
        canonical_repo,
        "worktree",
        "add",
        "--detach",
        str(worktree_path),
        base_sha,
        check=False,
    )

    if cp.returncode != 0:
        raise AIVPError(
            "Failed to create run worktree:\n"
            f"{cp.stderr}"
        )

    return validate_run_worktree(
        canonical_repo=canonical_repo,
        worktree_path=worktree_path,
        base_sha=base_sha,
    )
