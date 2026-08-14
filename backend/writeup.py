"""Generate a reproducible Markdown write-up from observable solver events."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from backend.prompts import ChallengeMeta
from backend.tracing import redact_sensitive


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.") or "solver"


def _fence(value: str) -> str:
    return f"````text\n{redact_sensitive(value).strip()}\n````"


def _read_events(trace_path: str) -> list[dict]:
    events: list[dict] = []
    try:
        with Path(trace_path).open(encoding="utf-8") as trace_file:
            for line in trace_file:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    events.append(item)
    except OSError:
        pass
    return events


def _artifact_lines(workspace_dir: str) -> list[str]:
    root = Path(workspace_dir)
    if not root.exists():
        return ["- Belum ada artefak yang tersimpan."]
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        return ["- Belum ada artefak yang tersimpan."]
    return [
        f"- `{path.relative_to(root).as_posix()}` ({path.stat().st_size} byte)" for path in files
    ]


def generate_writeup(
    challenge_dir: str,
    meta: ChallengeMeta,
    model_id: str,
    flag: str,
    method: str,
    trace_path: str,
    workspace_dir: str,
) -> Path:
    """Write latest WRITEUP.md and retain a model-specific copy."""
    events = _read_events(trace_path)
    steps: list[str] = []
    for event in events:
        event_type = event.get("type")
        step = event.get("step", "-")
        if event_type == "tool_call":
            steps.extend(
                [
                    f"### Langkah {step} — `{event.get('tool', '')}`",
                    "",
                    _fence(str(event.get("args", ""))),
                    "",
                ]
            )
        elif event_type == "tool_result":
            result = str(event.get("result", "")).strip()
            if result:
                steps.extend(["Hasil:", "", _fence(result), ""])

    if not steps:
        steps = ["Belum ada rekaman perintah yang dapat ditampilkan.", ""]

    connection = (
        redact_sensitive(meta.connection_info) if meta.connection_info else "Tidak dicantumkan"
    )
    contents = [
        f"# Write-up: {meta.name}",
        "",
        f"- Kategori: {meta.category or 'Tidak diketahui'}",
        f"- Poin: {meta.value}",
        f"- Model: `{model_id}`",
        f"- Dibuat: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- Target: `{connection}`",
        "",
        "## Deskripsi Challenge",
        "",
        redact_sensitive(meta.description) or "Tidak ada deskripsi.",
        "",
        "## Ringkasan Solusi",
        "",
        redact_sensitive(method).strip() or "Lihat langkah reproduksi di bawah.",
        "",
        "## Langkah Reproduksi",
        "",
        *steps,
        "## Artefak",
        "",
        *_artifact_lines(workspace_dir),
        "",
        "Artefak persisten berada di folder `workspace/` challenge ini.",
        "",
        "## Flag",
        "",
        f"`{flag}`",
        "",
        "## Catatan Keamanan",
        "",
        "Kredensial bernama (API key, token, cookie, PIN, password, dan header Authorization) "
        "disamarkan otomatis. Periksa kembali dokumen ini sebelum dipublikasikan.",
        "",
    ]
    markdown = "\n".join(contents)
    challenge_root = Path(challenge_dir)
    latest_path = challenge_root / "WRITEUP.md"
    archive_path = challenge_root / "writeups" / f"{_slug(model_id)}.md"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(markdown, encoding="utf-8")
    archive_path.write_text(markdown, encoding="utf-8")
    return latest_path
