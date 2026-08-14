import json

from backend.prompts import ChallengeMeta
from backend.tracing import SolverTracer, redact_sensitive
from backend.writeup import generate_writeup


def test_redaction_hides_credentials_but_preserves_flag(tmp_path):
    flag = "RTR{contoh_flag_aman}"
    tracer = SolverTracer("test", "gpt-5.6-terra", log_dir=str(tmp_path))
    tracer.tool_call(
        "web_fetch",
        {
            "url": "https://example.test/?token=rahasia",
            "Authorization": "Bearer sangat-rahasia",
            "flag": flag,
        },
        1,
    )
    tracer.event("credentials", pin="123456", flag=flag)
    tracer.close()

    contents = next(tmp_path.glob("trace-*.jsonl")).read_text(encoding="utf-8")
    assert "sangat-rahasia" not in contents
    assert "rahasia" not in contents
    assert "123456" not in contents
    assert flag in contents
    assert "[REDACTED]" in contents
    assert "abc" not in redact_sensitive("api_key=abc")


def test_writeup_contains_reproducible_steps_and_artifacts(tmp_path):
    challenge = tmp_path / "challenge"
    workspace = challenge / "workspace" / "gpt-5.6-terra"
    workspace.mkdir(parents=True)
    (workspace / "solve.py").write_text("print('ok')\n", encoding="utf-8")

    trace = tmp_path / "trace.jsonl"
    events = [
        {"type": "tool_call", "tool": "bash", "args": "python solve.py", "step": 1},
        {
            "type": "tool_result",
            "tool": "bash",
            "result": "Authorization: Bearer jangan-bocor\nflag ditemukan",
            "step": 1,
        },
    ]
    trace.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")

    path = generate_writeup(
        str(challenge),
        ChallengeMeta(name="Demo", category="web", description="Uji"),
        "gpt-5.6-terra",
        "RTR{flag_demo}",
        "Menjalankan solve.py",
        str(trace),
        str(workspace),
    )
    contents = path.read_text(encoding="utf-8")
    assert "python solve.py" in contents
    assert "solve.py" in contents
    assert "RTR{flag_demo}" in contents
    assert "jangan-bocor" not in contents
    assert (challenge / "writeups" / "gpt-5.6-terra.md").exists()
