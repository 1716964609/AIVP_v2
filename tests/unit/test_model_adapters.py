import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from aivp.models.base import ModelRequest
from aivp.models.claude import claude_argv
from aivp.models.claude_adapter import ClaudeAdapter
from aivp.models.codex import codex_base_argv
from aivp.models.codex_adapter import CodexAdapter


class FakeRuntime:
    def __init__(
        self,
        run_dir: Path,
        stdout: str = "raw-stdout",
    ):
        self.run_dir = run_dir
        self.stdout = stdout
        self.calls = []

    def command(
        self,
        argv,
        *,
        cwd,
        timeout_seconds,
        log_stem,
        stdin_text=None,
        actor=None,
        check=False,
    ):
        self.calls.append(
            {
                "argv": argv,
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "log_stem": log_stem,
                "actor": actor,
                "check": check,
            }
        )

        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=self.stdout,
            stderr="",
        )


class ModelAdapterTests(unittest.TestCase):
    def test_codex_generator_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            run_dir = root / "run"

            repo.mkdir()
            run_dir.mkdir()

            config = {
                "codex": {
                    "binary": "codex",
                    "generator_extra_args": [
                        "exec"
                    ],
                    "risk_extra_args": [
                        "exec"
                    ],
                    "model": "",
                    "reasoning_effort": "",
                }
            }

            runtime = FakeRuntime(run_dir)

            adapter = CodexAdapter(
                runtime,
                config,
            )

            request = ModelRequest(
                role="generator",
                prompt="implement task",
                repo=repo,
                timeout_seconds=300,
                log_stem="generate",
            )

            result = adapter.invoke(
                request
            )

            expected = codex_base_argv(
                config,
                risk=False,
                repo=repo,
            )

            expected.extend(
                [
                    "-o",
                    str(
                        run_dir
                        / "generate.last-message.txt"
                    ),
                    "implement task",
                ]
            )

            self.assertEqual(
                runtime.calls[0]["argv"],
                expected,
            )

            self.assertEqual(
                runtime.calls[0]["actor"],
                "codex",
            )

            self.assertEqual(
                result.provider,
                "openai",
            )

            self.assertEqual(
                result.last_message,
                "raw-stdout",
            )

    def test_codex_risk_schema_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            run_dir = root / "run"

            repo.mkdir()
            run_dir.mkdir()

            config = {
                "codex": {
                    "binary": "codex",
                    "generator_extra_args": [
                        "exec"
                    ],
                    "risk_extra_args": [
                        "exec"
                    ],
                    "model": "",
                    "reasoning_effort": "",
                }
            }

            runtime = FakeRuntime(run_dir)

            adapter = CodexAdapter(
                runtime,
                config,
            )

            schema = {
                "type": "object"
            }

            adapter.invoke(
                ModelRequest(
                    role="risk",
                    prompt="assess risk",
                    repo=repo,
                    timeout_seconds=300,
                    log_stem="codex-risk",
                    output_schema=schema,
                )
            )

            schema_path = (
                run_dir
                / "risk.schema.json"
            )

            self.assertTrue(
                schema_path.exists()
            )

            self.assertEqual(
                json.loads(
                    schema_path.read_text(
                        encoding="utf-8"
                    )
                ),
                schema,
            )

            argv = runtime.calls[0]["argv"]

            self.assertIn(
                "--output-schema",
                argv,
            )

            self.assertIn(
                str(
                    run_dir
                    / "codex-risk.raw.json"
                ),
                argv,
            )

    def test_claude_wrapper_is_decoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            run_dir = root / "run"

            repo.mkdir()
            run_dir.mkdir()

            config = {
                "claude": {
                    "binary": "claude",
                    "extra_args": [
                        "-p",
                        "--output-format",
                        "json",
                    ],
                    "max_turns": 2,
                    "model": "sonnet",
                }
            }

            stdout = json.dumps(
                {
                    "type": "result",
                    "result": (
                        '{"summary":"ok"}'
                    ),
                    "duration_ms": 1200,
                    "duration_api_ms": 900,
                    "num_turns": 1,
                    "total_cost_usd": 0.0123,
                    "session_id": "session-1",
                }
            )

            runtime = FakeRuntime(
                run_dir,
                stdout=stdout,
            )

            adapter = ClaudeAdapter(
                runtime,
                config,
            )

            request = ModelRequest(
                role="reviewer",
                prompt="review diff",
                repo=repo,
                timeout_seconds=300,
                log_stem="claude-review-0",
            )

            result = adapter.invoke(
                request
            )

            expected = claude_argv(
                config
            )

            expected.append(
                "review diff"
            )

            self.assertEqual(
                runtime.calls[0]["argv"],
                expected,
            )

            self.assertEqual(
                runtime.calls[0]["actor"],
                "claude",
            )

            self.assertEqual(
                result.last_message,
                '{"summary":"ok"}',
            )

            self.assertEqual(
                result.cost_estimate_usd,
                0.0123,
            )

            self.assertEqual(
                result.raw_metadata[
                    "session_id"
                ],
                "session-1",
            )

    def test_claude_plain_output_falls_back_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            run_dir = root / "run"

            repo.mkdir()
            run_dir.mkdir()

            config = {
                "claude": {
                    "binary": "claude",
                    "extra_args": [],
                    "max_turns": 2,
                    "model": "",
                }
            }

            runtime = FakeRuntime(
                run_dir,
                stdout="plain-output",
            )

            result = ClaudeAdapter(
                runtime,
                config,
            ).invoke(
                ModelRequest(
                    role="reviewer",
                    prompt="review",
                    repo=repo,
                    timeout_seconds=300,
                    log_stem="review",
                )
            )

            self.assertEqual(
                result.last_message,
                "plain-output",
            )

            self.assertIsNone(
                result.cost_estimate_usd
            )

            self.assertIsNone(
                result.input_tokens
            )

            self.assertEqual(
                result.model,
                "unknown",
            )


if __name__ == "__main__":
    unittest.main()
