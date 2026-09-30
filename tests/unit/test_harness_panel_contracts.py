import tempfile
import unittest
from pathlib import Path

from aivp.artifacts.registry import ArtifactRegistry
from aivp.risk.engine import LegacyCompatibleRiskEngine
from aivp.verification.deterministic import (
    DeterministicVerifier,
)


class FakeRuntime:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

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
        import subprocess

        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="ok",
            stderr="",
        )


class HarnessPanelContractTests(unittest.TestCase):
    def test_artifact_registry_round_trip(self):
        registry = ArtifactRegistry()

        path = Path("/tmp/example.json")

        registry.register(
            "verification",
            path,
        )

        self.assertEqual(
            registry.get("verification"),
            path,
        )

        self.assertEqual(
            registry.all(),
            {"verification": path},
        )

    def test_risk_engine_preserves_v1_aggregation(self):
        engine = LegacyCompatibleRiskEngine()

        result = engine.assess(
            config={
                "risk_policy": {
                    "high_risk_paths": [
                        "auth/**"
                    ],
                    "high_risk_patterns": [],
                }
            },
            paths=["auth/access.py"],
            diff_text="",
            codex_risk={"risk": "high"},
            claude_review={"risk": "low"},
        )

        self.assertEqual(
            result["rule"]["risk"],
            "high",
        )

        self.assertEqual(
            result["aggregate"]["final"],
            "high",
        )

        self.assertTrue(
            result["aggregate"]["human_required"]
        )

    def test_deterministic_verifier_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            runtime = FakeRuntime(root)

            verifier = DeterministicVerifier(
                runtime
            )

            result = verifier.verify(
                repo=root,
                config={
                    "verification": [
                        {
                            "name": "tests",
                            "argv": ["fake-test"],
                            "required": True,
                        }
                    ]
                },
                phase="round-0",
            )

            self.assertTrue(
                result["passed"]
            )


if __name__ == "__main__":
    unittest.main()
