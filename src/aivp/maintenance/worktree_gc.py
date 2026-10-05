from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aivp.errors import AIVPError
from aivp.repository.git import (
    assert_git_repo,
    git,
)


@dataclass(frozen=True)
class WorktreeCleanupResult:
    path: Path
    removed: bool
    dry_run: bool
    reason: str


def _top_level(repo: Path) -> Path:
    raw = git(
        repo,
        "rev-parse",
        "--show-toplevel",
    ).stdout.strip()

    if not raw:
        raise AIVPError(
            f"Cannot resolve Git top level: {repo}"
        )

    return Path(raw).expanduser().resolve()


def _common_dir(repo: Path) -> Path:
    raw = git(
        repo,
        "rev-parse",
        "--git-common-dir",
    ).stdout.strip()

    if not raw:
        raise AIVPError(
            f"Cannot resolve Git common dir: {repo}"
        )

    path = Path(raw)

    if not path.is_absolute():
        path = repo / path

    return path.expanduser().resolve()


def _registered_worktrees(
    canonical_repo: Path,
) -> set[Path]:
    cp = git(
        canonical_repo,
        "worktree",
        "list",
        "--porcelain",
    )

    paths: set[Path] = set()

    for line in cp.stdout.splitlines():
        if not line.startswith("worktree "):
            continue

        value = line[len("worktree "):]

        if not value.strip():
            continue

        paths.add(
            Path(value)
            .expanduser()
            .resolve()
        )

    return paths


def worktree_owned_by_repo(
    *,
    canonical_repo: Path,
    worktree_path: Path,
) -> bool:
    canonical_repo = (
        canonical_repo
        .expanduser()
        .resolve()
    )

    worktree_path = (
        worktree_path
        .expanduser()
        .resolve()
    )

    assert_git_repo(canonical_repo)

    canonical_root = _top_level(
        canonical_repo
    )

    if worktree_path == canonical_root:
        return False

    if not worktree_path.exists():
        return False

    if (
        worktree_path
        not in _registered_worktrees(
            canonical_root
        )
    ):
        return False

    try:
        assert_git_repo(worktree_path)

        worktree_root = _top_level(
            worktree_path
        )

        if worktree_root != worktree_path:
            return False

        return (
            _common_dir(canonical_root)
            == _common_dir(worktree_path)
        )

    except AIVPError:
        return False


def remove_owned_worktree(
    *,
    canonical_repo: Path,
    worktree_path: Path,
    dry_run: bool = True,
    allow_dirty: bool = False,
) -> WorktreeCleanupResult:
    canonical_repo = (
        canonical_repo
        .expanduser()
        .resolve()
    )

    worktree_path = (
        worktree_path
        .expanduser()
        .resolve()
    )

    assert_git_repo(canonical_repo)

    canonical_root = _top_level(
        canonical_repo
    )

    if worktree_path == canonical_root:
        raise AIVPError(
            "Refusing to remove the canonical "
            "repository"
        )

    if not worktree_path.exists():
        return WorktreeCleanupResult(
            path=worktree_path,
            removed=False,
            dry_run=dry_run,
            reason=(
                "worktree path is already absent"
            ),
        )

    if not worktree_owned_by_repo(
        canonical_repo=canonical_root,
        worktree_path=worktree_path,
    ):
        raise AIVPError(
            "Refusing to remove worktree that "
            "is not a registered worktree of "
            "the canonical repository"
        )

    if dry_run:
        return WorktreeCleanupResult(
            path=worktree_path,
            removed=False,
            dry_run=True,
            reason=(
                "registered owned worktree would "
                "be removed"
            ),
        )

    args = [
        "worktree",
        "remove",
    ]

    if allow_dirty:
        args.append("--force")

    args.append(
        str(worktree_path)
    )

    cp = git(
        canonical_root,
        *args,
        check=False,
    )

    if cp.returncode != 0:
        raise AIVPError(
            "Failed to remove owned worktree:\n"
            f"{cp.stderr}"
        )

    return WorktreeCleanupResult(
        path=worktree_path,
        removed=True,
        dry_run=False,
        reason="owned worktree removed",
    )
