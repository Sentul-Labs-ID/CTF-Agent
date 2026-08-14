import runpy
from pathlib import Path


def test_frontend_model_labels_and_project_root():
    project_root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(project_root / "frontend" / "gui.pyw"))
    options = namespace["MODEL_OPTIONS"]

    assert namespace["ROOT"] == project_root
    assert len(options) == 12
    assert sum(label.startswith("HEMAT |") for label in options) == 4
    assert sum(label.startswith("SEDANG |") for label in options) == 4
    assert sum(label.startswith("KUAT |") for label in options) == 4
    assert {spec for spec in options.values() if spec.startswith("codex/")} == {
        "codex/gpt-5.6-luna",
        "codex/gpt-5.6-terra",
        "codex/gpt-5.6-sol",
    }
    assert {spec for spec in options.values() if spec.startswith("google/")} == {
        "google/gemini-3.5-flash-lite",
        "google/gemini-3.6-flash",
        "google/gemini-3.1-pro-preview",
    }
