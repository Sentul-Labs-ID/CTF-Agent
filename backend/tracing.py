"""Per-tool-call JSONL event tracing — one file per solver, streamable via tail -f."""

from __future__ import annotations

import atexit
import json
import re
import time
from pathlib import Path

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|token)\s+)([^\s\"',;]+)"),
    re.compile(r"(?i)((?:set-)?cookie\s*:\s*)([^\r\n]+)"),
    re.compile(
        r"(?i)([\"']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|secret|session(?:id)?|pin)[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;&}]+)"
    ),
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{12,}\b"),
)
_SECRET_FIELD = re.compile(
    r"(?i)^(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|secret|cookie|session(?:id)?|pin|authorization)$"
)


def redact_sensitive(value: str) -> str:
    """Best-effort redaction for credentials without hiding CTF flag values."""
    redacted = value
    for index, pattern in enumerate(_SECRET_PATTERNS):
        if index == len(_SECRET_PATTERNS) - 1:
            redacted = pattern.sub("[REDACTED_API_KEY]", redacted)
        else:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def _redact_value(value, field_name: str = ""):
    if _SECRET_FIELD.match(field_name) and value not in (None, ""):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_sensitive(value)
    if isinstance(value, dict):
        return {key: _redact_value(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def _sanitize(s: str) -> str:
    return s.replace("/", "_").replace(" ", "_")


class SolverTracer:
    """Append-only JSONL event tracer. Flushes every write for tail -f streaming."""

    def __init__(self, challenge_name: str, model_id: str, log_dir: str = "logs") -> None:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        self.path = str(
            Path(log_dir) / f"trace-{_sanitize(challenge_name)}-{_sanitize(model_id)}-{ts}.jsonl"
        )
        self._fh = open(self.path, "a")
        atexit.register(self._close)

    def close(self) -> None:
        """Explicitly close the trace file. Safe to call multiple times."""
        if not self._fh.closed:
            try:
                self._fh.close()
            except Exception:
                pass

    _close = close  # atexit compat

    def _write(self, event: dict) -> None:
        try:
            safe_event = _redact_value(event)
            self._fh.write(json.dumps({"ts": time.time(), **safe_event}) + "\n")
            self._fh.flush()
        except Exception:
            pass

    def tool_call(self, tool_name: str, args: dict | str, step: int) -> None:
        safe_args = _redact_value(args)
        args_str = safe_args if isinstance(safe_args, str) else json.dumps(safe_args)
        self._write(
            {"type": "tool_call", "tool": tool_name, "args": args_str[:12000], "step": step}
        )

    def tool_result(self, tool_name: str, result: str, step: int) -> None:
        self._write(
            {"type": "tool_result", "tool": tool_name, "result": result[:20000], "step": step}
        )

    def model_response(
        self, text: str, step: int, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        self._write(
            {
                "type": "model_response",
                "text": text[:20000],
                "step": step,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )

    def usage(
        self, input_tokens: int, output_tokens: int, cache_read: int, cost_usd: float
    ) -> None:
        self._write(
            {
                "type": "usage",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_tokens": cache_read,
                "cost_usd": round(cost_usd, 6),
            }
        )

    def event(self, kind: str, **kwargs) -> None:
        self._write({"type": kind, **kwargs})
