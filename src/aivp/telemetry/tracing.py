from __future__ import annotations

import json

from contextlib import contextmanager
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterator,
    Mapping,
    Optional,
)

from opentelemetry.sdk.trace import (
    ReadableSpan,
    TracerProvider,
)
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import (
    Span,
    Status,
    StatusCode,
)


_SAFE_SPAN_NAMES = {
    "run",
    "model.call",
    "command",
    "verifier",
}


_SAFE_ATTRIBUTES = {
    "run.id",
    "step.id",
    "provider",
    "model",
    "role",
    "actor",
    "tool",
    "status",
    "returncode",
    "timeout_seconds",
    "latency_ms",
    "elapsed_seconds",
    "input_tokens",
    "cached_tokens",
    "output_tokens",
    "cost_usd",
    "dry_run",
}


def _safe_attributes(
    attributes: Mapping[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for key, value in attributes.items():
        if key not in _SAFE_ATTRIBUTES:
            continue

        if isinstance(
            value,
            (str, int, float, bool),
        ):
            result[key] = value

    return result


class JsonlSpanExporter(SpanExporter):
    def __init__(
        self,
        path: Path,
    ):
        self.path = path
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def export(
        self,
        spans,
    ) -> SpanExportResult:
        with self.path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            for span in spans:
                self._write_span(
                    handle,
                    span,
                )

        return SpanExportResult.SUCCESS

    def _write_span(
        self,
        handle,
        span: ReadableSpan,
    ) -> None:
        context = span.context

        parent_span_id: Optional[str] = None

        if span.parent is not None:
            parent_span_id = (
                f"{span.parent.span_id:016x}"
            )

        start_time = span.start_time
        end_time = span.end_time

        duration_ms = None

        if (
            start_time is not None
            and end_time is not None
        ):
            duration_ms = round(
                (
                    end_time
                    - start_time
                )
                / 1_000_000,
                3,
            )

        record = {
            "trace_id": (
                f"{context.trace_id:032x}"
                if context is not None
                else None
            ),
            "span_id": (
                f"{context.span_id:016x}"
                if context is not None
                else None
            ),
            "parent_span_id": (
                parent_span_id
            ),
            "name": span.name,
            "status": (
                span.status
                .status_code
                .name
            ),
            "start_time_unix_nano": (
                start_time
            ),
            "end_time_unix_nano": (
                end_time
            ),
            "duration_ms": duration_ms,
            "attributes": _safe_attributes(
                dict(
                    span.attributes
                    or {}
                )
            ),
        }

        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


class TracingSession:
    def __init__(
        self,
        *,
        enabled: bool,
        output_path: Path,
    ):
        self.enabled = enabled
        self.output_path = output_path
        self._provider: Optional[
            TracerProvider
        ] = None
        self._tracer = None

        if enabled:
            provider = TracerProvider()

            provider.add_span_processor(
                SimpleSpanProcessor(
                    JsonlSpanExporter(
                        output_path
                    )
                )
            )

            self._provider = provider
            self._tracer = (
                provider.get_tracer(
                    "aivp"
                )
            )

    @contextmanager
    def span(
        self,
        name: str,
        *,
        attributes: Optional[
            Mapping[str, Any]
        ] = None,
    ) -> Iterator[Optional[Span]]:
        if (
            not self.enabled
            or self._tracer is None
        ):
            yield None
            return

        safe_name = (
            name
            if name in _SAFE_SPAN_NAMES
            else "aivp.operation"
        )

        safe = _safe_attributes(
            attributes or {}
        )

        with self._tracer.start_as_current_span(
            safe_name,
            attributes=safe,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield span
            except Exception:
                span.set_status(
                    Status(
                        StatusCode.ERROR
                    )
                )
                raise
            else:
                span.set_status(
                    Status(
                        StatusCode.OK
                    )
                )

    def shutdown(self) -> None:
        if self._provider is not None:
            self._provider.shutdown()
