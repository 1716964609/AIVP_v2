from __future__ import annotations

import re

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Tuple

from aivp.errors import AIVPError
from aivp.structured import load_structured


EVAL_CASE_SCHEMA_VERSION = 1

_CASE_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class EvalCaseError(AIVPError):
    """Invalid M7 evaluation case."""


@dataclass(frozen=True)
class RepositoryBaseline:
    path: Path
    revision: str


@dataclass(frozen=True)
class EvalInputs:
    task_path: Path
    config_path: Path


@dataclass(frozen=True)
class TrialPolicy:
    count: int = 1


@dataclass(frozen=True)
class EvalCase:
    schema_version: int
    case_id: str
    description: str
    repository: RepositoryBaseline
    inputs: EvalInputs
    expected: Mapping[str, Any]
    graders: Tuple[str, ...]
    trials: TrialPolicy
    source_path: Path

    def load_task(self) -> Dict[str, Any]:
        return load_structured(
            self.inputs.task_path
        )

    def load_config(self) -> Dict[str, Any]:
        return load_structured(
            self.inputs.config_path
        )


def _freeze_value(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {
                key: _freeze_value(item)
                for key, item in value.items()
            }
        )

    if isinstance(value, list):
        return tuple(
            _freeze_value(item)
            for item in value
        )

    return value


def _mapping(
    value: Any,
    *,
    field: str,
) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise EvalCaseError(
            f"{field} must be an object/mapping"
        )

    return dict(value)


def _required_string(
    mapping: Mapping[str, Any],
    key: str,
    *,
    field: str,
) -> str:
    value = mapping.get(key)

    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise EvalCaseError(
            f"{field}.{key} must be "
            "a non-empty string"
        )

    return value.strip()


def _resolve_reference(
    case_path: Path,
    value: str,
) -> Path:
    candidate = Path(value).expanduser()

    if not candidate.is_absolute():
        candidate = (
            case_path.parent
            / candidate
        )

    return candidate.resolve()


def _load_graders(
    raw: Any,
) -> Tuple[str, ...]:
    if not isinstance(raw, list):
        raise EvalCaseError(
            "graders must be a list"
        )

    graders = []

    for value in raw:
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise EvalCaseError(
                "grader identifiers must be "
                "non-empty strings"
            )

        graders.append(
            value.strip()
        )

    if not graders:
        raise EvalCaseError(
            "at least one grader is required"
        )

    if len(set(graders)) != len(graders):
        raise EvalCaseError(
            "grader identifiers must be unique"
        )

    return tuple(graders)


def _load_trials(
    raw: Any,
) -> TrialPolicy:
    if raw is None:
        return TrialPolicy()

    trials = _mapping(
        raw,
        field="trials",
    )

    count = trials.get(
        "count",
        1,
    )

    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count < 1
    ):
        raise EvalCaseError(
            "trials.count must be an integer "
            "greater than or equal to 1"
        )

    return TrialPolicy(
        count=count
    )


def load_eval_case(
    path: Path,
) -> EvalCase:
    source_path = (
        path.expanduser().resolve()
    )

    raw = load_structured(
        source_path
    )

    schema_version = raw.get(
        "schema_version"
    )

    if schema_version != EVAL_CASE_SCHEMA_VERSION:
        raise EvalCaseError(
            "Unsupported eval case schema_version: "
            f"{schema_version!r}; expected "
            f"{EVAL_CASE_SCHEMA_VERSION}"
        )

    case_id = _required_string(
        raw,
        "id",
        field="case",
    )

    if not _CASE_ID_RE.fullmatch(
        case_id
    ):
        raise EvalCaseError(
            "case.id must match "
            "[a-z0-9][a-z0-9._-]*"
        )

    description_raw = raw.get(
        "description",
        "",
    )

    if not isinstance(
        description_raw,
        str,
    ):
        raise EvalCaseError(
            "case.description must be a string"
        )

    repository = _mapping(
        raw.get("repository"),
        field="repository",
    )

    repo_path = _resolve_reference(
        source_path,
        _required_string(
            repository,
            "path",
            field="repository",
        ),
    )

    revision = _required_string(
        repository,
        "revision",
        field="repository",
    )

    inputs = _mapping(
        raw.get("inputs"),
        field="inputs",
    )

    task_path = _resolve_reference(
        source_path,
        _required_string(
            inputs,
            "task",
            field="inputs",
        ),
    )

    config_path = _resolve_reference(
        source_path,
        _required_string(
            inputs,
            "config",
            field="inputs",
        ),
    )

    expected_raw = raw.get(
        "expected",
        {},
    )

    expected = _mapping(
        expected_raw,
        field="expected",
    )

    graders = _load_graders(
        raw.get("graders")
    )

    trials = _load_trials(
        raw.get("trials")
    )

    return EvalCase(
        schema_version=schema_version,
        case_id=case_id,
        description=description_raw.strip(),
        repository=RepositoryBaseline(
            path=repo_path,
            revision=revision,
        ),
        inputs=EvalInputs(
            task_path=task_path,
            config_path=config_path,
        ),
        expected=_freeze_value(expected),
        graders=graders,
        trials=trials,
        source_path=source_path,
    )
