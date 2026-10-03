import json
import tempfile
import unittest

from dataclasses import FrozenInstanceError
from pathlib import Path

from aivp.eval.case import (
    EvalCaseError,
    load_eval_case,
)


class EvalCaseTests(unittest.TestCase):
    def _write_json(
        self,
        path: Path,
        data,
    ) -> None:
        path.write_text(
            json.dumps(
                data,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    def _fixture(
        self,
        root: Path,
    ) -> Path:
        repo = root / "fixture-repo"
        repo.mkdir()

        self._write_json(
            root / "task.json",
            {
                "task": "Normalize username.",
                "acceptance": [
                    "Alice becomes alice."
                ],
                "constraints": [
                    "Do not add dependencies."
                ],
            },
        )

        self._write_json(
            root / "config.json",
            {
                "budgets": {
                    "max_fix_iterations": 2
                }
            },
        )

        case_path = root / "case.json"

        self._write_json(
            case_path,
            {
                "schema_version": 1,
                "id": "low-username-normalization",
                "description": (
                    "Representative low-risk "
                    "normalization task."
                ),
                "repository": {
                    "path": "./fixture-repo",
                    "revision": "abc123",
                },
                "inputs": {
                    "task": "./task.json",
                    "config": "./config.json",
                },
                "expected": {
                    "terminal_status": (
                        "AUTO_FINISHED"
                    ),
                    "verification": {
                        "passed": True
                    },
                },
                "graders": [
                    "expected-decision",
                    "verification",
                ],
                "trials": {
                    "count": 3
                },
            },
        )

        return case_path

    def test_loads_case_and_resolves_references(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case_path = self._fixture(root)

            case = load_eval_case(
                case_path
            )

            self.assertEqual(
                case.case_id,
                "low-username-normalization",
            )
            self.assertEqual(
                case.repository.path,
                (root / "fixture-repo").resolve(),
            )
            self.assertEqual(
                case.repository.revision,
                "abc123",
            )
            self.assertEqual(
                case.inputs.task_path,
                (root / "task.json").resolve(),
            )
            self.assertEqual(
                case.inputs.config_path,
                (root / "config.json").resolve(),
            )
            self.assertEqual(
                case.graders,
                (
                    "expected-decision",
                    "verification",
                ),
            )
            self.assertEqual(
                case.trials.count,
                3,
            )
            self.assertEqual(
                case.expected[
                    "terminal_status"
                ],
                "AUTO_FINISHED",
            )

    def test_reuses_existing_task_and_config_contracts(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case = load_eval_case(
                self._fixture(root)
            )

            task = case.load_task()
            config = case.load_config()

            self.assertEqual(
                task["task"],
                "Normalize username.",
            )
            self.assertEqual(
                task["acceptance"],
                [
                    "Alice becomes alice."
                ],
            )
            self.assertEqual(
                config["budgets"][
                    "max_fix_iterations"
                ],
                2,
            )

    def test_case_contract_is_frozen(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            case = load_eval_case(
                self._fixture(Path(td))
            )

            with self.assertRaises(
                FrozenInstanceError
            ):
                case.case_id = "changed"

    def test_expected_contract_is_deeply_frozen(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            case = load_eval_case(
                self._fixture(Path(td))
            )

            with self.assertRaises(TypeError):
                case.expected[
                    "terminal_status"
                ] = "HUMAN_REQUIRED"

            with self.assertRaises(TypeError):
                case.expected[
                    "verification"
                ]["passed"] = False

    def test_rejects_unsupported_schema_version(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case_path = self._fixture(root)

            data = json.loads(
                case_path.read_text(
                    encoding="utf-8"
                )
            )
            data["schema_version"] = 2
            self._write_json(
                case_path,
                data,
            )

            with self.assertRaises(
                EvalCaseError
            ):
                load_eval_case(
                    case_path
                )

    def test_rejects_invalid_trial_count(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case_path = self._fixture(root)

            data = json.loads(
                case_path.read_text(
                    encoding="utf-8"
                )
            )
            data["trials"]["count"] = 0
            self._write_json(
                case_path,
                data,
            )

            with self.assertRaises(
                EvalCaseError
            ):
                load_eval_case(
                    case_path
                )

    def test_rejects_duplicate_graders(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case_path = self._fixture(root)

            data = json.loads(
                case_path.read_text(
                    encoding="utf-8"
                )
            )
            data["graders"] = [
                "verification",
                "verification",
            ]
            self._write_json(
                case_path,
                data,
            )

            with self.assertRaises(
                EvalCaseError
            ):
                load_eval_case(
                    case_path
                )


if __name__ == "__main__":
    unittest.main()
