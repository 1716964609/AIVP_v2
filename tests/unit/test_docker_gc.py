from __future__ import annotations

import json
import subprocess
import unittest

from datetime import datetime, timezone
from unittest.mock import patch

from aivp.containment.docker_sandbox import (
    AIVP_DOCKER_OWNER_LABEL,
    AIVP_DOCKER_OWNER_VALUE,
    AIVP_DOCKER_RESOURCE_LABEL,
    AIVP_DOCKER_RESOURCE_VALUE,
    DockerSandbox,
    DockerSandboxPolicy,
)
from aivp.maintenance.docker_gc import (
    cleanup_stale_containers,
    list_owned_containers,
)


NOW = datetime(
    2026,
    10,
    5,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

CUTOFF = 7 * 24 * 60 * 60


def cp(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
):
    return subprocess.CompletedProcess(
        args=["docker"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def inspect_item(
    *,
    container_id: str,
    created: str,
    owner: str = AIVP_DOCKER_OWNER_VALUE,
    resource: str = AIVP_DOCKER_RESOURCE_VALUE,
    running: bool = False,
):
    return {
        "Id": container_id,
        "Created": created,
        "Config": {
            "Labels": {
                AIVP_DOCKER_OWNER_LABEL: owner,
                AIVP_DOCKER_RESOURCE_LABEL: resource,
            }
        },
        "State": {
            "Running": running,
        },
    }


class DockerGCTests(unittest.TestCase):
    def test_sandbox_argv_contains_ownership_labels(self):
        policy = DockerSandboxPolicy(
            image="aivp-sandbox:test",
        )

        sandbox = DockerSandbox(
            policy
        )

        with patch.object(
            type(__import__("pathlib").Path(".")),
            "is_dir",
            return_value=True,
        ):
            pass

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            argv = sandbox.build_argv(
                workspace=Path(tmp),
                command=["true"],
            )

        owner_value = (
            f"{AIVP_DOCKER_OWNER_LABEL}="
            f"{AIVP_DOCKER_OWNER_VALUE}"
        )

        resource_value = (
            f"{AIVP_DOCKER_RESOURCE_LABEL}="
            f"{AIVP_DOCKER_RESOURCE_VALUE}"
        )

        self.assertIn(
            owner_value,
            argv,
        )

        self.assertIn(
            resource_value,
            argv,
        )

    @patch(
        "aivp.maintenance.docker_gc."
        "subprocess.run"
    )
    def test_no_owned_containers_is_empty(
        self,
        run,
    ):
        run.return_value = cp(
            stdout=""
        )

        self.assertEqual(
            list_owned_containers(),
            [],
        )

        args = run.call_args.args[0]

        self.assertIn(
            (
                "label="
                f"{AIVP_DOCKER_OWNER_LABEL}="
                f"{AIVP_DOCKER_OWNER_VALUE}"
            ),
            args,
        )

    @patch(
        "aivp.maintenance.docker_gc."
        "subprocess.run"
    )
    def test_foreign_resource_label_is_ignored(
        self,
        run,
    ):
        run.side_effect = [
            cp(stdout="foreign-id\n"),
            cp(
                stdout=json.dumps(
                    [
                        inspect_item(
                            container_id="foreign-id",
                            created=(
                                "2026-09-01T00:00:00Z"
                            ),
                            resource="not-aivp-sandbox",
                        )
                    ]
                )
            ),
        ]

        self.assertEqual(
            list_owned_containers(),
            [],
        )

    @patch(
        "aivp.maintenance.docker_gc."
        "subprocess.run"
    )
    def test_recent_owned_container_is_preserved(
        self,
        run,
    ):
        run.side_effect = [
            cp(stdout="recent-id\n"),
            cp(
                stdout=json.dumps(
                    [
                        inspect_item(
                            container_id="recent-id",
                            created=(
                                "2026-10-04T00:00:00Z"
                            ),
                            running=True,
                        )
                    ]
                )
            ),
        ]

        results = cleanup_stale_containers(
            older_than_seconds=CUTOFF,
            dry_run=False,
            now=NOW,
        )

        self.assertEqual(
            len(results),
            1,
        )

        self.assertFalse(
            results[0].removed
        )

        self.assertEqual(
            run.call_count,
            2,
        )

    @patch(
        "aivp.maintenance.docker_gc."
        "subprocess.run"
    )
    def test_dry_run_does_not_remove_stale_container(
        self,
        run,
    ):
        run.side_effect = [
            cp(stdout="stale-id\n"),
            cp(
                stdout=json.dumps(
                    [
                        inspect_item(
                            container_id="stale-id",
                            created=(
                                "2026-09-01T00:00:00Z"
                            ),
                            running=True,
                        )
                    ]
                )
            ),
        ]

        results = cleanup_stale_containers(
            older_than_seconds=CUTOFF,
            dry_run=True,
            now=NOW,
        )

        self.assertFalse(
            results[0].removed
        )

        self.assertTrue(
            results[0].dry_run
        )

        self.assertEqual(
            run.call_count,
            2,
        )

    @patch(
        "aivp.maintenance.docker_gc."
        "subprocess.run"
    )
    def test_destructive_cleanup_removes_exact_stale_id(
        self,
        run,
    ):
        run.side_effect = [
            cp(stdout="stale-id\n"),
            cp(
                stdout=json.dumps(
                    [
                        inspect_item(
                            container_id="stale-id",
                            created=(
                                "2026-09-01T00:00:00Z"
                            ),
                            running=True,
                        )
                    ]
                )
            ),
            cp(),
        ]

        results = cleanup_stale_containers(
            older_than_seconds=CUTOFF,
            dry_run=False,
            now=NOW,
        )

        self.assertTrue(
            results[0].removed
        )

        rm_args = run.call_args_list[
            2
        ].args[0]

        self.assertEqual(
            rm_args,
            [
                "docker",
                "rm",
                "-f",
                "stale-id",
            ],
        )

    @patch(
        "aivp.maintenance.docker_gc."
        "subprocess.run"
    )
    def test_future_timestamp_fails_closed(
        self,
        run,
    ):
        run.side_effect = [
            cp(stdout="future-id\n"),
            cp(
                stdout=json.dumps(
                    [
                        inspect_item(
                            container_id="future-id",
                            created=(
                                "2026-10-06T00:00:00Z"
                            ),
                        )
                    ]
                )
            ),
        ]

        results = cleanup_stale_containers(
            older_than_seconds=0,
            dry_run=False,
            now=NOW,
        )

        self.assertFalse(
            results[0].removed
        )

        self.assertEqual(
            run.call_count,
            2,
        )


if __name__ == "__main__":
    unittest.main()
