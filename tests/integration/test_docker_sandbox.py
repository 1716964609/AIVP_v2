import os
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.containment.docker_sandbox import (
    DockerSandbox,
    DockerSandboxPolicy,
)


IMAGE = "postgres:17-alpine"


class DockerSandboxIntegrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        daemon = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if daemon.returncode != 0:
            raise unittest.SkipTest(
                "Docker daemon is unavailable"
            )

        image = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                IMAGE,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if image.returncode != 0:
            raise unittest.SkipTest(
                f"Required local image missing: {IMAGE}"
            )

    def sandbox(self) -> DockerSandbox:
        return DockerSandbox(
            DockerSandboxPolicy(
                image=IMAGE,
            )
        )

    def test_workspace_is_writable_and_canonical_is_hidden(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            canonical = root / "canonical"
            workspace = root / "workspace"

            canonical.mkdir()
            workspace.mkdir()

            canonical_secret = (
                canonical / "canonical-secret.txt"
            )

            canonical_secret.write_text(
                "canonical\n",
                encoding="utf-8",
            )

            host_canonical_path = str(
                canonical_secret.resolve()
            )

            script = f"""
printf 'sandbox\\n' > generated.txt

if [ -e '{host_canonical_path}' ]; then
    exit 41
fi

cat generated.txt
"""

            cp = self.sandbox().run(
                workspace=workspace,
                command=[
                    "sh",
                    "-lc",
                    script,
                ],
                timeout_seconds=10,
            )

            self.assertEqual(
                cp.returncode,
                0,
                msg=cp.stderr,
            )

            self.assertEqual(
                (
                    workspace
                    / "generated.txt"
                ).read_text(
                    encoding="utf-8"
                ),
                "sandbox\n",
            )

            self.assertEqual(
                canonical_secret.read_text(
                    encoding="utf-8"
                ),
                "canonical\n",
            )

    def test_network_namespace_has_no_external_route(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            cp = self.sandbox().run(
                workspace=Path(tmp),
                command=[
                    "sh",
                    "-lc",
                    (
                        "cat /proc/net/dev; "
                        "printf '\\n---ROUTE---\\n'; "
                        "cat /proc/net/route"
                    ),
                ],
                timeout_seconds=10,
            )

            self.assertEqual(
                cp.returncode,
                0,
                msg=cp.stderr,
            )

            netdev, route = cp.stdout.split(
                "---ROUTE---\n",
                1,
            )

            self.assertNotIn(
                "eth0:",
                netdev,
            )

            route_rows = [
                line.split()
                for line in route.splitlines()[1:]
                if line.strip()
            ]

            default_routes = [
                row
                for row in route_rows
                if (
                    len(row) >= 8
                    and row[1] == "00000000"
                    and row[7] == "00000000"
                )
            ]

            self.assertEqual(
                default_routes,
                [],
            )

    def test_host_environment_is_not_inherited_and_user_is_non_root(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get(
                "AIVP_HOST_SECRET"
            )

            os.environ[
                "AIVP_HOST_SECRET"
            ] = "must-not-cross-boundary"

            try:
                cp = self.sandbox().run(
                    workspace=Path(tmp),
                    command=[
                        "sh",
                        "-lc",
                        (
                            'printf "%s\\n" '
                            '"$(id -u)" '
                            '"$HOME" '
                            '"${AIVP_HOST_SECRET-unset}"'
                        ),
                    ],
                    timeout_seconds=10,
                )
            finally:
                if old is None:
                    os.environ.pop(
                        "AIVP_HOST_SECRET",
                        None,
                    )
                else:
                    os.environ[
                        "AIVP_HOST_SECRET"
                    ] = old

            self.assertEqual(
                cp.returncode,
                0,
                msg=cp.stderr,
            )

            self.assertEqual(
                cp.stdout.splitlines(),
                [
                    "65532",
                    "/tmp",
                    "unset",
                ],
            )

    def test_root_filesystem_is_read_only_but_tmp_is_writable(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            script = """
if touch /aivp-root-write-test 2>/dev/null; then
    exit 42
fi

printf 'ok\\n' > /tmp/aivp-tmp-test
cat /tmp/aivp-tmp-test
"""

            cp = self.sandbox().run(
                workspace=Path(tmp),
                command=[
                    "sh",
                    "-lc",
                    script,
                ],
                timeout_seconds=10,
            )

            self.assertEqual(
                cp.returncode,
                0,
                msg=cp.stderr,
            )

            self.assertEqual(
                cp.stdout,
                "ok\n",
            )


    def test_kernel_security_state_matches_policy(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            script = """
set -eu

test "$(
    awk '/^CapPrm:/ {print $2}' \
        /proc/self/status
)" = "0000000000000000"

test "$(
    awk '/^CapEff:/ {print $2}' \
        /proc/self/status
)" = "0000000000000000"

test "$(
    awk '/^NoNewPrivs:/ {print $2}' \
        /proc/self/status
)" = "1"

test "$(
    cat /sys/fs/cgroup/pids.max
)" = "128"

test "$(
    cat /sys/fs/cgroup/memory.max
)" = "536870912"

test "$(
    cat /sys/fs/cgroup/cpu.max
)" = "100000 100000"

printf 'security-state-ok\\n'
"""

            cp = self.sandbox().run(
                workspace=Path(tmp),
                command=[
                    "sh",
                    "-lc",
                    script,
                ],
                timeout_seconds=10,
            )

            self.assertEqual(
                cp.returncode,
                0,
                msg=cp.stderr,
            )

            self.assertEqual(
                cp.stdout,
                "security-state-ok\n",
            )

    def test_escape_surfaces_are_blocked(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            script = """
if touch /etc/aivp-breakout 2>/dev/null; then
    exit 51
fi

if [ -e /var/run/docker.sock ]; then
    exit 52
fi

if wget \
    -q \
    -T 2 \
    -O /tmp/network-proof \
    http://1.1.1.1 \
    2>/dev/null
then
    exit 53
fi

printf 'escape-blocked\\n'
"""

            cp = self.sandbox().run(
                workspace=Path(tmp),
                command=[
                    "sh",
                    "-lc",
                    script,
                ],
                timeout_seconds=10,
            )

            self.assertEqual(
                cp.returncode,
                0,
                msg=cp.stderr,
            )

            self.assertEqual(
                cp.stdout,
                "escape-blocked\n",
            )

    def test_tmpfs_is_writable_but_noexec(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            script = """
printf '#!/bin/sh\\nexit 0\\n' \
    > /tmp/aivp-exec-test

chmod +x /tmp/aivp-exec-test

if /tmp/aivp-exec-test 2>/dev/null; then
    exit 61
fi

test -f /tmp/aivp-exec-test

printf 'tmpfs-noexec-ok\\n'
"""

            cp = self.sandbox().run(
                workspace=Path(tmp),
                command=[
                    "sh",
                    "-lc",
                    script,
                ],
                timeout_seconds=10,
            )

            self.assertEqual(
                cp.returncode,
                0,
                msg=cp.stderr,
            )

            self.assertEqual(
                cp.stdout,
                "tmpfs-noexec-ok\n",
            )


if __name__ == "__main__":
    unittest.main()
